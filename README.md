[![GitHub Pages](https://img.shields.io/badge/Live_Demo-GitHub_Pages-2ea44f?style=for-the-badge&logo=github)](https://kinefi.github.io/siteyedekle)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=for-the-badge)](LICENSE)

# siteyedekle

`siteyedekle`, erişim izni olan bir web sitesinin HTML sayfalarını ve aynı alan adındaki kaynaklarını tarayıcıdan toplamayı deneyip ZIP arşivi olarak indiren statik bir web aracıdır.

## Kullanım

1. [Canlı demoyu](https://kinefi.github.io/siteyedekle) açın veya `index.html` dosyasını bir web sunucusunda yayınlayın.
2. İndirmek istediğiniz sitenin tam adresini (ör. `https://example.com/`) girin.
3. **Siteyi Klonla ve ZIP İndir** düğmesine basın. İşlem tamamlanırsa `siteyedekle.zip` indirilir.

## Özellikler

- Tarayıcıda çalışır; proje için ayrıca Node.js veya Python kurulumu gerekmez.
- HTML, CSS, JavaScript ve görsel gibi kaynakları toplamayı ve ZIP içinde yerel yollarla bağlamayı dener.
- Uygulama kodu ve stiller `assets/` dizininde tutulur.

## Önemli kısıtlamalar

- **CORS gereklidir:** Tarayıcılar başka bir alan adına yapılan istekleri hedef sunucunun CORS izni yoksa engeller. Bu araç bu güvenlik kısıtlamasını aşamaz. Hedef sunucu uygun `Access-Control-Allow-Origin` başlığını göndermiyorsa ana sayfa alınamaz ve ZIP oluşturulmaz. Bu durumda sunucu taraflı bir indirme servisi gerekir.
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
└── README.md
```

## Açık kaynak

Bu proje [Apache License 2.0](./LICENSE) altında özgür yazılımdır. 