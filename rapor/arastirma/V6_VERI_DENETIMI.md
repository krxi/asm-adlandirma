# v6 yayımlanmış veri: bağımsız bütünlük denetimi

Girdi: [`asmsense-data` v6 release](https://github.com/krxi/asmsense-data/releases/tag/v6) `veri-v6.zip`,
SHA-256 `e1286104e59860a34fc18fe908ccadc3896b4db40fe1a5a75253aa9cc7a8c201` (GitHub asset digest'iyle aynı).
Araç: `veri_denetim_v6.py` (model çağrısı ve ağ erişimi yok, ~30 sn). Bu belge yeni model eğitimi,
çıkarımı veya checkpoint seçimi içermez; tahmin satırları repodaki arşiv dosyalarıdır.

```sh
unzip veri-v6.zip -d /tmp/veri-v6
python3 veri_denetim_v6.py --veri /tmp/veri-v6 -o /tmp/v6-denetim.json \
  --tahmin valid_300=sonuc/valid300-molab-qwen3-8b-v5.jsonl \
  --tahmin test_sabit=sonuc/test2000-molab-qwen3-8b-v5.jsonl \
  --tahmin eval115=sonuc/eval115-molab-qwen3-8b-v5.jsonl
```

## Özet

| Denetim | Sonuç |
|---|---|
| Bölüm ayrıklığı (proje, kimlik, `(proje, dosya, ad)`) | train/valid/test/eval115 arasında **0** kesişim; `test_sabit ⊂ test`, `valid_300 ⊂ valid` |
| Hedef ad girdide (string dışı tanımlayıcı) | test_sabit **0**, eval115 **0**, valid_300 1. train'de asm'de 74, bağlamda 13 satır; asm'dekilerin 59'u önek atılmış hedefin sarmalanan import'la aynı olduğu durum (`janet_asin` → `call asin`), kalanı hedefin bir komut adıyla çakışması (`push`, `cpuid`): stripped binary'de de görünen sinyal, hat sızıntısı değil |
| Normalize asm birebir train'de | test_sabit 0, valid_300 0, eval115 0 (asm tekilleştirmesi beyan edildiği gibi çalışıyor) |
| Normalize decompile birebir train'de | test_sabit 51 (%2,6), valid_300 11 (%3,7), eval115 5 (%4,3); çoğu 6-20 komutluk küçük işlev. train adını kopyalamanın F1'i 0,00-0,20 |
| **Gömülü (vendored) train projesi** | **test_sabit: snkv ⊃ sqlite, 217 / 2.000 satır (%10,85) train'deki SQLite işleviyle birebir aynı adlı.** Tüm test: 1.404 / 12.290 (%11,4). valid_300: 16 satır (%5,3; blurhash~darknet-ocr, contiki-ng~daplink, slurp~jattach). eval115: 0 |

`v4` hattı, train'de bulunan `(dosya, ad)` çiftlerini valid/test'ten çıkarır. snkv, SQLite'ı başka dosya
adlarıyla gömdüğü için bu filtre onu yakalamamış; normalize asm de eşleşmiyor (yalnız 37 test satırı
normalize decompile düzeyinde SQLite'la birebir). Tespit ölçütü: değerlendirme projesinin ≥ 8 karakterlik ayırt edici adlarının en az %20'si
tek bir train projesinde de var (snkv: 440 / 1.038 = %42,4).

## Etki (tanısal; model seçimi için kullanılmadı)

Arşivlenmiş test2000 tahminleri `taban.f1` ile yeniden puanlandı:

| Koşu | hepsi (2.000) | snkv ∩ sqlite adı (217) | snkv diğer (292) | snkv dışı (1.491) |
|---|---:|---:|---:|---:|
| Qwen3-8B + LoRA v5 | 0,124 | 0,104 | 0,093 | 0,132 |
| Qwen3-8B + LoRA v1 | 0,106 | 0,108 | 0,082 | 0,110 |
| mimo-v2.6-pro + bağlam | 0,167 | 0,102 | 0,098 | 0,190 |
| deepseek-v4.1-flash + bağlam | 0,154 | 0,095 | 0,101 | 0,173 |
| mimo + bağlam + decompile | 0,192 | 0,145 | 0,113 | 0,214 |
| mimo yalnız decompile | 0,173 | 0,133 | 0,100 | 0,194 |

1. **Gömülü kopya test puanlarını şişirmiyor**: bütün modeller snkv satırlarında daha düşük. Küçük
   model SQLite adlarını eğitimden kopyalayarak avantaj kazanmamış.
2. **Küçük–büyük model farkını küçük gösteriyor**: v5 − (mimo + bağlam) eşli farkı, proje-kümeli
   bootstrap (2.000 tekrar, tohum 42, `aciklama_degerlendir.bootstrap_farki`) ile
   hepsi −0,044 [−0,076; −0,021], snkv hariç −0,058 [−0,082; −0,033].
3. **Validation'da ters yön**: valid_300'deki 16 gömülü-ad satırında v5 F1 0,444, kalan 284 satırda
   0,241; ortalama 0,252 → 0,241. Checkpoint seçimi küçük bir ezber ödülü taşıyor olabilir (~+0,011).

## Öneriler (bu PR uygulamaz)

- Yayın/makale metninde "proje ayrık" iddiasına snkv⊃sqlite istisnasını ve yukarıdaki etkiyi ekle;
  başlık sonucunu snkv dışı alt kümeyle birlikte raporla.
- Sonraki veri sürümünde gömülü kopya filtresini ad örtüşmesi + normalize decompile ile genişlet;
  snkv'nin SQLite işlevlerini (veya projeyi) testten çıkar. Mevcut test2000 kimlikleri bu belgede
  değiştirilmez.
- valid_300'ü gömülü-ad satırları hariç yeniden örnekle veya seçimde bu satırları ayrı raporla.

## Sınırlar

Ad örtüşmesi eşiği (≥ 8 karakter, ≥ %20) sezgiseldir; kısa adlarla gömülen kütüphaneleri ve yeniden
adlandırılmış kopyaları kaçırır. Normalize decompile eşleşmesi birebir hash'tir, bulanık benzerlik
değildir. Ön eğitim bulaşması bu denetimin kapsamı dışındadır.
