#!/usr/bin/env python3
"""veri/*.jsonl → mlx-lm sohbet biçimi (lora/veri/{train,valid,test}.jsonl).

  python3 lora/hazirla.py --egitim zlib --test zlib --duman      # yalnız duman testi
  python3 lora/hazirla.py --egitim p1,p2,p3 --test p4

Bölme PROJE bazlı: bir proje ya tamamen eğitimde ya tamamen testte.
Proje = satırdaki "proje" alanı, yoksa dosya adının gövdesi (veri/zlib.jsonl → zlib).
"""
import argparse, json, random, sys
from pathlib import Path

SISTEM = ("Sen deneyimli bir tersine mühendissin. Sana sembolleri silinmiş bir x86-64 fonksiyonu "
          "(Intel sözdizimi) verilecek. Projenin iç fonksiyonları sub_XXXX diye gizlendi; dış "
          "kütüphane çağrıları görünür. Fonksiyonun asıl kaynak koddaki adını tahmin et. "
          'Yalnız JSON dön: {"ad": "fonksiyon_adi"}')


def oku(veri: Path) -> dict[str, list[dict]]:
    projeler: dict[str, list[dict]] = {}
    for yol in sorted(veri.glob("*.jsonl")):
        for l in yol.open():
            if l.strip():
                r = json.loads(l)
                projeler.setdefault(r.get("proje") or yol.stem, []).append(r)
    return projeler


TOK = None  # --token-tavan verilirse tokenizer


def kes(asm: str, tavan: int, token_tavan: int = 0) -> str:
    satirlar = asm.split("\n")
    kesildi = len(satirlar) > tavan
    satirlar = satirlar[:tavan]
    # Cevap eğitimde kesilirse (mask_prompt ile) kayıp NaN olur: asm token tavanına sığmalı.
    while TOK and token_tavan and len(satirlar) > 1 and len(TOK.encode("\n".join(satirlar))) > token_tavan:
        satirlar = satirlar[: max(1, int(len(satirlar) * 0.9))]
        kesildi = True
    return "\n".join(satirlar + (["; ... kesildi"] if kesildi else []))


def mesaj(r: dict, tavan: int, token_tavan: int = 0) -> dict:
    return {"messages": [{"role": "system", "content": SISTEM},
                         {"role": "user", "content": kes(r["asm"], tavan, token_tavan)},
                         {"role": "assistant", "content": json.dumps({"ad": r["ad"]}, ensure_ascii=False)}],
            "id": r["id"], "opt": r["opt"]}


def tekil(satirlar: list[dict]) -> list[dict]:
    # Aynı asm (ör. -O0/-O2'de özdeş ya da kopya fonksiyon) bir kez girer.
    goruldu, cikti = set(), []
    for r in satirlar:
        if r["asm"] not in goruldu:
            goruldu.add(r["asm"])
            cikti.append(r)
    return cikti


def yaz(yol: Path, satirlar: list[dict], tavan: int, token_tavan: int = 0):
    with yol.open("w") as f:
        for r in satirlar:
            f.write(json.dumps(mesaj(r, tavan, token_tavan), ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--egitim", required=True, help="virgüllü proje adları")
    ap.add_argument("--test", required=True, help="virgüllü proje adları")
    ap.add_argument("--veri", type=Path, default=Path("veri"))
    ap.add_argument("--cikti", type=Path, default=Path("lora/veri"))
    ap.add_argument("--satir-tavan", type=int, default=200, help="asm en çok bu kadar satır")
    ap.add_argument("--token-tavan", type=int, default=1500,
                    help="asm en çok bu kadar token (0=kapalı); sistem+cevap payı için max-seq'ten ~500 az")
    ap.add_argument("--tokenizer", default="mlx-community/Qwen2.5-Coder-0.5B-Instruct-4bit")
    ap.add_argument("--valid-oran", type=float, default=0.05)
    ap.add_argument("--tohum", type=int, default=7)
    ap.add_argument("--duman", action="store_true", help="eğitim ve test aynı projeyse izin ver (YALNIZ duman testi)")
    a = ap.parse_args()

    egitim = [p for p in a.egitim.split(",") if p]
    test = [p for p in a.test.split(",") if p]
    ortak = set(egitim) & set(test)
    if ortak and not a.duman:
        sys.exit(f"sızıntı: {sorted(ortak)} hem eğitimde hem testte (duman testiyse --duman ver)")
    if ortak:
        print(f"UYARI: DUMAN TESTİ, eğitim=test {sorted(ortak)}; sonuçlar anlamsız", file=sys.stderr)
    global TOK
    if a.token_tavan:
        from transformers import AutoTokenizer  # .venv içinde var
        TOK = AutoTokenizer.from_pretrained(a.tokenizer)
    projeler = oku(a.veri)
    for p in egitim + test:
        if p not in projeler:
            sys.exit(f"proje yok: {p} (var olanlar: {sorted(projeler)})")

    rng = random.Random(a.tohum)
    tr = tekil([r for p in egitim for r in projeler[p]])
    te = tekil([r for p in test for r in projeler[p]])
    rng.shuffle(tr)
    nv = max(1, round(len(tr) * a.valid_oran))
    va, tr = tr[:nv], tr[nv:]

    a.cikti.mkdir(parents=True, exist_ok=True)
    for ad, l in (("train", tr), ("valid", va), ("test", te)):
        yaz(a.cikti / f"{ad}.jsonl", l, a.satir_tavan, a.token_tavan)
    print(f"train {len(tr)}  valid {len(va)}  test {len(te)}  → {a.cikti}")


if __name__ == "__main__":
    main()
