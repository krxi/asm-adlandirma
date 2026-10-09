# Yerel MLX ölçümü: 1.5B v3 LoRA, sabit testin ilk 500 satırı

`lora/olc.py`, model `mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit` + `lora/adaptor-15b-v3` (bağlamlı, yalnız ad hedefiyle eğitilmişti), greedy, 48 token. Test: `lora/test_sabit_idler.txt` ilk 500 id (molab test2000 ile aynı sıra). Hedef ham gerçek ad. Mac'te ~17 dk/koşu, ücretsiz.

| girdi | n | gerçek ad F1 | öneksiz F1 (ozet) | tam isabet |
|---|---:|---:|---:|---:|
| asm + bağlam (`--baglam ozet`) | 500 | 0.044 | 0.045 | 0 |
| yalnız asm (`--baglam yok`) | 500 | 0.037 | 0.038 | 0 |

Bağlamı olan 286 satırda: bağlamlı 0.067, bağlamsız 0.055; eşli fark +0.012 (bootstrap %95: -0.003 … +0.028).
Bağlamı olmayan 214 satırda iki girdi aynı: 0.014 / 0.014.

Yorum: bağlam yönünde küçük bir artış var ama güven aralığı sıfırı içeriyor, yani bu örneklemde anlamlı değil; mutlak düzey de çok düşük. Ciddi mod çöküşü var: en sık tahmin `v06_decompress` (%13,6), `crypto_pwhash_argon2id_…` tekrar döngüsü (%9,4); benzersiz tahmin oranı %35. 1.5B v3 adaptörü yeni test projelerine genellemiyor; molab Qwen3-8B tüm 2.000 satırda 0.106 almıştı (aynı 500 satırda karşılaştırma molab sonuç dosyası gelince yapılabilir). İki F1 tanımı burada neredeyse aynı çünkü 500 satırın az bir kısmı ozet önekli projelerden.
