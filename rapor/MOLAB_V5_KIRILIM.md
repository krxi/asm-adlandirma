# Kırılım: test2000-molab-qwen3-8b-v5.jsonl

`python3 analiz_molab.py sonuc/test2000-molab-qwen3-8b-v5.jsonl` çıktısı. n=2000, ortalama ad F1 **0.124**, tam isabet (F1=1) 26.

- Benzersiz tahmin: 1611 / 2000 (%81)
- Tahmin eğitimdeki bir adın birebir kopyası: 594 (%30); bunlarda F1 0.141, diğerlerinde 0.116
- Gerçek ad eğitimde de geçiyor (vendored/ortak ad): 270 satır
- En sık 10 tahmin: `XXH3_128bits_withSecret` ×10, `crypto_auth_hmacsha256` ×9, `utf8_decode` ×9, `random_init` ×8, `json_parse` ×7, `hash_init` ×7, `sqlite3_finalize` ×7, `vector_size` ×6, `XXH3_128bits` ×6, `string_length` ×6

### String sabiti

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| var | 299 | 0.299 | 44% | 18 |
| yok | 1701 | 0.093 | 77% | 8 |

### Komut sayısı

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| <20 | 344 | 0.096 | 75% | 3 |
| 20-59 | 720 | 0.131 | 69% | 7 |
| 60-199 | 785 | 0.133 | 72% | 13 |
| 200+ | 151 | 0.104 | 78% | 3 |

### Opt

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| -O0 | 729 | 0.127 | 73% | 14 |
| -O1 | 470 | 0.133 | 69% | 8 |
| -O2 | 210 | 0.098 | 77% | 1 |
| -O3 | 91 | 0.114 | 71% | 0 |
| -Os | 500 | 0.123 | 71% | 3 |

### Çağrı bağlamı

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| var | 1171 | 0.128 | 72% | 17 |
| yok | 829 | 0.117 | 73% | 9 |

### Export

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| evet | 1023 | 0.145 | 67% | 21 |
| hayır | 977 | 0.101 | 77% | 5 |

### Tahmin eğitim adı kopyası

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| evet | 594 | 0.141 | 71% | 9 |
| hayır | 1406 | 0.116 | 72% | 17 |

### Proje

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| snkv | 509 | 0.098 | 75% | 3 |
| eth.zig | 173 | 0.053 | 89% | 1 |
| qaws | 169 | 0.020 | 94% | 0 |
| toks | 153 | 0.063 | 86% | 0 |
| cex | 147 | 0.230 | 46% | 0 |
| cyaml | 132 | 0.132 | 68% | 0 |
| cq | 107 | 0.320 | 44% | 10 |
| adam | 98 | 0.218 | 49% | 2 |
| libhiae | 81 | 0.158 | 73% | 4 |
| fmag | 61 | 0.112 | 74% | 0 |
| onedraw | 59 | 0.184 | 61% | 3 |
| glm-5.2-in-c | 49 | 0.101 | 76% | 0 |
| opendis | 42 | 0.164 | 64% | 1 |
| fcvvdp | 41 | 0.026 | 90% | 0 |
| mu_json_x | 36 | 0.133 | 58% | 0 |
| tomlc17 | 26 | 0.158 | 65% | 0 |
| carquet | 21 | 0.081 | 76% | 0 |
| sajs | 19 | 0.080 | 79% | 0 |
| nanocolor | 15 | 0.051 | 80% | 0 |
| wlipsync | 15 | 0.111 | 80% | 0 |
| gallant | 12 | 0.200 | 75% | 2 |
| microcheck | 11 | 0.255 | 36% | 0 |
| photoc | 10 | 0.209 | 60% | 0 |
| zerocast | 6 | 0.267 | 50% | 0 |
| picomatch | 5 | 0.240 | 40% | 0 |
| cryptography-research-demo | 3 | 0.167 | 67% | 0 |

