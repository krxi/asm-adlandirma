#!/usr/bin/env python3
"""v5'in aynı 300 kimliğinde, aynı 0/1/2 hakem istemiyle v6 açıklama ölçümü."""
import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import aciklama_puan as hakem
from aciklama_degerlendir import bootstrap_farki
from olcum_v6 import KOK, iz, oku
from taban import f1

V5_PUAN = KOK / "sonuc/test2000-molab-qwen3-8b-v5-puan.jsonl"


def anahtar(r):
    return f"{r['id'].split(':')[0]}:{r['gercek']}"


def istemleri_hazirla(tahmin_yol, v5_puan_yol, kaynak_dizin, ref_yol, model):
    tahmin, onceki = oku(tahmin_yol), oku(v5_puan_yol)
    if set(onceki) - set(tahmin):
        raise ValueError("v5 açıklama örnekleminin tüm kimlikleri tahminde olmalı")
    kaynak = {}
    for yol in sorted(Path(kaynak_dizin).glob("*.jsonl")):
        with yol.open(encoding="utf-8") as dosya:
            for line in dosya:
                if line.strip():
                    r = json.loads(line)
                    if r["anahtar"] in kaynak and kaynak[r["anahtar"]] != r["kaynak"]:
                        raise ValueError("Aynı anahtarda çelişen C kaynakları")
                    kaynak[r["anahtar"]] = r["kaynak"]
    with Path(ref_yol).open(encoding="utf-8") as dosya:
        refs = [json.loads(line) for line in dosya if line.strip()]
    ref = {}
    for r in refs:
        if r["anahtar"] in ref and ref[r["anahtar"]] != r["aciklama"]:
            raise ValueError("Aynı anahtarda çelişen referanslar")
        ref[r["anahtar"]] = r["aciklama"]
    jobs = []
    for kimlik in onceki:
        r = tahmin[kimlik]
        k = anahtar(r)
        if k not in kaynak or k not in ref:
            raise ValueError(f"{kimlik}: C kaynak veya öğretmen referansı eksik; örneklem filtrelenmez")
        if r["gercek"] != kimlik.rsplit(":", 1)[-1]:
            raise ValueError(f"{kimlik}: gerçek ad kimlikle uyuşmuyor")
        for dil, alan in (("tr", "aciklama"), ("en", "aciklama_en")):
            govde = hakem.istem({"aciklama": r.get(alan)}, kaynak[k][:12000], ref[k], model)
            jobs.append({"id": kimlik, "dil": dil, "f1": f1(r["tahmin"], r["gercek"]),
                         "istem": govde, "istem_sha256": hashlib.sha256(
                             json.dumps(govde, ensure_ascii=False, sort_keys=True).encode()).hexdigest()})
    return jobs


def puanla(jobs, cikti, paralel):
    if not 1 <= paralel <= 16:
        raise ValueError("Hakem eşzamanlılık 1..16 olmalı")
    def is_(job):
        return job, hakem.sor(job["istem"])
    rows = {}
    with ThreadPoolExecutor(paralel) as pool:
        for job, score in pool.map(is_, jobs):
            r = rows.setdefault(job["id"], {"id": job["id"], "f1": job["f1"],
                                            "hakem": job["istem"]["model"]})
            dil = job["dil"]
            r.update({f"puan_{dil}": score["puan"], f"gerekce_{dil}": score["gerekce"],
                      f"istem_sha256_{dil}": job["istem_sha256"]})
    Path(cikti).parent.mkdir(parents=True, exist_ok=True)
    Path(cikti).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows.values()), encoding="utf-8")


def ozet(puan_yol, v5_yol=V5_PUAN, tekrar=2000):
    aday, v5 = oku(puan_yol), oku(v5_yol)
    if set(aday) != set(v5):
        raise ValueError("Açıklama puanları v5 ile aynı kimlik kümesi olmalı; hata satırlarını silmeyin")
    sonuc = {"girdiler": {"aday": iz(puan_yol), "v5": iz(v5_yol)}, "hedef_en": 0.25,
             "v5_yayin_en": 0.20, "diller": {},
             "protokol": "v5 ile aynı kimlikler, mimo-v2.6-pro varsayılan, C ilk 12000 karakter, aynı istem; puan=2 doğru"}
    ids = sorted(aday)
    for dil in ("tr", "en"):
        a, b = [aday[k].get(f"puan_{dil}") for k in ids], [v5[k].get(f"puan_{dil}") for k in ids]
        if any(p is not None and (type(p) is not int or p not in (0, 1, 2)) for p in a + b):
            raise ValueError("Puan 0, 1, 2 veya null olmalı")
        valid = [p for p in a if p is not None]
        bv = [p for p in b if p is not None]
        iyi = [aday[k]["f1"] for k in ids if aday[k].get(f"puan_{dil}") == 2]
        kotu = [aday[k]["f1"] for k in ids if aday[k].get(f"puan_{dil}") == 0]
        # Hatalar yanlış diye etiketlenmez; tam örneklem doğru oranında başarı değildir.
        s = {"n": len(a), "puanlanan": len(valid), "hata": len(a) - len(valid),
             "ortalama": sum(valid) / len(valid) if valid else None,
             "dogru_orani": a.count(2) / len(a),
             "tam_karar_dogru_orani": valid.count(2) / len(valid) if valid else None,
             "kismen_orani": a.count(1) / len(a), "yanlis_orani": a.count(0) / len(a),
             "v5_dogru_orani": b.count(2) / len(b),
             "v5_tam_karar_dogru_orani": bv.count(2) / len(bv) if bv else None,
             "v5_hata": len(b) - len(bv),
             "ad_f1_dogru": sum(iyi) / len(iyi) if iyi else None,
             "ad_f1_yanlis": sum(kotu) / len(kotu) if kotu else None}
        s.update(bootstrap_farki([int(p == 2) for p in a], [int(p == 2) for p in b],
                                [k.split('/')[0] for k in ids], 42, tekrar))
        s["hedef_gecildi"] = dil == "en" and not s["hata"] and s["dogru_orani"] >= 0.25
        sonuc["diller"][dil] = s
    return sonuc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="komut", required=True)
    score = sub.add_parser("puan", help="Hakemle puanla veya --kuru ile gerçek istemleri dışarı yaz")
    score.add_argument("tahmin", type=Path)
    score.add_argument("--kaynak", type=Path, default=KOK / "veri/kaynak-v4")
    score.add_argument("--referans", type=Path, default=KOK / "veri/aciklama-v4/codex.jsonl")
    score.add_argument("--model", default="mimo-v2.6-pro")
    score.add_argument("-j", type=int, default=8)
    score.add_argument("--kuru", action="store_true")
    summary = sub.add_parser("ozet", help="Var olan puanları oku; hakem çağırmaz")
    summary.add_argument("puanlar", type=Path)
    for parser in (score, summary):
        parser.add_argument("--v5-puan", type=Path, default=V5_PUAN)
        parser.add_argument("-o", "--cikti", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        if a.komut == "puan":
            jobs = istemleri_hazirla(a.tahmin, a.v5_puan, a.kaynak, a.referans, a.model)
            if a.kuru:
                a.cikti.parent.mkdir(parents=True, exist_ok=True)
                a.cikti.write_text("".join(json.dumps(j, ensure_ascii=False) + "\n" for j in jobs), encoding="utf-8")
                print(json.dumps({"kuru": True, "kimlik": len(jobs) // 2, "istem": len(jobs), "hakem": a.model}))
                return
            puanla(jobs, a.cikti, a.j)
            print(json.dumps(ozet(a.cikti, a.v5_puan), ensure_ascii=False, indent=2))
        else:
            sonuc = ozet(a.puanlar, a.v5_puan)
            metin = json.dumps(sonuc, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
            a.cikti.parent.mkdir(parents=True, exist_ok=True)
            a.cikti.write_text(metin, encoding="utf-8")
            print(metin, end="")
    except (ValueError, OSError) as hata:
        ap.exit(1, f"HATA: {hata}\n")


if __name__ == "__main__":
    main()
