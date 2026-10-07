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

## İlk taban sonuçları (2026-10-08, düşünmesiz, n=60, F1)

| model | -O0 | -O2 | tam isabet |
|---|---|---|---|
| mimo-v2.6-pro | 0.17 | 0.31 | 6 |
| deepseek-v4.1-flash | 0.10 | 0.13 | 0 |
| qwen3.8-flash-next | 0.06 | 0.17 | 0 |
| gemma-4-31b | 0.05 | 0.04 | 0 |

- 4-8 istek **HTTP 503** ile düştü (10 koşu × 6 eşzamanlı = 60 istek fazla). Sonraki turda
  toplam eşzamanlılığı ~16'da tut, yalnız `HATA` satırlarını yeniden sor.
- **Ezber riski:** zlib çok ünlü; mimo'nun `lm_init`, `longest_match` tam isabetleri
  kaynak kodu eğitimde görmüş olmasından olabilir. Gerçek test seti az bilinen veya
  bizim yazdığımız kodla kurulmalı; zlib yalnız ısınma.

## Evren platform API'si (2026-10-08 inceleme, giriş yapılmadan)

- İki ayrı anahtar var: LLM geçidi `evren_llm_...` (elimizde) ve platform API'si
  `evren_...` (**API Anahtarları** sayfasından Emin oluşturur). Başlık: `X-API-Key`.
- Platformun resmî örnekleri: model listeleme, sürümler, `/inference/predict`.
- Arayüz kodunda veri seti yükleme akışı var: `POST /datasets/{id}/upload/presign`
  (`files: [{filename, sha256_hash, file_size, client_uid}]`) → presigned URL'lere PUT →
  `POST /datasets/{id}/upload/confirm`. Kabul edilen uzantılar arasında `.jsonl/.json/.txt`
  da var. **Platform anahtarıyla çağrılabildiği doğrulanmadı.**
- Eğitim arayüzü görüntü odaklı (YOLO/DETR, `lr0`, `image_size`). LLM LoRA yalnız tanıtım
  tablosunda geçiyor ("LLaMA-3 8B LoRA ~100k örnek, 8 GPU ~39 dk"); arayüzden LLM eğitimi
  açılıyor mu doğrulanmadı.
- **Koşullar 4.9:** yüklenen veri, model ve çıktılar platform tarafından geliştirme ve
  araştırma için kullanılabilir. Açık kaynak türevi veri için sorun değil; özel veri yükleme.

## Evren platform API — anahtarla doğrulandı (2026-10-08, yalnız GET)

- Taban adres `https://api.ssyz.org.tr/api/v1`, başlık `X-API-Key`. `~/Desktop/evren.env`:
  `EVREN_PLT_API_KEY` (platform, **tam hesap yetkisi** — billing/transfer dahil, dikkat),
  `EVREN_MD_API_KEY` (yalnız model/çıkarım uçları; diğerlerinde 403).
- Çalışan okuma uçları: `/auth/me`, `/datasets`, `/models`, `/projects`, `/api-keys`,
  `/billing/balance` (1010 CR), `/billing/earning/overview`, `/me/stats`, `/llm/quota`
  (5 dk pencerede 2.5M token), `/training/jobs`, `/training/queue-status` (16 GPU),
  `/training/recipes`.
- Veri seti modaliteleri: VISION, TEXT, NLP, AUDIO, MULTIMODAL → metin (jsonl) veri seti açılabilir.
- **Eğitim tarifleri yalnız görüntü** (Hızlı/Standart/Kaliteli/Yüksek Çözünürlük, YOLO/DETR).
  API'de LLM/LoRA eğitimi görünmüyor; "LLM / NLP" yol haritasında yalnız çıkarım olarak geçiyor.
  → LoRA eğitimi şimdilik yerelde (Mac'te mlx-lm ile 0.5-1.5B model) ya da Evren ekibine sorarak.
- Kredi kuralları (seçme): 1000 veri +15, 10k veri +40 (günde 1), veri seti yayınlama +5,
  model yayınlama +10, günlük giriş +10.
- Hesapta zaten "Assembly yorumlayıcı" adlı **public** proje var (Emin açtı), henüz boş.
