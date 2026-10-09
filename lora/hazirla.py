#!/usr/bin/env python3
"""veri/*.jsonl → mlx-lm sohbet biçimi (lora/veri/{train,valid,test}.jsonl).

  .venv/bin/python lora/hazirla.py --baglam ozet --onek-at         # çağrı özetli eğitim
  .venv/bin/python lora/hazirla.py --egitim zlib --test zlib --duman      # yalnız duman testi

Bölme PROJE bazlı: bir proje ya tamamen eğitimde ya tamamen testte.
Proje = satırdaki "proje" alanı, yoksa dosya adının gövdesi (veri/zlib.jsonl → zlib).
"""
import argparse, json, random, re, sys
from pathlib import Path
from typing import Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SISTEM = ("Sen deneyimli bir tersine mühendissin. Sana sembolleri silinmiş bir x86-64 fonksiyonu "
          "(Intel sözdizimi) verilecek. Projenin iç fonksiyonları sub_XXXX diye gizlendi; dış "
          "kütüphane çağrıları görünür. Fonksiyonun asıl kaynak koddaki adını tahmin et. "
          'Yalnız JSON dön: {"ad": "fonksiyon_adi"}')
SISTEM_ACIKLAMA = SISTEM[:-1] + ', "aciklama": "tek cümle Türkçe"}'
SISTEM_V5 = (
    "Sen deneyimli bir tersine mühendissin. Sana sembolleri silinmiş bir x86-64 fonksiyonu "
    "(Intel sözdizimi) ve varsa çağrı bağlamı verilecek. İç fonksiyonlar sub_XXXX diye gizlendi; "
    "dış kütüphane çağrıları görünür. Önce fonksiyonun ne yaptığını tek cümle İngilizce açıkla, "
    "sonra asıl kaynak adını snake_case veya kaynak stilinde bir tanımlayıcı olarak tahmin et, "
    "sonra tek cümle Türkçe açıkla. Yalnız bu sırada JSON dön: "
    '{"aciklama_en": "Reads a record from the stream.", "ad": "read_record", '
    '"aciklama": "Akıştan bir kayıt okur."}'
)
BAGLAM_BASLIK = "\n\n; --- çağrılan fonksiyonlar ---\n"


def oku(veri: Path) -> dict[str, list[dict]]:
    projeler: dict[str, list[dict]] = {}
    for yol in sorted([*veri.glob("egitim/*.jsonl"), *veri.glob("test/*.jsonl")]):  # veri/egitim/<proje>.jsonl, veri/test/<proje>.jsonl
        for l in yol.open():
            if l.strip():
                r = json.loads(l)
                projeler.setdefault(r.get("proje") or yol.stem, []).append(r)
    return projeler


TOK = None  # --token-tavan verilirse tokenizer


def kes(asm: str, tavan: int) -> str:
    satirlar = asm.split("\n")
    kesildi = len(satirlar) > tavan
    satirlar = satirlar[:tavan]
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


def baglam_metni(r: dict, kip: str) -> str:
    if kip == "yok":
        return ""
    if kip == "derin":
        return r.get("baglam_derin") or r.get("baglam", "")
    return r.get("baglam", "")


def girdi(r: dict, kip: str, satir_tavan: int, token_tavan: int = 0) -> str:
    """Asm korunur; token tavanına önce ek bağlam feda edilerek uyulur."""
    asm = kes(r["asm"], satir_tavan)
    baglam = baglam_metni(r, kip)
    kesildi = False
    if TOK and token_tavan:
        while baglam and len(TOK.encode(asm + BAGLAM_BASLIK + baglam)) > token_tavan:
            yeni = baglam[:max(0, int(len(baglam) * 0.9))]
            if "\n" in yeni:
                yeni = yeni.rsplit("\n", 1)[0]
            if yeni == baglam:  # Tek satır/tek karakter bağlamda döngüye girme.
                yeni = baglam[:-1]
            baglam = yeni
            kesildi = True
        # Çok büyük tek bir fonksiyonda bağlam yokken de cevap için yer kalmalı.
        satirlar = asm.split("\n")
        while len(satirlar) > 1 and len(TOK.encode("\n".join(satirlar))) > token_tavan:
            satirlar = satirlar[:max(1, int(len(satirlar) * 0.9))]
            kesildi = True
        asm = "\n".join(satirlar)
    if baglam:
        if kesildi and (not TOK or not token_tavan or
                         len(TOK.encode(asm + BAGLAM_BASLIK + baglam + "\n; ... bağlam kesildi")) <= token_tavan):
            baglam += "\n; ... bağlam kesildi"
        return asm + BAGLAM_BASLIK + baglam
    return asm


def mesaj(r: dict, tavan: int, token_tavan: int = 0, ham: bool = False,
          baglam: str = "yok", aciklamalar: Optional[Dict[str, str]] = None) -> dict:
    ad = r["ad"] if ham else oneksiz(r)
    aciklama = (aciklamalar or {}).get(r["id"])
    hedef = {"ad": ad}
    if aciklama is not None:
        hedef["aciklama"] = aciklama
    return {"messages": [{"role": "system", "content": SISTEM_ACIKLAMA if aciklama is not None else SISTEM},
                         {"role": "user", "content": girdi(r, baglam, tavan, token_tavan)},
                         {"role": "assistant", "content": json.dumps(hedef, ensure_ascii=False)}],
            # mlx-lm bilinmeyen alanları yok sayar; olc.py bunlarla bağlam kipini değiştirebilir.
            "id": r["id"], "opt": r["opt"], "asm": r["asm"], "baglam": r.get("baglam", ""),
            "baglam_derin": r.get("baglam_derin", "")}


def tekil(satirlar: list[dict]) -> list[dict]:
    # Aynı asm (ör. -O0/-O2'de özdeş ya da kopya fonksiyon) bir kez girer.
    goruldu, cikti = set(), []
    for r in satirlar:
        if r["asm"] not in goruldu:
            goruldu.add(r["asm"])
            cikti.append(r)
    return cikti


def yaz(yol: Path, satirlar: list[dict], tavan: int, token_tavan: int = 0, ham: bool = False,
        baglam: str = "yok", aciklamalar: Optional[Dict[str, str]] = None):
    with yol.open("w") as f:
        for r in satirlar:
            f.write(json.dumps(mesaj(r, tavan, token_tavan, ham, baglam, aciklamalar), ensure_ascii=False) + "\n")


def aciklamalari_oku(veri: Path, projeler: list[str]) -> dict[str, str]:
    """veri/aciklama/<proje>.jsonl içindeki id → açıklama eşlemesini oku."""
    sonuc = {}
    for proje in projeler:
        yol = veri / "aciklama" / f"{proje}.jsonl"
        if not yol.exists():
            continue
        for l in yol.open():
            if l.strip():
                r = json.loads(l)
                if r.get("id") and "aciklama" in r:
                    sonuc[r["id"]] = r["aciklama"]
    return sonuc


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
                    help="asm+bağlam en çok bu kadar token (0=kapalı); sistem+cevap payı için max-seq'ten ~500 az")
    ap.add_argument("--tokenizer", default="mlx-community/Qwen2.5-Coder-0.5B-Instruct-4bit")
    ap.add_argument("--valid-oran", type=float, default=0.05)
    ap.add_argument("--tohum", type=int, default=7)
    ap.add_argument("--onek-at", action="store_true", help="eğitim hedeflerinden proje önekini at (cyaml_, mbedtls_)")
    ap.add_argument("--proje-tavan", type=int, default=0, help="eğitimde proje başına en çok fonksiyon (0=sınırsız)")
    ap.add_argument("--baglam", choices=("yok", "ozet", "derin"), default="yok",
                    help="asm'ye çağrılan fonksiyonların yok/özet/derin bağlamını ekle")
    ap.add_argument("--aciklama", action="store_true", help="varsa veri/aciklama/<proje>.jsonl açıklamasını hedefe ekle")
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
    aciklamalar = aciklamalari_oku(a.veri, egitim + test) if a.aciklama else {}
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
        yaz(a.cikti / f"{ad}.jsonl", l, a.satir_tavan, a.token_tavan, ham=(ad == "test"),
            baglam=a.baglam, aciklamalar=aciklamalar)
    print(f"train {len(tr)}  valid {len(va)}  test {len(te)}  → {a.cikti}")


if __name__ == "__main__":
    main()
