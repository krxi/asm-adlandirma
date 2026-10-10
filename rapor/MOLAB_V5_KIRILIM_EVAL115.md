# Kırılım: eval115-molab-qwen3-8b-v5.jsonl

`python3 analiz_molab.py sonuc/eval115-molab-qwen3-8b-v5.jsonl` çıktısı. n=115, ortalama ad F1 **0.155**, tam isabet (F1=1) 1.

- Benzersiz tahmin: 106 / 115 (%92)
- Tahmin eğitimdeki bir adın birebir kopyası: 43 (%37); bunlarda F1 0.166, diğerlerinde 0.149
- Gerçek ad eğitimde de geçiyor (vendored/ortak ad): 4 satır
- En sık 10 tahmin: `json_dump` ×2, `json_parse` ×2, `parse_int` ×2, `bfind` ×2, `parse_digits` ×2, `mz_stream_tell` ×2, `hash_init` ×2, `trex` ×2, `file_read` ×2, `emitter_emit_scalar` ×1

### String sabiti

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| var | 23 | 0.249 | 43% | 0 |
| yok | 92 | 0.132 | 70% | 1 |

### Komut sayısı

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| <20 | 23 | 0.140 | 70% | 1 |
| 20-59 | 49 | 0.121 | 69% | 0 |
| 60-199 | 37 | 0.209 | 54% | 0 |
| 200+ | 6 | 0.167 | 67% | 0 |

### Opt

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| -O0 | 60 | 0.188 | 58% | 1 |
| -O2 | 55 | 0.120 | 71% | 0 |

### Çağrı bağlamı

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| var | 59 | 0.174 | 59% | 0 |
| yok | 56 | 0.136 | 70% | 1 |

### Export

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| hayır | 115 | 0.155 | 64% | 1 |

### Tahmin eğitim adı kopyası

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| evet | 43 | 0.166 | 63% | 1 |
| hayır | 72 | 0.149 | 65% | 0 |

### Proje

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| cyaml | 24 | 0.313 | 29% | 0 |
| mu_json_x | 24 | 0.136 | 67% | 0 |
| sajs | 24 | 0.070 | 88% | 1 |
| tomlc17 | 24 | 0.117 | 71% | 0 |
| picomatch | 19 | 0.139 | 68% | 0 |

