# asm-adlandirma

Sembolleri silinmiş x86-64 fonksiyonuna anlamlı ad + açıklama veren model.
Platform: Evren (SSB) — LLM çıkarımı ve H200 eğitim.

## Plan

**Amaç:** "Benim verimle eğitilen küçük model, büyük hazır modellere yaklaştı ve
laptopta çalışıyor." Tavan (büyük Evren modelleri) · taban (küçük model, eğitimsiz)
· senin modelin (aynı küçük model + LoRA) aynı test setinde karşılaştırılır.

1. **Taban ölçüm** — zlib, 60 fonksiyon, 5 model × düşünmeli/düşünmesiz. *(çalışıyor)*
2. **Hata analizi** — hazır modeller nerede çöküyor: -O2, kısa fonksiyon, string'siz kod,
   sarmalayıcılar (`adler32` → "wrapper"). Fikir: çağrılan fonksiyonun bağlamını eklemek.
3. **Veri büyütme** — libpng, sqlite, lua, mbedtls… → binlerce çift; eğitim/test ayrımı
   *kütüphane bazında* (aynı kütüphane iki tarafa düşmesin, ezber ölçülmesin).
4. **Eğitim** — küçük açık model (Qwen/Gemma küçük sürüm), Evren H200'de LoRA.
5. **Paylaşım** — veri seti + sonuç tablosu + kısa yazı (Evren, GitHub, HF).

## Komutlar

```bash
python3 cikar.py kaynak/zlib -o veri/zlib.jsonl   # derle (-O0/-O2), fonksiyon→asm çiftleri
./kos.sh                                          # 5 model × 2 kip paralel (nohup ile)
python3 ozet.py                                   # tablo; sonuc/BITTI varsa hepsi bitti
python3 taban.py veri/zlib.jsonl -n 60 -m glm-5.3 [--dusunme]
```

- İç fonksiyon adları `sub_NNNN` ile gizlenir, dış çağrılar (memcpy…) görünür kalır.
- Skor: kelime örtüşmesi F1 (`crc32_update` ~ `update_crc`). Ayrıntı `sonuc/` altında.

## Evren sınırları ve dersler

- **Günlük kota: 15M token**, her gece 03:00 sıfırlanır (2026-10-08 ölçümü).
  Taban turu ≈ 2M token tahmini.
- Düşünme açıkken modeller 16K token'lık döngüye girip tek istekte 3,5 dk
  bekletebiliyor (`reasoning_effort: low` dahil). Varsayılan düşünme kapalı
  (`chat_template_kwargs.enable_thinking=false`, ~1-3 sn); açıkken tavan 4096.
- `glm-5.3` düşünme kapalıyken bile yavaş (~25 sn) ve JSON'dan önce gerekçe yazıyor.
