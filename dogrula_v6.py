#!/usr/bin/env python3
"""Yeniden üretilen v6 satırlarını sabit v4 ölçek verisi ve ikili eşlemeleriyle doğrula.

Örnek:
  python3 dogrula_v6.py --ad zlib lua tomlc17 codegraph tmux
  python3 dogrula_v6.py

Yalnız asm'si birebir aynı ve ikili eşlemesi bulunan kimlikler ``--idler`` altında
proje başına yazılır. Böylece bu listelerle çalışan decompile koluna uyumsuz satır girmez.
"""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path


ROLLER = ("egitim", "dogrulama", "test")


def jsonl(yol):
    with Path(yol).open() as f:
        for no, satir in enumerate(f, 1):
            if satir.strip():
                try:
                    yield json.loads(satir)
                except json.JSONDecodeError as e:
                    raise SystemExit(f"{yol}:{no}: geçersiz JSON: {e}") from e


def asm_ozeti(metin):
    return hashlib.sha256(metin.encode()).digest()


def dogrula(hedef_kok, ham_kok, ikili_kok, adlar=None):
    adlar = set(adlar) if adlar else None
    beklenen, sira, proje_rolu = {}, defaultdict(list), {}
    for rol in ROLLER:
        yol = Path(hedef_kok) / f"{rol}.jsonl"
        for r in jsonl(yol):
            proje = r["proje"]
            if adlar is not None and proje not in adlar:
                continue
            kimlik = r["id"]
            if kimlik in beklenen:
                raise SystemExit(f"hedef veride yinelenen id: {kimlik}")
            beklenen[kimlik] = (proje, asm_ozeti(r["asm"]))
            sira[proje].append(kimlik)
            proje_rolu[proje] = rol

    bulunan, ayni, yeni_gorulen = set(), set(), set()
    for yol in sorted((Path(ham_kok) / "ham").glob("*/*.jsonl")):
        if adlar is not None and yol.stem not in adlar:
            continue
        for r in jsonl(yol):
            kimlik = r.get("id")
            if kimlik not in beklenen:
                continue
            if kimlik in yeni_gorulen:
                raise SystemExit(f"yeniden üretilen veride yinelenen id: {kimlik}")
            yeni_gorulen.add(kimlik)
            bulunan.add(kimlik)
            if asm_ozeti(r["asm"]) == beklenen[kimlik][1]:
                ayni.add(kimlik)

    eslemeli = set()
    for yol in sorted(Path(ikili_kok).glob("**/*.jsonl")):
        for r in jsonl(yol):
            kimlik = r.get("id")
            if kimlik in beklenen:
                if kimlik in eslemeli:
                    raise SystemExit(f"ikili eşlemelerinde yinelenen id: {kimlik}")
                eslemeli.add(kimlik)

    proje = {}
    for ad in sorted(sira):
        ids = set(sira[ad])
        proje[ad] = {
            "rol": proje_rolu[ad],
            "hedef": len(ids),
            "id_eslesen": len(ids & bulunan),
            "asm_ayni": len(ids & ayni),
            "id_eksik": len(ids - bulunan),
            "asm_uyusmaz": len((ids & bulunan) - ayni),
            "esleme_eksik": len(ids - eslemeli),
            "decompile_hazir": len(ids & ayni & eslemeli),
        }
    sonuc = {
        "hedef_satir": len(beklenen),
        "eslesen_id": len(bulunan),
        "asm_birebir_ayni": len(ayni),
        "esleme_bulunamayan_id": len(set(beklenen) - eslemeli),
        "decompile_hazir": len(ayni & eslemeli),
        "proje_sayisi": len(sira),
        "eksigi_olan_proje": sum(any(v[k] for k in ("id_eksik", "asm_uyusmaz", "esleme_eksik"))
                                  for v in proje.values()),
        "proje": proje,
    }
    return sonuc, beklenen, sira, bulunan, ayni, eslemeli


def ciktilari_yaz(sonuc, beklenen, sira, bulunan, ayni, eslemeli,
                   rapor_yolu, uyusmaz_yolu, id_dizini, sira_yolu=None):
    rapor_yolu = Path(rapor_yolu)
    rapor_yolu.parent.mkdir(parents=True, exist_ok=True)
    rapor_yolu.write_text(json.dumps(sonuc, ensure_ascii=False, indent=2) + "\n")

    uyusmaz_yolu = Path(uyusmaz_yolu)
    uyusmaz_yolu.parent.mkdir(parents=True, exist_ok=True)
    with uyusmaz_yolu.open("w") as f:
        for kimlik, (proje, _) in beklenen.items():
            if kimlik in bulunan and kimlik not in ayni:
                f.write(json.dumps({"id": kimlik, "proje": proje,
                                    "neden": "asm_uyusmaz"}, ensure_ascii=False) + "\n")

    id_dizini = Path(id_dizini)
    id_dizini.mkdir(parents=True, exist_ok=True)
    for proje, kimlikler in sira.items():
        uygun = [x for x in kimlikler if x in ayni and x in eslemeli]
        (id_dizini / f"{proje}.txt").write_text("".join(x + "\n" for x in uygun))
    if sira_yolu is not None:
        sira_yolu = Path(sira_yolu)
        sira_yolu.parent.mkdir(parents=True, exist_ok=True)
        oncelik = {"test": 0, "dogrulama": 1, "egitim": 2}
        projeler = sorted(sonuc["proje"],
                          key=lambda p: (oncelik[sonuc["proje"][p]["rol"]], p))
        sira_yolu.write_text("".join(p + "\n" for p in projeler))


def kisitli_idleri_yaz(kisit_yolu, id_dizini, cikti_dizini, sira_yolu):
    """Doğrulanmış ID listelerinden, verilen sırayı koruyan küçük bir alt kuyruk üret."""
    istenen = [x.strip() for x in Path(kisit_yolu).read_text().splitlines() if x.strip()]
    hangi = {}
    for yol in sorted(Path(id_dizini).glob("*.txt")):
        for kimlik in yol.read_text().splitlines():
            hangi[kimlik] = yol.stem
    eksik = [x for x in istenen if x not in hangi]
    if eksik:
        raise SystemExit(f"kısıt listesindeki doğrulanmamış/eksik id: {len(eksik)}; ilk: {eksik[0]}")
    gruplar, proje_sirasi = defaultdict(list), []
    for kimlik in istenen:
        proje = hangi[kimlik]
        if proje not in gruplar:
            proje_sirasi.append(proje)
        gruplar[proje].append(kimlik)
    cikti_dizini = Path(cikti_dizini)
    cikti_dizini.mkdir(parents=True, exist_ok=True)
    for proje, kimlikler in gruplar.items():
        (cikti_dizini / f"{proje}.txt").write_text("".join(x + "\n" for x in kimlikler))
    sira_yolu = Path(sira_yolu)
    sira_yolu.parent.mkdir(parents=True, exist_ok=True)
    sira_yolu.write_text("".join(x + "\n" for x in proje_sirasi))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hedef", type=Path, default=Path("veri/bin/olcek"))
    ap.add_argument("--ham", type=Path, default=Path("veri/olcek-v6"))
    ap.add_argument("--ikili", type=Path, default=Path("veri/ikili-v6"))
    ap.add_argument("--rapor", type=Path, default=Path("veri/olcek-v6/dogrulama.json"))
    ap.add_argument("--asm-uyusmaz", type=Path,
                    default=Path("veri/olcek-v6/asm-uyusmaz.jsonl"))
    ap.add_argument("--idler", type=Path, default=Path("veri/olcek-v6/decompile-id"))
    ap.add_argument("--sira", type=Path, default=Path("veri/olcek-v6/decompile-sira.txt"),
                    help="test, doğrulama, eğitim öncelikli proje kuyruğu")
    ap.add_argument("--ad", nargs="*")
    ap.add_argument("--kisit-id", type=Path,
                    help="doğrulanmış ID'lerden ayrıca üretilecek alt kuyruk")
    ap.add_argument("--kisit-idler", type=Path,
                    default=Path("veri/olcek-v6/test2000-id"))
    ap.add_argument("--kisit-sira", type=Path,
                    default=Path("veri/olcek-v6/test2000-sira.txt"))
    a = ap.parse_args()
    veriler = dogrula(a.hedef, a.ham, a.ikili, a.ad)
    ciktilari_yaz(*veriler, a.rapor, a.asm_uyusmaz, a.idler, a.sira)
    if a.kisit_id is not None:
        kisitli_idleri_yaz(a.kisit_id, a.idler, a.kisit_idler, a.kisit_sira)
    sonuc = veriler[0]
    print(json.dumps({k: v for k, v in sonuc.items() if k != "proje"},
                     ensure_ascii=False, indent=2))
    eksikler = {k: v for k, v in sonuc["proje"].items()
                if any(v[x] for x in ("id_eksik", "asm_uyusmaz", "esleme_eksik"))}
    if eksikler:
        print("proje bazında eksikler:")
        for ad, v in eksikler.items():
            print(f"  {ad}: id_eksik={v['id_eksik']} asm_uyusmaz={v['asm_uyusmaz']} "
                  f"esleme_eksik={v['esleme_eksik']}")


if __name__ == "__main__":
    main()
