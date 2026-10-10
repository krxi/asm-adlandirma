#!/usr/bin/env python3
"""Sabit doğrulama tahminlerinde aynı kaynak işlevin optimizasyon çiftlerini denetle."""

import argparse
import math
import random
import statistics
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import dogrulama_guvencesi as dg
from taban import f1


def jsonl_oku(yol):
    return list(dg.jsonl_oku(yol).values())


def girdileri_yukle(veri_yolu: Path, tahmin_yolu: Path) -> list[dict]:
    once = [dg.sha256(p) for p in (veri_yolu, tahmin_yolu)]
    veri, tahminler = dg.jsonl_oku(veri_yolu), dg.jsonl_oku(tahmin_yolu)
    dg.ham_dogrula(veri_yolu, veri, tahminler)
    birlesik = []
    gerekli = ("proje", "dosya", "ad", "kip", "opt", "asm", "komut_sayisi")
    for kimlik, sonuc in sorted(tahminler.items()):
        ham = veri[kimlik]
        if any(alan not in ham for alan in gerekli):
            raise ValueError("Doğrulama satırında eşleme veya kırılım alanı eksik")
        tahmin, gercek, puan = sonuc.get("tahmin"), sonuc.get("gercek"), sonuc.get("f1")
        if not isinstance(tahmin, str) or not isinstance(gercek, str):
            raise ValueError("Tahmin/gercek metin olmalı")
        if gercek != ham["ad"]:
            raise ValueError("Sonuçtaki gercek kanonik veri etiketiyle uyuşmuyor")
        hesap = f1(tahmin, ham["ad"])
        if isinstance(puan, bool) or not isinstance(puan, (int, float)) or not math.isfinite(puan):
            raise ValueError("f1 sonlu sayı olmalı")
        if abs(puan - hesap) > 1e-12:
            raise ValueError("Sonuçtaki f1 kanonik taban.f1 ile aynı değil")
        birlesik.append({"ham": ham, "f1": hesap})
    if once != [dg.sha256(p) for p in (veri_yolu, tahmin_yolu)]:
        raise ValueError("Çalışma sırasında girdi değişti")
    return birlesik


def yuzdelik(sirali: list[float], oran: float) -> float:
    return sirali[min(len(sirali) - 1, int(len(sirali) * oran))]


def bootstrap(degerler: list[float], tohum: int, tekrar: int) -> list[float]:
    if not degerler:
        return []
    if len(degerler) == 1:
        return [degerler[0], degerler[0]]
    rng = random.Random(tohum)
    n = len(degerler)
    dagilim = sorted(math.fsum(rng.choice(degerler) for _ in range(n)) / n for _ in range(tekrar))
    return [yuzdelik(dagilim, 0.025), yuzdelik(dagilim, 0.975)]


def esleme_anahtari(ham: dict) -> tuple[str, str, str, str]:
    return ham["proje"], ham["dosya"], ham["ad"], ham["kip"]


def denetle(satirlar: list[dict], tohum: int = 42, tekrar: int = 2000) -> dict:
    if tekrar < 100:
        raise ValueError("Bootstrap tekrarı en az 100 olmalı")
    satirlar = sorted(satirlar, key=lambda r: (esleme_anahtari(r["ham"]), r["ham"]["opt"]))
    gruplar, opt_gruplari = defaultdict(dict), defaultdict(list)
    for satir in satirlar:
        ham = satir["ham"]
        anahtar, opt = esleme_anahtari(ham), ham["opt"]
        if opt in gruplar[anahtar]:
            raise ValueError("Aynı kaynak/kip/opt için birden çok doğrulama satırı")
        gruplar[anahtar][opt] = satir
        opt_gruplari[opt].append(satir)
    opt_ozeti = {}
    for opt, rs in sorted(opt_gruplari.items()):
        string_sayisi = sum('"' in r["ham"]["asm"] for r in rs)
        opt_ozeti[opt] = {
            "n": len(rs),
            "ortalama_f1": math.fsum(r["f1"] for r in rs) / len(rs),
            "string_var": string_sayisi,
            "string_orani": string_sayisi / len(rs),
            "komut_ortancasi": statistics.median(r["ham"]["komut_sayisi"] for r in rs),
        }
    ciftler = {}
    for sol, sag in combinations(sorted(opt_gruplari), 2):
        eslesen = [g for _, g in sorted(gruplar.items()) if sol in g and sag in g]
        farklar = [g[sag]["f1"] - g[sol]["f1"] for g in eslesen]
        string_ayni = sum(('"' in g[sol]["ham"]["asm"]) == ('"' in g[sag]["ham"]["asm"]) for g in eslesen)
        ciftler[f"{sol} -> {sag}"] = {
            "n": len(eslesen),
            "ortalama_f1_farki": math.fsum(farklar) / len(farklar) if farklar else None,
            "esli_bootstrap_ga95": bootstrap(farklar, tohum, tekrar),
            "string_durumu_ayni": string_ayni,
        }
    desenler = Counter("+".join(sorted(g)) for g in gruplar.values())
    return {
        "sema": 2,
        "bolum": "valid300",
        "satir": len(satirlar),
        "kaynak_islev_kip_grubu": len(gruplar),
        "birden_cok_opt_grubu": sum(len(g) > 1 for g in gruplar.values()),
        "opt_deseni": dict(sorted(desenler.items())),
        "opt": opt_ozeti,
        "esli_cift": ciftler,
        "bootstrap_tekrar": tekrar,
        "bootstrap_tohum": tohum,
        "bootstrap_birimi": "Aynı kaynak işlev/kip çifti; projeler arası bağımlılığı gidermez",
        "yorum": "Tanısal eşli karşılaştırma; küçük n ve çoklu karşılaştırma nedeniyle seçim kapısı değildir.",
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--veri", type=Path, required=True)
    ap.add_argument("--tahmin", type=Path, required=True)
    ap.add_argument("--tohum", type=int, default=42)
    ap.add_argument("--bootstrap", type=int, default=2000)
    ap.add_argument("-o", "--cikti", type=Path)
    a = ap.parse_args(argv)
    try:
        sonuc = denetle(girdileri_yukle(a.veri, a.tahmin), a.tohum, a.bootstrap)
        sonuc["girdi"] = {"veri": dg.dosya_izi(a.veri), "tahmin": dg.dosya_izi(a.tahmin)}
        sonuc["kod"] = dg.git_izi()
        metin = dg.json_metni(sonuc)
        if a.cikti:
            a.cikti.parent.mkdir(parents=True, exist_ok=True)
            a.cikti.write_bytes(metin.encode("utf-8"))
        else:
            print(metin, end="")
    except (OSError, ValueError, KeyError) as hata:
        ap.error(str(hata))


if __name__ == "__main__":
    main()
