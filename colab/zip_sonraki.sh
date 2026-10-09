#!/bin/sh
# Colab'a yüklenecek veri-sonraki.zip dosyasını repo kökünde hazırlar.
set -eu

KOK=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
VERI="$KOK/lora/veri-sonraki"
CIKTI="$KOK/veri-sonraki.zip"

for DOSYA in train.jsonl valid.jsonl test.jsonl test_sabit.jsonl; do
    if [ ! -f "$VERI/$DOSYA" ]; then
        echo "veri dosyası yok: $VERI/$DOSYA" >&2
        exit 1
    fi
done

GECICI_DIZIN=$(mktemp -d "${TMPDIR:-/tmp}/asm-veri-sonraki.XXXXXX")
GECICI="$GECICI_DIZIN/veri-sonraki.zip"
trap 'rm -f "$GECICI"; rmdir "$GECICI_DIZIN" 2>/dev/null || true' EXIT HUP INT TERM
(
    cd "$VERI"
    zip -q "$GECICI" train.jsonl valid.jsonl test.jsonl test_sabit.jsonl
)
mv "$GECICI" "$CIKTI"
rmdir "$GECICI_DIZIN"
trap - EXIT HUP INT TERM
echo "hazır: $CIKTI"
