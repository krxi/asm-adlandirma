#!/bin/sh
# Colab'a yüklenecek veri arşivini repo kökünde hazırlar: sh colab/zip_sonraki.sh [veri-sonraki-v2 | veri-sonraki]
set -eu

KOK=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
VERI="$KOK/lora/${1:-veri-sonraki-v2}"
CIKTI="$KOK/${1:-veri-sonraki-v2}.zip"

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
