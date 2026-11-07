[![GitHub Pages](https://img.shields.io/badge/Live_Demo-GitHub_Pages-2ea44f?style=for-the-badge&logo=github)](https://kinefi.github.io/siteyedekle)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=for-the-badge)](LICENSE)

# siteyedekle

`siteyedekle`, erişim izni olan bir web sitesinin HTML sayfalarını ve aynı alan adındaki kaynaklarını tarayıcıdan toplamayı deneyip ZIP arşivi olarak indiren statik bir web aracıdır.

## Kullanım

### Tarayıcı

1. [Canlı demoyu](https://kinefi.github.io/siteyedekle) açın veya `index.html` dosyasını bir web sunucusunda yayınlayın.
2. İndirmek istediğiniz sitenin tam adresini (ör. `https://example.com/`) girin.
3. **Siteyi Klonla ve ZIP İndir** düğmesine basın. İşlem tamamlanırsa `siteyedekle.zip` indirilir.

### Yerel komut satırı aracı

GitHub Pages yalnızca statik dosyaları sunar ve bu Python aracını çalıştırmaz. Betik Python 3.14+ ve yalnızca standart kütüphane gerektirir; ayrıca Python paketi kurmanız gerekmez.

`uv` yüklüyse, gerekli Python ortamını otomatik yöneterek betiği şöyle çalıştırabilirsiniz:

```bash
uv run --script tools/download_site.py "websitesi.com" --output websitesi.zip
```

`uv` kurulu değilse ve Python 3.14+ yüklüyse:

```bash
python3 tools/download_site.py "websitesi.com" --output websitesi.zip
```

Windows'ta Python Launcher kullanılabilir:

```powershell
py tools/download_site.py "websitesi.com" --output websitesi.zip
```

Şema (`https://` veya `http://`) yazılmazsa betik otomatik olarak `https://` kullanır. Şemayı açıkça verirseniz belirtilen protokol korunur.

İstek sınırlarını `--max-pages`, `--max-files`, `--max-bytes` ve `--timeout` seçenekleriyle ayarlayabilirsiniz. Betik HTTP 429/529 yanıtlarında `Retry-After` süresine uyar ve varsayılan olarak en fazla 3 kez yeniden dener; her denemede bekleme artar. İstekler arasında varsayılan 1,5 saniye bekler ve sunucu yavaşlama istediğinde bu aralık artırılır. İndirme sonunda atlanan dosyalar HTTP durum kodu, hız sınırlaması, ağ/zaman aşımı ve dosya/indirme sınırı gibi nedenlere göre gruplanarak raporlanır. `--retries` ve `--request-delay` ile ayarlanabilir. Ayrıntılar için `uv run --script tools/download_site.py --help` veya `python3 tools/download_site.py --help` komutunu çalıştırın.

ZIP, `--output` ile verilen konuma kaydedilir. Bu seçenek verilmezse komutun çalıştırıldığı dizinde `siteyedekle.zip` oluşturulur. Kaynak dosyalar kalıcı olarak diske veya cache'e yazılmaz; indirme sırasında bellekte işlenip doğrudan ZIP'e eklenir.

## Özellikler

- Tarayıcıda çalışır; proje için ayrıca Node.js veya Python kurulumu gerekmez.
- HTML, CSS, JavaScript ve görsel gibi kaynakları toplamayı ve ZIP içinde yerel yollarla bağlamayı dener.
- Uygulama kodu ve stiller `assets/` dizininde tutulur.

## Önemli kısıtlamalar

- **CORS gereklidir:** Tarayıcılar başka bir alan adına yapılan istekleri hedef sunucunun CORS izni yoksa engeller. Bu araç bu güvenlik kısıtlamasını aşamaz. Hedef sunucu uygun `Access-Control-Allow-Origin` başlığını göndermiyorsa ana sayfa alınamaz ve ZIP oluşturulmaz. Bu durumda sunucu taraflı bir indirme servisi gerekir.
- Yerel komut satırı aracı tarayıcı CORS kısıtlamasına tabi değildir; ancak yalnızca erişebildiği kaynakları indirebilir ve Python 3 kurulumu gerektirir.
- Tarama hedef alan adıyla sınırlıdır; üçüncü taraf CDN ve diğer dış kaynaklar alınmaz.
- İndirilebilen dosyalar, sitenin JavaScript ile çalışma zamanı içinde sonradan oluşturduğu içeriği veya sunucu özelliklerini içermez. Bu nedenle sonuç sitenin birebir, tamamen çalışan bir kopyası olmayabilir.
- Yalnızca indirme izniniz olan sitelerde kullanın ve sitenin kullanım koşullarına uyun.

## Geliştirme

Projeyi yerel olarak denemek için kök dizinde basit bir HTTP sunucusu başlatıp `index.html` dosyasını açabilirsiniz. Sayfayı doğrudan `file://` üzerinden açmak bazı tarayıcı özelliklerinde kısıtlamalara neden olabilir.

## Dosya Yapısı

```text
siteyedekle/
├── index.html
├── assets/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js
├── tools/
│   └── download_site.py
└── README.md
```

## Açık kaynak

Bu proje [Apache License 2.0](./LICENSE) altında özgür yazılımdır. 