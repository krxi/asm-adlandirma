# Doğrulamada aynı kaynak işlevin optimizasyon çiftleri

`opt_eslesme.py` ham `ad` ile sonuçtaki `gercek` değerini karşılaştırır;
`f1` değerini değişmeyen `taban.f1(tahmin, ad)` ile yeniden hesaplar.
Etiket veya skor uyuşmazsa rapor üretmez. Sonuç kimlikleri SHA-256 ile sabitlenen
valid300 kümesinden olmalı; test_sabit/eval115 kimlikleri dosya adı ne olursa
olsun reddedilir. Tam ham doğrulama dosyası sürüm kontrollü manifestteki
SHA-256 ile tanınır; aksi halde ham girdi de sabit kümenin kanonik alt kümesi olmalıdır.

## Yeniden üretim

Repo kökünde, mevcut salt okunur v4 doğrulama dosyasının yolu ile:

```sh
python3 opt_eslesme.py --veri "$VALIDATION_JSONL" \
  --tahmin sonuc/valid300-molab-qwen3-8b-v5.jsonl \
  --tohum 42 --bootstrap 2000 -o opt-denetim.json
python3 -m pytest -q tests/test_opt_eslesme.py tests/test_dogrulama_guvencesi.py
```

`opt-denetim.json` tek sayısal kaynaktır. `satir` ve `kaynak_islev_kip_grubu`
kapsamı; `opt` eşlenmemiş kohortların F1/string/komut istatistiklerini;
`esli_cift` aynı `(proje,dosya,ad,kip)` çiftlerinin sağ eksi sol farkını ve
bootstrap aralığını verir. `kod` commit/tree, `girdi` taşınabilir dosya adı ve
SHA-256 içerir. Elle taşınan eski sonuç tablosu kaldırıldı; bu düzeltmede gerçek
veri denetimi yeniden çalıştırılmadı (`not run`). Güncel CI sonucu PR #9'dadır.

JSON UTF-8, sıralı anahtarlar, 9 ondalık basamak ve kararlı toplama kullanır;
sentetik altın dosya özeti aynı Python 3.9/3.12 testlerinde doğrulanır.
Saat, yorumlayıcı yolu ve çalışma dizini çıktıya girmez.

## Yorum sınırı

Bu araç model eğitmez. Örnekleme birimi aynı kaynak işlev/kip çiftidir;
optimizasyon kopyaları bağımsız satırlar sayılmaz. Projeler arasındaki
bağımlılık ve küçük çift sayıları kalır. Buradaki aralıklar çoklu karşılaştırma
ile düzeltilmiş seçim kapıları değildir; keşif/tanı amacıyla kullanılmalıdır.
Mevcut v6 hattının kontrollü validation deneyi önceliklidir. Test kümeleri ve
kanonik skorlayıcı değiştirilmez; F1 kazancı iddia edilmez.
