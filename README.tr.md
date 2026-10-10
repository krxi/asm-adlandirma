# asm-adlandirma

[English](README.md) · **Türkçe**

**Sembolleri silinmiş bir binary'deki fonksiyona bakıp ona anlamlı bir ad ve kısa bir açıklama veren küçük bir dil modeli.**

## Güncel durum

v4 veri seti, 5 optimizasyon seviyesinde 341 projeden 228.177 fonksiyon içeriyor ve [Hugging Face'te](https://huggingface.co/datasets/krxi123/asm-adlandirma) `v4` config'iyle yayımlanıyor. Ghidra betiği hazır. Şimdiye kadarki en iyi küçük model, v5 verisiyle (önce açıklama, sonra ad) eğitilen Qwen3-8B + LoRA: sabit v4 test örnekleminde ad F1 0.124, `eval_115`'te 0.155; çağrı bağlamı verilen en iyi büyük model aynı test örnekleminde 0.167. Bkz. Sonuçlar, bölüm 6. Model adla birlikte tek cümlelik İngilizce ve Türkçe açıklama yazıyor.

Ghidra ya da IDA ile stripped bir programı açtığınızda yüzlerce `FUN_00401a30` görürsünüz. Tersine mühendisliğin büyük kısmı, bunların ne iş yaptığını tek tek anlayıp adlandırmaktır. Bu proje o ilk adımı bir modele öğretmeyi amaçlıyor:

```
girdi  (stripped x86-64)              hedeflenen çıktı
─────────────────────────────         ──────────────────────────────────────────
movzx  eax, byte ptr [rsi]            ad:       adler32_update
lea    rdx, [rdi + rax]               açıklama: Tampondaki baytlar üzerinden
cmp    rdx, 0xfff1      ← 65521                 Adler-32 sağlama toplamı hesaplar.
...
```

## Hedef

Büyük genel amaçlı modeller bu işi bir ölçüde yapabiliyor, ama yavaş, pahalı ve bulutta çalışıyorlar. Hedef:

> Bu iş için özel veriyle eğitilmiş **küçük** bir model, büyük modellere yaklaşabilir mi, hatta onları geçebilir mi? Üstelik dizüstü bilgisayarda çalışabilir mi?

Bunu ölçmek için üç katman aynı test setinde karşılaştırılıyor:

| Katman | Model | Rolü |
|---|---|---|
| Tavan | Büyük açık modeller (DeepSeek, GLM, MiMo, Gemma, Qwen) | Bugün hazır modellerle varılabilen nokta |
| Taban | Küçük açık model, eğitilmemiş hali | Başlangıç noktası |
| **Bu proje** | Aynı küçük model + bu veri setiyle LoRA | Katkı |

## Nasıl çalışıyor

1. **Veri üretimi (`cikar.py`):** Açık kaynak C projeleri farklı optimizasyon seviyelerinde (`-O0`, `-O2`) x86-64 için derlenir. Her fonksiyonun assembly kodu çıkarılır. Doğru cevap, yani gerçek fonksiyon adı, kaynak koddan bedavaya gelir; elle etiketleme gerekmez. Hangi projenin hangi commit'le, hangi bayraklarla derlendiği `projeler.json`'da durur.
2. **Stripped binary taklidi:** Çıktı, Ghidra'da stripped bir fonksiyona bakınca görülene benzer:
   - projenin kendi fonksiyonları `sub_01a3`, global verileri `dat_0042` olur (numaralar karıştırılır, `-O0` ve `-O2` ayrı ad uzayıdır),
   - dal hedefleri fonksiyon içi `loc_1`, `loc_2` etiketleridir,
   - dış kütüphane çağrıları (`memcpy`, `__stack_chk_fail`) ve string sabitleri (`; -> "out of memory"`) görünür kalır, çünkü gerçek bir binary'de de görünürler.
   
   Fonksiyonun gerçek adı kendi assembly'sinde geçiyorsa (ör. bir hata mesajında) satır `sizinti` olarak işaretlenir ve test setine alınmaz.
3. **Ölçüm (`taban.py`):** Modele yalnız assembly verilir, ad tahmini istenir. Tahmin kelime örtüşmesiyle (F1) puanlanır. Böylece `crc32_update` ile `update_crc` gibi yakın tahminler de kısmen doğru sayılır.

```
loc_6:
movzx   r9d, byte ptr [rsi + rdx]
add     rdi, r9                 ← adler32_z (-O2), modelin gördüğü hâli
add     rcx, rdi
inc     rdx
cmp     rax, rdx
jne     loc_6
```

## Veri

| | projeler | fonksiyon (-O0 + -O2) |
|---|---|---|
| Eğitim | zlib, libpng, sqlite, lua, mbedtls, zstd, libsodium, expat, brotli, jansson, lz4, libyaml, xxhash, cJSON | 16.804 |
| Test (ezbere dayanıklı) | tomlc17, cyaml, mu_json_x, sajs, picomatch | 777 → ölçüm seti 115 |

Veri seti Hugging Face'te: [krxi123/asm-adlandirma](https://huggingface.co/datasets/krxi123/asm-adlandirma) (eğitim 16.804, test 777, `eval_115` ölçüm seti, lisans metinleri dahil).

### Ölçeklenmiş veri (v4 hattı, 5 optimizasyon seviyesi)

`olcekle.py` ile GitHub'dan seçilen izin verici lisanslı (MIT, BSD, Apache-2.0, ISC, zlib) C projeleri `cikar_bin.py` (gerçek dylib + `strip -x`) ile `-O0/-O1/-O2/-O3/-Os` seviyelerinde derlendi. Proje derleme betikleri çalıştırılmadı, dosyalar tek tek clang ile derlendi; derlenemeyen dosya ve proje atlandı. Normalize assembly hash'iyle tekilleştirildi; doğrulama/test ile aynı assembly'yi taşıyan satırlar eğitimden, eğitimdeki (dosya, ad) çiftini taşıyan vendored kopyalar doğrulama/testten çıkarıldı. Her satırda `lisans` alanı var.

| ayrım | proje | satır | benzersiz kaynak fonksiyon |
|---|---:|---:|---:|
| eğitim | 290 | 196.117 | 72.179 |
| doğrulama | 23 | 19.770 | 6.667 |
| test (az bilinen, ≤200 yıldız, 2024+) | 28 | 12.290 | 4.685 |

473 projeden 352'si satır üretti, 120'si derlenemedi (çekirdek, gömülü, platforma bağlı kod). Yalnız clang kullanıldı. Veri git dışında; `python3 aday_bul.py` ve `python3 olcekle.py hepsi` ile yeniden üretilir.

Eğitim/test ayrımı **proje bazındadır**: bir projenin hiçbir fonksiyonu iki tarafa birden düşmez. Test projeleri bilerek az bilinen (2-190 yıldız), çoğu 2024-2025'te başlamış projelerden seçildi; büyük modellerin bunları eğitimde görmüş olma ihtimali zlib'e göre çok düşük. Lisanslar: [veri/LISANSLAR.md](veri/LISANSLAR.md).

## Sonuçlar

### 1. Ezbere dayanıklı test: az bilinen 5 proje, 115 fonksiyon

Ortalama ad F1 (1.0 = tam doğru). "Öneksiz" sütununda projenin ortak ad öneki (`cyaml_`, `mu_`, `sajs_`) iki taraftan da atılır; model bu öneki assembly'den bilemez.

| Model | -O0 | -O2 | öneksiz F1 | Tam isabet |
|---|---|---|---|---|
| mimo-v2.6-pro (düşünmeli) | **0.20** | **0.17** | **0.21** | 3 / 115 |
| mimo-v2.6-pro | 0.18 | 0.16 | 0.20 | **4 / 115** |
| glm-5.3 (düşünmeli) | 0.16 | 0.11 | 0.15 | **4 / 115** |
| qwen3.8-flash-next (düşünmeli) | 0.16 | 0.08 | 0.13 | 3 / 115 |
| deepseek-v4.1-flash (düşünmeli) | 0.12 | 0.08 | 0.12 | 3 / 115 |
| deepseek-v4.1-flash | 0.10 | 0.11 | 0.12 | 2 / 115 |
| glm-5.3 | 0.12 | 0.08 | 0.12 | 2 / 115 |
| qwen3.8-flash-next | 0.13 | 0.07 | 0.11 | 1 / 115 |
| gemma-4-31b (düşünmeli) | 0.11 | 0.08 | 0.10 | 2 / 115 |
| gemma-4-31b | 0.11 | 0.07 | 0.10 | 0 / 115 |
| qwen2.5-coder-0.5b, eğitimsiz | 0.00 | 0.01 | 0.01 | 0 / 112 |
| qwen2.5-coder-0.5b + LoRA v1 | 0.02 | 0.00 | 0.01 | 0 / 112 |

Düşünmeli koşularda `max_tokens` tavanı 12.288. deepseek ve qwen bu tavanda bile isteklerin yarısından fazlasında, glm 115'in 50'sinde cevaba varamadan düşünmeye devam ediyor; bu satırlar 0 sayıldı.

### 2. Ezber: düşünmek ünlü kodda işe yarıyor, bilinmeyen kodda yaramıyor

Aynı veri hattı, aynı sayıda fonksiyon (115), mimo-v2.6-pro:

| | düşünmesiz | düşünmeli |
|---|---|---|
| zlib (çok ünlü) | 9 tam isabet, F1 0.18 | **28 tam isabet**, F1 0.29 |
| az bilinen projeler | 4 tam isabet, F1 0.20 | 3 tam isabet, F1 0.21 |

Düşünme, zlib'de tam isabeti üç katına çıkarıyor; az bilinen kodda hiçbir şey katmıyor. En olası açıklama: model düşünürken assembly'yi "anlamıyor", tanıdığı kaynak kodu hatırlıyor. Hazır modellerin bu işteki başarısını ünlü kütüphanelerle ölçmek yanıltıcı.

### 3. Modeller nerede çöküyor

![Fonksiyon türüne göre F1](grafik/test-hata.png)

- **Sarmalayıcılar: bütün modellerde 0.** Tek bir iç fonksiyonu çağıran kısa fonksiyonun adı, çağrılanı bilmeden bulunamıyor (çağrı bağlamıyla da düzelmedi, bkz. 4).
- **String'ler en güçlü ipucu.** String sabiti olan fonksiyonlarda F1 belirgin şekilde yüksek (mimo 0.27'ye karşı 0.15).
- **-O2 daha zor.** Hemen her modelde -O2 F1'i -O0'dan düşük.
- **Uzun fonksiyonlar kolay değil.** zlib'de en kolay grup uzun fonksiyonlar (mimo düşünmeli 0.58, [grafik](grafik/zlib-hata.png)); az bilinen kodda aynı grup 0.15. Yine ezberin izi.

### 4. Çağrı bağlamı

Fonksiyonun assembly'sine, çağırdığı iç fonksiyonlar hakkında bilgi eklendi (düşünmesiz, öneksiz F1):

- **özet**: çağrılanların importları, iç çağrıları ve string'leri
- **derin**: ayrıca kısa çağrılanların tam assembly'si ve iki seviye özet

| Model | bağlamsız | özet | derin | uzun fonksiyonlar (bağlamsız → derin) |
|---|---|---|---|---|
| mimo-v2.6-pro | 0.20 | 0.22 | **0.24** | 0.12 → 0.25 |
| deepseek-v4.1-flash | 0.12 | 0.17 | 0.17 | 0.10 → 0.18 |
| qwen3.8-flash-next | 0.11 | 0.15 | 0.16 | 0.06 → 0.18 |
| gemma-4-31b | 0.10 | 0.09 | 0.10 | 0.04 → 0.11 |
| glm-5.3 | 0.12 | 0.14 | 0.13 | 0.06 → 0.05 |

Bağlam en çok uzun ve iç fonksiyon çağıran fonksiyonlarda işe yarıyor (glm hariç: 115 isteğin 35'inde cevap kesildi, uzun girdi ona yaramıyor). Derin bağlam özetin üstüne az şey katıyor. **Sarmalayıcılar derin bağlamla da 0'da kalıyor** (test setinde yalnız 6 tane; çağrılanın tam assembly'si bile modeli doğru ada götürmüyor).

### 5. Küçük model, ilk LoRA denemesi (MacBook Air M4)

Qwen2.5-Coder-0.5B (4-bit), 1.500 adım (~1 saat 40 dk, 4,8 GB bellek). İki deneme de **işe yaramadı**:

| deneme | veri | F1 | tam isabet | ne oldu |
|---|---|---|---|---|
| eğitimsiz | — | 0.01 | 0 / 112 | çoğu cevap anlamsız |
| LoRA v1 | 14.710 fonksiyon, gerçek adlar | 0.01 | 0 / 112 | proje öneklerini ezberledi: 112 tahminin 54'ü `mbedtls_…` |
| LoRA v2 | 10.360 fonksiyon, önek atılmış, proje başına ≤1.500 | 0.02 | 0 / 112 | mod çöküşü: 112 tahminin 56'sı iki ad |

0.5B model ve yarım epoch bu iş için yetersiz görünüyor. Sıradaki denemeler: daha büyük taban (1.5B-3B), daha uzun eğitim, girdiye çağrı bağlamı.

### 6. Daha büyük küçük modeller: 1.5B ve 8B LoRA

Aynı sabit v4 test örneklemi (`lora/test_sabit_idler.txt`, az bilinen test projeleri) ve `eval_115` seti. Gerçek ad F1'i tahmini gerçek adla karşılaştırır; öneksiz F1 proje önekini iki taraftan atar. Ayrıntı: [rapor/MOLAB_IKI_F1.md](rapor/MOLAB_IKI_F1.md), [sonuc/SABIT500_LORA15_V3.md](sonuc/SABIT500_LORA15_V3.md).

| model | test | n | gerçek ad F1 (-O0 / -O2 / hepsi) | öneksiz F1 (hepsi) | tam isabet (gerçek / öneksiz) |
|---|---|---:|---|---:|---|
| mimo-v2.6-pro, çağrı bağlamlı (büyük, referans) | v4 test, sabit örneklem | 2.000 | 0.178 / 0.154 / 0.167 | 0.170 | 40 / 45 |
| deepseek-v4.1-flash, çağrı bağlamlı (büyük, referans) | v4 test, sabit örneklem | 2.000 | 0.161 / 0.130 / 0.154 | 0.156 | 40 / 45 |
| **Qwen3-8B + LoRA v5** (açıklama → ad, 95 bin satır, 1 epoch) | v4 test, sabit örneklem | 2.000 | 0.127 / 0.098 / **0.124** | 0.126 | 26 / 31 |
| **Qwen3-8B + LoRA v5** | `eval_115` | 115 | 0.188 / 0.120 / **0.155** | 0.173 | 1 / 2 |
| Qwen3-8B + LoRA v1 (yalnız ad, 41 bin satır × 2 epoch) | v4 test, sabit örneklem | 2.000 | 0.108 / 0.093 / 0.106 | 0.108 | 25 / 33 |
| Qwen3-8B + LoRA v1 | `eval_115` | 115 | 0.102 / 0.085 / 0.094 | 0.111 | 1 / 4 |
| Qwen2.5-Coder-1.5B + LoRA v3, çağrı bağlamlı (MLX, laptop) | sabit örneklemin ilk 500'ü | 500 | 0.044 | 0.045 | 0 |
| Qwen2.5-Coder-1.5B + LoRA v3, yalnız assembly | sabit örneklemin ilk 500'ü | 500 | 0.037 | 0.038 | 0 |

Aynı 500 satırda 8B 0.108, 1.5B 0.044 alıyor. 1.5B adaptörü yeni projelere genellemiyor ve ciddi mod çöküşü var (en sık tahmin satırların %13,6'sı). 8B, sıfırın belirgin üstüne çıkan ilk küçük model.

**v5 ve v1 (aynı taban model, aynı 2.000 test satırı).** v5 veriyi ve hedefi değiştiriyor: her kaynak fonksiyon en az bir kez giriyor (95.000 satır, 72.061 fonksiyon), proje öneki kuralı düzeltildi, model önce tek cümle İngilizce açıklama, sonra ad, sonra Türkçe açıklama yazıyor. Gerçek ad F1 0.106'dan 0.124'e çıktı (eşli fark +0.018, %95 bootstrap aralığı +0.009 … +0.026), `eval_115`'te 0.094'ten 0.155'e. Eğitimdeki bir adın birebir kopyası olan tahminler %42'den %30'a indi. String sabiti olmayan fonksiyonlar hâlâ zor (0.093, önce 0.079; string'lilerde 0.299). Model aynı satırlarda çağrı bağlamlı mimo-v2.6-pro'nun 0.044 altında (aralık -0.053 … -0.034). Checkpoint 300 doğrulama satırında seçildi (5.938 adımın 4.500.'sü; doğrulama ad F1 0.263), test kümeleri bir kez ölçüldü.

**Darboğaz açıklamanın doğruluğu.** Hakem model (mimo-v2.6-pro) modelin açıklamalarını 300 test satırında C kaynağıyla karşılaştırdı (`aciklama_puan_v5.py`): İngilizce açıklama %20,0 doğru, %15,3 kısmen doğru, %64,7 yanlış (Türkçe: %20,9 / %18,9 / %60,1). Açıklama doğruyken ad F1 0.306, yanlışken 0.054. Model fonksiyonu genellikle ne yaptığına inandığı şeyle tutarlı adlandırıyor; açık sorun fonksiyonu assembly'den anlamak.

Kırılım: [rapor/MOLAB_V5_KIRILIM.md](rapor/MOLAB_V5_KIRILIM.md); öğretmen etiket denetimi: [rapor/OGRETMEN_DENETIM.md](rapor/OGRETMEN_DENETIM.md).

### Not: zlib ısınma turu ve veri hattındaki sızıntılar

İlk zlib ölçümü (v1, 60 fonksiyon) daha basit bir veri hattıyla yapıldı ve o hat modele farkında olmadan ipucu sızdırıyordu: global değişken adları (`crc_table`, `configuration_table`), alfabetik `sub_` numaraları, `.o` ofsetleri. Bir tersine mühendislik modeliyle (Codex) yapılan denetimden sonra bu sızıntılar kapatıldı (v3). v1 sonuçları `sonuc/zlib-*.jsonl` altında duruyor ama yukarıdaki karşılaştırmalar v3 hatla yapıldı.

## Yol haritası

**1. Temel** ✅
- [x] Veri üretim hattı (-O0/-O2, sızıntısız v3)
- [x] Büyük modellerle taban ölçüm, ezbere dayanıklı test seti, hata analizi
- [x] 14 projeden 16.804 fonksiyon; açık yayın ([Hugging Face](https://huggingface.co/datasets/krxi123/asm-adlandirma), EVREN)

**2. Girdiyi zenginleştirmek**
- [x] Çağrı bağlamı (çağrılan fonksiyonların importları ve string'leri): büyük modellerde F1 belirgin arttı
- [x] Derin bağlam: kısa çağrılanların tam assembly'si, iki seviye özet: özetin üstüne küçük kazanç, sarmalayıcılar hâlâ 0
- [x] Gerçek link + strip ile veri hattı (`cikar_bin.py`, v4): zlib, lua, tomlc17'de denendi, [rapor](VERI_HATTI_V4.md)

**3. Küçük model**
- [x] İlk LoRA denemeleri (0.5B): işe yaramadı, önek ezberi ve mod çöküşü
- [x] 1.5B model, çağrı bağlamlı: gerçek ad F1 0.044, genellemiyor
- [x] Qwen3-8B + LoRA: gerçek ad F1 0.106 (v4 test), 0.094 (`eval_115`)
- [x] Qwen3-8B + LoRA v5 (açıklama + ad): gerçek ad F1 0.124 (v4 test), 0.155 (`eval_115`)
- [x] Damıtma verisi: kaynak kodu gören öğretmen model (mimo-v2.6-pro) 17.581 fonksiyonun hepsine tek cümlelik Türkçe açıklama yazdı (ort. 12,5 kelime)
- [x] Küçük model ad + açıklama birlikte üretsin (v5: İngilizce + Türkçe)

**4. Araç**
- [ ] Ghidra betiği: `FUN_…` fonksiyonlarını yerel modelle adlandırıp açıklama yazar (betik hazır: [ghidra/](ghidra/README.md); Ghidra 12 headless'ta uçtan uca çalıştı, kuru kip)

**5. Yayın**
- [ ] Modelin açık yayını ve karşılaştırma yazısı

## Kendiniz çalıştırın

Gereksinimler: `clang`, `objdump` (LLVM), Python 3.9+. Ölçüm için OpenAI uyumlu bir LLM uç noktası gerekiyor.

```bash
python3 cikar.py --projeler projeler.json             # projeleri indir, derle → veri/egitim, veri/test
python3 test_seti.py                                  # ölçüm seti → veri/test.jsonl
python3 taban.py veri/test.jsonl -n 1000 -m <model>   # ad tahmini + puan (sonuc/ altına); --dusunme, --devam
python3 ozet.py test                                  # sonuç tablosu
python3 analiz.py veri/test.jsonl -o grafik/test-hata.png   # fonksiyon türüne göre hata analizi
```

Her satır bir fonksiyon: `id`, `proje`, `surum`, `dosya`, `opt`, `ad` (doğru cevap), `komut_sayisi`, `sizinti`, `asm`, `baglam`, `baglam_derin`.

Gerçek binary hattı (v4): projeyi `-O0`/`-O2` dylib olarak linkler, `strip -x` uygular, fonksiyon sınırlarını stripped kopyadan alır.

```bash
python3 cikar_bin.py --projeler projeler.json zlib lua tomlc17   # → veri/bin/
python3 -m unittest test_cikar_bin
```

Damıtma (kaynak kodu gören öğretmen modelden tek cümlelik açıklama):

```bash
python3 kaynak_kod.py -j 6                       # fonksiyon → C gövdesi, veri/kaynak/
python3 aciklama.py -m <model> -j 6 --devam      # → veri/aciklama/
python3 aciklama_puan.py sonuc/<koşu>.jsonl -m <hakem>   # açıklamaları kaynağa göre 0-2 puanla
```

LoRA (Apple Silicon, mlx-lm):

```bash
python3.12 -m venv .venv && .venv/bin/pip install mlx-lm transformers matplotlib
.venv/bin/python lora/hazirla.py --onek-at --proje-tavan 1500   # → lora/veri
sh lora/egit.sh                                                 # ayarlar lora/ayar.yaml
.venv/bin/python lora/olc.py                                    # test setinde ölç → sonuc/
```

Ölçümler [EVREN](https://evren.ssyz.org.tr) yapay zekâ platformunun Türkiye'deki altyapısında yapıldı.

## Lisans

Kod MIT lisanslıdır. `veri/` altındaki assembly, derlenen projelerin kendi lisanslarına tabidir: [veri/LISANSLAR.md](veri/LISANSLAR.md).
