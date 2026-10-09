# Ad F1: gerçek ad ve öneksiz ad

`python3 iki_f1.py` çıktısı, 38 sonuç dosyası. Elle düzenlemeyin; betiği yeniden çalıştırın.

- **gerçek ad F1**: `taban.f1(tahmin, gerçek ad)`. Ad snake/camel sözcüklere bölünür, sözcük kümelerinin F1'i.
- **öneksiz F1**: `ozet.f1_oneksiz`. Projenin ortak öneki (aşağıdaki tablo, ilk sütun) iki taraftan atılır;
  model öneki assembly'den bilemez.
- **dosyadaki f1**: sonuç dosyasına koşu sırasında yazılan değer. Hedef öneksizse gerçek ad F1'inden farklıdır.
- **hedef**: dosyadaki `gercek` alanı veri/'deki gerçek adla aynı mı.

| koşu | n | gerçek ad F1 (-O0 / -O2 / hepsi) | öneksiz F1 (-O0 / -O2 / hepsi) | fark | tam isabet gerçek / öneksiz | dosyadaki f1 | hedef |
|---|---:|---|---|---:|---|---:|---|
| zlib-mimo-v2.6-pro-dusunme | 60 | 0.450 / 0.472 / 0.459 | 0.450 / 0.472 / 0.459 | +0.000 | 22 / 22 | 0.459 | gerçek ad |
| zlib-v3-mimo-v2.6-pro-dusunme | 115 | 0.260 / 0.333 / 0.294 | 0.260 / 0.333 / 0.294 | +0.000 | 28 / 28 | 0.294 | gerçek ad |
| zlib-mimo-v2.6-pro | 60 | 0.237 / 0.327 / 0.276 | 0.237 / 0.327 / 0.276 | +0.000 | 7 / 7 | 0.276 | gerçek ad |
| test-mimo-v2.6-pro-baglam2 | 115 | 0.247 / 0.182 / 0.216 | 0.266 / 0.207 / 0.238 | +0.022 | 5 / 8 | 0.216 | gerçek ad |
| test-mimo-v2.6-pro-baglam | 115 | 0.223 / 0.165 / 0.195 | 0.244 / 0.189 / 0.218 | +0.023 | 4 / 7 | 0.195 | gerçek ad |
| zlib-deepseek-v4.1-flash-dusunme | 60 | 0.191 / 0.253 / 0.218 | 0.191 / 0.253 / 0.218 | +0.000 | 11 / 11 | 0.218 | gerçek ad |
| test-mimo-v2.6-pro-dusunme | 115 | 0.199 / 0.172 / 0.186 | 0.220 / 0.204 / 0.213 | +0.026 | 3 / 6 | 0.186 | gerçek ad |
| test-mimo-v2.6-pro | 115 | 0.180 / 0.165 / 0.173 | 0.200 / 0.190 / 0.195 | +0.022 | 4 / 7 | 0.173 | gerçek ad |
| zlib-v3-mimo-v2.6-pro | 115 | 0.163 / 0.190 / 0.176 | 0.163 / 0.190 / 0.176 | +0.000 | 9 / 9 | 0.176 | gerçek ad |
| test-deepseek-v4.1-flash-baglam2 | 115 | 0.194 / 0.121 / 0.159 | 0.203 / 0.138 / 0.172 | +0.013 | 3 / 4 | 0.159 | gerçek ad |
| test-deepseek-v4.1-flash-baglam | 115 | 0.192 / 0.123 / 0.159 | 0.198 / 0.140 / 0.170 | +0.012 | 2 / 3 | 0.159 | gerçek ad |
| test-qwen3.8-flash-next-baglam2 | 115 | 0.204 / 0.086 / 0.148 | 0.213 / 0.102 / 0.160 | +0.012 | 1 / 2 | 0.148 | gerçek ad |
| test-glm-5.3-dusunme | 115 | 0.159 / 0.114 / 0.138 | 0.172 / 0.123 / 0.148 | +0.011 | 4 / 5 | 0.138 | gerçek ad |
| test-qwen3.8-flash-next-baglam | 115 | 0.171 / 0.091 / 0.133 | 0.181 / 0.109 / 0.147 | +0.014 | 1 / 2 | 0.133 | gerçek ad |
| zlib-glm-5.3-dusunme | 60 | 0.112 / 0.183 / 0.143 | 0.112 / 0.183 / 0.143 | +0.000 | 5 / 5 | 0.143 | gerçek ad |
| test-glm-5.3-baglam | 115 | 0.153 / 0.084 / 0.120 | 0.165 / 0.102 / 0.135 | +0.015 | 3 / 5 | 0.120 | gerçek ad |
| test-qwen3.8-flash-next-dusunme | 115 | 0.162 / 0.081 / 0.123 | 0.171 / 0.096 / 0.135 | +0.012 | 3 / 3 | 0.123 | gerçek ad |
| test-glm-5.3-baglam2 | 115 | 0.135 / 0.085 / 0.111 | 0.153 / 0.102 / 0.128 | +0.017 | 2 / 5 | 0.111 | gerçek ad |
| test-deepseek-v4.1-flash | 115 | 0.105 / 0.114 / 0.109 | 0.116 / 0.125 / 0.121 | +0.012 | 2 / 3 | 0.109 | gerçek ad |
| test-glm-5.3 | 115 | 0.122 / 0.077 / 0.101 | 0.137 / 0.096 / 0.118 | +0.017 | 2 / 5 | 0.101 | gerçek ad |
| zlib-deepseek-v4.1-flash | 60 | 0.105 / 0.130 / 0.116 | 0.105 / 0.130 / 0.116 | +0.000 | 0 / 0 | 0.116 | gerçek ad |
| test-deepseek-v4.1-flash-dusunme | 115 | 0.121 / 0.082 / 0.102 | 0.133 / 0.096 / 0.115 | +0.013 | 3 / 4 | 0.102 | gerçek ad |
| test-qwen3.8-flash-next | 115 | 0.128 / 0.075 / 0.103 | 0.143 / 0.082 / 0.114 | +0.011 | 1 / 2 | 0.103 | gerçek ad |
| zlib-qwen3.8-flash-next | 60 | 0.059 / 0.171 / 0.107 | 0.059 / 0.171 / 0.107 | +0.000 | 0 / 0 | 0.107 | gerçek ad |
| test-gemma-4-31b-dusunme | 115 | 0.107 / 0.080 / 0.094 | 0.115 / 0.092 / 0.104 | +0.010 | 2 / 3 | 0.094 | gerçek ad |
| test-gemma-4-31b | 115 | 0.106 / 0.075 / 0.091 | 0.117 / 0.084 / 0.101 | +0.010 | 0 / 1 | 0.091 | gerçek ad |
| test-gemma-4-31b-baglam2 | 115 | 0.108 / 0.076 / 0.093 | 0.109 / 0.085 / 0.098 | +0.005 | 0 / 0 | 0.093 | gerçek ad |
| test-gemma-4-31b-baglam | 115 | 0.087 / 0.076 / 0.082 | 0.094 / 0.085 / 0.090 | +0.008 | 0 / 0 | 0.082 | gerçek ad |
| zlib-v3-deepseek-v4.1-flash | 115 | 0.056 / 0.096 / 0.074 | 0.056 / 0.096 / 0.074 | +0.000 | 1 / 1 | 0.074 | gerçek ad |
| zlib-v3-qwen3.8-flash-next | 115 | 0.053 / 0.096 / 0.073 | 0.053 / 0.096 / 0.073 | +0.000 | 0 / 0 | 0.073 | gerçek ad |
| zlib-gemma-4-31b-dusunme | 60 | 0.046 / 0.088 / 0.064 | 0.046 / 0.088 / 0.064 | +0.000 | 0 / 0 | 0.064 | gerçek ad |
| zlib-gemma-4-31b | 60 | 0.052 / 0.044 / 0.049 | 0.052 / 0.044 / 0.049 | +0.000 | 0 / 0 | 0.049 | gerçek ad |
| zlib-qwen3.8-flash-next-dusunme | 60 | 0.029 / 0.058 / 0.042 | 0.029 / 0.058 / 0.042 | +0.000 | 2 / 2 | 0.042 | gerçek ad |
| zlib-v3-gemma-4-31b | 115 | 0.013 / 0.047 / 0.028 | 0.013 / 0.047 / 0.028 | +0.000 | 0 / 0 | 0.028 | gerçek ad |
| zlib-glm-5.3 | 60 | 0.044 / 0.000 / 0.025 | 0.044 / 0.000 / 0.025 | +0.000 | 1 / 1 | 0.025 | gerçek ad |
| test-Qwen2.5-Coder-0.5B-lora-v2 | 112 | 0.021 / 0.019 / 0.020 | 0.022 / 0.022 / 0.022 | +0.002 | 0 / 0 | 0.020 | gerçek ad |
| test-Qwen2.5-Coder-0.5B-Instruct-4bit-lora | 112 | 0.017 / 0.000 / 0.009 | 0.017 / 0.000 / 0.009 | +0.000 | 0 / 0 | 0.009 | gerçek ad |
| test-Qwen2.5-Coder-0.5B-Instruct-4bit-taban | 112 | 0.000 / 0.009 / 0.004 | 0.000 / 0.012 / 0.006 | +0.001 | 0 / 0 | 0.004 | gerçek ad |

Dosyadaki `f1` alanı, aynı dosyadaki `gercek` ile yeniden hesaplanan değerle her satırda tutuyor.

## Önek tanımları test projelerinde

İki kod yolu farklı önek buluyor. `hazirla_olcek.py` varsayılanı proje adından bağımsız en sık `xxx_` başını alıyor; bu, bazı projelerde anlamlı fiilleri (sajs `eat_`, picomatch `emit_`) eğitim ve test hedefinden siliyor.

| test projesi | ozet.py (öneksiz F1) | hazirla_olcek.py siklik (varsayılan) | hazirla_olcek.py proje |
|---|---|---|---|
| cyaml | cyaml | cyaml | cyaml |
| mu_json_x | mu | mu | mu |
| picomatch | pm | emit | - |
| sajs | sajs | eat | - |
| tomlc17 | toml | - | - |
