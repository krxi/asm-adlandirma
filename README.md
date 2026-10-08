# asm-adlandirma

**Sembolleri silinmiş bir binary'deki fonksiyona bakıp ona anlamlı bir ad ve kısa bir açıklama veren küçük bir dil modeli.**

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

- **Sarmalayıcılar: bütün modellerde 0.** Tek bir iç fonksiyonu çağıran kısa fonksiyonun adı, çağrılanı bilmeden bulunamıyor. Çağrı bağlamı eklemek bir sonraki deney.
- **String'ler en güçlü ipucu.** String sabiti olan fonksiyonlarda F1 belirgin şekilde yüksek (mimo 0.27'ye karşı 0.15).
- **-O2 daha zor.** Hemen her modelde -O2 F1'i -O0'dan düşük.
- **Uzun fonksiyonlar kolay değil.** zlib'de en kolay grup uzun fonksiyonlar (mimo düşünmeli 0.58, [grafik](grafik/zlib-hata.png)); az bilinen kodda aynı grup 0.15. Yine ezberin izi.

### 4. Küçük model, ilk LoRA denemesi (MacBook Air M4)

Qwen2.5-Coder-0.5B (4-bit), 1.500 adım (~1 saat 40 dk, 4,8 GB bellek). İki deneme de **işe yaramadı**:

| deneme | veri | F1 | tam isabet | ne oldu |
|---|---|---|---|---|
| eğitimsiz | — | 0.01 | 0 / 112 | çoğu cevap anlamsız |
| LoRA v1 | 14.710 fonksiyon, gerçek adlar | 0.01 | 0 / 112 | proje öneklerini ezberledi: 112 tahminin 54'ü `mbedtls_…` |
| LoRA v2 | 10.360 fonksiyon, önek atılmış, proje başına ≤1.500 | 0.02 | 0 / 112 | mod çöküşü: 112 tahminin 56'sı iki ad |

0.5B model ve yarım epoch bu iş için yetersiz görünüyor. Sıradaki denemeler: daha büyük taban (1.5B-3B), daha uzun eğitim, girdiye çağrı bağlamı.

### Not: zlib ısınma turu ve veri hattındaki sızıntılar

İlk zlib ölçümü (v1, 60 fonksiyon) daha basit bir veri hattıyla yapıldı ve o hat modele farkında olmadan ipucu sızdırıyordu: global değişken adları (`crc_table`, `configuration_table`), alfabetik `sub_` numaraları, `.o` ofsetleri. Bir tersine mühendislik modeliyle (Codex) yapılan denetimden sonra bu sızıntılar kapatıldı (v3). v1 sonuçları `sonuc/zlib-*.jsonl` altında duruyor ama yukarıdaki karşılaştırmalar v3 hatla yapıldı.

## Yol haritası

- [x] Veri üretim hattı (zlib, -O0/-O2)
- [x] Büyük modellerle taban ölçüm
- [x] Az bilinen projelerden ezbere dayanıklı test seti
- [x] Hata analizi: hangi fonksiyon türlerinde modeller çöküyor
- [x] Veri büyütme: 14 projeden 16.804 fonksiyon, eğitim/test ayrımı proje bazında
- [ ] Gerçek link + strip ile veri hattı (şu an `.o` dosyalarından)
- [ ] Çağrı bağlamı: çağrılan ve çağıran fonksiyonların bilgisini girdiye eklemek
- [ ] Küçük modele LoRA eğitimi ve karşılaştırma (ilk deneme yapıldı, işe yaramadı)
- [x] Veri setinin açık yayını ([Hugging Face](https://huggingface.co/datasets/krxi123/asm-adlandirma))
- [ ] Modelin açık yayını

## Kendiniz çalıştırın

Gereksinimler: `clang`, `objdump` (LLVM), Python 3.9+. Ölçüm için OpenAI uyumlu bir LLM uç noktası gerekiyor.

```bash
python3 cikar.py --projeler projeler.json             # projeleri indir, derle → veri/egitim, veri/test
python3 test_seti.py                                  # ölçüm seti → veri/test.jsonl
python3 taban.py veri/test.jsonl -n 1000 -m <model>   # ad tahmini + puan (sonuc/ altına); --dusunme, --devam
python3 ozet.py test                                  # sonuç tablosu
python3 analiz.py veri/test.jsonl -o grafik/test-hata.png   # fonksiyon türüne göre hata analizi
```

Her satır bir fonksiyon: `id`, `proje`, `surum`, `dosya`, `opt`, `ad` (doğru cevap), `komut_sayisi`, `sizinti`, `asm`.

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
