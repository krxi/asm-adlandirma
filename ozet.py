#!/usr/bin/env python3
"""sonuc/*.jsonl → model × kip tablosu (F1, tam isabet, hata, kesik, token).

  python3 ozet.py            # hepsi
  python3 ozet.py test       # yalnız sonuc/test-*.jsonl
  python3 ozet.py --md test  # README için markdown

kesik: düşünme max_tokens tavanına çarpıp cevap veremeden biten istek.
"""
import json, sys
from pathlib import Path

md = "--md" in sys.argv
onek = next((x for x in sys.argv[1:] if not x.startswith("--")), "")
satirlar = []
for p in sorted(Path("sonuc").glob(f"{onek}*.jsonl")):
    L = [json.loads(l) for l in p.open()]
    f1 = lambda o: [r["f1"] for r in L if r.get("opt") == o]
    ort = lambda x: f"{sum(x) / len(x):.2f}" if x else "-"
    hata = sum(1 for r in L if str(r.get("aciklama", "")).startswith("HATA"))
    kesik = sum(1 for r in L if not r.get("tahmin") and r.get("token") and r.get("bitis") in ("length", None))
    satirlar.append((p.stem, ort(f1("-O0")), ort(f1("-O2")), sum(r["f1"] == 1 for r in L), len(L), hata, kesik,
                     sum(r.get("token", 0) for r in L)))

if md:
    print("| koşu | -O0 F1 | -O2 F1 | tam isabet | kesik | token |\n|---|---|---|---|---|---|")
    for ad, o0, o2, isabet, n, hata, kesik, token in sorted(satirlar, key=lambda s: -s[3]):
        print(f"| {ad} | {o0} | {o2} | {isabet} / {n} | {kesik} | {token:,} |")
else:
    print(f"{'koşu':<40}{'-O0 F1':>8}{'-O2 F1':>8}{'isabet':>8}{'n':>5}{'hata':>6}{'kesik':>6}{'token':>10}")
    for s in satirlar:
        print(f"{s[0]:<40}{s[1]:>8}{s[2]:>8}{s[3]:>8}{s[4]:>5}{s[5]:>6}{s[6]:>6}{s[7]:>10}")
