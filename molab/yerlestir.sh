#!/bin/sh
# molab'dan indirilen adaptor-Qwen3-8B.zip ve sonuc-molab.zip'i repoya yerleştirir.
# Kullanım: sh molab/yerlestir.sh [indirme_klasoru]   (varsayılan ~/Downloads)
set -eu
D="${1:-$HOME/Downloads}"
KOK="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "$D/adaptor-Qwen3-8B.zip" ]; then
  mkdir -p "$KOK/lora/adaptor-molab-qwen3-8b"
  unzip -oj "$D/adaptor-Qwen3-8B.zip" -d "$KOK/lora/adaptor-molab-qwen3-8b"
  ls -la "$KOK/lora/adaptor-molab-qwen3-8b"
fi
if [ -f "$D/sonuc-molab.zip" ]; then
  T="$(mktemp -d)"
  unzip -oj "$D/sonuc-molab.zip" -d "$T"
  cp "$T/sonuc-test-Qwen3-8B-lora.jsonl" "$KOK/sonuc/test-molab-qwen3-8b-lora.jsonl"
  cp "$T/sonuc-eval115-Qwen3-8B-lora.jsonl" "$KOK/sonuc/eval115-molab-qwen3-8b-lora.jsonl"
  { echo; echo "--- egitim.log (tam) ---"; cat "$T/egitim.log"; } >> "$KOK/sonuc/log-molab-qwen3-8b.txt"
  rm -rf "$T"
  ls -la "$KOK"/sonuc/*molab*
fi
