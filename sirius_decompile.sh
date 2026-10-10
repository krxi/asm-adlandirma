#!/usr/bin/env bash
# Sirius'ta proje başına checkpoint'li, tek Ghidra süreçli v6 kuyruğu.
set -u

kok=${1:-"$HOME/asm-v6"}
idler_dizini=${2:-"$kok/idler"}
cikti_dizini=${3:-"$kok/cikti"}
sira_yolu=${4:-"$kok/sira.txt"}
ghidra=${GHIDRA_HOME:-"$HOME/araclar/ghidra_12.1.4_PUBLIC"}
java=${JAVA_HOME:-"$HOME/araclar/jdk21"}
export JAVA_HOME=$java
export JAVA_TOOL_OPTIONS=${JAVA_TOOL_OPTIONS:--Xmx1500m}
mkdir -p "$cikti_dizini" "$kok/log"

isle() {
    proje=$1
    idler="$idler_dizini/$proje.txt"
    if [[ ! -f "$idler" ]]; then
        printf '%s %s idler-yok\n' "$(date -Is)" "$proje"
        return
    fi
    ikili="$kok/ikili/$proje"
    if [[ ! -d "$ikili" ]]; then
        printf '%s %s ikili-yok\n' "$(date -Is)" "$proje"
        return
    fi
    bas=$(date +%s)
    printf '%s %s basladi\n' "$(date -Is)" "$proje"
    python3 "$kok/kod/decompile_ghidra.py" "$ikili" \
        --idler "$idler" -o "$cikti_dizini/$proje.jsonl" --devam \
        --ghidra "$ghidra" --java-home "$java" \
        >> "$kok/log/$proje.log" 2>&1
    durum=$?
    printf '%s %s bitti durum=%d sure_sn=%d\n' \
        "$(date -Is)" "$proje" "$durum" "$(($(date +%s) - bas))"
}

if [[ -f "$sira_yolu" ]]; then
    while IFS= read -r proje; do
        [[ -n "$proje" ]] && isle "$proje"
    done < "$sira_yolu"
else
    while IFS= read -r idler; do
        isle "$(basename "$idler" .txt)"
    done < <(find "$idler_dizini" -maxdepth 1 -type f -name '*.txt' | sort)
fi
