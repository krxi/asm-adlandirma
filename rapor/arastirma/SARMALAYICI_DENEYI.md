# Doğrulama kümesinde tek adımlık wrapper kontrolü

`deney` yalnız sabit valid300 hedeflerinde, aynı proje/sürüm/ikili/opt kapsamında
çağrılan işlevin **özgün tahminini** aktarır. Gerçek adlar aktarım kararına girmez;
döngü, belirsizlik, eksik bağ veya geçersiz tahminde çekimser kalır. Mevcut
`dogrulama_deneyi` koruması ve tek-adım algoritması değiştirilmedi.

## Yeniden üretim

Repo kökünde, sürüm kontrollü manifestin doğruladığı mevcut v4 validation dosyasıyla:

```sh
python3 sarmalayici_deneyi.py say --veri "$VALIDATION_JSONL" \
  --tahmin sonuc/valid300-molab-qwen3-8b-v5.jsonl > wrapper-sayim.json
python3 sarmalayici_deneyi.py deney --veri "$VALIDATION_JSONL" \
  --tahmin sonuc/valid300-molab-qwen3-8b-v5.jsonl > wrapper-deney.json
python3 -m pytest -q tests/test_sarmalayici_deneyi.py tests/test_dogrulama_guvencesi.py
```

`wrapper-sayim.json` varsayılan olarak yalnız sabit doğrulama hedeflerini sayar.
`--idler` yalnız bu kümenin alt kümesi olabilir. Dosya adı güvence değildir:
test_sabit/eval115 ve doğrulama dışı kimlikler içerikten reddedilir. Birden fazla
ham dosyayı birleştiren eski CLI yolu kapatıldı; tam validation dosyası SHA-256
ile, alt kümesi ise sabit kimlik ve kanonik etiketlerle doğrulanır.

`deney` çıktısı kanonik/öneksiz F1 ve aktarım kapsamını; `say` çıktısı yalnız
validation wrapper sayısını, mevcut skorları ve matematiksel onarım sınırını
verir. Böyle bir sınır elde edilmiş veya beklenen model kazancı değildir.
Test/eval115 alt grup puanları ve onarım sınırları bu PR'ın rapor ve kanıtından
çıkarıldı; deney gerekçesi olarak kullanılmaz. Gerçek validation analizi bu
düzeltmede yeniden çalıştırılmadı (`not run`); sayılar komut çıktısından üretilmelidir.

## Kanıt ve sınırlar

JSON `iz` alanında `python3` ile taşınabilir komut, public checkout commit/tree,
repo-göreli dosya veya yalnız dosya adı + SHA-256 bulunur; mutlak çalışma yolu yoktur.
Birim testleri sayımın test kimliklerini reddettiğini, çıktı yollarını ve mevcut
deney korumasının kaynak metninin değişmediğini sınar. Güncel CI PR #4'tedir.
Tam pytest gerçek arşiv tahminlerini rapor regresyonu için yeniden puanlar;
bu, yeni model çıkarımı değildir. Yeni eğitim, inference ve test deneyi çalıştırılmadı.
Mevcut v6 hattının validation karşılaştırması ayrı iş olarak kalır.
