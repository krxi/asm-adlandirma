# Mevcut v6 hattı üzerinde doğrulama pilotu — taslak

**Gerçek veri önkoşulları ve GPU koşusu: not run.** Beklenen veri hash'leri
henüz doğrulanmadığından `v6_girdi_manifest.json` içindeki değerler `null`;
araç bu durumda çalışmayı başlatmaz. Bu PR taslak kalmalıdır.

## Tek veri hattı

Ana depodaki `dogrula_v6.py` ikili/assembly eşleme çıktıları,
`decompile_ghidra.py` ve `lora/hazirla_sonraki.py --surum v6` kullanılır.
Pilot ham decompile cache kabul etmez, ikinci bir anonimleştirme veya
hazırlama hattı kurmaz. Mevcut hazırlanmış v5 ve v6 `train.jsonl` /
`valid_300.jsonl` dosyalarını okur; ana hazırlayıcı yeniden çağrılmaz.
Benchmark veya sabit kimlik dosyaları yeniden üretilmez.

Girdi manifesti, ana hazırlayıcı/doğrulayıcının halka açık kod kimliklerini
ve **önceden gözden geçirilmiş** veri/proof SHA-256 değerlerini sabitler.
Önceki v5 eğitim dosyası ve tam eğitim sırası da beklenen hash ile denetlenir;
çalıştırılan dosyanın hash'ini sonradan yazmak bu sözleşmenin yerine geçmez.
Gerçek artefaktlar bağımsız doğrulanıp manifest doldurulmadan plan/eğitim
başlamaz. Ürün CLI'ında otomatik hash mühürleme veya manifest geçersiz kılma
yoktur. Proje-ID dizin hash'i, sıralı `{dosya_adı: SHA256(baytlar)}`
sözlüğünün `ozet()` çıktısıdır; sıra hash'i mevcut `veri_sirasi()` ile tam
v5 eğitim kimlik sırasının `ozet()` çıktısıdır.

Ana `dogrula_v6.py` raporundaki proje rolü, doğrulanmış kimlik üyeliği ve
`decompile_hazir` sayısı kontrol edilir. Bu raporun başarı çıkış kodu tek
başına yeterli değildir. Manifestin kanıt dosyaları için beklenen hash'leri,
aynı mevcut ana hat koşusuna ait oldukları incelendikten sonra sabitlenmelidir.
Pilot ikiliyi yeniden analiz etmez; sahte veya yanlış onaylanmış bir köken
manifestine karşı kriptografik üretici kimliği doğrulaması sağlamaz.

## Eşli karşılaştırma

Combined kolu ana hazırlayıcının v6 mesajlarını aynen kullanır. Assembly
kontrolü aynı **SISTEM_V6** ve aynı assistant hedefini korur; yalnız kullanıcı
mesajındaki decompile bölümünü, doğrulanmış v5 assembly/çağrı bağlamıyla
değiştirir. Böylece iki kolun sistem mesajı aynıdır; bu kontrol eski tarihsel
v5 istemiyle aynıymış gibi sunulmaz. v5/v6 kimlik, sıra, proje, optimizasyon,
hedef baytları ve decompile öncesi kullanıcı metni birebir eşleşmelidir.

Sızıntı denetimi ana `ad_sizintisi` yardımcısını kullanır; hem ham
`gercek_ad` hem assistant JSON'daki gerçek öneksiz eğitim hedefi denetlenir.
`lfs_dir_compact` / `dir_compact` ve Mach-O alt çizgili biçimler sentetik
regresyonla korunur. Ana hazırlayıcının proje-içi anonimleştirmesi tekrar
uygulanmaz. Decompile içinde kalan sızıntı bayrağı pilotu durdurur; ana hattın
sızıntı yüzünden decompile'ı zaten çıkardığı satırlar temizdir. Decompile
bulunmayan ana hat satırları düşürülmez; kapsam ayrı raporlanır.

asm, bağlam ve decompile ayrı aranır. Stripped binary'de de görünen adlar
sızıntı sayılmaz: komut adları (`push`), bağlamın `komut`/`string` etiketleri ve
asm/bağlamdaki tanımsız dış semboller (`; -> statvfs`, `çağırır abort`). Bu
dylib'de tanımlı fonksiyon kendi import'u olamaz; öneksiz hedef yalnız satırın
kendi import'u ise muaftır (`sigar_statvfs` → `statvfs`). Ham ad import dışında
ve decompile'ın tamamında katı denetlenir. Yayımlanmış v5/v6 release'lerinde
(95.000 train + 300 valid, iki sürüm) bu kuralla 0 satır reddedilir; önceki
katı kural 119 / 124 train ve sabit valid çapasından 1 satırı reddediyordu.

Validation kimlikleri ve sırası sabit valid300 cache'iyle eşleştirilir.
Test_sabit/eval115 kimlikleri adından bağımsız reddedilir; eğitimde mevcut
ayrılmış proje hash'leri reddedilir. Yeni test seçeneği yoktur.

## Komutlar

Repo kökünden, manifest gerçek girdilerle önceden doğrulandıktan sonra:

```sh
python3 lora/v6_dogrulama.py plan \
  --train ../prepared-v5/train.jsonl --valid ../prepared-v5/valid_300.jsonl \
  --train-v6 ../prepared-v6/train.jsonl --valid-v6 ../prepared-v6/valid_300.jsonl \
  --dogrulama-raporu ../v6-proof/dogrulama.json \
  --dogrulanmis-idler ../v6-proof/decompile-id --output ../runs/v6-plan
python3 -m pytest -q
ruff check lora/v6_dogrulama.py tests/test_v6_dogrulama.py
ruff format --check lora/v6_dogrulama.py tests/test_v6_dogrulama.py
```

GPU için ayrı Python 3.11+ ortamında `lora/requirements-v6.txt` kullanılır;
yukarıdaki komutta `plan` yerine `run`, yeni çıktı dizini ve
`--model ../models/qwen3-8b` verilir. Model önceden yerelde bulunmalıdır;
araç ağdan indirmez. Tek bf16 CUDA GPU desteklenir. Bellek/süre/GPU maliyeti
ölçülmedi; herhangi bir GPU'ya sığma vaadi yoktur.

Varsayılan plan kol başına 100 optimizer adımı, aynı 1.600 eğitim örneği,
etkin batch 16, 4.096 bağlam ve iki kolda tüm 300 validation satırıdır.
Toplam 600 validation üretimi vardır; harici model API çağrısı yoktur.
Gerçek token uzunlukları GPU ağırlıkları yüklenmeden önce kontrol edilir;
girdi veya hedef kesilmez. Plan bu üst sınırları hesaplar, ölçülmüş hız yazmaz.

Tek önceden belirlenmiş karşılaştırmanın validation tarama koşulu kanonik
F1 farkı en az +0,01, eşli **proje** bootstrap %95 alt sınırı pozitif ve
geçerli JSON oranı azalmamış olmasıdır. Farklı optimizasyonlar aynı proje
kümesiyle birlikte örneklenir. Beş aday arasında seçim yapılacaksa bu tek
karşılaştırma eşiği yeterli değildir; literatür raporundaki aile düzeyi
çoklu karşılaştırma protokolü ayrıca önceden belirlenmelidir.

Çıktılar repo dışındadır. Yeni F1 kazancı veya el değmemiş final test sonucu
iddiası yoktur. Tam pytest, sentetik sınır testlerinin yanında mevcut gerçek
`sonuc/*.jsonl` arşivlerini rapor regresyonu için yeniden puanlar; yalnız
sentetik veya hiç benchmark puanlama yok diye tanımlanmaz.
