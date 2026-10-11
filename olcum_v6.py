#!/usr/bin/env python3
"""Molab/Colab final JSONL'lerinden v6/v5 eşli ölçüm; GPU ve HF yazma işlemi yok."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path

from aciklama_degerlendir import bootstrap_farki
from ogretmen_denetim import bootstrap_araligi
from taban import f1, kelimeler

KOK = Path(__file__).resolve().parent
BOLUMLER = {"test_sabit": 2000, "eval115": 115}
V5_DOSYALAR = {"test_sabit": "test2000-molab-qwen3-8b-v5.jsonl",
               "eval115": "eval115-molab-qwen3-8b-v5.jsonl"}
V5_YAYIN = {"test_sabit": 0.124, "eval115": 0.155}
HEDEFLER = {"test_sabit": 0.14, "eval115": 0.17}


def oku(yol):
    with Path(yol).open(encoding="utf-8") as dosya:
        rows = [json.loads(line) for line in dosya if line.strip()]
    ids = [r["id"] for r in rows]
    if not rows or len(ids) != len(set(ids)):
        raise ValueError(f"{Path(yol).name}: boş dosya veya yinelenen id")
    return {r["id"]: r for r in rows}


def iz(yol):
    return {"dosya": Path(yol).name, "sha256": hashlib.sha256(Path(yol).read_bytes()).hexdigest()}


def indir(repo, revision, cikti):
    """Tek HF commit'inden final çıktıları al; son/ eğitim checkpoint'ini indirme."""
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        raise ValueError("HF_TOKEN ortam değişkeni gerekli (macOS: gizli calistir python3 olcum_v6.py indir ...)")
    from huggingface_hub import HfApi, hf_hub_download
    try:
        sha = HfApi(token=token).repo_info(repo, revision=revision).sha
        yollar = {}
        for ad in ("kosu.json", "en_iyi.json", "test_sabit-sonuc.jsonl", "eval115-sonuc.jsonl",
                   "test_sabit-tamam.json", "eval115-tamam.json"):
            yollar[ad] = Path(hf_hub_download(repo, ad, revision=sha, token=token, local_dir=cikti))
    except Exception as hata:
        raise RuntimeError(f"HF final sonuçları hazır değil veya erişilemiyor ({type(hata).__name__}); "
                           "son/ tek başına tamamlanmış test değildir.") from None
    en_iyi = json.loads(yollar["en_iyi.json"].read_text())
    kosu = json.loads(yollar["kosu.json"].read_text())
    for bolum, n in BOLUMLER.items():
        damga = json.loads(yollar[f"{bolum}-tamam.json"].read_text())
        if damga != {"en_iyi": en_iyi, "kosu": kosu}:
            raise ValueError(f"{bolum}: final damgası checkpoint/koşu ile uyuşmuyor")
        if len(oku(yollar[f"{bolum}-sonuc.jsonl"])) != n:
            raise ValueError(f"{bolum}: tamamlanmamış sonuç dosyası")
    manifest = {"repo": repo, "revision": sha, "en_iyi": en_iyi,
                "dosyalar": [iz(p) for p in yollar.values()]}
    # kosu.json yerel yollar içerebilir; yalnız indirilen özel dizinde kalır.
    Path(cikti, "hf-olcum-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def oneksiz(r, veri):
    at = set(veri["oneksiz_onek"])
    t = set(kelimeler(r["tahmin"])) - at
    g = set(kelimeler(veri["gercek_ad"])) - at or set(kelimeler(veri["gercek_ad"]))
    return 2 * len(t & g) / (len(t) + len(g)) if t & g else 0.0


def eslestir(veri, aday, v5, beklenen):
    if len(veri) != beklenen or set(veri) != set(aday) or set(veri) != set(v5):
        raise ValueError(f"Tam eşli kapsam gerekli: veri={len(veri)}, aday={len(aday)}, v5={len(v5)}, "
                         f"beklenen={beklenen}; id kümeleri aynı olmalı")
    rows = []
    for kimlik in sorted(veri):
        d, a, b = veri[kimlik], aday[kimlik], v5[kimlik]
        if not isinstance(d.get("oneksiz_onek"), list):
            raise ValueError(f"{kimlik}: öneksiz ölçüm metadata eksik")
        for alan in ("decompile_var", "decompile_kirpildi"):
            if type(d.get(alan)) is not bool:
                raise ValueError(f"{kimlik}: {alan} bool metadata gerekli")
        if d["decompile_kirpildi"] and not d["decompile_var"]:
            raise ValueError(f"{kimlik}: decompile yokken kırpıldı olamaz")
        if d["opt"] not in ("-O0", "-O1", "-O2", "-O3", "-Os", "-Oz"):
            raise ValueError(f"{kimlik}: beklenmeyen opt")
        for r in (a, b):
            if r.get("gercek") != d["gercek_ad"] or r.get("opt") != d["opt"] or r.get("proje") != d["proje"]:
                raise ValueError(f"{kimlik}: hedef/opt/proje eşleşmiyor")
            if not isinstance(r.get("tahmin"), str):
                raise ValueError(f"{kimlik}: tahmin string olmalı (boş string kabul edilir)")
        rows.append({"id": kimlik, "proje": d["proje"], "opt": d["opt"],
                     "decompile": "yok" if not d["decompile_var"] else "kirpildi" if d["decompile_kirpildi"] else "tam",
                     "f1": f1(a["tahmin"], d["gercek_ad"]), "v5_f1": f1(b["tahmin"], d["gercek_ad"]),
                     "oneksiz_f1": oneksiz(a, d), "v5_oneksiz_f1": oneksiz(b, d),
                     "tam_isabet": a["tahmin"] == d["gercek_ad"],
                     "kayitli_f1_uyumsuz": "f1" in a and abs(a["f1"] - f1(a["tahmin"], d["gercek_ad"])) > 0.00051})
    return rows


def ozet(rows):
    if not rows:
        return {"n": 0, "f1": None, "v5_f1": None, "fark": None, "oneksiz_f1": None,
                "v5_oneksiz_f1": None, "tam_isabet": 0, "f1_tam_isabet": 0, "oneksiz_f1_tam_isabet": 0}
    mean = lambda k: math.fsum(r[k] for r in rows) / len(rows)
    return {"n": len(rows), "f1": mean("f1"), "v5_f1": mean("v5_f1"),
            "fark": mean("f1") - mean("v5_f1"), "oneksiz_f1": mean("oneksiz_f1"),
            "v5_oneksiz_f1": mean("v5_oneksiz_f1"), "tam_isabet": sum(r["tam_isabet"] for r in rows),
            "f1_tam_isabet": sum(r["f1"] == 1 for r in rows),
            "oneksiz_f1_tam_isabet": sum(r["oneksiz_f1"] == 1 for r in rows),
            "kayitli_f1_uyumsuz": sum(r["kayitli_f1_uyumsuz"] for r in rows)}


def rapor(veri_dizin, aday_dizin, v5_dizin, tekrar=2000, tohum=42, kuru=False):
    if tekrar < 100:
        raise ValueError("Bootstrap tekrar >=100 olmalı")
    sonuc = {"surum": "v6-olcum-1", "kuru_v5": kuru,
             "protokol": {"kaynak": "molab/egit.py final eval", "do_sample": False,
                          "enable_thinking": False, "max_new_tokens": 160,
                          "checkpoint": "valid F1 en iyi; son/ eğitim son-adımıdır",
                          "bootstrap_tekrar": tekrar, "bootstrap_tohum": tohum,
                          "yorum": "Proje-kümeli GA95 ana aralık; satır aralığı tarihsel tanı. Alt gruplar tanısal, seçim kapısı değil."},
             "girdiler": {}, "bolumler": {}}
    for bolum, n in BOLUMLER.items():
        veri_yol = Path(veri_dizin, bolum + ".jsonl")
        v5_yol = Path(v5_dizin, V5_DOSYALAR[bolum])
        aday_yol = v5_yol if kuru else Path(aday_dizin, bolum + "-sonuc.jsonl")
        rows = eslestir(oku(veri_yol), oku(aday_yol), oku(v5_yol), n)
        s = ozet(rows)
        s.update(bootstrap_farki([r["f1"] for r in rows], [r["v5_f1"] for r in rows],
                                [r["proje"] for r in rows], tohum, tekrar))
        s["satir_bootstrap_ga95_tanisal"] = bootstrap_araligi([r["f1"] - r["v5_f1"] for r in rows], tohum, tekrar)
        s["v5_yayin_f1"] = V5_YAYIN[bolum]
        s["v5_yayin_tutuyor"] = round(s["v5_f1"], 3) == V5_YAYIN[bolum]
        s["hedef_f1"] = HEDEFLER[bolum]
        s["hedef_gecildi"] = not kuru and s["f1"] >= HEDEFLER[bolum]
        filtreler = {"var": lambda r: r["decompile"] != "yok",
                     **{k: lambda r, k=k: r["decompile"] == k for k in ("tam", "kirpildi", "yok")}}
        opts = ["-O0", "-O1", "-O2", "-O3"] + sorted({r["opt"] for r in rows} - {"-O0", "-O1", "-O2", "-O3"})
        s["opt"] = {opt: ozet([r for r in rows if r["opt"] == opt]) for opt in opts}
        s["decompile"] = {k: ozet([r for r in rows if fn(r)]) for k, fn in filtreler.items()}
        s["opt_decompile"] = {opt: {k: ozet([r for r in rows if r["opt"] == opt and fn(r)])
                                    for k, fn in filtreler.items()} for opt in s["opt"]}
        sonuc["girdiler"][bolum] = {"veri": iz(veri_yol), "aday": iz(aday_yol), "v5": iz(v5_yol)}
        sonuc["bolumler"][bolum] = s
    manifest = Path(aday_dizin, "hf-olcum-manifest.json")
    if not kuru and manifest.exists():
        sonuc["hf"] = json.loads(manifest.read_text())
    return sonuc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="komut", required=True)
    download = sub.add_parser("indir", help="HF final JSONL+tamam damgalarını indir; model yüklemez")
    download.add_argument("--repo", default="krxi123/asmsense-lora-v6")
    download.add_argument("--revision", default="main")
    download.add_argument("--cikti", type=Path, required=True)
    report = sub.add_parser("rapor", help="Yerel molab/Colab JSONL veya indir çıktısı")
    report.add_argument("--veri", type=Path, required=True)
    report.add_argument("--sonuc", type=Path, default=Path("sonuc/v6"))
    report.add_argument("--v5", type=Path, default=KOK / "sonuc")
    report.add_argument("--kuru-v5", action="store_true")
    report.add_argument("--bootstrap", type=int, default=2000)
    report.add_argument("--tohum", type=int, default=42)
    report.add_argument("-o", "--cikti", type=Path)
    a = ap.parse_args(argv)
    try:
        s = indir(a.repo, a.revision, a.cikti) if a.komut == "indir" else rapor(
            a.veri, a.sonuc, a.v5, a.bootstrap, a.tohum, a.kuru_v5)
        metin = json.dumps(s, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if a.komut == "rapor" and a.cikti:
            a.cikti.parent.mkdir(parents=True, exist_ok=True)
            a.cikti.write_text(metin, encoding="utf-8")
        print(metin, end="")
    except (ValueError, OSError, RuntimeError) as hata:
        ap.exit(1, f"HATA: {hata}\n")


if __name__ == "__main__":
    main()
