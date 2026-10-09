#!/usr/bin/env python3
"""Repodaki veri/test/*.jsonl'den küçük, belirlenimci bir örnek veri ağacı kur.

Testler ve CI duman adımı büyük, git dışı veriye (veri/egitim, veri/bin/olcek) ihtiyaç duymadan
veri hattını uçtan uca çalıştırabilsin diye:

  python3 tests/ornek.py /tmp/ornek      # → /tmp/ornek/veri/{egitim,test,aciklama,bin/olcek}

Gerçek ayrımı taklit etmez; yalnız biçimi ve proje bazlı bölmeyi korur.
"""
import json, sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
KAYNAK = KOK / "veri" / "test"

# rol → projeler. Eğitim/test projeleri ayrık; tomlc17'de sizinti satırları var (test_seti eler).
EGITIM = ("cyaml", "sajs")
DOGRULAMA = ("mu_json_x",)
TEST = ("tomlc17", "picomatch")
PROJE_BASINA = 8  # her (proje, opt) için en kısa bu kadar satır + varsa sizinti satırları


def sec(proje: str) -> list[dict]:
    satirlar = [json.loads(l) for l in (KAYNAK / f"{proje}.jsonl").open() if l.strip()]
    secilen = []
    for opt in ("-O0", "-O2"):
        # Kısa asm: dosyalar küçük kalsın. Bağlamlı ve bağlamsız satırların ikisi de girsin.
        havuz = sorted((r for r in satirlar if r["opt"] == opt and not r["sizinti"]),
                       key=lambda r: (len(r["asm"]), r["id"]))
        baglamli = [r for r in havuz if r.get("baglam")][: PROJE_BASINA // 2]
        baglamsiz = [r for r in havuz if not r.get("baglam")][: PROJE_BASINA - len(baglamli)]
        secilen += baglamli + baglamsiz
    secilen += sorted((r for r in satirlar if r["sizinti"]), key=lambda r: len(r["asm"]))[:2]
    return secilen


def yaz(yol: Path, satirlar: list[dict]):
    yol.parent.mkdir(parents=True, exist_ok=True)
    with yol.open("w") as f:
        for r in satirlar:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def kur(hedef: Path) -> dict[str, list[dict]]:
    """hedef/veri altına örnek ağacı yaz; rol → satırlar döner."""
    veri = Path(hedef) / "veri"
    roller = {"egitim": [], "dogrulama": [], "test": []}
    for rol, projeler in (("egitim", EGITIM), ("dogrulama", DOGRULAMA), ("test", TEST)):
        for p in projeler:
            satirlar = sec(p)
            roller[rol] += satirlar
            # v3 düzeni (lora/hazirla.py, test_seti.py): doğrulama projeleri ayrı dizinde değil.
            if rol != "dogrulama":
                yaz(veri / rol / f"{p}.jsonl", satirlar)
    # v4 düzeni (lora/hazirla_olcek.py): rol başına tek dosya.
    for rol, satirlar in roller.items():
        yaz(veri / "bin" / "olcek" / f"{rol}.jsonl", satirlar)
    # Öğretmen açıklamaları (lora/hazirla.py --aciklama): eğitim satırlarının yarısına.
    for p in EGITIM:
        satirlar = [r for r in roller["egitim"] if r["proje"] == p][::2]
        yaz(veri / "aciklama" / f"{p}.jsonl",
            [{"id": r["id"], "aciklama": f"{r['ad']} için örnek açıklama."} for r in satirlar])
    return roller


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("kullanım: python3 tests/ornek.py <hedef-dizin>")
    roller = kur(Path(sys.argv[1]))
    print(json.dumps({rol: len(s) for rol, s in roller.items()}))
