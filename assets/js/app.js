function logMessage(message) {
    const logElement = document.getElementById('log');
    if (!logElement) return;

    const timestamp = new Date().toLocaleTimeString('tr-TR', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });

    const value = `${timestamp} - ${message}`;
    logElement.textContent += (logElement.textContent ? '\n' : '') + value;
    logElement.scrollTop = logElement.scrollHeight;
}

function resetLog() {
    const logElement = document.getElementById('log');
    if (!logElement) return;
    logElement.textContent = 'İşlem başlatıldı...';
}

function isSameOrigin(candidateUrl, baseUrl) {
    try {
        const candidate = new URL(candidateUrl, baseUrl);
        const base = new URL(baseUrl);
        return candidate.origin === base.origin;
    } catch (error) {
        return false;
    }
}

function isAssetCandidate(candidateUrl) {
    if (!candidateUrl) return false;

    const value = candidateUrl.trim();
    if (!value || value.startsWith('mailto:') || value.startsWith('tel:') || value.startsWith('javascript:') || value.startsWith('#')) {
        return false;
    }

    return true;
}

function normalizeUrl(rawUrl, baseUrl) {
    try {
        const candidate = new URL(rawUrl, baseUrl);
        candidate.hash = '';
        candidate.search = '';
        return candidate.href;
    } catch (error) {
        return rawUrl;
    }
}

function toLocalFilePath(rawUrl) {
    try {
        const url = new URL(rawUrl);
        let pathname = decodeURIComponent(url.pathname || '/');

        if (pathname === '/' || pathname === '') {
            return 'index.html';
        }

        pathname = pathname.replace(/^\/+/, '');

        if (pathname.endsWith('/')) {
            pathname += 'index.html';
        }

        if (!pathname.includes('.')) {
            pathname += '.html';
        }

        return pathname.replace(/[\\]+/g, '/');
    } catch (error) {
        return 'index.html';
    }
}

function collectHtmlAssets(html, pageUrl) {
    const fragment = document.createElement('div');
    fragment.innerHTML = html;
    const foundUrls = new Set();

    const selectors = [
        'img[src]',
        'script[src]',
        'link[href]',
        'video[src]',
        'audio[src]',
        'source[src]',
        'iframe[src]',
        'a[href]'
    ];

    selectors.forEach((selector) => {
        fragment.querySelectorAll(selector).forEach((element) => {
            const attributeName = selector.includes('[href]') ? 'href' : 'src';
            const rawValue = element.getAttribute(attributeName);

            if (!isAssetCandidate(rawValue)) {
                return;
            }

            const absolute = normalizeUrl(rawValue, pageUrl);
            foundUrls.add(absolute);
        });
    });

    return Array.from(foundUrls);
}

function rewriteCssUrls(cssText, pageUrl, fileMap) {
    const cssReplacements = cssText.replace(/url\((['"]?)(.*?)\1\)/gi, (match, quote, urlValue) => {
        const trimmed = (urlValue || '').trim();
        if (!trimmed || trimmed.startsWith('data:') || trimmed.startsWith('#')) {
            return match;
        }

        try {
            const absolute = normalizeUrl(trimmed, pageUrl);
            const mappedFile = fileMap.get(absolute);
            if (!mappedFile) {
                return match;
            }

            return `url(${quote}./${mappedFile}${quote})`;
        } catch (error) {
            return match;
        }
    });

    return cssReplacements.replace(/@import\s*(?:url\()?\s*(['"]?)([^'"\)]+)\1\s*\)?/gi, (match, quote, importValue) => {
        const trimmed = (importValue || '').trim();
        if (!trimmed || trimmed.startsWith('data:') || trimmed.startsWith('#')) {
            return match;
        }

        try {
            const absolute = normalizeUrl(trimmed, pageUrl);
            const mappedFile = fileMap.get(absolute);
            if (!mappedFile) {
                return match;
            }

            return `@import ${quote}./${mappedFile}${quote}`;
        } catch (error) {
            return match;
        }
    });
}

function rewriteHtmlDocument(html, pageUrl, fileMap) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');

    doc.querySelectorAll('[src],[href],[srcset]').forEach((element) => {
        const attributes = [];

        if (element.hasAttribute('src')) {
            attributes.push('src');
        }

        if (element.hasAttribute('href')) {
            attributes.push('href');
        }

        if (element.hasAttribute('srcset')) {
            attributes.push('srcset');
        }

        attributes.forEach((attribute) => {
            const rawValue = element.getAttribute(attribute);
            if (!rawValue || !isAssetCandidate(rawValue)) {
                return;
            }

            const absolute = normalizeUrl(rawValue, pageUrl);
            const mappedFile = fileMap.get(absolute);
            if (!mappedFile) {
                return;
            }

            if (attribute === 'srcset') {
                const candidates = rawValue.split(',').map((part) => part.trim()).filter(Boolean);
                const rewrittenCandidates = candidates.map((candidate) => {
                    const match = candidate.match(/^([^\s]+)(\s+.*)?$/);
                    if (!match) {
                        return candidate;
                    }

                    const urlPart = match[1];
                    const rest = match[2] || '';
                    const mapped = fileMap.get(normalizeUrl(urlPart, pageUrl));
                    return mapped ? `./${mapped}${rest}` : candidate;
                });

                element.setAttribute(attribute, rewrittenCandidates.join(', '));
                return;
            }

            element.setAttribute(attribute, `./${mappedFile}`);
        });
    });

    return doc.documentElement.outerHTML;
}

async function collectSiteAssets(targetUrl) {
    const rootUrl = new URL(targetUrl);
    const queue = [rootUrl.href];
    const seen = new Set();
    const fileMap = new Map();
    const downloaded = new Map();

    while (queue.length) {
        const currentUrl = queue.shift();
        if (!currentUrl || seen.has(currentUrl)) {
            continue;
        }

        seen.add(currentUrl);
        const normalizedUrl = normalizeUrl(currentUrl, rootUrl.href);

        try {
            logMessage(`İstek gönderiliyor: ${normalizedUrl}`);
            const response = await fetch(normalizedUrl, { cache: 'no-store' });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status} - ${response.statusText}`);
            }

            const contentType = (response.headers.get('content-type') || '').toLowerCase();
            const localFilePath = toLocalFilePath(normalizedUrl);
            fileMap.set(normalizedUrl, localFilePath);

            if (contentType.includes('text/html')) {
                const html = await response.text();
                downloaded.set(normalizedUrl, { type: 'html', content: html });

                collectHtmlAssets(html, normalizedUrl).forEach((assetUrl) => {
                    const absolute = normalizeUrl(assetUrl, normalizedUrl);
                    if (isSameOrigin(absolute, rootUrl.href) && !seen.has(absolute) && isAssetCandidate(absolute)) {
                        queue.push(absolute);
                    }
                });

                continue;
            }

            if (contentType.includes('text/css')) {
                const cssText = await response.text();
                downloaded.set(normalizedUrl, { type: 'css', content: cssText });

                const cssAssetUrls = (cssText.match(/url\((['"]?)(.*?)\1\)|@import\s*(?:url\()?\s*(['"]?)([^'"\)]+)\3\s*\)?/gi) || []);
                cssAssetUrls.forEach((match) => {
                    const urlMatch = match.match(/url\((['"]?)(.*?)\1\)|@import\s*(?:url\()?\s*(['"]?)([^'"\)]+)\3\s*\)?/i);
                    const discoveredUrl = (urlMatch && (urlMatch[2] || urlMatch[4])) || '';
                    if (!discoveredUrl || discoveredUrl.startsWith('data:') || discoveredUrl.startsWith('#')) {
                        return;
                    }

                    const absolute = normalizeUrl(discoveredUrl, normalizedUrl);
                    if (isSameOrigin(absolute, rootUrl.href) && !seen.has(absolute) && isAssetCandidate(absolute)) {
                        queue.push(absolute);
                    }
                });

                continue;
            }

            downloaded.set(normalizedUrl, { type: 'binary', content: await response.blob() });
        } catch (error) {
            logMessage(`İçerik indirme hatası: ${normalizedUrl} - ${error.message}`);
        }
    }

    const zip = new JSZip();

    downloaded.forEach((entry, url) => {
        const localFilePath = fileMap.get(url) || toLocalFilePath(url);

        if (entry.type === 'css') {
            zip.file(localFilePath, rewriteCssUrls(entry.content, url, fileMap));
            return;
        }

        if (entry.type === 'html') {
            const html = rewriteHtmlDocument(entry.content, url, fileMap);
            zip.file(localFilePath, html);
            return;
        }

        zip.file(localFilePath, entry.content);
    });

    const rootHtml = downloaded.get(rootUrl.href)?.content || '';
    if (rootHtml) {
        zip.file('index.html', rewriteHtmlDocument(rootHtml, rootUrl.href, fileMap));
    }

    return zip;
}

async function startCloning() {
    resetLog();

    const input = document.getElementById('targetUrl');
    const button = document.querySelector('button');

    if (!input || !button) {
        logMessage('Sayfa formu yüklenemedi.');
        return;
    }

    const targetUrl = input.value.trim();
    if (!targetUrl) {
        logMessage('Lütfen bir site URL adresi girin.');
        return;
    }

    try {
        const siteUrl = new URL(targetUrl);
        if (!siteUrl.protocol.startsWith('http')) {
            throw new Error('Geçerli bir HTTP/HTTPS URL girin.');
        }

        const previousText = button.textContent;
        button.disabled = true;
        button.textContent = 'İndiriliyor...';
        logMessage(`Klonlama başlatıldı: ${siteUrl.href}`);

        const zip = await collectSiteAssets(siteUrl.href);
        const blob = await zip.generateAsync({ type: 'blob' });

        saveAs(blob, 'siteyedekle.zip');
        logMessage('ZIP dosyası indirildi.');
        button.textContent = previousText;
        button.disabled = false;
    } catch (error) {
        logMessage(`Klonlama hatası: ${error.message}`);
        button.disabled = false;
    }
}

window.startCloning = startCloning;
