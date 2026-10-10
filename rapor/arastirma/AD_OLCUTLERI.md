# Dondurulmuş doğrulama tahminlerinde ad ölçütleri

Bu araç model kazancı değil, aynı tahminlerin farklı ölçütlerle puanlanmasını
inceler. Kanonik `taban.f1`, mevcut öneksiz F1, dar bire-bir eşleme F1,
mevcut geniş `f1_es` ve tam ad doğruluğu ayrı kalır. Sözlük değiştirilmedi.

## Girdi güvencesi

`dogrulama_manifest.json`, kabul edilen v5 tahmin dosyasının SHA-256'sını sürüm
kontrolünde tutar. Dosya adı yeterli değildir: tek bir tahmin değişikliği bile
puanlamadan önce reddedilir. Sabit valid300 kimlik/etiket/proje eşleşmesi ve
test_sabit/eval115 kimlikleri içerikten denetlenir. Yeni bir tahmin sürümü
kabul etmek manifestin ayrı incelenen güncellemesini gerektirir.

`ozet.onekler(veri=None)` varsayılan olarak repo içindeki `veri/` dizinini
kullanır; `ONEK` importu artık çalışma dizininden bağımsızdır. Açık veri kökü
parametresi de desteklenir. Repo kökünden tarihsel puanlama ve skor formülü
aynıdır; yalnız başka dizinden importun yanlış/boş harita üretmesi düzeltildi.

## Yeniden üretim

```sh
python3 ad_olcutleri.py --veri "$VALIDATION_JSONL" \
  --tahmin sonuc/valid300-molab-qwen3-8b-v5.jsonl > ad-olcutleri.json
python3 -m pytest -q tests/test_ad_olcutleri.py tests/test_ad_olcut_guvencesi.py tests/test_dogrulama_guvencesi.py
```

JSON `iz` alanı herkese açık checkout'un commit/tree kimliklerini, dosya adı
ve SHA-256'yı kaydeder; kişisel kök dizin veya yorumlayıcı yolu yazmaz.
Bu düzeltmede gerçek validation tekrarı çalıştırılmadı (`not run`); eski elle
taşınmış sonuçlar ve laboratuvar günlüğü kaldırıldı. Güncel pytest/Ruff
kanıtı PR #5'in Checks bölümündedir.

Dar eşleme dilsel varsayımdır; semantik hakem değildir. Satır bootstrap'ı
eski yardımcı tanı olarak korunur, optimizasyon kopyalarının bağımsız olduğu
veya modelin geliştiği iddiasına dayanak olamaz. Model seçimi için proje/kaynak
kümeli değerlendirme gerekir. Test kümelerine yeni ölçüt uygulanmaz.
