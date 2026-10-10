#!/usr/bin/env python3
"""Sabit valid300 tahminlerinde ek ad ölçütlerini karşılaştır; yalnız toplu JSON üret.

EXPERIMENTAL: skor tanımının değişmesi model kazancı değildir. Veri/istem/önbellek
değişmez; yeni çıkarım, test puanlama veya sözlük ayarlaması yapılmaz.
"""

import argparse
import hashlib
import json
import shlex
import sys
from pathlib import Path
from types import MappingProxyType

import ozet
import dogrulama_guvencesi as dg
from ogretmen_denetim import bootstrap_araligi
from taban import ESANLAM_GRUPLARI, f1, harmonik, kelime_pr, kelimeler

KOK = Path(__file__).resolve().parent
DOGRULAMA = KOK / "sonuc/valid300-molab-qwen3-8b-v5.jsonl"

# Sonuçlar görülmeden sabitlenen dilsel varsayımlar; anlamsal doğruluk oracle'ı değil.
DAR_GRUPLAR = (
    ("init", "initialize", "initialise", "setup"),
    ("buf", "buffer"),
    ("alloc", "allocate"),
    ("len", "length"),
    ("str", "string"),
    ("ctx", "context"),
    ("msg", "message"),
    ("ptr", "pointer"),
)
DAR_ESLEME = MappingProxyType({k: grup[0] for grup in DAR_GRUPLAR for k in grup})


def dar_esleme_f1(tahmin, gercek):
    """Özgün sözcük kümeleri arasında azami bire-bir eşleme; paydalar daraltılmaz."""
    t, g = sorted(set(kelimeler(tahmin))), sorted(set(kelimeler(gercek)))
    sahip = {}

    def yer_bul(sozcuk, gezilen):
        for hedef in g:
            esit = sozcuk == hedef or DAR_ESLEME.get(sozcuk, sozcuk) == DAR_ESLEME.get(hedef, hedef)
            if not esit or hedef in gezilen:
                continue
            gezilen.add(hedef)
            if hedef not in sahip or yer_bul(sahip[hedef], gezilen):
                sahip[hedef] = sozcuk
                return True
        return False

    eslesen = sum(yer_bul(sozcuk, set()) for sozcuk in t)
    return harmonik(eslesen / len(t), eslesen / len(g)) if eslesen else 0.0


def jsonl_oku(yol):
    sonuc = {}
    with Path(yol).open(encoding="utf-8") as dosya:
        for no, satir in enumerate(dosya, 1):
            if not satir.strip():
                continue
            try:
                r = json.loads(satir)
            except ValueError:
                raise ValueError(f"{Path(yol).name}:{no}: geçersiz JSON") from None
            if not isinstance(r, dict) or not isinstance(r.get("id"), str) or not r["id"]:
                raise ValueError(f"{Path(yol).name}:{no}: kimlik eksik/geçersiz")
            if r["id"] in sonuc:
                raise ValueError(f"{Path(yol).name}:{no}: yinelenen kimlik")
            sonuc[r["id"]] = r
    if not sonuc:
        raise ValueError("Boş girdi")
    return sonuc


def dogrula(veri, tahminler, sabit):
    """Başka bölümleri/kimlikleri kabul etme; etiketler yalnız puanlamada kullanılır."""
    if not sabit or tahminler.keys() != sabit.keys():
        raise ValueError("Yalnız repodaki sabit valid300 hedefleri kabul edilir")
    if any(not isinstance(r.get("proje"), str) or not r["proje"] for r in sabit.values()):
        raise ValueError("Sabit doğrulama proje alanı eksik/geçersiz")
    projeler = {r["proje"] for r in sabit.values()}
    if any(not isinstance(r.get("proje"), str) or r["proje"] not in projeler for r in veri.values()):
        raise ValueError("Doğrulama projesi olmayan veri reddedildi")
    for k, r in tahminler.items():
        if k not in veri or veri[k]["proje"] != sabit[k]["proje"] or r.get("proje") != sabit[k]["proje"]:
            raise ValueError("Sabit doğrulama kimliği/projesi uyuşmuyor")
        ad = veri[k].get("ad")
        if not isinstance(ad, str) or not ad or ad != r.get("gercek") or ad != sabit[k].get("gercek"):
            raise ValueError("Ham veri/önbellek/sabit doğrulama hedefi eksik veya uyuşmuyor")
        if not isinstance(r.get("tahmin"), str):
            raise ValueError("Tahmin alanı metin olmalı")


def karsilastir(veri, tahminler, sabit):
    dogrula(veri, tahminler, sabit)
    puanlar = {ad: [] for ad in ("ad_f1", "oneksiz_f1", "dar_esleme_f1", "f1_es", "tam_ad_dogrulugu")}
    for k, r in tahminler.items():
        tahmin, ad = r["tahmin"], veri[k]["ad"]
        puanlar["ad_f1"].append(f1(tahmin, ad))
        puanlar["oneksiz_f1"].append(ozet.f1_oneksiz({"id": k, "tahmin": tahmin, "gercek": ad}))
        puanlar["dar_esleme_f1"].append(dar_esleme_f1(tahmin, ad))
        puanlar["f1_es"].append(harmonik(*kelime_pr(tahmin, ad, esanlam=True)))
        puanlar["tam_ad_dogrulugu"].append(float(tahmin == ad))
    sonuc = {
        "etiket": "EXPERIMENTAL: ölçüt tanımı farkı; model kazancı değil",
        "bolum": "valid300",
        "n": len(tahminler),
        "veri_n": len(veri),
        "proje_sayisi": len({r["proje"] for r in sabit.values()}),
        "olcutler": {ad: sum(v) / len(v) for ad, v in puanlar.items()},
        "tanim_farki": {},
    }
    for ad in ("dar_esleme_f1", "f1_es"):
        farklar = [b - a for a, b in zip(puanlar["ad_f1"], puanlar[ad])]
        sonuc["tanim_farki"][ad] = {
            "ad_f1_farki": sum(farklar) / len(farklar),
            "artan_satir_n": sum(f > 0 for f in farklar),
            "azalan_satir_n": sum(f < 0 for f in farklar),
            "esli_yuzde95_ga": bootstrap_araligi(farklar, tohum=42, tekrar=1000),
        }
    return sonuc


def sha256(yol):
    h = hashlib.sha256()
    with Path(yol).open("rb") as dosya:
        for blok in iter(lambda: dosya.read(1048576), b""):
            h.update(blok)
    return h.hexdigest()


def nesne_sha256(nesne):
    return hashlib.sha256(json.dumps(nesne, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--veri", type=Path, required=True, help="salt okunur v4 validation JSONL")
    ap.add_argument("--tahmin", type=Path, required=True, help="sabit valid300 hedeflerinin mevcut tahminleri")
    a = ap.parse_args(argv)
    try:
        dg.tahmin_ozetini_dogrula(a.tahmin)
        yollar = {"veri": a.veri, "tahmin": a.tahmin, "sabit": DOGRULAMA}
        izler = {rol: dg.dosya_izi(p) for rol, p in yollar.items()}
        veri, tahminler = jsonl_oku(a.veri), jsonl_oku(a.tahmin)
        sabit = dg.ham_dogrula(a.veri, veri, tahminler)
        sonuc = karsilastir(veri, tahminler, sabit)
        if any(sha256(p) != izler[rol]["sha256"] for rol, p in yollar.items()):
            raise ValueError("Çalışma sırasında girdi değişti; sonuç yayımlanmadı")
        kodlar = ("ad_olcutleri.py", "taban.py", "ozet.py", "ogretmen_denetim.py")
        sonuc["iz"] = {
            "komut": shlex.join(
                ["python3", "ad_olcutleri.py", "--veri", izler["veri"]["dosya"], "--tahmin", izler["tahmin"]["dosya"]]
            ),
            **dg.git_izi(),
            "python": sys.version.split()[0],
            "girdi_sha256": izler,
            "kod_sha256": {ad: sha256(KOK / ad) for ad in kodlar},
            "dar_esleme_sha256": nesne_sha256(DAR_GRUPLAR),
            "eski_esanlam_sha256": nesne_sha256(ESANLAM_GRUPLARI),
            "onek_sha256": nesne_sha256({k: sorted(v) for k, v in sorted(ozet.ONEK.items())}),
            "bootstrap": {"birim": "esli satir olcut farki", "tohum": 42, "tekrar": 1000},
        }
        print(json.dumps(sonuc, ensure_ascii=False, indent=2, sort_keys=True))
    except (ValueError, OSError) as hata:
        ap.error(str(hata))


if __name__ == "__main__":
    main()
