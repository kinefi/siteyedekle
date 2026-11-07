#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///

"""Download an authorized same-origin website into a static ZIP archive."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import html
import io
import posixpath
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import deque
from html.parser import HTMLParser


USER_AGENT = "siteyedekle/1.0 (authorized static-site export)"
CSS_URL_RE = re.compile(
    r"url\(\s*(?P<quote>['\"]?)(?P<url>.*?)(?P=quote)\s*\)"
    r"|@import\s+(?:url\()?[\s'\"]*(?P<import>[^)'\"\s;]+)",
    re.IGNORECASE,
)
SRCSET_RE = re.compile(r"(?P<url>\S+)(?P<descriptor>\s+[^,]+)?")


def normalize_url(value: str, base: str) -> str:
    absolute = urllib.parse.urljoin(base, value.strip())
    parsed = urllib.parse.urlsplit(absolute)
    path = urllib.parse.quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
    query = urllib.parse.quote(parsed.query, safe="/?%:@!$&'()*+,;=-._~")
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, query, ""))


def normalize_start_url(value: str) -> str:
    value = value.strip()
    parsed = urllib.parse.urlsplit(value)
    if not parsed.scheme:
        value = f"https:{value}" if value.startswith("//") else f"https://{value}"
    return normalize_url(value, value)


def origin(url: str) -> tuple[str, str, int | None]:
    parsed = urllib.parse.urlsplit(url)
    scheme = parsed.scheme.lower()
    port = parsed.port
    if port is None:
        port = 443 if scheme == "https" else 80
    return scheme, (parsed.hostname or "").lower(), port


def safe_url(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    return parsed.scheme in ("http", "https") and bool(parsed.hostname) and not parsed.username and not parsed.password


def local_path(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    path = urllib.parse.unquote(parsed.path or "/")
    path = posixpath.normpath("/" + path.lstrip("/"))
    if path == "/":
        path = "/index.html"
    elif path.endswith("/"):
        path += "index.html"
    elif not posixpath.splitext(path)[1]:
        path += ".html"

    path = path.lstrip("/")
    if parsed.query:
        digest = hashlib.sha256(parsed.query.encode("utf-8")).hexdigest()[:10]
        stem, extension = posixpath.splitext(path)
        path = f"{stem}-{digest}{extension}"
    return path


class ReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.references: list[tuple[str, str, str]] = []
        self.output: list[str] = []

    def _render_tag(self, tag: str, attrs: list[tuple[str, str | None]], closed: bool = False) -> None:
        rewritten: list[tuple[str, str | None]] = []
        for name, value in attrs:
            if value is not None and name.lower() in ("href", "src", "poster", "srcset", "style"):
                self.references.append((tag.lower(), name.lower(), value))
            rewritten.append((name, value))
        rendered_attrs = "".join(
            f" {name}" if value is None else f' {name}="{html.escape(value, quote=True)}"'
            for name, value in rewritten
        )
        suffix = " />" if closed else ">"
        self.output.append(f"<{tag}{rendered_attrs}{suffix}")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._render_tag(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._render_tag(tag, attrs, closed=True)

    def handle_endtag(self, tag: str) -> None:
        self.output.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.output.append(data)

    def handle_entityref(self, name: str) -> None:
        self.output.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.output.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self.output.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self.output.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self.output.append(f"<?{data}>")


def rewrite_css(css: str, base_url: str, source_path: str, paths: dict[str, str], base_origin: tuple[str, str, int | None]) -> str:
    def replace(match: re.Match[str]) -> str:
        raw_url = match.group("url") if match.group("url") is not None else match.group("import")
        if not raw_url or raw_url.startswith(("data:", "#")):
            return match.group(0)
        absolute = normalize_url(raw_url, base_url)
        if origin(absolute) != base_origin or absolute not in paths:
            return match.group(0)
        relative = posixpath.relpath(paths[absolute], posixpath.dirname(source_path) or ".")
        if not relative.startswith("."):
            relative = "./" + relative
        if match.group("url") is not None:
            quote = match.group("quote") or ""
            return f"url({quote}{relative}{quote})"
        return f'@import "{relative}"'

    return CSS_URL_RE.sub(replace, css)


def rewrite_html(
    content: str,
    page_url: str,
    source_path: str,
    paths: dict[str, str],
    base_origin: tuple[str, str, int | None],
) -> tuple[str, list[tuple[str, str, str]]]:
    parser = ReferenceParser()
    parser.feed(content)
    parser.close()
    references = parser.references

    def replace_reference(tag: str, attribute: str, value: str) -> str:
        if attribute == "style":
            return rewrite_css(value, page_url, source_path, paths, base_origin)
        if attribute == "srcset":
            rewritten: list[str] = []
            for candidate in value.split(","):
                candidate = candidate.strip()
                match = SRCSET_RE.fullmatch(candidate)
                if not match:
                    rewritten.append(candidate)
                    continue
                raw_url = match.group("url")
                absolute = normalize_url(raw_url, page_url)
                local = local_reference(absolute, page_url, source_path, paths, base_origin)
                rewritten.append(local + (match.group("descriptor") or ""))
            return ", ".join(rewritten)
        absolute = normalize_url(value, page_url)
        return local_reference(absolute, page_url, source_path, paths, base_origin, preserve_fragment=True)

    parser = ReferenceParser()
    parser.feed(content)
    parser.close()
    output: list[str] = []
    ref_index = 0
    for token in parser.output:
        if token.startswith("<") and not token.startswith(("</", "<!", "<?")):
            tag_match = re.match(r"<([^\s/>]+)", token)
            tag = tag_match.group(1).lower() if tag_match else ""
            attrs = list(re.finditer(r'([^\s=/>]+)="([^"]*)"', token))
            for attr_match in reversed(attrs):
                name = attr_match.group(1).lower()
                if name not in ("href", "src", "poster", "srcset", "style"):
                    continue
                decoded_value = html.unescape(attr_match.group(2))
                replacement = replace_reference(tag, name, decoded_value)
                token = token[:attr_match.start(2)] + html.escape(replacement, quote=True) + token[attr_match.end(2):]
            output.append(token)
        else:
            output.append(token)
    return "".join(output), references


def local_reference(
    absolute: str,
    page_url: str,
    source_path: str,
    paths: dict[str, str],
    base_origin: tuple[str, str, int | None],
    preserve_fragment: bool = False,
) -> str:
    parsed = urllib.parse.urlsplit(absolute)
    fragment = parsed.fragment
    normalized = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
    if origin(normalized) != base_origin or normalized not in paths:
        return absolute
    relative = posixpath.relpath(paths[normalized], posixpath.dirname(source_path) or ".")
    if not relative.startswith("."):
        relative = "./" + relative
    return relative + (f"#{fragment}" if preserve_fragment and fragment else "")


def retry_after_seconds(error: urllib.error.HTTPError) -> float | None:
    value = error.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def skip_reason(error: Exception) -> str:
    if isinstance(error, urllib.error.HTTPError):
        if error.code in (429, 529):
            return "throttle (429/529)"
        return f"HTTP {error.code}"
    if isinstance(error, (TimeoutError,)):
        return "timeout"
    if isinstance(error, urllib.error.URLError):
        if isinstance(error.reason, (TimeoutError,)):
            return "timeout"
        return "network"
    if isinstance(error, ValueError):
        if "boyut" in str(error).lower():
            return "file size limit"
        return "invalid URL / redirect"
    if isinstance(error, OSError):
        return "network"
    return "other error"


def fetch(
    url: str,
    timeout: float,
    per_file_limit: int,
    expected_origin: tuple[str, str, int | None],
    retries: int,
) -> tuple[bytes, str, str, int]:
    if not safe_url(url):
        raise ValueError(f"Güvenli olmayan veya desteklenmeyen URL: {url}")
    throttled_responses = 0
    for attempt in range(retries + 1):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                final_url = normalize_url(response.geturl(), url)
                if origin(final_url) != expected_origin:
                    raise ValueError(f"Farklı alan adına yönlendirme engellendi: {final_url}")
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > per_file_limit:
                    raise ValueError(f"Dosya boyutu sınırı aşıldı ({content_length} bayt)")
                data = response.read(per_file_limit + 1)
                if len(data) > per_file_limit:
                    raise ValueError(f"Dosya boyutu {per_file_limit} bayt sınırını aştı")
                return data, response.headers.get_content_type().lower(), final_url, throttled_responses
        except urllib.error.HTTPError as error:
            if error.code not in (429, 529):
                raise
            throttled_responses += 1
            if attempt >= retries:
                raise
            delay = retry_after_seconds(error)
            delay = max(delay or 0, min(2 ** (attempt + 1), 30))
            print(f"HTTP {error.code}: {delay:g} saniye beklenip tekrar denenecek.", file=sys.stderr)
            error.close()
            time.sleep(delay)


def download_site(
    start_url: str,
    output: str,
    max_pages: int,
    max_files: int,
    max_bytes: int,
    timeout: float,
    retries: int,
    request_delay: float,
) -> int:
    start_url = normalize_start_url(start_url)
    if not safe_url(start_url):
        raise ValueError("HTTP veya HTTPS biçiminde geçerli bir URL girin (kullanıcı bilgisi içeren URL'ler desteklenmez).")

    site_origin = origin(start_url)
    queue: deque[tuple[str, bool]] = deque([(start_url, True)])
    queued_urls = {start_url}
    seen: set[str] = set()
    pages_seen = 0
    skipped: dict[str, str] = {}
    downloaded: dict[str, tuple[bytes, str]] = {}
    paths: dict[str, str] = {}
    total_bytes = 0
    active_request_delay = request_delay
    per_file_limit = min(max_bytes, 50 * 1024 * 1024)

    while queue:
        url, is_page = queue.popleft()
        url = normalize_url(url, start_url)
        queued_urls.discard(url)
        if url in seen or origin(url) != site_origin or not safe_url(url):
            continue
        if len(downloaded) >= max_files:
            skipped[url] = "max files limit"
            for pending_url in queued_urls:
                skipped.setdefault(pending_url, "max files limit")
            print(f"Atlandı: en fazla dosya sayısı sınırına ({max_files}) ulaşıldı.", file=sys.stderr)
            break
        if is_page and pages_seen >= max_pages:
            skipped[url] = "max pages limit"
            continue
        seen.add(url)
        if is_page:
            pages_seen += 1

        print(f"İndiriliyor: {url}", file=sys.stderr)
        try:
            data, content_type, final_url, throttled_responses = fetch(
                url, timeout, per_file_limit, site_origin, retries
            )
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            print(f"Atlandı: {url} ({exc})", file=sys.stderr)
            reason = skip_reason(exc)
            skipped[url] = reason
            if isinstance(exc, urllib.error.HTTPError) and exc.code in (429, 529):
                active_request_delay = min(max(active_request_delay, 0.5) * 2, 10)
                print(f"İstek aralığı {active_request_delay:g} saniyeye çıkarılıyor.", file=sys.stderr)
            if url == start_url:
                raise RuntimeError(
                    "Ana sayfa alınamadı. Bu yerel araç tarayıcı CORS kısıtlamasını kullanmaz; "
                    f"ancak sunucu erişimi, ağ veya TLS hataları yine de indirmeyi engelleyebilir. ({exc})"
                ) from exc
            if active_request_delay:
                time.sleep(active_request_delay)
            continue

        if throttled_responses:
            active_request_delay = min(max(active_request_delay, 0.5) * 2, 10)
            print(f"Sunucu yavaşlama istedi; istek aralığı {active_request_delay:g} saniyeye çıkarılıyor.",
                  file=sys.stderr)
        if final_url != url:
            url = final_url
            seen.add(url)
        if total_bytes + len(data) > max_bytes:
            print(f"Atlandı: toplam boyut sınırı ({max_bytes} bayt) aşıldı.", file=sys.stderr)
            skipped[url] = "total size limit"
            for pending_url in queued_urls:
                skipped.setdefault(pending_url, "total size limit")
            break
        total_bytes += len(data)
        downloaded[url] = (data, content_type)
        paths[url] = local_path(url)

        is_html = content_type == "text/html"
        decoded = data.decode("utf-8", errors="replace") if is_html or content_type == "text/css" else ""
        if is_html:
            parser = ReferenceParser()
            parser.feed(decoded)
            parser.close()
            for tag, attribute, value in parser.references:
                values = [value]
                if attribute == "srcset":
                    values = [match.group("url") for part in value.split(",") if (match := SRCSET_RE.fullmatch(part.strip()))]
                elif attribute == "style":
                    values = [match.group("url") or match.group("import") for match in CSS_URL_RE.finditer(value)]
                for raw_value in values:
                    if not raw_value or raw_value.startswith(("data:", "javascript:", "mailto:", "tel:", "#")):
                        continue
                    candidate = normalize_url(raw_value, url)
                    if origin(candidate) != site_origin or candidate in seen or candidate in queued_urls:
                        continue
                    queue.append((candidate, tag == "a" and attribute == "href"))
                    queued_urls.add(candidate)
        elif content_type == "text/css":
            for match in CSS_URL_RE.finditer(decoded):
                raw_value = match.group("url") or match.group("import")
                if not raw_value or raw_value.startswith(("data:", "#")):
                    continue
                candidate = normalize_url(raw_value, url)
                if origin(candidate) == site_origin and candidate not in seen and candidate not in queued_urls:
                    queue.append((candidate, False))
                    queued_urls.add(candidate)
        if active_request_delay:
            time.sleep(active_request_delay)

    if start_url not in downloaded:
        raise RuntimeError("Ana sayfa indirilemedi; ZIP oluşturulmadı.")

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for url, (data, content_type) in downloaded.items():
            path = paths[url]
            if content_type == "text/html" or url == start_url:
                rendered, _ = rewrite_html(data.decode("utf-8", errors="replace"), url, path, paths, site_origin)
                data = rendered.encode("utf-8")
            elif content_type == "text/css":
                data = rewrite_css(data.decode("utf-8", errors="replace"), url, path, paths, site_origin).encode("utf-8")
            archive.writestr(path, data)

    print(f"Atlanan dosya nedenleri ({len(skipped)} toplam):", file=sys.stderr)
    if skipped:
        reasons: dict[str, int] = {}
        for reason in skipped.values():
            reasons[reason] = reasons.get(reason, 0) + 1
        for reason, count in sorted(reasons.items()):
            print(f"  {reason}: {count}", file=sys.stderr)
    else:
        print("  Yok", file=sys.stderr)

    print(f"Tamamlandı: {len(downloaded)} dosya indirildi, {len(skipped)} dosya atlandı, {total_bytes} bayt -> {output}")
    return len(downloaded)


def main() -> int:
    parser = argparse.ArgumentParser(description="Yetkili olduğunuz bir web sitesini statik ZIP arşivine aktarın.")
    parser.add_argument("url", help="İndirilecek sitenin adresi (şema yoksa HTTPS kullanılır)")
    parser.add_argument("-o", "--output", default="siteyedekle.zip", help="ZIP dosyasının adı (varsayılan: siteyedekle.zip)")
    parser.add_argument("--max-pages", type=int, default=250, help="En fazla taranacak HTML sayfası (varsayılan: 250)")
    parser.add_argument("--max-files", type=int, default=1000, help="En fazla indirilecek dosya (varsayılan: 1000)")
    parser.add_argument("--max-bytes", type=int, default=200 * 1024 * 1024, help="Toplam indirme sınırı, bayt (varsayılan: 20MB)")
    parser.add_argument("--timeout", type=float, default=20, help="İstek zaman aşımı, saniye (varsayılan: 20)")
    parser.add_argument("--retries", type=int, default=3, help="HTTP 429/529 için tekrar deneme sayısı (varsayılan: 3)")
    parser.add_argument("--request-delay", type=float, default=1.5, help="İstekler arasındaki bekleme, saniye (varsayılan: 1.5)")
    args = parser.parse_args()

    if (
        args.max_pages < 1 or args.max_files < 1 or args.max_bytes < 1 or args.timeout <= 0
        or args.retries < 0 or args.request_delay < 0
    ):
        parser.error("Limitler ve zaman aşımı sıfırdan büyük; tekrar deneme ve istek aralığı sıfır veya daha büyük olmalıdır.")
    try:
        download_site(
            args.url,
            args.output,
            args.max_pages,
            args.max_files,
            args.max_bytes,
            args.timeout,
            args.retries,
            args.request_delay,
        )
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
