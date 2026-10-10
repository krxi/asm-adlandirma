"""Araştırma araçları için sabit kimlik sınırı ve taşınabilir kanıt yardımcıları."""

import hashlib
import json
import math
import subprocess
from pathlib import Path

KOK = Path(__file__).resolve().parent
MANIFEST = KOK / "rapor/arastirma/dogrulama_manifest.json"


def sha256(yol):
    return hashlib.sha256(Path(yol).read_bytes()).hexdigest()


def manifest_oku():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def jsonl_oku(yol):
    sonuc = {}
    for no, satir in enumerate(Path(yol).read_text(encoding="utf-8").splitlines(), 1):
        if not satir.strip():
            continue
        try:
            r = json.loads(satir)
        except ValueError:
            raise ValueError(f"JSONL satırı {no}: geçersiz JSON") from None
        if not isinstance(r, dict) or not isinstance(r.get("id"), str) or not r["id"]:
            raise ValueError(f"JSONL satırı {no}: kimlik eksik")
        if r["id"] in sonuc:
            raise ValueError("Yinelenen kimlik")
        sonuc[r["id"]] = r
    if not sonuc:
        raise ValueError("Boş JSONL")
    return sonuc


def kimlik_kumesi_dogrula(kimlikler, izinli, yasak):
    kimlikler = list(kimlikler)
    if not kimlikler or len(kimlikler) != len(set(kimlikler)):
        raise ValueError("Boş veya yinelenen kimlik kümesi")
    if set(kimlikler) & set(yasak):
        raise ValueError("Test veya eval115 kimliği reddedildi")
    if not set(kimlikler) <= set(izinli):
        raise ValueError("Sabit doğrulama kimlik kümesi dışında girdi")


def dayanaklar():
    m = manifest_oku()
    yol = KOK / m["sabit_dogrulama"]["dosya"]
    if sha256(yol) != m["sabit_dogrulama"]["sha256"]:
        raise ValueError("Sabit doğrulama dayanağının SHA-256 değeri uyuşmuyor")
    sabit = jsonl_oku(yol)
    yasak = set((KOK / "lora/test_sabit_idler.txt").read_text(encoding="utf-8").splitlines())
    yasak |= set(jsonl_oku(KOK / "veri/test.jsonl"))
    kimlik_kumesi_dogrula(sabit, sabit, yasak)
    return sabit, yasak


def kimlikleri_dogrula(kimlikler):
    sabit, yasak = dayanaklar()
    kimlik_kumesi_dogrula(kimlikler, sabit, yasak)
    return sabit


def ham_dogrula(veri_yolu, veri, tahminler):
    """Tam v4 doğrulama dosyası veya sabit kümenin kanonik alt kümesi; ada bakılmaz."""
    sabit, yasak = dayanaklar()
    if set(veri) & yasak:
        raise ValueError("Ham girdide test veya eval115 kimliği var")
    if sha256(veri_yolu) != manifest_oku()["tam_dogrulama_sha256"]:
        kimlik_kumesi_dogrula(veri, sabit, yasak)
    kimlik_kumesi_dogrula(tahminler, sabit, yasak)
    if not set(tahminler) <= set(veri):
        raise ValueError("Tahminde validation verisi dışında kimlik var")
    for k in set(veri) & set(sabit):
        r, s = veri[k], sabit[k]
        if r.get("ad") != s.get("gercek") or r.get("proje") != s.get("proje") or r.get("opt") != s.get("opt"):
            raise ValueError("Kanonik doğrulama etiketi/projesi/opt bilgisi uyuşmuyor")
    return sabit


def tahmin_ozetini_dogrula(yol, surum="v5"):
    beklenen = manifest_oku()["dondurulmus_tahminler"].get(surum)
    if not beklenen or sha256(yol) != beklenen:
        raise ValueError("Dondurulmuş tahmin SHA-256 değeri uyuşmuyor")


def dosya_izi(yol):
    p = Path(yol).resolve()
    try:
        ad = p.relative_to(KOK.resolve()).as_posix()
    except ValueError:
        ad = p.name
    return {"dosya": ad, "sha256": sha256(p)}


def git_izi():
    def oku(ref):
        return subprocess.check_output(["git", "rev-parse", ref], cwd=KOK, text=True).strip()

    return {"commit": oku("HEAD"), "tree": oku("HEAD^{tree}")}


def json_metni(nesne):
    """Sürümler arasında aynı UTF-8 JSON: sıralı anahtar, 9 basamak, NaN yok."""
    def duzelt(x):
        if isinstance(x, float):
            if not math.isfinite(x):
                raise ValueError("Sonlu olmayan JSON sayısı")
            return round(x, 9) if round(x, 9) != 0 else 0.0
        if isinstance(x, dict):
            return {k: duzelt(v) for k, v in sorted(x.items())}
        if isinstance(x, (list, tuple)):
            return [duzelt(v) for v in x]
        return x

    return json.dumps(duzelt(nesne), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
