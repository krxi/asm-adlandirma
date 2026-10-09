# Kırılım: test2000-molab-qwen3-8b.jsonl

`python3 analiz_molab.py sonuc/test2000-molab-qwen3-8b.jsonl` çıktısı. n=2000, ortalama ad F1 **0.106**, tam isabet (F1=1) 25.

- Benzersiz tahmin: 1536 / 2000 (%77)
- Tahmin eğitimdeki bir adın birebir kopyası: 836 (%42); bunlarda F1 0.089, diğerlerinde 0.118
- Gerçek ad eğitimde de geçiyor (vendored/ortak ad): 270 satır
- En sık 10 tahmin: `BtreeCursor` ×13, `crypto_core_ed25519_scalar_sub` ×11, `free_expr` ×9, `crypto_core_ed25519_scalar_reduce` ×9, `http1_sse_on_close` ×9, `plutovg_path_add_ellipse` ×8, `http1_sse_on_open` ×7, `main` ×7, `runtime_http_on_request` ×7, `ecma_builtin_int16array_dispatch_construct` ×6

### String sabiti

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| var | 299 | 0.258 | 51% | 14 |
| yok | 1701 | 0.079 | 80% | 11 |

### Komut sayısı

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| <20 | 344 | 0.082 | 78% | 4 |
| 20-59 | 720 | 0.117 | 72% | 8 |
| 60-199 | 785 | 0.115 | 75% | 12 |
| 200+ | 151 | 0.060 | 87% | 1 |

### Opt

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| -O0 | 729 | 0.108 | 76% | 9 |
| -O1 | 470 | 0.107 | 76% | 7 |
| -O2 | 210 | 0.093 | 78% | 2 |
| -O3 | 91 | 0.128 | 70% | 2 |
| -Os | 500 | 0.103 | 75% | 5 |

### Çağrı bağlamı

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| var | 1171 | 0.109 | 75% | 14 |
| yok | 829 | 0.101 | 76% | 11 |

### Export

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| evet | 1023 | 0.123 | 72% | 20 |
| hayır | 977 | 0.088 | 80% | 5 |

### Tahmin eğitim adı kopyası

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| evet | 836 | 0.089 | 79% | 8 |
| hayır | 1164 | 0.118 | 73% | 17 |

### Proje

| grup | n | F1 | F1=0 payı | tam isabet |
|---|---:|---:|---:|---:|
| snkv | 509 | 0.093 | 76% | 2 |
| eth.zig | 173 | 0.052 | 90% | 2 |
| qaws | 169 | 0.025 | 93% | 1 |
| toks | 153 | 0.046 | 89% | 0 |
| cex | 147 | 0.215 | 50% | 0 |
| cyaml | 132 | 0.104 | 78% | 0 |
| cq | 107 | 0.279 | 48% | 7 |
| adam | 98 | 0.193 | 50% | 2 |
| libhiae | 81 | 0.094 | 80% | 1 |
| fmag | 61 | 0.079 | 80% | 0 |
| onedraw | 59 | 0.175 | 71% | 5 |
| glm-5.2-in-c | 49 | 0.074 | 84% | 0 |
| opendis | 42 | 0.106 | 81% | 2 |
| fcvvdp | 41 | 0.041 | 85% | 0 |
| mu_json_x | 36 | 0.081 | 75% | 0 |
| tomlc17 | 26 | 0.136 | 73% | 1 |
| carquet | 21 | 0.035 | 86% | 0 |
| sajs | 19 | 0.055 | 89% | 0 |
| nanocolor | 15 | 0.063 | 73% | 0 |
| wlipsync | 15 | 0.033 | 93% | 0 |
| gallant | 12 | 0.200 | 75% | 2 |
| microcheck | 11 | 0.096 | 73% | 0 |
| photoc | 10 | 0.107 | 70% | 0 |
| zerocast | 6 | 0.245 | 50% | 0 |
| picomatch | 5 | 0.340 | 40% | 0 |
| cryptography-research-demo | 3 | 0.167 | 67% | 0 |

