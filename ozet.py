#!/usr/bin/env python3
"""sonuc/*.jsonl → model × kip tablosu (F1, tam isabet, token)."""
import json
from pathlib import Path

print(f"{'model':<34}{'-O0 F1':>8}{'-O2 F1':>8}{'isabet':>8}{'hata':>6}{'token':>10}")
for p in sorted(Path("sonuc").glob("*.jsonl")):
    L = [json.loads(l) for l in p.open()]
    f1 = lambda o: [r["f1"] for r in L if r.get("opt") == o]
    ort = lambda x: f"{sum(x) / len(x):.2f}" if x else "-"
    hata = sum(1 for r in L if str(r.get("aciklama", "")).startswith("HATA"))
    print(f"{p.stem:<34}{ort(f1('-O0')):>8}{ort(f1('-O2')):>8}{sum(r['f1'] == 1 for r in L):>8}"
          f"{hata:>6}{sum(r.get('token', 0) for r in L):>10}")
