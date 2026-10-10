# Kör açıklama değerlendirmesi — sabit valid300

Araç ağ/model çağrısı yapmaz. Yalnız hash'i manifestle sabitlenmiş valid300
kimlikleri kabul edilir. Ham doğrulama etiketi/proje/opt kontrol edilir;
yeniden adlandırılmış test_sabit/eval115 içerikleri reddedilir.

## Kapsam ve rubrik

Her aday sabit havuzun tamamı için boş olmayan İngilizce açıklama vermelidir.
**Asgari kapsam %100**; eksik satır veya açıklamada beklenen/mevcut sayılarla
hata verilir. Adayların kesişimini alıp zor örnekleri düşürmek yoktur.
Örnekleme bu sabit havuzdan proje dengeli ve tohumlu yapılır. Başarılı plan
her adayın kapsamını ve seçilen dağılımı ayrı raporlar.

`ana_islem`, `girdi_cikti`, `yan_etki`: `dogru=1`, `kismi=0.5`, `yanlis=0`,
`bilinmiyor=0`. `uydurma`: `yok=1`, `var=0`, `bilinmiyor=0`.
Bileşik puanın **paydası daima dört**; tümü bilinmeyen örnek bile kapsamda
kalır. Bilinmeyen, semantik olarak yanlış ilan edilmez; seçim için muhafazakâr
alt puan alır. Alan başına tüm etiket oranları, karar kapsamı,
`uydurma_var_orani` ve `var+bilinmiyor` risk oranı ayrıca üretilir.

İlk `--tahmin` referans sistemdir. Her aday için `aday_kapilari` şunları verir:
karar kapsamı azalmadı, `uydurma=var` artmadı, bilinmeyen dahil uydurma riski
artmadı ve bu üç koşulun birleşik güvenlik kapısı. Bu kapı tek başına kalite
artışı değildir; ayrıca önceden belirlenmiş açıklama farkı ve değişmemiş
kanonik/öneksiz ad F1 değerlendirilmelidir.

## Paket ve etiket bütünlüğü

Puanlayıcı yalnız C kaynağı ve İngilizce açıklamayı görür. C içindeki işlev
adı doğal olarak kalır; sistem/tahmin/F1/özgün ID alanları gösterilmez.
Paket değiştirilmeyen özgün JSONL'dir. Yanında üretilen etiket şablonunun
her satırı özgün **paket baytlarının SHA-256** değerini taşır. İki puanlayıcı
bu şablonun ayrı kopyalarını doldurur; paketi düzenlemez. Kör anahtar da aynı
hash'e bağlıdır. Puanlama gerçek paket dosyasını yeniden hash'ler; farklı
paket, eksik etiket veya eksik uzlaşı kabul edilmez.

Anahtar varsayılan olarak repo dışındaki `../asmsense-ozel/` içine
`*.asmsense-kor-anahtar.json` adıyla, yalnız kullanıcı okuma/yazma izinleriyle
yazılır. Bu desen ayrıca `.gitignore` içindedir. Açıkça repo içi bir anahtar
veya paket yolu vermek de reddedilir. Mevcut dosyaların üzerine yazılmaz.

## Yeniden üretim

Repo kökünden; girdiler mevcut, salt okunur validation artefaktlarıdır:

```sh
python3 aciklama_degerlendir.py plan --veri ../validation.jsonl \
  --tahmin v5=../v5-validation.jsonl --tahmin aday=../aday-validation.jsonl \
  -n 100 --tohum 42 -o ../aciklama-plan.json
python3 aciklama_degerlendir.py paketle --veri ../validation.jsonl \
  --tahmin v5=../v5-validation.jsonl --tahmin aday=../aday-validation.jsonl \
  --kaynak ../kaynak-v4 -n 100 --tohum 42 --paket ../kor/paket.jsonl \
  --anahtar ../asmsense-ozel/inceleme.asmsense-kor-anahtar.json
python3 aciklama_degerlendir.py puanla --paket ../kor/paket.jsonl \
  --anahtar ../asmsense-ozel/inceleme.asmsense-kor-anahtar.json \
  --etiket ../kor/puanlayici-a.jsonl --etiket ../kor/puanlayici-b.jsonl \
  --uzlasi ../kor/uzlasi.jsonl --tohum 42 -o ../aciklama-sonuc.json
python3 -m pytest -q
ruff check aciklama_degerlendir.py dogrulama_guvencesi.py tests/test_aciklama_degerlendir.py tests/test_dogrulama_guvencesi.py
ruff format --check aciklama_degerlendir.py dogrulama_guvencesi.py tests/test_aciklama_degerlendir.py tests/test_dogrulama_guvencesi.py
```

Alan başına ham uyum ve [Cohen kappa](https://doi.org/10.1177/001316446002000104)
raporlanır. Tek sınıfta beklenen uyum 1 ise kappa **null ve açıklamalı** olur;
kusursuz görünen uyum 1.0 kappa diye sunulmaz. Uzlaşı yoksa kalite kapıları
`null` ve uzlaşı `not run` kalır. Uzlaşıda hiçbir bilinmeyen örnek çıkarılmaz.
Eşli bootstrap projeleri birlikte örnekler; optimizasyon kopyaları bağımsız
satır sayılmaz. Çoklu aday aralıkları tanısaldır; çoklu karşılaştırma düzeltmesi
olmaksızın aday seçimi için kullanılmamalıdır.

## Durum ve sınırlar

Bu revizyonda gerçek insan puanlaması ve yeni model çıkarımı **not run**;
yeni açıklama veya F1 kazanımı yoktur. Kendi sentetik kaynaklarımızla paket,
etiket bütünlüğü ve puanlama regresyonları koşulur. Tam pytest ayrıca gerçek
arşiv tahminlerini rapor regresyonu için yeniden puanlar. Halka açık güncel
commit/tree ve CI kanıtı PR #8 açıklamasındadır; eski laboratuvar günlüğü
ve elle taşınmış örneklem sayıları kaldırılmıştır.

C kaynağındaki bazı davranışlar optimizasyonla silinmiş olabilir. İnsanların
bağımsızlığı ve kaynak/binary kökeni bu araçla kanıtlanmaz. %100 çıktı kapsamı
ve muhafazakâr bilinmeyen puanı seçilim yanlılığını azaltır, insan kalibrasyonunu
ikame etmez. Mevcut test2000 geliştirmede kullanılmıştır; el değmemiş nihai
test gibi sunulmaz ve burada yeni test puanlaması yapılmaz.
