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

Eğitim/test ayrımı **proje bazındadır**: bir projenin hiçbir fonksiyonu iki tarafa birden düşmez. Test projeleri bilerek az bilinen (2-190 yıldız), çoğu 2024-2025'te başlamış projelerden seçildi; büyük modellerin bunları eğitimde görmüş olma ihtimali zlib'e göre çok düşük. Lisanslar: [veri/LISANSLAR.md](veri/LISANSLAR.md).

## İlk sonuçlar

zlib'den rastgele seçilen 60 fonksiyon, ortalama F1 (1.0 = tam doğru):

| Model | -O0 | -O2 | Tam isabet |
|---|---|---|---|
| mimo-v2.6-pro (düşünmeli) | **0.39** | 0.28 | **16 / 60** |
| mimo-v2.6-pro | 0.17 | **0.31** | 6 / 60 |
| deepseek-v4.1-flash (düşünmeli) | 0.16 | 0.12 | 7 / 60 |
| deepseek-v4.1-flash | 0.10 | 0.13 | 0 / 60 |
| qwen3.8-flash-next | 0.06 | 0.17 | 0 / 60 |
| gemma-4-31b (düşünmeli) | 0.05 | 0.09 | 0 / 60 |
| gemma-4-31b | 0.05 | 0.04 | 0 / 60 |

İlk gözlemler:

- **Hazır modeller bu işte zayıf.** En iyi model bile fonksiyonların dörtte birinden azını tam doğru adlandırıyor.
- **Düşünmek işe yarıyor ama pahalı.** MiMo'da düşünme açılınca tam isabet 6'dan 16'ya çıkıyor; harcanan token yaklaşık 3 katına çıkıyor.
- **Sarmalayıcılar zor.** `-O0`'da `adler32` sadece `adler32_z`'yi çağıran bir sarmalayıcı. Modeller çoğunlukla "wrapper" diyor. Çağrılan fonksiyonun bağlamı olmadan doğru adı bulmak imkânsıza yakın.
- **Ezber riski.** zlib çok yaygın bir kütüphane. Bazı tam isabetler, modelin kaynak kodu eğitimde görmüş olmasından gelebilir. Bu yüzden zlib yalnız bir ısınma turu. Asıl test seti az bilinen projelerden kurulacak.

## Yol haritası

- [x] Veri üretim hattı (zlib, -O0/-O2)
- [x] Büyük modellerle taban ölçüm
- [ ] Az bilinen projelerden ezbere dayanıklı test seti
- [ ] Hata analizi: hangi fonksiyon türlerinde modeller çöküyor
- [ ] Veri büyütme: binlerce fonksiyon (libpng, sqlite, lua, mbedtls…). Eğitim/test ayrımı proje bazında yapılacak.
- [ ] Çağrı bağlamı: çağrılan ve çağıran fonksiyonların bilgisini girdiye eklemek
- [ ] Küçük modele LoRA eğitimi ve karşılaştırma
- [ ] Veri seti ve modelin açık yayını

## Kendiniz çalıştırın

Gereksinimler: `clang`, `objdump` (LLVM), Python 3.9+. Ölçüm için OpenAI uyumlu bir LLM uç noktası gerekiyor.

```bash
git clone https://github.com/madler/zlib kaynak/zlib
python3 cikar.py kaynak/zlib -o veri/zlib.jsonl      # fonksiyon → assembly çiftleri
python3 taban.py veri/zlib.jsonl -n 60 -m <model>    # ad tahmini + puan (sonuc/ altına)
python3 ozet.py                                      # sonuç tablosu
```

`veri/zlib.jsonl` her satırda bir fonksiyon içerir: `id`, `dosya`, `opt`, `ad` (doğru cevap), `komut_sayisi`, `asm`.

Ölçümler [EVREN](https://evren.ssyz.org.tr) yapay zekâ platformunun Türkiye'deki altyapısında yapıldı.

## Lisans

Kod MIT lisanslıdır. `veri/` altındaki assembly, derlenen projelerin kendi lisanslarına tabidir (zlib: zlib License).
