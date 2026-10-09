#!/usr/bin/env python3
"""Önek kuralı denetimi: lora/hazirla_olcek.py hangi projelerde hangi adları yanlış kırpıyor?

  python3 onek_denetim.py                                   # veri/test + varsa veri/egitim, veri/bin/olcek
  python3 onek_denetim.py veri/bin/olcek/*.jsonl -o rapor/ONEK_DENETIM_V4.md

Üç kural karşılaştırılır:
  siklik  hazirla_olcek.onekler varsayılanı: en sık "xxx_" başı (≥%30 ve ≥5 ad), proje adına bakmaz
  proje   aynı eşik, ama önek proje adıyla ilişkili olmalı (--onek-kurali proje)
  ozet    ozet.onekler: README'deki öneksiz F1'in tanımı (yalnız veri/egitim ve veri/test)

"Yanlış kırpma": siklik kuralının attığı ama proje kuralının atmadığı önek. Böyle bir adın eğitim
hedefinden anlamlı bir sözcüğü (eat_, emit_, get_) silinir. "Çakışma": kırpma sonrası iki farklı
adın aynı hedefe düşmesi (ör. eat_value ve value).
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lora"))
import hazirla as h  # noqa: E402
import hazirla_olcek as ho  # noqa: E402


def varsayilan_dosyalar() -> list[Path]:
    veri = Path("veri")
    return sorted(
        [
            *veri.glob("*.jsonl"),
            *veri.glob("test/*.jsonl"),
            *veri.glob("egitim/*.jsonl"),
            *veri.glob("bin/olcek/*.jsonl"),
        ]
    )


def oku(dosyalar: list[Path]) -> dict[str, set[str]]:
    """proje → benzersiz adlar (aynı id birden çok dosyada olabilir)."""
    adlar = defaultdict(set)
    for p in dosyalar:
        for satir in p.open():
            if satir.strip():
                r = json.loads(satir)
                adlar[r.get("proje") or p.stem].add(r["ad"])
    return adlar


def kirp(ad: str, proje: str, onekler: dict[str, set[str]]) -> str:
    eski = h.ONEK
    try:
        h.ONEK = onekler
        return h.oneksiz({"ad": ad, "proje": proje})
    finally:
        h.ONEK = eski


def denetle(adlar: dict[str, set[str]]) -> list[dict]:
    satirlar = [{"proje": p, "ad": a} for p, ads in adlar.items() for a in ads]
    siklik, proje = ho.onekler(satirlar, "siklik"), ho.onekler(satirlar, "proje")
    sonuc = []
    for p in sorted(adlar):
        ads = sorted(adlar[p])
        s_onek, p_onek = siklik.get(p, set()), proje.get(p, set())
        kirpilan = {a: kirp(a, p, siklik) for a in ads}
        dogru = {a: kirp(a, p, proje) for a in ads}
        yanlis = [a for a in ads if kirpilan[a] != dogru[a]]
        hedefler = defaultdict(list)
        for a in ads:
            hedefler[kirpilan[a].lower()].append(a)
        cakisma = sorted(tuple(sorted(v)) for v in hedefler.values() if len(v) > 1)
        sonuc.append(
            {
                "proje": p,
                "ad": len(ads),
                "siklik": sorted(s_onek),
                "proje_kurali": sorted(p_onek),
                "yanlis": yanlis,
                "ornek": [(a, kirpilan[a]) for a in yanlis[:6]],
                "cakisma": cakisma,
            }
        )
    return sonuc


def rapor(sonuc: list[dict], dosyalar: list[Path]) -> str:
    etkilenen = [s for s in sonuc if s["yanlis"]]
    toplam_ad = sum(s["ad"] for s in sonuc)
    toplam_yanlis = sum(len(s["yanlis"]) for s in sonuc)
    md = [
        "# Önek kuralı denetimi",
        "",
        f"`python3 onek_denetim.py` çıktısı. Girdi: {', '.join(f'`{p}`' for p in dosyalar)}.",
        "",
        f"{len(sonuc)} proje, {toplam_ad} benzersiz ad. `hazirla_olcek.py` varsayılan kuralı (siklik) "
        f"{len(etkilenen)} projede proje adıyla ilgisiz bir öneki atıyor; bu {toplam_yanlis} adın "
        f"(%{100 * toplam_yanlis / max(1, toplam_ad):.1f}) eğitim/test hedefini değiştiriyor.",
        "",
        "Düzeltme: `lora/hazirla_olcek.py --onek-kurali proje` (aynı eşik, önek proje adıyla ilişkili olmalı).",
        "",
        *(
            []
            if any("olcek" in p.parts for p in dosyalar)
            else [
                "v4 verisi (`veri/bin/olcek/`) bu girdide yok; 341 projenin tamamı için "
                "`python3 onek_denetim.py veri/bin/olcek/*.jsonl -o rapor/ONEK_DENETIM_V4.md` çalıştırılmalı.",
                "",
            ]
        ),
        "## Projeler",
        "",
        "| proje | ad | siklik öneki | proje kuralı öneki | yanlış kırpılan | çakışan hedef |",
        "|---|---:|---|---|---:|---:|",
    ]
    sirali = sorted(sonuc, key=lambda s: (-len(s["yanlis"]), s["proje"]))
    for s in sirali:
        if not (s["siklik"] or s["proje_kurali"]):
            continue
        md.append(
            f"| {s['proje']} | {s['ad']} | {', '.join(s['siklik']) or '-'} | "
            f"{', '.join(s['proje_kurali']) or '-'} | {len(s['yanlis'])} | {len(s['cakisma'])} |"
        )
    onksuz = sum(1 for s in sonuc if not (s["siklik"] or s["proje_kurali"]))
    md += ["", f"Tabloda olmayan {onksuz} projede iki kural da önek bulmuyor.", ""]
    if etkilenen:
        md += ["## Örnekler (gerçek ad → siklik kuralıyla hedef)", ""]
        for s in sirali:
            if s["yanlis"]:
                ornek = ", ".join(f"`{a}` → `{k}`" for a, k in s["ornek"])
                md.append(f"- **{s['proje']}** ({len(s['yanlis'])}/{s['ad']}): {ornek}")
        cakisan = [(s["proje"], c) for s in sirali for c in s["cakisma"] if s["yanlis"]]
        if cakisan:
            md += ["", "## Çakışmalar (kırpma sonrası aynı hedef)", ""]
            for p, c in cakisan[:20]:
                md.append(f"- {p}: {' / '.join(f'`{a}`' for a in c)}")
    return "\n".join(md) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dosyalar", nargs="*", type=Path)
    ap.add_argument("-o", "--cikti", type=Path, default=Path("rapor/ONEK_DENETIM.md"))
    a = ap.parse_args()
    dosyalar = sorted(a.dosyalar) or varsayilan_dosyalar()
    if not dosyalar:
        sys.exit("veri dosyası yok")
    sonuc = denetle(oku(dosyalar))
    a.cikti.parent.mkdir(parents=True, exist_ok=True)
    a.cikti.write_text(rapor(sonuc, dosyalar))
    yanlis = sum(len(s["yanlis"]) for s in sonuc)
    print(f"{len(sonuc)} proje, {yanlis} yanlış kırpılan ad → {a.cikti}")


if __name__ == "__main__":
    main()
