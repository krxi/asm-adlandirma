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

Yayınlanan kopya: Hugging Face [krxi123/asm-adlandirma](https://huggingface.co/datasets/krxi123/asm-adlandirma)
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
4. Model uç noktaları (Evren) ve öğretmen modelleri zamanla değişebilir. `sonuc/` altındaki ham çıktılar asıl kayıttır.
