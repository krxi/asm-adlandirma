#!/bin/sh
# Bütün modeller paralel, düşünmeli ve düşünmesiz; kimse kimseyi beklemez.
cd "$(dirname "$0")"
for m in deepseek-v4.1-flash glm-5.3 mimo-v2.6-pro gemma-4-31b qwen3.8-flash-next; do
  python3 taban.py veri/zlib.jsonl -n 60 -j 6 -m "$m" > "sonuc/log-$m.txt" 2>&1 &
  python3 taban.py veri/zlib.jsonl -n 60 -j 6 -m "$m" --dusunme > "sonuc/log-$m-dusunme.txt" 2>&1 &
done
wait
echo bitti > sonuc/BITTI
