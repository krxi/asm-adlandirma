#!/usr/bin/env python3
"""Sonraki deney verisi: girdi = asm + çağrı bağlamı, hedef = ad + kısa açıklama.

  .venv/bin/python lora/hazirla_sonraki.py --cikti lora/veri-sonraki

Kaynak: veri/bin/olcek/{egitim,dogrulama,test}.jsonl (hazirla_olcek.py ile aynı proje bazlı ayrım)
ve veri/aciklama-v4/codex.jsonl ("proje/dosya:ad" anahtarlı öğretmen açıklamaları).
Açıklaması olmayan satır train/valid'den atılır; testte kalır (hedefte yalnız ad), puan ada bakar.
Ek alanlar: proje, baglam_var, gercek_ad (önekli ham ad; taban.py ile aynı puan buna göre),
oneksiz_onek (ozet.ONEK'teki proje öneki; notebook öneksiz F1'i iki_f1.py ile aynı hesaplasın diye).

v2 (önerilen): --onek-kurali proje --test-ham-ad. ozet.ONEK veri/egitim ve veri/test'ten okunur:
betiği o dizinlerin bulunduğu repo kökünden çalıştırın.
"""
import argparse, json, random, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(Path(__file__).resolve().parent.parent))
import hazirla as h
from hazirla_olcek import onekler


def acikla_oku(yol: Path) -> dict[str, str]:
    return {r["anahtar"]: r["aciklama"] for r in map(json.loads, yol.open()) if r.get("aciklama")}


def satir(r: dict, aciklama, a, ham: bool = False) -> dict:
    hedef = {"ad": r["ad"] if ham else h.oneksiz(r)}
    if aciklama:
        hedef["aciklama"] = aciklama
    return {"messages": [{"role": "system", "content": h.SISTEM_ACIKLAMA},
                         {"role": "user", "content": h.girdi(r, "ozet", a.satir_tavan, a.token_tavan)},
                         {"role": "assistant", "content": json.dumps(hedef, ensure_ascii=False)}],
            "id": r["id"], "proje": r["proje"], "opt": r["opt"],
            "baglam_var": bool(r.get("baglam")), "gercek_ad": r["ad"],
            "oneksiz_onek": sorted(OZET_ONEK.get(r["proje"], ()))}


OZET_ONEK: dict[str, set[str]] = {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--veri", type=Path, default=Path("veri/bin/olcek"))
    ap.add_argument("--aciklama", type=Path, default=Path("veri/aciklama-v4/codex.jsonl"))
    ap.add_argument("--cikti", type=Path, default=Path("lora/veri-sonraki"))
    ap.add_argument("--proje-tavan", type=int, default=1500, help="eğitimde proje başına en çok satır (0=sınırsız)")
    ap.add_argument("--satir-tavan", type=int, default=200)
    ap.add_argument("--token-tavan", type=int, default=2500,
                    help="asm+bağlam token tavanı; notebook MAX_UZUNLUK=3072, sistem+cevaba ~500 pay")
    ap.add_argument("--tokenizer", default="mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit",
                    help="Colab modeliyle aynı Qwen2.5 sözlüğü; yerelde önbellekte")
    ap.add_argument("--onek-kurali", choices=("siklik", "proje"), default="siklik",
                    help="hazirla_olcek.py ile aynı; proje: yalnız proje adıyla ilişkili önek (v2)")
    ap.add_argument("--test-ham-ad", action="store_true", help="test hedefinde gerçek adı koru (v2)")
    ap.add_argument("--tohum", type=int, default=7)
    a = ap.parse_args()
    if a.token_tavan:
        from transformers import AutoTokenizer
        h.TOK = AutoTokenizer.from_pretrained(a.tokenizer)
    aciklamalar = acikla_oku(a.aciklama)
    ayrim = {ad: [json.loads(l) for l in (a.veri / f"{dosya}.jsonl").open()]
             for ad, dosya in (("train", "egitim"), ("valid", "dogrulama"), ("test", "test"))}
    h.ONEK = onekler([r for v in ayrim.values() for r in v], a.onek_kurali)
    import ozet as ozet_modulu  # import anında cwd'deki veri/egitim ve veri/test'ten önek çıkarır
    OZET_ONEK.update(ozet_modulu.ONEK)
    anahtar = lambda r: f"{r['proje']}/{r['dosya']}:{r['ad']}"
    ozet = {"onek_atilan_proje": len(h.ONEK), "onek_kurali": a.onek_kurali,
            "test_hedefi": "gercek" if a.test_ham_ad else "oneksiz", "token_tavan": a.token_tavan}
    for ad in ("train", "valid"):
        once = len(ayrim[ad])
        ayrim[ad] = [r for r in h.tekil(ayrim[ad]) if anahtar(r) in aciklamalar]
        ozet[f"{ad}_atilan(kopya+aciklamasiz)"] = once - len(ayrim[ad])
    if a.proje_tavan:
        gruplar = defaultdict(list)
        for r in ayrim["train"]:
            gruplar[r["proje"]].append(r)
        ayrim["train"] = [r for p, rs in sorted(gruplar.items())
                          for r in (random.Random(f"{p}{a.tohum}").sample(rs, a.proje_tavan)
                                    if len(rs) > a.proje_tavan else rs)]
    random.Random(a.tohum).shuffle(ayrim["train"])
    a.cikti.mkdir(parents=True, exist_ok=True)
    for ad, rs in ayrim.items():
        with (a.cikti / f"{ad}.jsonl").open("w") as f:
            for r in rs:
                ham = ad == "test" and a.test_ham_ad
                f.write(json.dumps(satir(r, aciklamalar.get(anahtar(r)), a, ham), ensure_ascii=False) + "\n")
        ozet[ad] = {"satir": len(rs), "proje": len({r["proje"] for r in rs}),
                    "baglam_var": sum(bool(r.get("baglam")) for r in rs),
                    "aciklamali": sum(anahtar(r) in aciklamalar for r in rs),
                    "opt": dict(sorted(Counter(r["opt"] for r in rs).items()))}
    (a.cikti / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(ozet, ensure_ascii=False))


if __name__ == "__main__":
    main()
