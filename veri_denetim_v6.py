#!/usr/bin/env python3
"""Yayımlanmış v6 sohbet verisinin bağımsız denetimi; model çağrısı ve ağ erişimi yok.

  python3 veri_denetim_v6.py --veri /path/to/veri-v6 -o /tmp/v6-denetim.json \
      --tahmin valid_300=sonuc/valid300-molab-qwen3-8b-v5.jsonl

Ölçülenler:
  * bölüm ayrıklığı: proje, kimlik ve kaynak fonksiyon (proje, dosya, ad) kesişimleri;
  * hedef ad sızıntısı: gerçek ad ve asistan hedefi, kullanıcı girdisinin asm / bağlam / decompile
    kısımlarında tanımlayıcı olarak mı yoksa string sabiti içinde mi geçiyor;
  * bölümler arası yakın kopya: sub_/dat_/FUN_ kimlikleri normalize edilmiş asm ve decompile metni
    train'de birebir var mı, varsa train'deki adı kopyalamak ne kadar F1 verir (ezber tavanı);
  * gömülü (vendored) kopya: bir değerlendirme projesinin ayırt edici adlarının (>= 8 karakter) en az
    %20'si tek bir train projesinde de varsa o çift ve train'deki adla birebir aynı satırlar.

--tahmin verilirse aynı bölümdeki tahminlerin F1'i kopya/kopya değil diye ayrıca raporlanır. Bu tanısaldır;
model veya checkpoint seçimi için kullanılmaz.
"""

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from lora.hazirla import BAGLAM_BASLIK, DECOMPILE_BASLIK
from taban import f1

BOLUMLER = ("train", "valid", "test", "test_sabit", "valid_300", "eval115")
DEGERLENDIRME = ("valid", "test", "test_sabit", "valid_300", "eval115")
# Ayrık olması gereken bölüm çiftleri (alt kümeler: test_sabit ⊂ test, valid_300 ⊂ valid).
AYRIK = (("train", "valid"), ("train", "test"), ("train", "eval115"), ("valid", "test"), ("valid", "eval115"))
ALT_KUME = (("test_sabit", "test"), ("valid_300", "valid"))
MIN_AD = 4  # get/set/len gibi kısa adlar tesadüfen geçer; sızıntı sayılmaz.
VENDOR_AD = 8  # gömülü kopya taramasında yalnız ayırt edici (uzun) adlar sayılır.
VENDOR_ESIK = 0.2
BOYUTLAR = ((5, "<=5"), (20, "6-20"), (100, "21-100"), (math.inf, ">100"))

STRING = re.compile(r'"(?:\\.|[^"\\\n])*"')
KIMLIK_NORM = (
    (re.compile(r"\bsub_[0-9a-fA-F]+\b"), "sub_"),
    (re.compile(r"\b(?:dat|DAT)_[0-9a-fA-F]+\b"), "dat_"),
    (re.compile(r"\b(?:FUN|LAB|PTR_DAT|PTR_FUN|PTR_LOOP|thunk_FUN)_[0-9a-fA-F]+\b"), "ghidra_"),
)


def satirlar(yol):
    with Path(yol).open(encoding="utf-8") as dosya:
        for satir in dosya:
            if satir.strip():
                yield json.loads(satir)


def kisimlar(user):
    """Kullanıcı girdisini (asm, bağlam, decompile) olarak böl; olmayan kısım boş string."""
    govde, _, decompile = user.partition(DECOMPILE_BASLIK)
    asm, _, baglam = govde.partition(BAGLAM_BASLIK)
    return asm, baglam, decompile


def normalize(metin):
    for desen, yerine in KIMLIK_NORM:
        metin = desen.sub(yerine, metin)
    return " ".join(metin.split())


def ozet_hash(metin):
    return hashlib.sha256(normalize(metin).encode()).hexdigest() if metin.strip() else None


def komut_sayisi(asm):
    return sum(1 for s in asm.splitlines() if s.strip() and not s.rstrip().endswith(":"))


def boyut(n):
    return next(ad for tavan, ad in BOYUTLAR if n <= tavan)


def hedef(r):
    return json.loads(r["messages"][2]["content"])["ad"]


def kaynak_fonksiyon(r):
    dosya = r["id"].split(":", 1)[0]
    return r["proje"], dosya, r["gercek_ad"]


def sizinti(ad, kisim):
    """Adın kısımdaki geçişi: ('kimlik', 'string', None). Kimlik geçişi string dışındaki tam tanımlayıcıdır."""
    if len(ad) < MIN_AD or ad not in kisim:
        return None
    desen = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(ad) + r"(?![A-Za-z0-9_])")
    if desen.search(STRING.sub('""', kisim)):
        return "kimlik"
    return "string" if any(ad in s for s in STRING.findall(kisim)) else "alt_dizgi"


def satir_kaydi(r):
    user = next(m["content"] for m in r["messages"] if m["role"] == "user")
    asm, baglam, decompile = kisimlar(user)
    adlar = {r["gercek_ad"], hedef(r)}
    return {
        "id": r["id"],
        "proje": r["proje"],
        "kaynak": kaynak_fonksiyon(r),
        "ad": r["gercek_ad"],
        "boyut": boyut(komut_sayisi(asm)),
        "asm": ozet_hash(asm),
        "decompile": ozet_hash(decompile),
        "sizinti": {
            k: sorted({s for s in (sizinti(ad, metin) for ad in adlar) if s})
            for k, metin in (("asm", asm), ("baglam", baglam), ("decompile", decompile))
        },
    }


def ortalama(degerler):
    return math.fsum(degerler) / len(degerler) if degerler else None


def kopya_ozeti(kayitlar, train_adlari, anahtar):
    """train'de aynı normalize metni olan satırlar ve train adını kopyalamanın F1 tavanı."""
    kopya = [k for k in kayitlar if k[anahtar] and k[anahtar] in train_adlari]
    f1ler = [f1(train_adlari[k[anahtar]].most_common(1)[0][0], k["ad"]) for k in kopya]
    boyutlar = Counter(k["boyut"] for k in kopya)
    return {
        "satir": len(kopya),
        "oran": len(kopya) / len(kayitlar) if kayitlar else 0.0,
        "kopya_ad_f1": ortalama(f1ler),
        "kopya_ad_birebir": sum(train_adlari[k[anahtar]].most_common(1)[0][0] == k["ad"] for k in kopya),
        "boyut": {ad: boyutlar.get(ad, 0) for _, ad in BOYUTLAR},
        "proje": dict(Counter(k["proje"] for k in kopya).most_common(10)),
    }


def gomulu_kopyalar(kayitlar, train_proje_adlari):
    """Değerlendirme projesi -> ayırt edici adlarını en çok paylaştığı train projesi (oran >= VENDOR_ESIK)."""
    proje_adlari = defaultdict(set)
    for k in kayitlar:
        proje_adlari[k["proje"]].add(k["ad"])
    ciftler = {}
    for proje, adlar in sorted(proje_adlari.items()):
        ayirt = {ad for ad in adlar if len(ad) >= VENDOR_AD}
        if not ayirt:
            continue
        kaynak = max(sorted(train_proje_adlari), key=lambda t: len(ayirt & train_proje_adlari[t]))
        oran = len(ayirt & train_proje_adlari[kaynak]) / len(ayirt)
        if oran >= VENDOR_ESIK:
            satir = [k for k in kayitlar if k["proje"] == proje and k["ad"] in train_proje_adlari[kaynak]]
            ciftler[proje] = {
                "train_projesi": kaynak,
                "ayirt_edici_ad_orani": oran,
                "ayni_adli_satir": len(satir),
                "proje_satiri": sum(k["proje"] == proje for k in kayitlar),
                "bolum_orani": len(satir) / len(kayitlar),
                "kimlikler": {k["id"] for k in satir},
            }
    return ciftler


def tahmin_ozeti(kayitlar, tahminler, kopya_kimlikleri, gomulu_kimlikleri):
    eslesen = [k for k in kayitlar if k["id"] in tahminler]
    if len(eslesen) != len(tahminler):
        raise ValueError(f"tahmin kimlikleri bölümle uyuşmuyor: {len(tahminler)} tahmin, {len(eslesen)} eşleşen")
    sonuc = {}
    for grup, secim in (
        ("hepsi", eslesen),
        ("kopya", [k for k in eslesen if k["id"] in kopya_kimlikleri]),
        ("kopya_degil", [k for k in eslesen if k["id"] not in kopya_kimlikleri]),
        ("gomulu_ad", [k for k in eslesen if k["id"] in gomulu_kimlikleri]),
        ("gomulu_ad_degil", [k for k in eslesen if k["id"] not in gomulu_kimlikleri]),
    ):
        puan = [f1(str(tahminler[k["id"]].get("tahmin") or ""), k["ad"]) for k in secim]
        sonuc[grup] = {"n": len(secim), "f1": ortalama(puan)}
    return sonuc


def denetle(veri, tahmin_yollari=None):
    kayitlar = {b: [satir_kaydi(r) for r in satirlar(Path(veri, b + ".jsonl"))] for b in BOLUMLER}
    projeler = {b: {k["proje"] for k in ks} for b, ks in kayitlar.items()}
    kimlikler = {b: {k["id"] for k in ks} for b, ks in kayitlar.items()}
    kaynaklar = {b: {k["kaynak"] for k in ks} for b, ks in kayitlar.items()}

    rapor = {
        "surum": "v6-veri-denetimi-1",
        "satir": {b: len(ks) for b, ks in kayitlar.items()},
        "proje": {b: len(p) for b, p in projeler.items()},
        "ayriklik": {},
        "alt_kume": {},
        "sizinti": {},
        "kopya": {},
        "gomulu": {},
        "ad_onceligi": {},
    }
    for a, b in AYRIK:
        rapor["ayriklik"][f"{a}~{b}"] = {
            "proje": sorted(projeler[a] & projeler[b]),
            "kimlik": len(kimlikler[a] & kimlikler[b]),
            "kaynak_fonksiyon": len(kaynaklar[a] & kaynaklar[b]),
        }
    for alt, ust in ALT_KUME:
        rapor["alt_kume"][f"{alt}⊂{ust}"] = len(kimlikler[alt] - kimlikler[ust]) == 0

    for b, ks in kayitlar.items():
        say = Counter()
        for k in ks:
            for kisim, turler in k["sizinti"].items():
                for tur in turler:
                    say[f"{kisim}.{tur}"] += 1
        rapor["sizinti"][b] = dict(sorted(say.items()))

    train_adlari = {anahtar: defaultdict(Counter) for anahtar in ("asm", "decompile")}
    for k in kayitlar["train"]:
        for anahtar in train_adlari:
            if k[anahtar]:
                train_adlari[anahtar][k[anahtar]][k["ad"]] += 1
    train_ad_kumesi = {k["ad"] for k in kayitlar["train"]}
    train_proje_adlari = defaultdict(set)
    for k in kayitlar["train"]:
        train_proje_adlari[k["proje"]].add(k["ad"])
    kopya_kimlikleri, gomulu_kimlikleri = {}, {}
    for b in DEGERLENDIRME:
        rapor["kopya"][b] = {
            anahtar: kopya_ozeti(kayitlar[b], train_adlari[anahtar], anahtar) for anahtar in train_adlari
        }
        kopya_kimlikleri[b] = {
            k["id"] for k in kayitlar[b] if any(k[a] and k[a] in train_adlari[a] for a in train_adlari)
        }
        rapor["ad_onceligi"][b] = sum(k["ad"] in train_ad_kumesi for k in kayitlar[b]) / max(1, len(kayitlar[b]))
        ciftler = gomulu_kopyalar(kayitlar[b], train_proje_adlari)
        gomulu_kimlikleri[b] = set().union(*(c.pop("kimlikler") for c in ciftler.values()))
        rapor["gomulu"][b] = {
            "ciftler": ciftler,
            "satir": len(gomulu_kimlikleri[b]),
            "oran": len(gomulu_kimlikleri[b]) / max(1, len(kayitlar[b])),
        }

    if tahmin_yollari:
        rapor["tahmin_tanisal"] = {}
        for b, yol in tahmin_yollari.items():
            tahminler = {r["id"]: r for r in satirlar(yol)}
            rapor["tahmin_tanisal"][b] = tahmin_ozeti(kayitlar[b], tahminler, kopya_kimlikleri[b], gomulu_kimlikleri[b])
    return rapor


def baglama(deger):
    bolum, ayrac, yol = deger.partition("=")
    if not ayrac or bolum not in DEGERLENDIRME or not yol:
        raise argparse.ArgumentTypeError(f"BÖLÜM=YOL bekleniyor; bölüm {DEGERLENDIRME} içinden")
    return bolum, Path(yol)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--veri", type=Path, required=True, help="veri-v6.zip'in açıldığı dizin")
    ap.add_argument("--tahmin", type=baglama, action="append", default=[], help="BÖLÜM=tahmin.jsonl (tanısal)")
    ap.add_argument("-o", "--cikti", type=Path)
    a = ap.parse_args(argv)
    rapor = denetle(a.veri, dict(a.tahmin))
    metin = json.dumps(rapor, ensure_ascii=False, indent=2) + "\n"
    if a.cikti:
        a.cikti.parent.mkdir(parents=True, exist_ok=True)
        a.cikti.write_text(metin, encoding="utf-8")
    print(metin, end="")


if __name__ == "__main__":
    main()
