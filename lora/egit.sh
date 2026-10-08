#!/bin/sh
# LoRA eğitimi. Ek bayraklar mlx_lm.lora'ya geçer:
#   sh lora/egit.sh --iters 30 --adapter-path /tmp/ad
cd "$(dirname "$0")/.." || exit 1
exec caffeinate -i .venv/bin/python -m mlx_lm lora -c lora/ayar.yaml "$@"
