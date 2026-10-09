# README düzeltme taslağı: hangi sayı hangi F1 tanımıyla

README.md ve README.tr.md değiştirilmedi. Bu dosya önerilen değişiklikleri listeler. Sayılar
`python3 iki_f1.py` çıktısından ([F1_IKI_TANIM.md](F1_IKI_TANIM.md)) alındı ve README'deki
yuvarlanmış değerlerle karşılaştırıldı.

İki tanım:

- **gerçek ad F1**: `taban.f1(tahmin, gerçek ad)`.
- **öneksiz F1**: `ozet.f1_oneksiz`. Projenin ortak öneki (cyaml, mu, sajs, toml, pm) iki taraftan atılır.

## Denetim sonucu

| README bölümü | Sütun | Tanım (doğrulandı) | Durum |
|---|---|---|---|
| 1. Memorization-resistant test | -O0, -O2 | gerçek ad | etiket yok |
| 1. | Prefix-stripped F1 | öneksiz | doğru etiketli |
| 1. | Exact matches | gerçek ad (mimo: 4; öneksiz tanımla 7) | etiket yok |
| 2. Memorization, "little-known projects" satırı | F1 | **öneksiz** (mimo 0.195 → 0.20; gerçek ad 0.173) | etiket yok, zlib satırıyla karışık |
| 2. | exact matches | **gerçek ad** (4 ve 3; öneksiz 7 ve 6) | aynı hücrede F1 öneksiz, isabet gerçek |
| 2. zlib satırı | F1, exact | ikisi aynı (zlib'de önek yok) | sorun yok |
| 3. Where models fail, grafik ve 0.27/0.15 | F1 | gerçek ad (`analiz.py` dosyadaki `f1` alanını kullanıyor) | etiket yok |
| 4. Call context | bütün sütunlar | öneksiz | doğru etiketli |
| 5. Small model, F1 sütunu | F1 | **öneksiz**: untrained 0.006 → 0.01 (gerçek ad 0.004 → 0.00) | etiket yok; tablo 1'deki aynı koşuyla farklı görünüyor |

Tablo 1 ile tablo 5 aynı koşuyu farklı tanımla veriyor: tablo 1'de untrained `0.00 / 0.01 / 0.01`,
tablo 5'te `0.01`. Okuyucu bunu çelişki sanabilir.

## Önerilen değişiklikler (README.md; README.tr.md'de aynısı)

1. "## Results" başlığının hemen altına iki tanımı tek paragrafta koy:

   > Two scores are reported. **Name F1** compares the prediction with the real function name.
   > **Prefix-stripped F1** first removes the project's common name prefix (`cyaml_`, `mu_`, `sajs_`, `toml_`, `pm_`)
   > from both sides, because the model cannot infer it from assembly. Exact matches are counted on the real name.
   > Both scores for every run: [rapor/F1_IKI_TANIM.md](rapor/F1_IKI_TANIM.md).

2. Tablo 1 başlıkları: `-O0` → `Name F1 -O0`, `-O2` → `Name F1 -O2`, `Exact matches` → `Exact matches (real name)`.

3. Tablo 2: hücre biçimini tanımı söyleyecek şekilde değiştir, ör.
   `4 exact matches, F1 0.20` → `4 exact, name F1 0.17, prefix-stripped F1 0.20`
   (little-known, düşünmesiz) ve `3 exact, name F1 0.19, prefix-stripped F1 0.21` (düşünmeli).
   zlib satırı olduğu gibi kalabilir; altına "zlib has no project prefix, so both scores are equal" notu.

4. Bölüm 3 grafik açıklaması: "F1 by function type" → "Name F1 by function type".

5. Tablo 5: `F1` → `Prefix-stripped F1`, ya da tablo 1 ile aynı olsun diye iki sütun: untrained `0.00 / 0.01`,
   LoRA v1 `0.01 / 0.01`, LoRA v2 `0.02 / 0.02` (name / prefix-stripped).

6. Yeni LoRA sonuçları (Qwen3-8B, eval115 0.094, test2000 0.106) README'ye girerken:
   bu koşular `lora/hazirla_olcek.py` varsayılanıyla hazırlandıysa test hedefi **üçüncü bir tanımla**
   öneksizdir: `hazirla_olcek.onekler` proje adından bağımsız en sık `xxx_` başını atar ve test projelerinde
   sajs için `eat_`, picomatch için `emit_` fiillerini siler (`ozet.py` bunları önek saymaz).
   O koşunun sonuç JSONL'i şu komutla iki tanıma çevrilmeli, README'ye bu iki sayı girmeli:

   ```bash
   python3 iki_f1.py <sonuç.jsonl> -o rapor/F1_qwen3-8b.md
   ```

   `iki_f1.py`, `gercek` alanı veri/'deki adla eşleşmeyen satırları "hedef öneksiz" diye sayar ve gerçek adla
   yeniden puanlar. Bunun için veri/ altında o koşunun id'lerini içeren test dosyası olmalı
   (v4 için `veri/bin/olcek/test.jsonl`).
   Sonraki koşularda `hazirla_olcek.py --test-ham-ad` (ve tercihen `--onek-kurali proje`) test hedefini
   büyük modellerle aynı tanıma getirir.
