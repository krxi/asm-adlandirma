#!/usr/bin/env python3
"""Sabit valid300 üzerinde kör açıklama değerlendirmesi; ağ veya model çağrısı yok."""

import argparse
import hashlib
import json
import math
import os
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

import dogrulama_guvencesi as dg

BOYUTLAR = ("ana_islem", "girdi_cikti", "yan_etki")
ALANLAR = (*BOYUTLAR, "uydurma")
NITELIKLER = {"dogru", "kismi", "yanlis", "bilinmiyor"}
UYDURMA = {"yok", "var", "bilinmiyor"}
KOK = Path(__file__).resolve().parent


def jsonl_oku(yol):
    satirlar = []
    for no, satir in enumerate(Path(yol).read_text(encoding="utf-8").splitlines(), 1):
        if satir.strip():
            try:
                kayit = json.loads(satir)
            except ValueError:
                raise ValueError(f"JSONL satırı {no}: geçersiz JSON") from None
            if not isinstance(kayit, dict):
                raise ValueError("JSONL satırı nesne olmalı")
            satirlar.append(kayit)
    if not satirlar:
        raise ValueError("Boş JSONL")
    return satirlar


def dosya_ozeti(yol):
    return dg.sha256(yol)


def tahmin_argumani(deger):
    if "=" not in deger:
        raise argparse.ArgumentTypeError("tahmin SISTEM=YOL biçiminde olmalı")
    sistem, yol = deger.split("=", 1)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", sistem) or not yol:
        raise argparse.ArgumentTypeError("sistem etiketi ASCII harf/rakam/alt çizgi; yol boş olamaz")
    return sistem, Path(yol)


def girdileri_yukle(veri_yolu, tahminler):
    if not tahminler or len({ad for ad, _ in tahminler}) != len(tahminler):
        raise ValueError("En az bir benzersiz sistem gerekli")
    sabit, yasak = dg.dayanaklar()
    veri = dg.jsonl_oku(veri_yolu)
    sistemler = {}
    for ad, yol in tahminler:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", ad):
            raise ValueError("Geçersiz sistem etiketi")
        rs = dg.jsonl_oku(yol)
        dg.ham_dogrula(veri_yolu, veri, rs)
        dg.kimlik_kumesi_dogrula(rs, sabit, yasak)
        acik = sum(isinstance(r.get("aciklama_en"), str) and bool(r["aciklama_en"].strip()) for r in rs.values())
        # Kesişim almak yok: her aday sabit doğrulama havuzunun tamamını kapsar.
        if set(rs) != set(sabit) or acik != len(sabit):
            raise ValueError(
                f"Aday kapsamı eşik altında: {ad}, beklenen={len(sabit)}, mevcut={len(rs)}, "
                f"aciklama_en={acik}, gerekli_oran=1.0"
            )
        sistemler[ad] = rs
    if not set(sabit) <= set(veri):
        raise ValueError("Sabit doğrulama havuzunda ham veri eksik")
    return {k: veri[k] for k in sorted(sabit)}, sistemler


def _sirala(deger, tohum):
    return hashlib.sha256(f"{tohum}\0{deger}".encode()).hexdigest()


def ornekle(veri, n, tohum):
    if n <= 0 or n > len(veri):
        raise ValueError("n pozitif ve sabit havuzdan büyük olmamalı")
    projeler = defaultdict(list)
    for kimlik, kayit in veri.items():
        projeler[kayit["proje"]].append(kimlik)
    for proje, ids in projeler.items():
        ids.sort(key=lambda x: _sirala(f"{proje}\0{x}", tohum))
    proje_sirasi = sorted(projeler, key=lambda x: _sirala(x, tohum))
    secilen, sira = [], 0
    while len(secilen) < n:
        for proje in proje_sirasi:
            if sira < len(projeler[proje]) and len(secilen) < n:
                secilen.append(projeler[proje][sira])
        sira += 1
    return secilen


def _dagilim(veri, kimlikler, alan):
    return dict(sorted(Counter(str(veri[k].get(alan) or "bilinmiyor") for k in kimlikler).items()))


def plan_hazirla(veri_yolu, tahminler, n, tohum):
    iz = {"veri": dg.dosya_izi(veri_yolu), **{ad: dg.dosya_izi(yol) for ad, yol in tahminler}}
    veri, sistemler = girdileri_yukle(veri_yolu, tahminler)
    secilen = ornekle(veri, n, tohum)
    if iz != {"veri": dg.dosya_izi(veri_yolu), **{ad: dg.dosya_izi(yol) for ad, yol in tahminler}}:
        raise ValueError("Girdi çalışma sırasında değişti")
    stringler = Counter("var" if '"' in veri[k].get("asm", "") else "yok" for k in secilen)
    manifest = {
        "sema": 2,
        "bolum": "valid300",
        "n": len(secilen),
        "tohum": tohum,
        "sabit_havuz": len(veri),
        "sistemler": [ad for ad, _ in tahminler],
        "referans": tahminler[0][0],
        "aday_kapsami": {ad: {"beklenen": len(veri), "mevcut": len(rs), "oran": 1.0} for ad, rs in sistemler.items()},
        "asgari_aday_kapsami": 1.0,
        "secilen_id_sha256": hashlib.sha256("\n".join(secilen).encode()).hexdigest(),
        "iz": {**dg.git_izi(), "girdiler": iz},
        "dagilim": {
            "proje": _dagilim(veri, secilen, "proje"),
            "opt": _dagilim(veri, secilen, "opt"),
            "string": dict(sorted(stringler.items())),
        },
        "bilinmeyen_puani": 0.0,
        "puan_paydasi": 4,
    }
    return manifest, secilen, {"veri": veri, "sistemler": sistemler}


def kaynaklari_yukle(yol):
    yollar = sorted(yol.glob("*.jsonl")) if yol.is_dir() else [yol]
    kaynaklar = {}
    for dosya in yollar:
        for kayit in jsonl_oku(dosya):
            anahtar, kaynak = kayit.get("anahtar"), kayit.get("kaynak")
            if isinstance(anahtar, str) and isinstance(kaynak, str) and kaynak:
                if anahtar in kaynaklar and kaynaklar[anahtar] != kaynak:
                    raise ValueError("Bir anahtar için birden çok farklı kaynak")
                kaynaklar[anahtar] = kaynak
    return kaynaklar


def kaynak_anahtari(kayit):
    return f"{kayit['proje']}/{kayit['dosya']}:{kayit['ad']}"


def repo_disinda_yeni(yol):
    yol = Path(yol).resolve()
    if yol == KOK.resolve() or KOK.resolve() in yol.parents:
        raise ValueError("Kör paket, etiket ve anahtar repo dışında olmalı")
    if yol.exists():
        raise ValueError("Çıktı dosyası zaten var; üzerine yazılmaz")
    return yol


def ozel_yaz(yol, metin):
    yol.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(yol, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as dosya:
        dosya.write(metin)


def paketle(manifest, secilen, girdiler, kaynak_yolu, paket_yolu, anahtar_yolu=None):
    dg.kimlikleri_dogrula(secilen)
    kaynaklar = kaynaklari_yukle(kaynak_yolu)
    veri, sistemler = girdiler["veri"], girdiler["sistemler"]
    if any(kaynak_anahtari(veri[k]) not in kaynaklar for k in secilen):
        raise ValueError("Seçilen işlevlerden birinin C kaynağı yok")
    adaylar = [(k, s) for k in secilen for s in sorted(sistemler)]
    adaylar.sort(key=lambda x: _sirala(f"{x[0]}\0{x[1]}", manifest["tohum"] + 1))
    paket, gizli = [], []
    for no, (kimlik, sistem) in enumerate(adaylar, 1):
        ornek = f"A{no:04d}"
        paket.append(
            {
                "ornek": ornek,
                "c_kaynagi": kaynaklar[kaynak_anahtari(veri[kimlik])],
                "aciklama_en": sistemler[sistem][kimlik]["aciklama_en"],
            }
        )
        gizli.append({"ornek": ornek, "id": kimlik, "sistem": sistem, "proje": veri[kimlik]["proje"]})
    metin = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in paket)
    paket_sha = hashlib.sha256(metin.encode("utf-8")).hexdigest()
    paket_yolu = repo_disinda_yeni(paket_yolu)
    anahtar_yolu = repo_disinda_yeni(
        anahtar_yolu or KOK.parent / "asmsense-ozel" / f"{paket_sha[:16]}.asmsense-kor-anahtar.json"
    )
    sablon_yolu = repo_disinda_yeni(paket_yolu.with_name(paket_yolu.name + ".etiket-sablonu.jsonl"))
    if len({paket_yolu, anahtar_yolu, sablon_yolu}) != 3:
        raise ValueError("Paket, anahtar ve etiket şablonu ayrı dosya olmalı")
    # Etiketler özgün paketi değiştirmez; her satır o paketin gerçek bayt hash'ini taşır.
    sablon = [{"ornek": r["ornek"], "paket_sha256": paket_sha, **dict.fromkeys(ALANLAR, ""), "not": ""} for r in paket]
    ozel_yaz(paket_yolu, metin)
    ozel_yaz(anahtar_yolu, dg.json_metni({"manifest": manifest, "paket_sha256": paket_sha, "esleme": gizli}))
    ozel_yaz(sablon_yolu, "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in sablon))
    return {
        "paket": dg.dosya_izi(paket_yolu),
        "anahtar": dg.dosya_izi(anahtar_yolu),
        "etiket_sablonu": sablon_yolu.name,
    }


def etiketleri_yukle(yol, paket_sha):
    etiketler = {}
    for kayit in jsonl_oku(yol):
        ornek = kayit.get("ornek")
        if not isinstance(ornek, str) or not ornek or ornek in etiketler:
            raise ValueError("Eksik veya yinelenen örnek")
        if kayit.get("paket_sha256") != paket_sha:
            raise ValueError("Etiket dosyası farklı paket SHA-256 değerine bağlı")
        if any(kayit.get(k) not in NITELIKLER for k in BOYUTLAR) or kayit.get("uydurma") not in UYDURMA:
            raise ValueError("Geçersiz veya doldurulmamış değerlendirme alanı")
        etiketler[ornek] = kayit
    return etiketler


def cohen_kappa(a, b):
    if not a or len(a) != len(b):
        return None
    n = len(a)
    ca, cb = Counter(a), Counter(b)
    beklenen = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    if math.isclose(beklenen, 1.0):
        return None
    return (sum(x == y for x, y in zip(a, b)) / n - beklenen) / (1 - beklenen)


def puan(kayit):
    ceviri = {"dogru": 1.0, "kismi": 0.5, "yanlis": 0.0, "bilinmiyor": 0.0}
    toplam = sum(ceviri[kayit[b]] for b in BOYUTLAR) + (kayit["uydurma"] == "yok")
    return toplam / 4, sum(kayit[k] != "bilinmiyor" for k in ALANLAR)


def alan_ozeti(etiketler):
    n = len(etiketler)
    if not n:
        raise ValueError("Boş sistem değerlendirmesi")
    oranlar = {}
    for alan in ALANLAR:
        say = Counter(r[alan] for r in etiketler)
        oranlar[alan] = {k: say[k] / n for k in sorted(UYDURMA if alan == "uydurma" else NITELIKLER)}
    return {
        "n": n,
        "ortalama": math.fsum(puan(r)[0] for r in etiketler) / n,
        "karar_kapsami": sum(puan(r)[1] for r in etiketler) / (4 * n),
        "alan_oranlari": oranlar,
        "uydurma_var_orani": oranlar["uydurma"]["var"],
        "uydurma_risk_orani": oranlar["uydurma"]["var"] + oranlar["uydurma"]["bilinmiyor"],
    }


def bootstrap_farki(a, b, projeler, tohum, tekrar=2000):
    if not a or len(a) != len(b) or len(a) != len(projeler):
        raise ValueError("Eşli karşılaştırma kapsamları farklı")
    farklar = [x - y for x, y in zip(a, b)]
    gruplar = defaultdict(list)
    for proje, fark in zip(projeler, farklar):
        gruplar[proje].append(fark)
    gs = [gruplar[k] for k in sorted(gruplar)]
    rng, dagilim = random.Random(tohum), []
    for _ in range(tekrar):
        secilen = [rng.choice(gs) for _ in gs]
        dagilim.append(math.fsum(x for g in secilen for x in g) / sum(map(len, secilen)))
    dagilim.sort()
    return {
        "fark": math.fsum(farklar) / len(farklar),
        "ga95": [dagilim[int(0.025 * tekrar)], dagilim[int(0.975 * tekrar)]],
        "bootstrap_birimi": "proje; aynı kaynak/opt satırları birlikte",
        "proje_sayisi": len(gs),
    }


def puanla(anahtar_yolu, etiket_yollari, uzlasi_yolu, tohum, paket_yolu):
    if len(etiket_yollari) != 2 or len({p.resolve() for p in etiket_yollari}) != 2:
        raise ValueError("İki ayrı puanlayıcı dosyası gerekli")
    paket_sha = dosya_ozeti(paket_yolu)
    gizli = json.loads(anahtar_yolu.read_text(encoding="utf-8"))
    if gizli.get("paket_sha256") != paket_sha:
        raise ValueError("Kör anahtar ile özgün paket SHA-256 uyuşmuyor")
    paket = jsonl_oku(paket_yolu)
    rs = gizli["esleme"]
    esleme = {r["ornek"]: r for r in rs}
    paket_idler = {r["ornek"] for r in paket}
    if len(esleme) != len(rs) or len(paket_idler) != len(paket) or set(esleme) != paket_idler:
        raise ValueError("Paket/anahtar örnek kapsamı farklı veya yinelenmiş")
    sistemler = gizli["manifest"]["sistemler"]
    n = gizli["manifest"]["n"]
    if not sistemler or len(set(sistemler)) != len(sistemler):
        raise ValueError("Kör anahtarda sistem kapsamı bozuk")
    ids = sorted({r["id"] for r in rs})
    dg.kimlikleri_dogrula(ids)
    if len(ids) != n or len(rs) != n * len(sistemler):
        raise ValueError("Kör anahtarda sabit eşli örnek kapsamı eksik")
    if {(r["id"], r["sistem"]) for r in rs} != {(k, s) for k in ids for s in sistemler}:
        raise ValueError("Kör anahtarda sistem/işlev eşleşmesi eksik")
    sabit, _ = dg.dayanaklar()
    if any(r["proje"] != sabit[r["id"]]["proje"] for r in rs):
        raise ValueError("Kör anahtarın proje bilgisi kanonik kimlikten farklı")
    etiketler = [etiketleri_yukle(yol, paket_sha) for yol in etiket_yollari]
    beklenen = set(esleme)
    if any(set(e) != beklenen for e in etiketler):
        raise ValueError("Puanlayıcı örnek kapsamı eksik/fazla")
    uyum = {}
    for alan in ALANLAR:
        a, b = ([e[k][alan] for k in sorted(beklenen)] for e in etiketler)
        kappa = cohen_kappa(a, b)
        uyum[alan] = {
            "n": len(a),
            "ham": sum(x == y for x, y in zip(a, b)) / len(a),
            "kappa": kappa,
            "kappa_nedeni": "tek sınıf nedeniyle beklenen uyum 1; kappa tanımsız" if kappa is None else None,
        }
    sonuc = {
        "sema": 2,
        "manifest": gizli["manifest"],
        "paket_sha256": paket_sha,
        "puanlayici_sayisi": 2,
        "uyum": uyum,
        "iz": {**dg.git_izi(), "etiketler": [dg.dosya_izi(yol) for yol in etiket_yollari]},
        "puanlayici_alan_oranlari": {
            str(i + 1): {s: alan_ozeti([e[k] for k in sorted(e) if esleme[k]["sistem"] == s]) for s in sistemler}
            for i, e in enumerate(etiketler)
        },
    }
    if uzlasi_yolu is None:
        sonuc.update({"uzlasi": "not run", "aday_kapilari": None})
        return sonuc
    uzlasi = etiketleri_yukle(uzlasi_yolu, paket_sha)
    if set(uzlasi) != beklenen:
        raise ValueError("Uzlaşı örnek kapsamı eksik/fazla")
    sk = {s: {} for s in sistemler}
    for ornek in sorted(uzlasi):
        r = esleme[ornek]
        sk[r["sistem"]][r["id"]] = uzlasi[ornek]
    ozet = {s: alan_ozeti([sk[s][k] for k in ids]) for s in sistemler}
    referans = gizli["manifest"]["referans"]
    if referans not in sistemler:
        raise ValueError("Referans sistem kör anahtarda yok")
    farklar, kapilar = {}, {}
    for aday in sorted(set(sistemler) - {referans}):
        a, r = ozet[aday], ozet[referans]
        fark = bootstrap_farki(
            [puan(sk[aday][k])[0] for k in ids],
            [puan(sk[referans][k])[0] for k in ids],
            [sabit[k]["proje"] for k in ids],
            tohum,
        )
        farklar[f"{aday} - {referans}"] = {"n": n, **fark}
        kapi = {
            "karar_kapsami_azalmadi": a["karar_kapsami"] >= r["karar_kapsami"],
            "uydurma_var_artmadi": a["uydurma_var_orani"] <= r["uydurma_var_orani"],
            "uydurma_bilinmeyen_riski_artmadi": a["uydurma_risk_orani"] <= r["uydurma_risk_orani"],
        }
        kapi["guvenlik_kapisi"] = all(kapi.values())
        kapilar[aday] = kapi
    sonuc.update({"uzlasi": "run", "sistemler": ozet, "eslenik_farklar": farklar, "aday_kapilari": kapilar})
    sonuc["iz"]["uzlasi"] = dg.dosya_izi(uzlasi_yolu)
    return sonuc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    alt = ap.add_subparsers(dest="komut", required=True)
    ortak = argparse.ArgumentParser(add_help=False)
    ortak.add_argument("--veri", type=Path, required=True)
    ortak.add_argument("--tahmin", action="append", type=tahmin_argumani, required=True, metavar="SISTEM=YOL")
    ortak.add_argument("-n", type=int, default=100)
    ortak.add_argument("--tohum", type=int, default=42)
    plan = alt.add_parser("plan", parents=[ortak])
    plan.add_argument("-o", "--cikti", type=Path)
    paket = alt.add_parser("paketle", parents=[ortak])
    paket.add_argument("--kaynak", type=Path, required=True)
    paket.add_argument("--paket", type=Path, required=True)
    paket.add_argument("--anahtar", type=Path, help="varsayılan: repo dışındaki ../asmsense-ozel/")
    deger = alt.add_parser("puanla")
    deger.add_argument("--paket", type=Path, required=True, help="değiştirilmemiş özgün kör paket")
    deger.add_argument("--anahtar", type=Path, required=True)
    deger.add_argument("--etiket", action="append", type=Path, required=True)
    deger.add_argument("--uzlasi", type=Path)
    deger.add_argument("--tohum", type=int, default=42)
    deger.add_argument("-o", "--cikti", type=Path)
    a = ap.parse_args(argv)
    try:
        if a.komut in ("plan", "paketle"):
            sonuc, secilen, girdiler = plan_hazirla(a.veri, a.tahmin, a.n, a.tohum)
            if a.komut == "paketle":
                sonuc = {**sonuc, "paketleme": paketle(sonuc, secilen, girdiler, a.kaynak, a.paket, a.anahtar)}
        else:
            sonuc = puanla(a.anahtar, a.etiket, a.uzlasi, a.tohum, a.paket)
        metin = dg.json_metni(sonuc)
        if getattr(a, "cikti", None):
            yol = repo_disinda_yeni(a.cikti)
            ozel_yaz(yol, metin)
        else:
            print(metin, end="")
    except ValueError as hata:
        ap.error(str(hata))
    except KeyError:
        ap.error("Paket veya etiket şemasında gerekli alan eksik")
    except OSError:
        ap.error("Girdi/çıktı dosyası kullanılamadı; kişisel yol günlüğe yazılmadı")


if __name__ == "__main__":
    main()
