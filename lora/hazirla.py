#!/usr/bin/env python3
"""veri/*.jsonl → mlx-lm sohbet biçimi (lora/veri/{train,valid,test}.jsonl).

  .venv/bin/python lora/hazirla.py                                # rol'e göre: veri/egitim → train, veri/test.jsonl → test
  .venv/bin/python lora/hazirla.py --egitim zlib --test zlib --duman      # yalnız duman testi

Bölme PROJE bazlı: bir proje ya tamamen eğitimde ya tamamen testte.
Proje = satırdaki "proje" alanı, yoksa dosya adının gövdesi (veri/zlib.jsonl → zlib).
"""
import argparse, json, random, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SISTEM = ("Sen deneyimli bir tersine mühendissin. Sana sembolleri silinmiş bir x86-64 fonksiyonu "
          "(Intel sözdizimi) verilecek. Projenin iç fonksiyonları sub_XXXX diye gizlendi; dış "
          "kütüphane çağrıları görünür. Fonksiyonun asıl kaynak koddaki adını tahmin et. "
          'Yalnız JSON dön: {"ad": "fonksiyon_adi"}')


def oku(veri: Path) -> dict[str, list[dict]]:
    projeler: dict[str, list[dict]] = {}
    for yol in sorted(veri.glob("*/*.jsonl")):            # veri/egitim/<proje>.jsonl, veri/test/<proje>.jsonl
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


ONEK: dict[str, set[str]] = {}  # --onek-at verilirse proje → ad öneki (ozet.onekler)


def oneksiz(r: dict) -> str:
    """mbedtls_mpi_core_read → mpi_core_read, sqlite3VdbeMemSet → VdbeMemSet: model projenin önekini
    assembly'den bilemez; hedefte kalırsa küçük model anlam yerine önek ezberliyor."""
    ad = r["ad"]
    for p in sorted(ONEK.get(r.get("proje", ""), ()), key=len, reverse=True):
        yeni = re.sub(rf"^(?i:{re.escape(p)})_?", "", ad)
        if yeni and yeni != ad:
            return yeni
    return ad


def mesaj(r: dict, tavan: int, token_tavan: int = 0, ham: bool = False) -> dict:
    return {"messages": [{"role": "system", "content": SISTEM},
                         {"role": "user", "content": kes(r["asm"], tavan, token_tavan)},
                         {"role": "assistant", "content": json.dumps({"ad": r["ad"] if ham else oneksiz(r)}, ensure_ascii=False)}],
            "id": r["id"], "opt": r["opt"]}


def tekil(satirlar: list[dict]) -> list[dict]:
    # Aynı asm (ör. -O0/-O2'de özdeş ya da kopya fonksiyon) bir kez girer.
    goruldu, cikti = set(), []
    for r in satirlar:
        if r["asm"] not in goruldu:
            goruldu.add(r["asm"])
            cikti.append(r)
    return cikti


def yaz(yol: Path, satirlar: list[dict], tavan: int, token_tavan: int = 0, ham: bool = False):
    with yol.open("w") as f:
        for r in satirlar:
            f.write(json.dumps(mesaj(r, tavan, token_tavan, ham), ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--egitim", default="", help="virgüllü proje adları (vars. veri/egitim/ altındakiler)")
    ap.add_argument("--test", default="", help="virgüllü proje adları (vars. veri/test/ altındakiler)")
    ap.add_argument("--test-dosyasi", type=Path, default=Path("veri/test.jsonl"),
                    help="test satırları bu dosyadaki fonksiyonlarla sınırlanır (büyük modellerle aynı set)")
    ap.add_argument("--veri", type=Path, default=Path("veri"))
    ap.add_argument("--cikti", type=Path, default=Path("lora/veri"))
    ap.add_argument("--satir-tavan", type=int, default=200, help="asm en çok bu kadar satır")
    ap.add_argument("--token-tavan", type=int, default=1500,
                    help="asm en çok bu kadar token (0=kapalı); sistem+cevap payı için max-seq'ten ~500 az")
    ap.add_argument("--tokenizer", default="mlx-community/Qwen2.5-Coder-0.5B-Instruct-4bit")
    ap.add_argument("--valid-oran", type=float, default=0.05)
    ap.add_argument("--tohum", type=int, default=7)
    ap.add_argument("--onek-at", action="store_true", help="eğitim hedeflerinden proje önekini at (cyaml_, mbedtls_)")
    ap.add_argument("--proje-tavan", type=int, default=0, help="eğitimde proje başına en çok fonksiyon (0=sınırsız)")
    ap.add_argument("--duman", action="store_true", help="eğitim ve test aynı projeyse izin ver (YALNIZ duman testi)")
    a = ap.parse_args()

    egitim = [p for p in a.egitim.split(",") if p] or sorted(x.stem for x in (a.veri / "egitim").glob("*.jsonl"))
    test = [p for p in a.test.split(",") if p] or sorted(x.stem for x in (a.veri / "test").glob("*.jsonl"))
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

    global ONEK
    if a.onek_at:
        from ozet import onekler
        ONEK = onekler()
    rng = random.Random(a.tohum)
    tr = []
    for p in egitim:
        l = tekil(projeler[p])
        if a.proje_tavan and len(l) > a.proje_tavan:
            l = random.Random(f"{p}{a.tohum}").sample(l, a.proje_tavan)
        tr += l
    te = tekil([r for p in test for r in projeler[p]])
    if a.test_dosyasi and a.test_dosyasi.exists() and not a.duman:
        secili = {json.loads(l)["id"] for l in a.test_dosyasi.open()}
        te = [r for r in te if r["id"] in secili]
    rng.shuffle(tr)
    nv = max(1, round(len(tr) * a.valid_oran))
    va, tr = tr[:nv], tr[nv:]

    a.cikti.mkdir(parents=True, exist_ok=True)
    for ad, l in (("train", tr), ("valid", va), ("test", te)):
        # test hedefi hep gerçek ad: büyük modellerle aynı puanlama
        yaz(a.cikti / f"{ad}.jsonl", l, a.satir_tavan, a.token_tavan, ham=(ad == "test"))
    print(f"train {len(tr)}  valid {len(va)}  test {len(te)}  → {a.cikti}")


if __name__ == "__main__":
    main()
