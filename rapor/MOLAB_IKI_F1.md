# molab Qwen3-8B LoRA: iki F1 tanımı

Kaynak: `~/Downloads/sonuc-molab.zip` (sonuc-test-Qwen3-8B-lora.jsonl, sonuc-eval115-Qwen3-8B-lora.jsonl), `iki_f1.py` ile yeniden puanlandı.
Test dosyasındaki 2.000 id, `lora/test_sabit_idler.txt` ile aynı küme ve aynı sırada: sabit test kümesi molab'la birebir doğrulandı.
molab test hedefi ham gerçek addı; dosyadaki `f1` gerçek ad F1'iyle her satırda aynı. Bu iki dosyada önek hatası puanı bozmamış; önek düzeltmesi eğitim hedeflerini ilgilendiriyor.

| koşu | n | gerçek ad F1 (-O0 / -O2 / hepsi) | öneksiz F1 (-O0 / -O2 / hepsi) | tam isabet gerçek / öneksiz |
|---|---:|---|---|---|
| test (sabit 2000) | 2000 | 0.108 / 0.093 / 0.106 | 0.110 / 0.095 / 0.108 | 25 / 33 |
| eval115 | 115 | 0.102 / 0.085 / 0.094 | 0.118 / 0.103 / 0.111 | 1 / 4 |

Aynı 500 satırda (sabit testin ilki): molab Qwen3-8B 0.108, yerel 1.5B v3 LoRA bağlamlı 0.044 (`sonuc/SABIT500_LORA15_V3.md`).
