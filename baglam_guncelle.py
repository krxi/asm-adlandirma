#!/usr/bin/env python3
"""Seçili veri kümesine kaynak satırlardaki çağrı bağlamlarını ekle.

  python3 baglam_guncelle.py veri/test.jsonl veri/test/*.jsonl
  python3 baglam_guncelle.py veri/zlib-v3.jsonl veri/egitim/zlib.jsonl
"""
import argparse, json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hedef", type=Path)
    ap.add_argument("kaynak", nargs="+", type=Path)
    a = ap.parse_args()

    baglamlar = {}
    for yol in a.kaynak:
        for satir in yol.open():
            kayit = json.loads(satir)
            for alan in ("baglam", "baglam_derin"):
                if alan not in kayit:
                    raise SystemExit(f"{alan} alanı yok: {yol}: {kayit.get('id')}")
            deger = (kayit["baglam"], kayit["baglam_derin"], kayit["sizinti"])
            onceki = baglamlar.setdefault(kayit["id"], deger)
            if onceki != deger:
                raise SystemExit(f"çelişen bağlam: {kayit['id']}")

    satirlar = [json.loads(satir) for satir in a.hedef.open()]
    eksik = [kayit["id"] for kayit in satirlar if kayit["id"] not in baglamlar]
    if eksik:
        raise SystemExit(f"kaynakta bulunamayan {len(eksik)} id: {', '.join(eksik[:5])}")
    gecici = a.hedef.with_suffix(a.hedef.suffix + ".baglam.tmp")
    with gecici.open("w") as f:
        for kayit in satirlar:
            kayit["baglam"], kayit["baglam_derin"], kayit["sizinti"] = baglamlar[kayit["id"]]
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
    gecici.replace(a.hedef)
    print(f"{len(satirlar)} satır güncellendi → {a.hedef}")


if __name__ == "__main__":
    main()
