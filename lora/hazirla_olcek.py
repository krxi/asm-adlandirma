#!/usr/bin/env python3
"""v4 ölçek verisini mlx-lm sohbet biçimine dönüştür.

  .venv/bin/python lora/hazirla_olcek.py --onek-at

Girdi bölümleri hazır proje ayrımını korur. Sızıntılı satırlar atılır; export
satırları tutulur. Eğitim kümesindeki proje/örnek tavanları tohumlu uygulanır.
"""
import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lora.hazirla as hazirla
from taban import kelimeler


BOLUM_DOSYALARI = {
    "train": "egitim.jsonl",
    "valid": "dogrulama.jsonl",
    "test": "test.jsonl",
}


def asm_normalize(asm: str) -> str:
    """Tekilleştirme için satır içi boşlukları normalize et; çıktıyı değiştirme."""
    return "\n".join(
        re.sub(r"[ \t]+", " ", satir.strip())
        for satir in asm.splitlines()
        if satir.strip()
    )


def oku(yol: Path) -> tuple[list[dict], dict[str, int]]:
    """Sızıntıyı ele, (proje, ad, normalize asm) tekrarlarını ilk kayda indir."""
    satirlar, goruldu = [], set()
    sayac = Counter()
    with yol.open(encoding="utf-8") as f:
        for no, satir in enumerate(f, 1):
            if not satir.strip():
                continue
            sayac["ham"] += 1
            r = json.loads(satir)
            if r.get("export") is True:
                sayac["export_ham"] += 1
            if r.get("sizinti") is True:
                sayac["sizinti"] += 1
                continue
            try:
                anahtar = (r["proje"], r["ad"], asm_normalize(r["asm"]))
            except KeyError as e:
                raise ValueError(f"{yol}:{no}: zorunlu alan yok: {e.args[0]}") from e
            if anahtar in goruldu:
                sayac["tekrar"] += 1
                continue
            goruldu.add(anahtar)
            satirlar.append(r)
            if r.get("export") is True:
                sayac["export_tekil"] += 1
    sayac["tekil"] = len(satirlar)
    return satirlar, dict(sayac)


def onekleri_bul(satirlar: list[dict]) -> dict[str, set[str]]:
    """ozet.onekler ile aynı kuralı bellekteki v4 projelerine uygula."""
    adlar = defaultdict(list)
    for r in satirlar:
        adlar[r["proje"]].append(kelimeler(r["ad"]))
    sonuc = {}
    for proje, proje_adlari in adlar.items():
        say = Counter(k[0] for k in proje_adlari if len(k) > 1)
        proje_kisa = proje.lower().replace("_", "").removeprefix("lib")

        def ilgili(k: str) -> bool:
            return proje_kisa.startswith(k.rstrip("0123456789")) or (
                len(k) <= 3 and proje_kisa.startswith(k[0])
            )

        sonuc[proje] = {
            k for k, n in say.items()
            if n >= 0.1 * len(proje_adlari) and ilgili(k)
        }
    return sonuc


def oneksiz(r: dict, onekler: dict[str, set[str]]) -> str:
    """hazirla.oneksiz ile aynı biçimde en uzun proje önekini hedef adından at."""
    ad = r["ad"]
    for onek in sorted(onekler.get(r["proje"], ()), key=len, reverse=True):
        yeni = re.sub(rf"^(?i:{re.escape(onek)})_?", "", ad)
        if yeni and yeni != ad:
            return yeni
    return ad


def girdileri_kirp(satirlar: list[dict], token_tavan: int) -> list[tuple[str, int]]:
    """Asm ve varsa bağlamı birleştir; sondan Qwen token tavanına kırp.

    Bağlam asm'den sonra geldiği için hazirla.girdi gibi önce bağlam feda edilir.
    Fast tokenizer toplu çağrılarla kullanılır; bu büyük ölçekte belirgin hız kazandırır.
    """
    metinler = []
    for r in satirlar:
        baglam = r.get("baglam", "")
        metinler.append(
            r["asm"] + (hazirla.BAGLAM_BASLIK + baglam if baglam else "")
        )
    kodlanan = hazirla.TOK(
        metinler, add_special_tokens=False, return_attention_mask=False
    )["input_ids"]
    sonuc = []
    for metin, tokenler in zip(metinler, kodlanan):
        if len(tokenler) <= token_tavan:
            sonuc.append((metin, len(tokenler)))
        else:
            kirpik = hazirla.TOK.decode(
                tokenler[:token_tavan],
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False,
            )
            sonuc.append((kirpik, token_tavan))
    return sonuc


def egitimi_ornekle(
    satirlar: list[dict], proje_tavan: int, max_ornek: int, tohum: int
) -> tuple[list[dict], int, int]:
    """Önce proje başına, sonra bütün eğitim kümesine tohumlu tavan uygula."""
    projeler = defaultdict(list)
    for r in satirlar:
        projeler[r["proje"]].append(r)

    cikti, proje_elenen = [], 0
    for proje in sorted(projeler):
        adaylar = projeler[proje]
        if proje_tavan and len(adaylar) > proje_tavan:
            secilen = random.Random(f"{proje}{tohum}").sample(adaylar, proje_tavan)
            proje_elenen += len(adaylar) - len(secilen)
        else:
            secilen = adaylar
        cikti.extend(secilen)

    rng = random.Random(tohum)
    rng.shuffle(cikti)
    max_elenen = 0
    if max_ornek and len(cikti) > max_ornek:
        max_elenen = len(cikti) - max_ornek
        cikti = cikti[:max_ornek]
    return cikti, proje_elenen, max_elenen


def mesaj(r: dict, hedef: str, girdi: str, meta: bool) -> dict:
    sonuc = {
        "messages": [
            {"role": "system", "content": hazirla.SISTEM},
            {"role": "user", "content": girdi},
            {"role": "assistant", "content": json.dumps({"ad": hedef}, ensure_ascii=False)},
        ]
    }
    if meta:
        sonuc.update({"id": r["id"], "opt": r["opt"], "proje": r["proje"]})
    return sonuc


def yuzdelik95(sayilar: list[int]) -> int:
    return sorted(sayilar)[max(0, (95 * len(sayilar) + 99) // 100 - 1)]


def yaz(
    yol: Path,
    satirlar: list[dict],
    token_tavan: int,
    onekler: dict[str, set[str]],
    onek_at: bool,
    meta: bool,
) -> tuple[float, int, int]:
    tokenler = []
    with yol.open("w", encoding="utf-8") as f:
        for bas in range(0, len(satirlar), 512):
            yigin = satirlar[bas:bas + 512]
            girdiler = girdileri_kirp(yigin, token_tavan)
            for r, (girdi, token) in zip(yigin, girdiler):
                hedef = oneksiz(r, onekler) if onek_at else r["ad"]
                kayit = mesaj(r, hedef, girdi, meta)
                f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
                tokenler.append(token)
    if not tokenler:
        return 0.0, 0, 0
    return sum(tokenler) / len(tokenler), yuzdelik95(tokenler), sum(tokenler)


def eval115_oku(yol: Path) -> list[dict]:
    satirlar = []
    with yol.open(encoding="utf-8") as f:
        for no, satir in enumerate(f, 1):
            if not satir.strip():
                continue
            r = json.loads(satir)
            for alan in ("id", "proje", "opt", "ad", "asm"):
                if alan not in r:
                    raise ValueError(f"{yol}:{no}: zorunlu alan yok: {alan}")
            satirlar.append(r)
    return satirlar


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--veri", type=Path, default=Path("veri/bin/olcek"))
    ap.add_argument("--cikti", type=Path, default=Path("lora/veri-olcek"))
    ap.add_argument("--eval115", type=Path, default=Path("veri/test.jsonl"))
    ap.add_argument("--token-tavan", type=int, default=2000,
                    help="asm+bağlam en çok bu kadar Qwen tokenı")
    ap.add_argument("--tokenizer", default="mlx-community/Qwen2.5-Coder-0.5B-Instruct-4bit")
    ap.add_argument("--yalniz-yerel", action="store_true",
                    help="tokenizer için Hugging Face ağına başvurma")
    ap.add_argument("--proje-tavan", type=int, default=2000,
                    help="eğitimde proje başına en çok örnek (0=sınırsız)")
    ap.add_argument("--max-ornek", type=int, default=0,
                    help="toplam eğitim örneği tavanı (0=hepsi)")
    ap.add_argument("--tohum", type=int, default=7)
    ap.add_argument("--onek-at", action="store_true",
                    help="eğitim/valid hedeflerinden proje önekini at")
    a = ap.parse_args()

    if a.token_tavan <= 0:
        ap.error("--token-tavan sıfırdan büyük olmalı")
    if a.proje_tavan < 0 or a.max_ornek < 0:
        ap.error("örnek tavanları negatif olamaz")

    from transformers import AutoTokenizer

    hazirla.TOK = AutoTokenizer.from_pretrained(
        a.tokenizer, use_fast=True, local_files_only=a.yalniz_yerel
    )

    bolumler, sayaclar = {}, {}
    for bolum, dosya in BOLUM_DOSYALARI.items():
        yol = a.veri / dosya
        if not yol.is_file():
            sys.exit(f"veri dosyası yok: {yol}")
        bolumler[bolum], sayaclar[bolum] = oku(yol)

    proje_kumeleri = {ad: {r["proje"] for r in satirlar} for ad, satirlar in bolumler.items()}
    for sol, sag in (("train", "valid"), ("train", "test"), ("valid", "test")):
        ortak = proje_kumeleri[sol] & proje_kumeleri[sag]
        if ortak:
            sys.exit(f"proje sızıntısı: {sol}/{sag}: {sorted(ortak)}")

    tumu = [r for satirlar in bolumler.values() for r in satirlar]
    onekler = onekleri_bul(tumu) if a.onek_at else {}
    bolumler["train"], proje_elenen, max_elenen = egitimi_ornekle(
        bolumler["train"], a.proje_tavan, a.max_ornek, a.tohum
    )

    a.cikti.mkdir(parents=True, exist_ok=True)
    for bolum in ("train", "valid", "test"):
        ort, p95, toplam = yaz(
            a.cikti / f"{bolum}.jsonl",
            bolumler[bolum],
            a.token_tavan,
            onekler,
            a.onek_at and bolum != "test",
            meta=bolum == "test",
        )
        s = sayaclar[bolum]
        print(
            f"{bolum:>5}: ham {s['ham']}, sızıntı -{s.get('sizinti', 0)}, "
            f"tekrar -{s.get('tekrar', 0)}, çıktı {len(bolumler[bolum])}, "
            f"export {s.get('export_ham', 0)} ham/{s.get('export_tekil', 0)} filtre sonrası/"
            f"{sum(r.get('export') is True for r in bolumler[bolum])} çıktıda; "
            f"token ort {ort:.1f}, p95 {p95}, toplam {toplam}"
        )

    eval115 = eval115_oku(a.eval115)
    ort, p95, toplam = yaz(
        a.cikti / "eval115.jsonl", eval115, a.token_tavan, {}, False, meta=True
    )
    print(
        f"eval115: çıktı {len(eval115)}; token ort {ort:.1f}, p95 {p95}, toplam {toplam}"
    )
    print(
        f"eğitim örnekleme: proje tavanı -{proje_elenen}, max örnek -{max_elenen}; "
        f"önek atılan proje {sum(bool(x) for x in onekler.values())}; → {a.cikti}"
    )


if __name__ == "__main__":
    main()
