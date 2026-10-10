#!/usr/bin/env python3
"""sonuc/*.jsonl → model × kip tablosu (F1, tam isabet, hata, kesik, token).

  python3 ozet.py            # hepsi
  python3 ozet.py test       # yalnız sonuc/test-*.jsonl
  python3 ozet.py --md test  # README için markdown

kesik: düşünme max_tokens tavanına çarpıp cevap veremeden biten istek.
öneksiz F1: projenin ortak ad öneki (cyaml_, mu_, sajs_ …) iki taraftan da atılarak hesaplanır;
model projenin önekini assembly'den bilemez.
"""
import json, sys
from collections import Counter
from pathlib import Path

from taban import kelimeler


def onekler(veri=None) -> dict[str, set[str]]:
    """Proje → ad öneki; varsayılan veri kökü çalışma dizininden bağımsızdır."""
    veri = Path(__file__).resolve().parent / "veri" if veri is None else Path(veri)
    sonuc = {}
    for p in [*veri.glob("egitim/*.jsonl"), *veri.glob("test/*.jsonl")]:
        adlar = [kelimeler(json.loads(l)["ad"]) for l in p.open()]
        say = Counter(k[0] for k in adlar if len(k) > 1)
        proje = p.stem.lower().replace("_", "").removeprefix("lib")
        ilgili = lambda k: proje.startswith(k.rstrip("0123456789")) or (len(k) <= 3 and proje.startswith(k[0]))
        sonuc[p.stem] = {k for k, n in say.items() if n >= 0.1 * len(adlar) and ilgili(k)}
    return sonuc


ONEK = onekler()


def f1_oneksiz(r: dict) -> float:
    at = ONEK.get(r["id"].split("/")[0], set()) if "/" in r["id"] else set()
    t = set(kelimeler(str(r.get("tahmin") or ""))) - at
    g = set(kelimeler(r["gercek"])) - at or set(kelimeler(r["gercek"]))
    ortak = len(t & g)
    return 0.0 if not ortak else 2 * ortak / (len(t) + len(g))


def main():
    md = "--md" in sys.argv
    onek = next((x for x in sys.argv[1:] if not x.startswith("--")), "")
    satirlar = []
    for p in sorted(Path("sonuc").glob(f"{onek}*.jsonl")):
        L = [json.loads(l) for l in p.open()]
        f1 = lambda o: [r["f1"] for r in L if r.get("opt") == o]
        ort = lambda x: f"{sum(x) / len(x):.2f}" if x else "-"
        hata = sum(1 for r in L if str(r.get("aciklama", "")).startswith("HATA"))
        kesik = sum(1 for r in L if not r.get("tahmin") and r.get("token") and r.get("bitis") in ("length", None))
        satirlar.append((p.stem, ort(f1("-O0")), ort(f1("-O2")), ort([f1_oneksiz(r) for r in L]),
                         sum(r["f1"] == 1 for r in L), len(L), hata, kesik, sum(r.get("token", 0) for r in L)))

    if md:
        print("| koşu | -O0 F1 | -O2 F1 | öneksiz F1 | tam isabet | kesik | token |\n|---|---|---|---|---|---|---|---|")
        for ad, o0, o2, oneksiz, isabet, n, hata, kesik, token in sorted(satirlar, key=lambda s: -float(s[3])):
            print(f"| {ad} | {o0} | {o2} | {oneksiz} | {isabet} / {n} | {kesik} | {token:,} |")
    else:
        print(f"{'koşu':<40}{'-O0 F1':>8}{'-O2 F1':>8}{'öneksiz':>8}{'isabet':>8}{'n':>5}{'hata':>6}{'kesik':>6}{'token':>10}")
        for s in satirlar:
            print(f"{s[0]:<40}{s[1]:>8}{s[2]:>8}{s[3]:>8}{s[4]:>8}{s[5]:>5}{s[6]:>6}{s[7]:>6}{s[8]:>10}")


if __name__ == "__main__":
    main()
