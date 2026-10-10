#!/usr/bin/env python3
"""Sarmalayıcıları salt okunur say; sabit valid300 üzerinde tek adımlık tahmin aktarımını dene.

Hiçbir model çağrılmaz, istem/veri/sonuç dosyası yazılmaz. Çıktı yalnız toplu JSON'dur.
Örnek komutlar ve sınırlar: rapor/arastirma/SARMALAYICI_DENEYI.md.
"""

import argparse
import hashlib
import json
import re
import shlex
import sys
from collections import Counter
from pathlib import Path

import ozet
import dogrulama_guvencesi as dg
from analiz import turler
from cikar import ic_cagrilar
from ogretmen_denetim import bootstrap_araligi
from taban import f1

KOK = Path(__file__).resolve().parent
DOGRULAMA = KOK / "sonuc/valid300-molab-qwen3-8b-v5.jsonl"
SARMALAYICI = "sarmalayıcı"
ALANLAR = ("proje", "surum", "opt", "kip", "kimlik")


def jsonl_oku(yollar):
    """Kimlikleri yalnız iç eşlemede tut; hatalara satır içeriği koyma."""
    sonuc = {}
    for yol in yollar:
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


def tahminleri_al(kayitlar):
    if any(not isinstance(r.get("tahmin"), str) for r in kayitlar.values()):
        raise ValueError("Tahmin alanı metin olmalı")
    return {k: r["tahmin"] for k, r in kayitlar.items()}


def etiketleri_dogrula(veri, kayitlar):
    """Puanlanacak eski kaydın hedefini doğrula; bu kontrol tahmin üretmez."""
    if any(k not in veri or r.get("gercek") != veri[k].get("ad") for k, r in kayitlar.items()):
        raise ValueError("Puanlanan önbellek/ham veri hedefleri eksik veya uyuşmuyor")


def veri_dogrula(veri):
    for r in veri.values():
        if not all(isinstance(r.get(k), str) for k in ("asm", "opt", "proje")):
            raise ValueError("ASM/opt/proje alanı eksik/geçersiz")
        if type(r.get("komut_sayisi")) is not int or r["komut_sayisi"] < 0:
            raise ValueError("Komut sayısı negatif olmayan tamsayı olmalı")


def kapsam(r):
    if not all(isinstance(r.get(k), str) and r[k] for k in ALANLAR):
        raise ValueError("v4 proje/surum/opt/kip/kimlik gerekli; v3 eşlemesi tahmin edilmez")
    if not re.fullmatch(r"sub_[0-9a-f]+", r["kimlik"]):
        raise ValueError("Geçersiz anonim fonksiyon kimliği")
    return tuple(r[k] for k in ALANLAR)


def dongu_dugumleri(kenarlar):
    bitti, dongu = set(), set()
    for bas in kenarlar:
        yol, yer = [], {}
        while bas in kenarlar and bas not in bitti:
            if bas in yer:
                dongu.update(yol[yer[bas] :])
                break
            yer[bas] = len(yol)
            yol.append(bas)
            bas = kenarlar[bas]
        bitti.update(yol)
    return dongu


def tek_adim(veri, temel, ek):
    """Yalnız özgün önbellekten aktar; etiket okumaz, girdi sözlüklerini değiştirmez."""
    if not temel.keys() <= veri.keys() or not ek.keys() <= veri.keys():
        raise ValueError("Tahmin önbelleğinde doğrulama verisi dışından kimlik var")
    if any(k in temel and temel[k] != v for k, v in ek.items()):
        raise ValueError("Özgün tahmin önbellekleri çelişiyor")
    indeks = {}
    for k, r in veri.items():
        anahtar = kapsam(r)
        if anahtar in indeks:
            raise ValueError("Aynı ikili kapsamında belirsiz anonim kimlik")
        indeks[anahtar] = k
    sarmallar = {k for k, r in veri.items() if SARMALAYICI in turler(r)}
    kenarlar = {}
    for k in sarmallar:
        hedefler = ic_cagrilar(veri[k]["asm"])
        if len(hedefler) == 1:
            hedef = indeks.get(kapsam(veri[k])[:-1] + (hedefler[0],))
            if hedef is not None:
                kenarlar[k] = hedef
    dongu = dongu_dugumleri(kenarlar)
    onbellek, aday = {**temel, **ek}, dict(temel)
    say = Counter(
        dict.fromkeys(("sarmalayici", "bag_eksik", "dongu", "tahmin_eksik", "gecersiz", "aktarilan", "degisen"), 0)
    )
    for k in temel:
        if k not in sarmallar:
            continue
        say["sarmalayici"] += 1
        hedef = kenarlar.get(k)
        if hedef is None:
            say["bag_eksik"] += 1
        elif k in dongu or hedef in dongu:
            say["dongu"] += 1
        elif hedef not in onbellek:
            say["tahmin_eksik"] += 1
        else:
            ad = onbellek[hedef]
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", ad) or re.fullmatch(
                r"(?:sub|FUN|DAT|loc|ext)_[0-9a-f]+", ad, re.I
            ):
                say["gecersiz"] += 1
                continue
            aday[k] = ad
            say["aktarilan"] += 1
            say["degisen"] += ad != temel[k]
    return aday, dict(say)


def puanlar(veri, tahminler):
    if any(not isinstance(veri[k].get("ad"), str) or not veri[k]["ad"] for k in tahminler):
        raise ValueError("Puanlama için ham ad alanı gerekli")
    return {
        "ad_f1": [f1(t, veri[k]["ad"]) for k, t in tahminler.items()],
        "oneksiz_f1": [ozet.f1_oneksiz({"id": k, "gercek": veri[k]["ad"], "tahmin": t}) for k, t in tahminler.items()],
    }


def sayim(veri, tahminler=None):
    sarmal = {k for k, r in veri.items() if SARMALAYICI in turler(r)}
    sonuc = {
        "n": len(veri),
        "proje_sayisi": len({r["proje"] for r in veri.values()}),
        "sarmalayici_n": len(sarmal),
        "sarmalayici_opt": dict(sorted(Counter(veri[k]["opt"] for k in sarmal).items())),
        "sarmalayici_stringsiz_n": sum("string'siz" in turler(veri[k]) for k in sarmal),
        "sarmalayici_kimlikli_n": sum(all(veri[k].get(a) for a in ALANLAR) for k in sarmal),
        "sarmalayici_tek_ic_hedef_n": sum(len(ic_cagrilar(veri[k]["asm"])) == 1 for k in sarmal),
    }
    if tahminler is not None:
        if tahminler.keys() != veri.keys():
            raise ValueError("Sayımda tahmin/veri kimlik kümeleri eşit olmalı; kısmi puanlama yapılmaz")
        sonuc["mevcut"] = {}
        for ad, degerler in puanlar(veri, tahminler).items():
            sarmal_puan = [v for k, v in zip(tahminler, degerler) if k in sarmal]
            ort = sum(degerler) / len(degerler)
            pay = (len(sarmal_puan) - sum(sarmal_puan)) / len(veri)
            sonuc["mevcut"][ad] = {
                "ortalama": ort,
                "sarmalayici_ortalama": sum(sarmal_puan) / len(sarmal_puan) if sarmal_puan else None,
                "kusursuz_onarim_azami_artis": pay,
                "kusursuz_onarim_tavani": ort + pay,
            }
    return sonuc


def dogrulama_deneyi(veri, temel, ek, sabit):
    """Sabit valid300 hedefleri ve onların doğrulama projeleri dışında deneme yapma."""
    if temel.keys() != sabit.keys():
        raise ValueError("Deney hedefleri repodaki sabit valid300 ile aynı olmalı")
    projeler = {r["proje"] for r in sabit.values()}
    if any(r["proje"] not in projeler for r in veri.values()):
        raise ValueError("Doğrulama projesi olmayan veri reddedildi")
    if any(k not in veri or veri[k]["proje"] != r["proje"] for k, r in sabit.items()):
        raise ValueError("Sabit doğrulama kimliği/projesi uyuşmuyor")
    aday, kapsam_say = tek_adim(veri, temel, ek)
    sonuc = {
        "bolum": "valid300",
        "n": len(temel),
        "veri_n": len(veri),
        "veri_proje_sayisi": len(projeler),
        "kapsam": kapsam_say,
        "deney": None,
    }
    once = puanlar(veri, temel)
    sonuc["mevcut"] = {ad: sum(v) / len(v) for ad, v in once.items()}
    if kapsam_say["aktarilan"]:
        sonra = puanlar(veri, aday)
        sonuc["deney"] = {}
        for ad, v in once.items():
            farklar = [b - a for a, b in zip(v, sonra[ad])]
            sonuc["deney"][ad] = {
                "ortalama": sum(sonra[ad]) / len(v),
                "esli_fark": sum(farklar) / len(v),
                "esli_yuzde95_ga": bootstrap_araligi(farklar, tohum=42, tekrar=1000),
            }
    sonuc["durum"] = "run" if sonuc["deney"] is not None else "not run: aktarılabilir çağrılan tahmini yok"
    return sonuc


def sha256(yol):
    h = hashlib.sha256()
    with Path(yol).open("rb") as dosya:
        for blok in iter(lambda: dosya.read(1048576), b""):
            h.update(blok)
    return h.hexdigest()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("kip", choices=("say", "deney"))
    ap.add_argument("--veri", required=True, nargs="+", type=Path)
    ap.add_argument("--tahmin", type=Path)
    ap.add_argument("--idler", type=Path, help="yalnız say: sabit doğrulama kümesinden kimlikler")
    ap.add_argument("--cagri-tahmin", type=Path, help="yalnız deney: özgün doğrulama callee önbelleği")
    a = ap.parse_args(argv)
    try:
        if Path.cwd().resolve() != KOK:
            raise ValueError("Mevcut önek tanımını korumak için repo kökünden çalıştırın")
        if len(a.veri) != 1:
            raise ValueError("Kimlik kökeni için tek doğrulanmış ham validation dosyası gerekir")
        if a.kip == "deney" and (a.idler or not a.tahmin):
            raise ValueError("Deney --tahmin gerektirir; hedef değiştiren --idler kabul edilmez")
        if a.kip == "say" and a.cagri_tahmin:
            raise ValueError("Sayımda yeni tahmin aktarımı yapılmaz")
        yollar = {"veri": a.veri[0], "sabit": DOGRULAMA}
        for rol, yol in (("tahmin", a.tahmin), ("idler", a.idler), ("cagri_tahmin", a.cagri_tahmin)):
            if yol:
                yollar[rol] = yol
        izler = {rol: dg.dosya_izi(p) for rol, p in yollar.items()}
        veri = jsonl_oku(a.veri)
        veri_dogrula(veri)
        sabit, _ = dg.dayanaklar()
        kayitlar = jsonl_oku([a.tahmin]) if a.tahmin else None
        idler = list(sabit)
        if a.idler:
            idler = [s.strip() for s in a.idler.read_text(encoding="utf-8").splitlines() if s.strip()]
        hedefler = kayitlar if a.kip == "deney" else idler
        dg.ham_dogrula(a.veri[0], veri, hedefler)
        if a.kip == "say":
            dg.kimlikleri_dogrula(idler)
            veri = {k: veri[k] for k in idler}
        tahmin = None
        if kayitlar is not None:
            etiketleri_dogrula(veri, kayitlar)
            tahmin = tahminleri_al(kayitlar)
        if a.kip == "say":
            sonuc = {"bolum": "valid300", **sayim(veri, tahmin)}
        else:
            ek = tahminleri_al(jsonl_oku([a.cagri_tahmin])) if a.cagri_tahmin else {}
            sonuc = dogrulama_deneyi(veri, tahmin, ek, sabit)
        if any(sha256(p) != izler[rol]["sha256"] for rol, p in yollar.items()):
            raise ValueError("Çalışma sırasında girdi değişti; sonuç yayımlanmadı")
        komut = ["python3", "sarmalayici_deneyi.py", a.kip, "--veri", izler["veri"]["dosya"]]
        for rol, bayrak in (("tahmin", "--tahmin"), ("idler", "--idler"), ("cagri_tahmin", "--cagri-tahmin")):
            if rol in izler:
                komut.extend((bayrak, izler[rol]["dosya"]))
        kodlar = ("sarmalayici_deneyi.py", "analiz.py", "cikar.py", "taban.py", "ozet.py", "ogretmen_denetim.py")
        sonuc["iz"] = {
            "komut": shlex.join(komut),
            **dg.git_izi(),
            "girdi_sha256": izler,
            "kod_sha256": {ad: sha256(KOK / ad) for ad in kodlar},
            "onek_sha256": hashlib.sha256(
                json.dumps({k: sorted(v) for k, v in sorted(ozet.ONEK.items())}).encode()
            ).hexdigest(),
            "siniflandirici": "analiz.turler: sarmalayıcı",
        }
        print(json.dumps(sonuc, ensure_ascii=False, indent=2, sort_keys=True))
    except ValueError as hata:
        ap.error(str(hata))
    except OSError:
        ap.error("Girdi veya sürüm bilgisi okunamadı")


if __name__ == "__main__":
    main()
