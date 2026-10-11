# Sıfırdan yeniden üretim

Bu belge, repodaki veriyi ve README'deki ölçümleri sıfırdan üretmek için gereken komutları sırasıyla verir.
Komutlar betiklerin kendi yardım metinlerinden alındı. Her adımın sonunda neyi kontrol edeceğiniz yazıyor.
Sonda, repodan yeniden üretilemeyen parçaların listesi var.

## 0. Ortam

| Gereken | Neden | Not |
|---|---|---|
| macOS + Apple clang **21** | Hedef `x86_64-apple-macos12`, Mach-O `.o`/dylib, `strip -x` | v4 raporu: Apple clang 21.0.0, sistem Python 3.9.6 ([VERI_HATTI_V4.md](VERI_HATTI_V4.md)). CI'da Xcode 26.6 (clang 21) ile `test_cikar_bin` geçiyor; Xcode 15.4 (clang 15) ile `cikar_bin.py` kod içi bir baytı `<unknown>` komut olarak görüp duruyor |
| `objdump` (LLVM) | Disassembly, relokasyon, `__cstring` | Xcode komut satırı araçlarıyla gelir |
| Python 3.9+ | Bütün betikler | Testler 3.9 ve 3.12'de CI'da koşar |
| `gh` (oturum açık) | Yalnız `aday_bul.py` (v4 aday listesi) | |
| Evren ya da OpenAI uyumlu uç nokta | `taban.py`, `aciklama.py`, `aciklama_puan.py` | `EVREN_LLM_API_KEY` ortam değişkeni ya da `EVREN_ENV` dosyası; anahtar repoya girmez |
| Apple Silicon + `mlx-lm` | Yerel LoRA (`lora/egit.sh`, `lora/olc.py`) | `python3.12 -m venv .venv && .venv/bin/pip install mlx-lm transformers matplotlib` |
| NVIDIA GPU (Colab) | `colab/egit.ipynb` | Sürümler notebook'un ilk hücresinde sabit |

Hızlı doğrulama (derleyici ve ağ gerekmez):

```bash
python3 -m pip install pytest
python3 -m pytest -q          # Linux'ta Mach-O testleri atlanır, macOS'ta hepsi koşar
```

## 1. Git'te olan ve olmayan

| Yol | Git'te mi | Nasıl üretilir |
|---|---|---|
| `projeler.json` | evet | elle: 14 eğitim + 5 test projesi, commit ve bayraklar sabit |
| `veri/test/*.jsonl` (777 satır), `veri/test.jsonl` (115) | evet | adım 2 |
| `veri/zlib.jsonl`, `veri/zlib-v3.jsonl` | evet | v1/v3 zlib ısınma verisi (adım 2) |
| `sonuc/*.jsonl`, `sonuc/log-*.txt` | evet | adım 3 |
| `veri/egitim/` (16.804 satır) | hayır | adım 2 |
| `veri/kaynak/`, `veri/aciklama/` | hayır | adım 4 |
| `veri/bin/` (v4: 228.177 satır) | hayır | adım 5 |
| `.notlar/aday-projeler.json` (v4 proje listesi) | **hayır** | adım 5; aşağıdaki "Açık noktalar"a bakın |
| `lora/veri*/`, `lora/adaptor*/` | hayır | adım 6 |

Yayınlanan kopya: Hugging Face [krxi123/asmsense](https://huggingface.co/datasets/krxi123/asmsense)
(v3 eğitim/test, `eval_115`, `aciklama` config'i ve `v4` config'i).

## 2. v3 verisi: eğitim + ezbere dayanıklı test seti

```bash
python3 cikar.py --projeler projeler.json      # indir, -O0/-O2 derle → veri/egitim/<ad>.jsonl, veri/test/<ad>.jsonl
python3 test_seti.py -k 12                     # → veri/test.jsonl (proje × kip başına ≤12, sızıntısız)
```

Kontrol:

- `wc -l veri/test/*.jsonl` toplamı **777**, `veri/test.jsonl` **115** satır olmalı.
- `git diff --stat veri/test` boş olmalı: numaralandırma ve seçim sabit tohumla yapılıyor, ama bayt bayt aynılık
  bu belgede doğrulanmadı. Farklı clang sürümü asm'yi değiştirebilir; o durumda en azından sayılar ve
  `pytest tests/test_veri_semasi.py` tutmalı.
- `pytest tests/test_veri_semasi.py`: şema, kimlik tekilliği, `sizinti` bayrağının `cikar.sizar_mi` ile tutarlılığı,
  ölçüm setinin test verisinin sızıntısız alt kümesi olması ve asm'de projenin gerçek iç adlarının geçmemesi.

## 3. Büyük modellerle taban ölçümü (README tablo 1–4)

```bash
python3 taban.py veri/test.jsonl -n 1000 -m <model>                      # → sonuc/test-<model>.jsonl
python3 taban.py veri/test.jsonl -n 1000 -m <model> --dusunme --tavan 12288
python3 taban.py veri/test.jsonl -n 1000 -m <model> --baglam             # özet bağlam → ...-baglam.jsonl
python3 taban.py veri/test.jsonl -n 1000 -m <model> --baglam-derin       # derin bağlam → ...-baglam2.jsonl
python3 taban.py veri/test.jsonl -n 1000 -m <model> --devam --kesik-de   # yarıda kalan/kesik satırları tamamla
python3 ozet.py --md test                                                # README tablosu
python3 iki_f1.py                                                        # gerçek ad + öneksiz F1 → rapor/F1_IKI_TANIM.md
python3 analiz.py veri/test.jsonl -o grafik/test-hata.png                # tür bazlı hata analizi
```

zlib ezber karşılaştırması (README tablo 2): aynı komutlar `veri/zlib-v3.jsonl` ile; `sh kos.sh` v1 zlib koşularını paralel başlatır.

Puanlama `taban.f1`: ad snake/camel sözcüklere bölünür, küçük harfe çevrilir, **sözcük kümelerinin** F1'i alınır
(sıra ve tekrar önemsiz). `ozet.py`'deki "öneksiz F1" projenin ortak önekini iki taraftan da atar.
`lora/olc.py` aynı fonksiyonu içe aktarır; `colab/*.ipynb` kopyasını taşır ve `tests/test_f1.py` kopyanın
`taban.py` ile birebir aynı kaldığını denetler.

Kontrol: Ölçüm `temperature=0` olsa da uç nokta belirlenimci olmayabilir; yeni koşu küçük farklar verebilir.
README'deki tablolar `sonuc/` altındaki dosyalardan `ozet.py` ile tekrar üretilebilir olmalı.

## 4. Öğretmen açıklamaları (damıtma)

```bash
python3 kaynak_kod.py -j 6                                  # v3: fonksiyon → C gövdesi, veri/kaynak/
python3 aciklama.py --kuru -n 3                             # istemleri gör, istek atma
python3 aciklama.py -m <model> -j 6 --devam                 # → veri/aciklama/<proje>.jsonl
python3 hf_yukle.py                                         # kuru: 17.581 satırı doğrula, yükleme yok
python3 aciklama_puan.py sonuc/<koşu>.jsonl -m <hakem> -j 6 # öğrenci açıklamalarını 0-2 puanla
```

v4 için aynı adımlar ayrı dizinlerle:

```bash
python3 kaynak_kod.py --veri-dosyalari veri/bin/olcek/{egitim,dogrulama,test}.jsonl   # → veri/kaynak-v4/
python3 aciklama.py --kaynak-dizini veri/kaynak-v4 --cikti-dizini veri/aciklama-v4 -m <model> -j 6 --devam
```

Kontrol: `hf_yukle.py` kuru kipi beklenen satır sayısını (17.581) doğrular. v4 kaynak eşleşmesi son koşuda
83.474 / 83.531 kaynak fonksiyon buldu (son commit mesajı).

## 5. v4 verisi: gerçek link + strip, 5 optimizasyon

```bash
python3 aday_bul.py -o .notlar/aday-projeler.json           # GitHub'dan izin verici lisanslı aday projeler
python3 olcekle.py hepsi --liste projeler.json .notlar/aday-projeler.json -j 3
#   = indir → cikar (cikar_bin.py, -O0/-O1/-O2/-O3/-Os) → birlestir (tekilleştir, ayır) → rapor
python3 -m pytest -q test_cikar_bin.py                      # macOS: gerçek link/strip regresyonları
```

Çıktı: `veri/bin/olcek/{egitim,dogrulama,test}.jsonl`, `veri/bin/olcek/rapor.json`.

Kontrol (README "Scaled dataset" tablosu): eğitim 290 proje / 196.117 satır, doğrulama 23 / 19.770,
test 28 / 12.290. Toplam 228.177 satır.

## 6. LoRA verisi

v3 (yerel, mlx-lm):

```bash
.venv/bin/python lora/hazirla.py --onek-at --proje-tavan 1500 [--baglam ozet] [--aciklama]   # → lora/veri
```

v4 (ölçekli):

```bash
.venv/bin/python lora/hazirla_olcek.py --cikti lora/veri-olcek --baglam ozet --proje-tavan 1500
```

`--token-tavan` (varsayılan 1500) tokenizer'ı Hugging Face'ten indirir. Ağsız deneme için `--token-tavan 0` verin.
Örnek veri üzerinde iki betiğin de uçtan uca koşusu:

```bash
python3 tests/ornek.py /tmp/ornek && cd /tmp/ornek
python3 <repo>/lora/hazirla.py --veri veri --cikti lora/veri --token-tavan 0 --baglam ozet --onek-at --aciklama
python3 <repo>/lora/hazirla_olcek.py --veri veri/bin/olcek --cikti lora/veri-olcek --token-tavan 0 --proje-tavan 5
```

CI bu komutları her push'ta çalıştırır (`.github/workflows/test.yml`).

## 7. Eğitim ve ölçüm

Yerel (Apple Silicon): `sh lora/egit.sh` (`lora/ayar.yaml`), sonra `.venv/bin/python lora/olc.py`.

Colab: `sh colab/zip_hazirla.sh` (`lora/veri-15b-aciklama/` → `veri.zip`), `colab/egit.ipynb`'yi GPU çalışma
zamanında baştan sona çalıştırın ([colab/README.md](colab/README.md)). Son hücre `lora/olc.py` biçiminde
sonuç JSONL'i yazar. `python3 ozet.py` ile diğer koşularla aynı tabloda görünür.

### v6 final ölçüm kiti (GPU/ağırlık indirmeden)

`molab/egit.py` ve v6 Colab motoru tam eğitimin sonunda **valid F1 ile seçilmiş**
adaptörü `test_sabit` (2.000) ve `eval115` (115) üzerinde ölçer. Üretim greedy,
`enable_thinking=False`, `max_new_tokens=160`; `son/` ise devam için son-adım
adaptörüdür, en iyi adaptör veya tamamlanmış test anlamına gelmez. Bu yüzden kit
yerel model üretimini tekrarlamaz: final JSONL ve tamamlanma damgalarını okur.
Eğitim sürerken test dosyalarını ölçüm/seçim amacıyla açmayın.

```bash
python3 -m pip install huggingface_hub  # yalnız HF indirme için
# HF_TOKEN yalnız ortamdan; macOS'ta Anahtar Zinciri sarmalayıcısı:
gizli calistir python3 olcum_v6.py indir --cikti sonuc/v6
# Linux/molab/Colab/sirius: HF_TOKEN güvenli ortamda tanımlandıktan sonra:
# python3 olcum_v6.py indir --cikti sonuc/v6
python3 olcum_v6.py rapor --veri /path/to/veri-v6 --sonuc sonuc/v6 -o /tmp/olcum-v6.json
```

Yerel molab/Colab çalışma dizininde `test_sabit-sonuc.jsonl` ve
`eval115-sonuc.jsonl` varsa `--sonuc /path/to/run` ile indirmeden çalışır.
HF indirme tek commit'e sabitlenir; iki damga `kosu.json`/`en_iyi.json` ile
eşleşmeli ve sonuçlar tam olmalı. Özel indirme dizini ve `kosu.json` yerel
yol/koşu bilgisi içerebilir; ham dosyaları herkese açık commit'e eklemeyin.

Rapor gerçek ad F1'i `taban.f1` ile yeniden hesaplar (dosyadaki skor körlemesine
kullanılmaz); öneksiz F1 için v6 satırındaki `oneksiz_onek` kullanılır.
v5 tahminleri varsayılan olarak repodaki `sonuc/*-v5.jsonl` dosyalarıdır.
Eksik/yinelenen kimlik, değişmiş hedef/opt/proje veya eksik decompile metadata
ölçümü durdurur; kesişim alt kümesi sessizce seçilmez.
Ana eşli %95 bootstrap aralığı 2.000 tekrar/42 tohumla **proje kümelerini**
yeniden örnekler (opt kopyaları birlikte); tarihsel satır aralığı yalnız tanısaldır.
`opt` ve `opt_decompile` -O0…-O3 yanında verideki -Os'u da içerir.
`decompile.var` kapsanan satırlardır; `tam`/`kirpildi`/`yok` ayrık alt kümelerdir.
Boş gruplar `n=0, f1=null` olarak görünür. Alt grup farkları tanısaldır.
`tam_isabet` birebir ad eşitliği, `f1_tam_isabet` ise sözcük kümesi F1=1 sayısıdır.
F1 hedefleri test2000 ≥0.14 ve eval115 ≥0.17; v5 yayımlanmış kıyas 0.124/0.155.

Açıklama için aynı v5 **300 kimliği**, aynı C kaynak/ref ve hakem istemi kullanılır
(rastgele yeni örneklem veya kaynağı olmayan satırların elenmesi yok):

```bash
python3 aciklama_puan_v6.py puan sonuc/v6/test_sabit-sonuc.jsonl \
  --kaynak /path/to/veri/kaynak-v4 --referans /path/to/veri/aciklama-v4/codex.jsonl \
  --model mimo-v2.6-pro -j 8 -o /tmp/v6-puan.jsonl
python3 aciklama_puan_v6.py ozet /tmp/v6-puan.jsonl -o /tmp/v6-aciklama.json
```

Kaynak/ref git dışıdır (adım 4); `--kuru` hakem çağırmadan gerçek 600 istemi
çıktıya yazar. Canlı hakem için mevcut `EVREN_LLM_API_KEY`/`EVREN_ENV` kullanılır.
İngilizce hedef puan=2 oranı ≥%25 ve sıfır hakem hatasıdır.
Hata satırları silinmez: `dogru_orani` tüm 300 satırın, `tam_karar_dogru_orani`
yalnız karar verilmiş satırların oranıdır. v5 EN %20.0 = 59/295 karar;
tam örneklemde 59/300 = %19.67 (5 hata). TR 62/296 = %20.95 (4 hata).
İki dil ayrı raporlanır; doğru/yanlış açıklamalar için ad F1 ve eşli proje GA da vardır.

v6 sonuçları hazır olmadan kitin v5 kuru denemesi:

```bash
python3 olcum_v6.py rapor --veri /path/to/veri-v6 --kuru-v5 -o /tmp/v5-kuru.json
python3 aciklama_puan_v6.py ozet sonuc/test2000-molab-qwen3-8b-v5-puan.jsonl -o /tmp/v5-aciklama.json
python3 aciklama_puan_v6.py puan sonuc/test2000-molab-qwen3-8b-v5.jsonl \
  --kaynak /path/to/veri/kaynak-v4 --referans /path/to/veri/aciklama-v4/codex.jsonl \
  --kuru -o /tmp/v5-istemler.jsonl
python3 -m pytest -q tests/test_olcum_v6.py
```

Gerçek v5 çıktılarıyla kuru deneme: F1 0.1236480880/0.1554451346,
öneksiz F1 0.1256643579/0.1729606625; v5'e karşı fark ve GA `[0,0]`.
Bu **v6 sonucu değildir**. v6 metadata ile test decompile 1.999/2.000
(347 kırpılmış), eval115 115/115 (15 kırpılmış). Gerçek kaynak/ref ile
300 kimlik/600 hakem istemi ağsız hazırlanır; mevcut puanlar EN %20.0'ı yeniden üretir.

## 8. Açık noktalar (repodan tam üretilemeyen)

1. **v4 proje listesi git'te değil.** `olcekle.py` varsayılan olarak `.notlar/aday-projeler.json` okur. Bu dosya
   `.gitignore`'da. `aday_bul.py` GitHub aramasını bugünkü yıldız/tarih durumuyla yaptığı için yeniden çalıştırmak
   **aynı 473 projeyi ve commit'leri vermez**. v4'ü birebir üretmek için bu listenin (ad, url, commit, rol, lisans)
   repoya ya da HF'ye konması gerekir.
2. **`lora/veri-15b-aciklama/` hangi komutla üretildi, kayıtlı değil.** `colab/zip_hazirla.sh` bu dizini bekliyor.
   `hazirla.py --aciklama` v3 düzeninde açıklama ekler. `hazirla_olcek.py`'de açıklama seçeneği yok.
3. **v3 ve v4 hazırlamada test hedefi farklı.** `hazirla.py` test hedefini hep gerçek adla yazar (büyük modellerle
   aynı puanlama). `hazirla_olcek.py` ise önek atmayı test dahil bütün bölümlere uygular. `olc.py` ve Colab
   ölçümü hedefteki adla puanladığı için v4 test F1'i öneksiz adlara göredir. Bu yüzden büyük modellerin düz F1'i ile
   doğrudan karşılaştırılamaz. `ozet.py`'deki öneksiz F1 ile karşılaştırmak daha doğru olur.
   Ayrıca varsayılan önek kuralı proje adından bağımsızdır (sajs'ta `eat_`, picomatch'te `emit_` atılır).
   Yeni koşularda `--test-ham-ad` ve `--onek-kurali proje` kullanın. Eski sonuç dosyalarını iki tanımla
   puanlamak için `python3 iki_f1.py <dosya.jsonl>` ([rapor/F1_IKI_TANIM.md](rapor/F1_IKI_TANIM.md)).
4. Model uç noktaları (Evren) ve öğretmen modelleri zamanla değişebilir. `sonuc/` altındaki ham çıktılar asıl kayıttır.
