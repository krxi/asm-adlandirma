# Kırılım: eval115-molab-qwen3-8b.jsonl

`python3 analiz_molab.py sonuc/eval115-molab-qwen3-8b.jsonl` çıktısı. n=115, ortalama ad F1 **0.094**, tam isabet (F1=1) 1.

- Benzersiz tahmin: 103 / 115 (%90)
- Tahmin eğitimdeki bir adın birebir kopyası: 56 (%49); bunlarda F1 0.127, diğerlerinde 0.061
- Gerçek ad eğitimde de geçiyor (vendored/ortak ad): 4 satır
- En sık 10 tahmin: `rtmp_event_ping` ×4, `json_object_iter` ×2, `atoi` ×2, `string_rfind` ×2, `hash_iter` ×2, `json_init` ×2, `emit_byte` ×2, `cmp_write_bin` ×2, `vm_call` ×2, `read_file` ×2

### String sabiti

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| var | 23 | 0.141 | 70% | 0 |
| yok | 92 | 0.082 | 80% | 1 |

### Komut sayısı

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| <20 | 23 | 0.152 | 70% | 1 |
| 20-59 | 49 | 0.091 | 76% | 0 |
| 60-199 | 37 | 0.076 | 84% | 0 |
| 200+ | 6 | 0.000 | 100% | 0 |

### Opt

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| -O0 | 60 | 0.102 | 78% | 1 |
| -O2 | 55 | 0.085 | 78% | 0 |

### Çağrı bağlamı

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| var | 59 | 0.066 | 81% | 0 |
| yok | 56 | 0.123 | 75% | 1 |

### Export

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| hayır | 115 | 0.094 | 78% | 1 |

### Tahmin eğitim adı kopyası

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| evet | 56 | 0.127 | 73% | 1 |
| hayır | 59 | 0.061 | 83% | 0 |

### Proje

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| cyaml | 24 | 0.080 | 79% | 0 |
| mu_json_x | 24 | 0.084 | 75% | 0 |
| sajs | 24 | 0.081 | 88% | 1 |
| tomlc17 | 24 | 0.103 | 75% | 0 |
| picomatch | 19 | 0.126 | 74% | 0 |

