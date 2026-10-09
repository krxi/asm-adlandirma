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

v5: --surum v5 --cikti lora/veri-v5. Üç alanlı hedef, açıklamasızlarda yalnız ad,
proje öneki, ham test adları, jenerik ad filtresi, fonksiyon kapsamı ve opt dengesi.
1.500'den fazla fonksiyonlu projelerde varsayılan kapsam önceliklidir; kesin
tavan için --kapsam-onceligi tavan. Her iki durumda istisnalar özete yazılır.
Qwen3 tokenizer tercih edilir, indirilemezse önbellekteki Qwen2.5 kullanılır.
"""
import argparse, json, math, random, re, sys
from collections import Counter, defaultdict
from functools import lru_cache
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


JENERIK = re.compile(r"^(main|init|foo|bar|baz|helper|test|f[0-9]+|test_.*|sub_.*)$", re.I)
OPT_AGIRLIK = {"-O0": .15, "-O1": .20, "-O2": .25, "-O3": .20, "-Os": .20}
YEDEK_TOKENIZER = "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"


def anahtar(r):
    return f"{r['proje']}/{r['dosya']}:{r['ad']}"


def jsonl_oku(yol):
    with yol.open(encoding="utf-8") as f:
        for l in f:
            if l.strip():
                yield json.loads(l)


def satir_v5(r, tr, en, a, ham=False):
    # Kısmi öğretmen hedefleri kullanılmaz: ya üç alan ya yalnız ad.
    tam = bool(tr and en)
    hedef = {}
    if tam:
        hedef["aciklama_en"] = en
    hedef["ad"] = r["ad"] if ham else h.oneksiz(r)
    if tam:
        hedef["aciklama"] = tr
    girdi = h.girdi(r, "ozet", a.satir_tavan, a.token_tavan)
    # Eski girdi() çok uzun tek asm satırını kesmez; v5'te tavan yine geçerli.
    if a.token_tavan and len(h.TOK.encode(girdi)) > a.token_tavan:
        girdi = h.TOK.decode(h.TOK.encode(girdi)[:a.token_tavan])
        while len(h.TOK.encode(girdi)) > a.token_tavan:
            girdi = girdi[:-1]
    return {"messages": [{"role": "system", "content": h.SISTEM_V5},
                         {"role": "user", "content": girdi},
                         {"role": "assistant", "content": json.dumps(hedef, ensure_ascii=False)}],
            "id": r["id"], "proje": r["proje"], "opt": r["opt"],
            "baglam_var": bool(r.get("baglam")), "gercek_ad": r["ad"],
            "oneksiz_onek": sorted(OZET_ONEK.get(r["proje"], ())),
            "hedef_tur": "tam" if tam else "ad"}


def egitim_sec_v5(rs, hedef=95000, proje_tavan=1500, tohum=7, kapsam_onceligi=True):
    """İlk varyantlar önce; sonra farklı opt'lu en çok bir ek varyant.

    rs, kaynak anahtarı ve hazırlanmış satır içeren kayıtlardır. Ağırlık satır
    sayısına değil opt'a uygulanır. Girdi sırasından bağımsız, tohumlu seçim.
    Kapsam ve tavan çelişirse varsayılan olarak kapsam korunur.
    """
    gruplar = defaultdict(list)
    for r in rs:
        gruplar[r["kaynak"]].append(r)
    rng = random.Random(tohum)
    ilkler, ikinciler = [], []
    for key in sorted(gruplar):
        opts = defaultdict(list)
        for r in sorted(gruplar[key], key=lambda x: x["satir"]["id"]):
            opts[r["satir"]["opt"]].append(r)
        secimler = []
        for _ in range(min(2, len(opts))):
            adlar = sorted(opts)
            opt = rng.choices(adlar, weights=[OPT_AGIRLIK.get(o, .2) for o in adlar])[0]
            secimler.append(rng.choice(opts.pop(opt)))
        ilkler.append(secimler[0])
        if len(secimler) > 1:
            ikinciler.append(secimler[1])
    rng.shuffle(ilkler)
    rng.shuffle(ikinciler)
    sonuc, say = [], Counter()
    for r in ilkler:
        p = r["satir"]["proje"]
        if kapsam_onceligi or not proje_tavan or say[p] < proje_tavan:
            sonuc.append(r)
            say[p] += 1
    ilk_sayi = len(sonuc)
    for r in ikinciler:
        p = r["satir"]["proje"]
        if len(sonuc) >= hedef:
            break
        if not proje_tavan or say[p] < proje_tavan:
            sonuc.append(r)
            say[p] += 1
    rng.shuffle(sonuc)
    return sonuc, {"uygun_fonksiyon": len(gruplar), "secilen_fonksiyon": ilk_sayi,
                   "tavandan_atilan_fonksiyon": len(gruplar) - ilk_sayi,
                   "ikinci_varyant": len(sonuc) - ilk_sayi,
                   "hedef_satir": hedef, "hedefe_eksik": max(0, hedef - len(sonuc)),
                   "tavan_asan_projeler": dict(sorted((p, n) for p, n in say.items()
                                                       if proje_tavan and n > proje_tavan))}


def dengeli_sec_v5(rs, n=300, tohum=7):
    rng = random.Random(tohum)
    projeler = defaultdict(list)
    for r in sorted(rs, key=lambda x: x["satir"]["id"]):
        projeler[r["satir"]["proje"]].append(r)
    for p in sorted(projeler):
        rng.shuffle(projeler[p])
    sonuc = []
    while len(sonuc) < n and any(projeler.values()):
        for p in sorted(projeler):
            if projeler[p] and len(sonuc) < n:
                sonuc.append(projeler[p].pop())
    return sonuc


def yuzdelikler(ns):
    ns = sorted(ns)
    if not ns:
        return dict.fromkeys(("p50", "p90", "p99", "maks"), 0)
    return {**{f"p{p}": ns[max(0, math.ceil(len(ns) * p / 100) - 1)] for p in (50, 90, 99)},
            "maks": ns[-1]}


def puan_onekleri(veri):
    """ozet.onekler ölçütü; cwd yerine kaynak veri kökünü kullanır."""
    from taban import kelimeler
    sonuc = {}
    for p in sorted([*veri.glob("egitim/*.jsonl"), *veri.glob("test/*.jsonl")]):
        adlar = [kelimeler(r["ad"]) for r in jsonl_oku(p)]
        say = Counter(k[0] for k in adlar if len(k) > 1)
        proje = p.stem.lower().replace("_", "").removeprefix("lib")
        ilgili = lambda k: proje.startswith(k.rstrip("0123456789")) or (len(k) <= 3 and proje.startswith(k[0]))
        sonuc[p.stem] = {k for k, n in say.items() if n >= .1 * len(adlar) and ilgili(k)}
    return sonuc


def tokenizer_v5(a):
    from transformers import AutoTokenizer
    tercih = a.tokenizer or "Qwen/Qwen3-8B"
    try:
        tok = AutoTokenizer.from_pretrained(tercih, cache_dir=str(a.tokenizer_cache) if a.tokenizer_cache else None)
        return tok, {"kullanilan": tercih, "tercih": tercih, "yedek_nedeni": None}
    except (OSError, ValueError) as e:
        if a.tokenizer:
            raise
        tok = AutoTokenizer.from_pretrained(YEDEK_TOKENIZER, local_files_only=True)
        return tok, {"kullanilan": YEDEK_TOKENIZER, "tercih": tercih,
                     "yedek_nedeni": f"{type(e).__name__}: Qwen3 indirilemedi/önbellekte yok"}


def hazirla_v5(a):
    if not 0 < a.token_tavan <= 2500:
        raise ValueError("v5 token tavanı 1..2500 olmalı")
    tr = acikla_oku(a.aciklama)
    en = {r["anahtar"]: r["aciklama_en"] for r in jsonl_oku(a.aciklama_detay) if r.get("aciklama_en")}
    yollar = {ad: a.veri / f"{dosya}.jsonl" for ad, dosya in
              (("train", "egitim"), ("valid", "dogrulama"), ("test", "test"))}
    yollar["eval115"] = a.eval115
    # İlk taramada asm'yi bellekte tutma; önekler yalnız proje/ad ile hesaplanır.
    h.ONEK = onekler((r for ad in ("train", "valid", "test") for r in jsonl_oku(yollar[ad])),
                    "proje", belirlenimci=True)
    OZET_ONEK.clear()
    OZET_ONEK.update(puan_onekleri(a.veri.resolve().parents[1]))
    idler = [s.strip() for s in a.test_idler.read_text().splitlines() if s.strip()]
    test_idler = Counter(r["id"] for r in jsonl_oku(yollar["test"]))
    eksik = [i for i in idler if not test_idler[i]]
    if eksik:
        raise ValueError(f"test_sabit eksik id ({len(eksik)}): {eksik[:5]}")
    if len(set(idler)) != len(idler) or any(test_idler[i] != 1 for i in idler):
        raise ValueError("test_sabit id'leri benzersiz olmalı")
    h.TOK, tok_ozet = tokenizer_v5(a)
    # girdi() kesme sırasında aynı metinleri, opt varyantları aynı hedefi tekrar sayar.
    h.TOK.encode = lru_cache(maxsize=4096)(h.TOK.encode)
    ozet = {"surum": "v5", "tohum": a.tohum, "valid_300_tohum": 7,
            "onek_kurali": "proje", "onek_atilan_proje": len(h.ONEK), "test_hedefi": "gercek",
            "tokenizer": tok_ozet, "token_tavan": a.token_tavan, "max_uzunluk": a.max_uzunluk,
            "sistem_token": len(h.TOK.encode(h.SISTEM_V5)),
            "toplam_token_olcumu": "chat_template, enable_thinking=False, add_generation_prompt=False",
            "proje_tavan": a.proje_tavan, "kapsam_onceligi": a.kapsam_onceligi == "kapsam",
            "opt_agirlik": OPT_AGIRLIK, "filtreler": {}}
    bolumler = {}
    for ad, yol in yollar.items():
        rs, kaynaklar, uygun_kaynaklar = [], set(), set()
        filtre = dict.fromkeys(("girdi", "jenerik", "aciklamasiz", "kismi_aciklama", "uzunluk_asan",
                               "uzunluktan_atilan"), 0)
        for r in jsonl_oku(yol):
            filtre["girdi"] += 1
            key = anahtar(r)
            if ad == "train" and JENERIK.fullmatch(r["ad"]):
                filtre["jenerik"] += 1
                continue
            kaynaklar.add(key)
            if not (tr.get(key) and en.get(key)):
                filtre["aciklamasiz"] += 1
                filtre["kismi_aciklama"] += bool(tr.get(key) or en.get(key))
            s = satir_v5(r, tr.get(key), en.get(key), a, ham=ad in ("test", "eval115"))
            m = s["messages"]
            token = {"girdi": len(h.TOK.encode(m[1]["content"])),
                     "hedef": len(h.TOK.encode(m[2]["content"])),
                     "toplam": len(h.TOK.apply_chat_template(m, tokenize=True, add_generation_prompt=False,
                                                            enable_thinking=False, return_dict=False))}
            if token["toplam"] > a.max_uzunluk:
                filtre["uzunluk_asan"] += 1
                if ad == "train":
                    filtre["uzunluktan_atilan"] += 1
                    continue
            uygun_kaynaklar.add(key)
            rs.append({"kaynak": key, "satir": s, "token": token})
            if filtre["girdi"] % 10000 == 0:
                print(f"{ad}: {filtre['girdi']} satır işlendi", file=sys.stderr, flush=True)
        filtre["uzunluktan_kaybolan_fonksiyon"] = len(kaynaklar - uygun_kaynaklar)
        if ad == "train":
            once = len(rs)
            rs, ozet["secim"] = egitim_sec_v5(rs, a.hedef_satir, a.proje_tavan, a.tohum,
                                             a.kapsam_onceligi == "kapsam")
            filtre["varyant_seciminde_atilan"] = once - len(rs)
        ozet["filtreler"][ad] = filtre
        bolumler[ad] = rs
    bolumler["valid_300"] = dengeli_sec_v5(bolumler["valid"], tohum=7)
    test = {r["satir"]["id"]: r for r in bolumler["test"]}
    bolumler["test_sabit"] = [test[i] for i in idler]
    a.cikti.mkdir(parents=True, exist_ok=True)
    for ad, rs in bolumler.items():
        with (a.cikti / f"{ad}.jsonl").open("w", encoding="utf-8") as f:
            for r in rs:
                f.write(json.dumps(r["satir"], ensure_ascii=False) + "\n")
        ss = [r["satir"] for r in rs]
        ozet[ad] = {"satir": len(rs), "proje": len({r["proje"] for r in ss}),
                    "fonksiyon": len({r["kaynak"] for r in rs}),
                    "baglam_var": sum(r["baglam_var"] for r in ss),
                    "opt": dict(sorted(Counter(r["opt"] for r in ss).items())),
                    "hedef_tur": dict(sorted(Counter(r["hedef_tur"] for r in ss).items())),
                    "token": {k: yuzdelikler([r["token"][k] for r in rs]) for k in ("girdi", "hedef", "toplam")},
                    "uzunluk_asan": sum(r["token"]["toplam"] > a.max_uzunluk for r in rs)}
    (a.cikti / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(ozet, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--veri", type=Path, default=Path("veri/bin/olcek"))
    ap.add_argument("--aciklama", type=Path, default=Path("veri/aciklama-v4/codex.jsonl"))
    ap.add_argument("--cikti", type=Path, default=Path("lora/veri-sonraki"))
    ap.add_argument("--proje-tavan", type=int, default=1500,
                    help="proje başına satır (0=sınırsız); v5 kapsam önceliğinde ilk varyantlar korunur")
    ap.add_argument("--satir-tavan", type=int, default=200)
    ap.add_argument("--token-tavan", type=int, default=2500,
                    help="asm+bağlam token tavanı; notebook MAX_UZUNLUK=3072, sistem+cevaba ~500 pay")
    ap.add_argument("--tokenizer", default=None,
                    help="varsayılan eski akışta Qwen2.5; v5'te Qwen3-8B, indirilemezse Qwen2.5")
    ap.add_argument("--onek-kurali", choices=("siklik", "proje"), default="siklik",
                    help="hazirla_olcek.py ile aynı; proje: yalnız proje adıyla ilişkili önek (v2)")
    ap.add_argument("--test-ham-ad", action="store_true", help="test hedefinde gerçek adı koru (v2)")
    ap.add_argument("--tohum", type=int, default=7)
    ap.add_argument("--surum", choices=("v5",), default=None)
    ap.add_argument("--aciklama-detay", type=Path, default=Path("veri/aciklama-v4/codex-detay.jsonl"))
    ap.add_argument("--eval115", type=Path, default=Path("veri/test.jsonl"))
    ap.add_argument("--test-idler", type=Path, default=Path(__file__).with_name("test_sabit_idler.txt"))
    ap.add_argument("--tokenizer-cache", type=Path)
    ap.add_argument("--max-uzunluk", type=int, default=3072)
    ap.add_argument("--hedef-satir", type=int, default=95000)
    ap.add_argument("--kapsam-onceligi", choices=("kapsam", "tavan"), default="kapsam")
    a = ap.parse_args()
    if a.surum == "v5":
        hazirla_v5(a)
        return
    a.tokenizer = a.tokenizer or YEDEK_TOKENIZER
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
