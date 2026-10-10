#!/usr/bin/env python3
"""v5 model açıklamalarını (TR ve EN ayrı) C kaynağına göre hakem modelle 0-2 puanla.

  python3 aciklama_puan_v5.py sonuc/test2000-molab-qwen3-8b-v5.jsonl -n 300 -j 8

id biçimi "proje/dosya:opt:kip:kimlik:ad"; kaynak veri/kaynak-v4, referans veri/aciklama-v4/codex.jsonl.
Çıktı <girdi>-puan.jsonl ve stdout özeti. Hakem ve istem aciklama_puan.py ile aynı.
"""
import argparse, json, random, statistics as st
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import aciklama_puan as ap_


def anahtar(r):
    yol, ad = r["id"].split(":")[0], r["gercek"]
    return f"{yol}:{ad}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sonuc", type=Path)
    ap.add_argument("-m", "--model", default="mimo-v2.6-pro")
    ap.add_argument("-n", type=int, default=300)
    ap.add_argument("-j", type=int, default=8)
    a = ap.parse_args()
    kaynak = {}
    for p in Path("veri/kaynak-v4").glob("*.jsonl"):
        for l in p.open():
            r = json.loads(l)
            kaynak[r["anahtar"]] = r["kaynak"]
    ref = {json.loads(l)["anahtar"]: json.loads(l)["aciklama"] for l in open("veri/aciklama-v4/codex.jsonl")}
    R = [json.loads(l) for l in a.sonuc.open()]
    R = [r for r in R if anahtar(r) in kaynak and anahtar(r) in ref]
    R = random.Random(42).sample(R, min(a.n, len(R)))

    def is_(r):
        k = anahtar(r)
        out = dict(id=r["id"], f1=r["f1"])
        for dil, alan in (("tr", "aciklama"), ("en", "aciklama_en")):
            c = ap_.sor(ap_.istem({"aciklama": r.get(alan)}, kaynak[k][:12000], ref[k], a.model))
            out[f"puan_{dil}"], out[f"gerekce_{dil}"] = c["puan"], c["gerekce"]
        return out

    with ThreadPoolExecutor(a.j) as h:
        S = list(h.map(is_, R))
    cikti = a.sonuc.with_name(a.sonuc.stem + "-puan.jsonl")
    cikti.write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in S))
    for dil in ("tr", "en"):
        p = [s[f"puan_{dil}"] for s in S if s[f"puan_{dil}"] is not None]
        print(f"{dil}: n={len(p)} ortalama {st.mean(p):.3f}  2:{p.count(2) / len(p):.1%} 1:{p.count(1) / len(p):.1%} 0:{p.count(0) / len(p):.1%}")
    iyi = [s["f1"] for s in S if s["puan_en"] == 2]; kotu = [s["f1"] for s in S if s["puan_en"] == 0]
    print(f"ad F1: açıklama doğruyken {st.mean(iyi):.3f} (n={len(iyi)}), yanlışken {st.mean(kotu):.3f} (n={len(kotu)})")
    print("→", cikti)


if __name__ == "__main__":
    main()
