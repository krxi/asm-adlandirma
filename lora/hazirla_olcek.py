#!/usr/bin/env python3
"""Ölçeklenmiş v4 verisi (veri/bin/olcek/{egitim,dogrulama,test}.jsonl) → sohbet biçimi.

  .venv/bin/python lora/hazirla_olcek.py --cikti lora/veri-olcek --baglam ozet --proje-tavan 1500

Biçim lora/hazirla.py ile aynı ({"messages": [system, user, assistant], id, opt, ...}).
Ayrım olcekle.py'den gelir ve proje bazlıdır: valid = doğrulama projeleri, test = az bilinen projeler.
Önek atma: projedeki adların ≥%30'u aynı "xxx_" önekiyle başlıyorsa hedeften atılır.
"""
import argparse, json, random, re, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hazirla as h


def onekler(satirlar):
    adlar = defaultdict(set)
    for r in satirlar:
        adlar[r["proje"]].add(r["ad"])
    sonuc = {}
    for proje, ads in adlar.items():
        say = Counter(m.group(1).lower() for a in ads if (m := re.match(r"^([A-Za-z][A-Za-z0-9]{1,11})_", a)))
        if say and (en := say.most_common(1)[0])[1] >= 0.3 * len(ads) and en[1] >= 5:
            sonuc[proje] = {en[0]}
    return sonuc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--veri", type=Path, default=Path("veri/bin/olcek"))
    ap.add_argument("--cikti", type=Path, default=Path("lora/veri-olcek"))
    ap.add_argument("--baglam", choices=("yok", "ozet"), default="ozet")
    ap.add_argument("--proje-tavan", type=int, default=1500, help="eğitimde proje başına en çok satır (0=sınırsız)")
    ap.add_argument("--satir-tavan", type=int, default=200)
    ap.add_argument("--token-tavan", type=int, default=1500)
    ap.add_argument("--tokenizer", default="mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit")
    ap.add_argument("--ham-ad", action="store_true", help="önek atma")
    ap.add_argument("--tohum", type=int, default=7)
    a = ap.parse_args()
    if a.token_tavan:
        from transformers import AutoTokenizer
        h.TOK = AutoTokenizer.from_pretrained(a.tokenizer)
    ayrim = {ad: [json.loads(l) for l in (a.veri / f"{dosya}.jsonl").open()]
             for ad, dosya in (("train", "egitim"), ("valid", "dogrulama"), ("test", "test"))}
    if not a.ham_ad:
        h.ONEK = onekler([r for v in ayrim.values() for r in v])
    if a.proje_tavan:
        gruplar = defaultdict(list)
        for r in ayrim["train"]:
            gruplar[r["proje"]].append(r)
        ayrim["train"] = [r for p, rs in sorted(gruplar.items())
                          for r in (random.Random(f"{p}{a.tohum}").sample(rs, a.proje_tavan)
                                    if len(rs) > a.proje_tavan else rs)]
    random.Random(a.tohum).shuffle(ayrim["train"])
    a.cikti.mkdir(parents=True, exist_ok=True)
    ozet = {}
    for ad, rs in ayrim.items():
        h.yaz(a.cikti / f"{ad}.jsonl", rs, a.satir_tavan, a.token_tavan, a.ham_ad, a.baglam)
        ozet[ad] = {"satir": len(rs), "proje": len({r["proje"] for r in rs}),
                    "opt": dict(sorted(Counter(r["opt"] for r in rs).items()))}
    ozet["onek_atilan_proje"] = len(h.ONEK)
    (a.cikti / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(ozet, ensure_ascii=False))


if __name__ == "__main__":
    main()
