#!/usr/bin/env python3
"""veri/test/*.jsonl → veri/test.jsonl: ezbere dayanıklı ölçüm seti.

Her (proje, kip) için en çok k fonksiyon, adı asm'de geçenler (sizinti) hariç.
Eğitim projelerinde birebir aynı adla geçen test fonksiyonlarını da raporlar.

  python3 test_seti.py -k 12
"""
import argparse, json, random
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", type=int, default=12, help="proje × kip başına en çok fonksiyon")
    ap.add_argument("-o", "--cikti", type=Path, default=Path("veri/test.jsonl"))
    ap.add_argument("--tohum", type=int, default=7)
    a = ap.parse_args()

    egitim_adlari = {json.loads(l)["ad"].lower() for p in Path("veri/egitim").glob("*.jsonl") for l in p.open()}
    secilen = []
    for p in sorted(Path("veri/test").glob("*.jsonl")):
        L = [r for r in map(json.loads, p.open()) if not r["sizinti"]]
        for opt in ("-O0", "-O2"):
            havuz = [r for r in L if r["opt"] == opt]
            random.Random(f"{p.stem}{opt}{a.tohum}").shuffle(havuz)
            secilen += havuz[: a.k]
    # taban.py kendi içinde karıştırıyor; -n ile tamamı alınır
    with a.cikti.open("w") as f:
        for r in secilen:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    ortak = [r["ad"] for r in secilen if r["ad"].lower() in egitim_adlari]
    print(f"{len(secilen)} fonksiyon → {a.cikti}")
    for proje in sorted({r["proje"] for r in secilen}):
        print(f"  {proje}: {sum(r['proje'] == proje for r in secilen)}")
    print(f"eğitimde aynı adla geçen: {len(ortak)} {sorted(set(ortak))[:15]}")


if __name__ == "__main__":
    main()
