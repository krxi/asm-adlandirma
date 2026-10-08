# -*- coding: utf-8 -*-
"""Ghidra'ya bağlı olmayan metin biçimleme yardımcıları.

Bu dosya bilerek Python 2.7 sözdizimiyle de ayrıştırılabilir. Böylece aynı
yardımcılar hem PyGhidra/Python 3'te hem eski Jython kurulumlarında çalışır.
"""
from __future__ import unicode_literals

import json
import keyword
import re


try:
    METIN = (str, unicode)  # noqa: F821 - yalnız Python 2'de tanımlı
except NameError:
    METIN = (str,)


TURKCE = {
    "ç": "c", "Ç": "C", "ğ": "g", "Ğ": "G", "ı": "i", "İ": "I",
    "ö": "o", "Ö": "O", "ş": "s", "Ş": "S", "ü": "u", "Ü": "U",
}


def string_goster(deger, sinir=80):
    """Bir string'i veri setindeki ``"..."`` gösterimine çevir."""
    deger = metin(deger)
    deger = (deger.replace("\\", "\\\\").replace('"', '\\"')
             .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t"))
    if len(deger) > sinir:
        deger = deger[:sinir].rstrip("\\") + "…"
    return '"' + deger + '"'


def metin(deger):
    """Java/Python değerini güvenli biçimde metne dönüştür."""
    if deger is None:
        return ""
    if isinstance(deger, METIN):
        return deger
    return str(deger)


def islenenleri_temizle(islenenler):
    """Ghidra'nın otomatik sembollerini ve sık görülen yazım farklarını gizle."""
    sonuc = metin(islenenler).strip().lower()
    sonuc = re.sub(r"\b(?:dat|lab|off|unk|ptr)_[0-9a-f]+\b", "veri", sonuc,
                    flags=re.IGNORECASE)
    sonuc = re.sub(r"\b(?:switchd|jumptable)_[a-z0-9_.$]+\b", "veri", sonuc,
                    flags=re.IGNORECASE)
    sonuc = re.sub(r"\bfun_([0-9a-f]+)\b", r"sub_\1", sonuc, flags=re.IGNORECASE)
    sonuc = re.sub(r"\s*,\s*", ", ", sonuc)
    sonuc = re.sub(r"\s+", " ", sonuc)
    return sonuc


def asm_bicimle(komutlar):
    """Soyut komut kayıtlarını eğitim verisine benzeyen assembly'ye çevir.

    Her kayıt ``adres``, ``mnemonik`` ve ``islenenler`` alanlarını taşıyabilir.
    Doğrudan yerel dal için ``dal``, çağrı için çözülmüş ``cagri`` ve string
    referansı için ham ``string`` alanı kullanılır. Ghidra nesnesi gerekmez.
    """
    etiketler = {}
    for kayit in komutlar:
        hedef = kayit.get("dal")
        if hedef is not None and hedef not in etiketler:
            etiketler[hedef] = "loc_%d" % (len(etiketler) + 1)

    satirlar = []
    for kayit in komutlar:
        adres = kayit.get("adres")
        if adres in etiketler:
            satirlar.append(etiketler[adres] + ":")

        mnemonik = metin(kayit.get("mnemonik")).strip().lower()
        if kayit.get("cagri"):
            islenenler = metin(kayit["cagri"])
        elif kayit.get("dal") is not None:
            islenenler = etiketler[kayit["dal"]]
        else:
            islenenler = islenenleri_temizle(kayit.get("islenenler", ""))
        satir = mnemonik + (("\t" + islenenler) if islenenler else "")
        if kayit.get("string") is not None:
            satir += "    ; -> " + string_goster(kayit["string"])
        satirlar.append(satir)
    return "\n".join(satirlar)


def tekil(liste, deger, sinir):
    if deger not in liste and len(liste) < sinir:
        liste.append(deger)


def ic_cagrilar(asm):
    """Assembly'deki anonim iç çağrıları ilk görülme sırasıyla döndür."""
    sonuc = []
    for satir in asm.splitlines():
        eslesme = re.match(r"^\s*(?:call|jmp)\w*\s+(sub_[0-9a-f]+)\b", satir, re.I)
        if eslesme:
            tekil(sonuc, eslesme.group(1).lower(), 8)
    return sonuc


def fonksiyon_ozeti(kimlik, komut_sayisi, asm):
    """``cikar.py`` bağlamıyla aynı biçimde tek satırlık özet üret."""
    ithaller, stringler = [], []
    for satir in asm.splitlines():
        cagri = re.match(r"^\s*(?:call|jmp)\w*\s+([^\s;]+)", satir, re.I)
        if cagri:
            hedef = cagri.group(1)
            if not hedef.startswith(("sub_", "loc_")):
                tekil(ithaller, hedef, 6)
        yazi = re.search(r";\s*->\s*(\".*\")\s*$", satir)
        if yazi:
            hedef = yazi.group(1)
            if len(hedef) > 60:
                hedef = hedef[:58].rstrip("\\") + '…"'
            tekil(stringler, hedef, 4)

    cagrilar = ic_cagrilar(asm)[:4]
    parcalar = []
    if ithaller or cagrilar:
        parcalar.append("çağırır " + ", ".join(ithaller + cagrilar))
    if stringler:
        parcalar.append("string " + ", ".join(stringler))
    bas = "%s (%d komut)" % (kimlik, komut_sayisi)
    return bas + ((": " + "; ".join(parcalar)) if parcalar else "")


def cevap_ayristir(yanit):
    """OpenAI yanıtındaki son JSON nesnesinden ad ve açıklamayı al."""
    icerik = yanit["choices"][0]["message"].get("content") or ""
    nesneler = re.findall(r"\{[^{}]*\}", metin(icerik), flags=re.DOTALL)
    if not nesneler:
        return {"ad": metin(icerik).strip()[:80], "aciklama": ""}
    try:
        sonuc = json.loads(nesneler[-1])
    except (TypeError, ValueError):
        return {"ad": "", "aciklama": metin(icerik).strip()[:300]}
    return {"ad": metin(sonuc.get("ad", "")),
            "aciklama": metin(sonuc.get("aciklama", ""))}


# Modelin girdiden kopyaladığı yer tutucular ve komut adları ad sayılmaz.
ANLAMSIZ = re.compile(r"^(sub|fun|dat|loc|lab)_[0-9a-f?]+$|^(fonksiyon_adi|snake_case_tahmin)$|^(push|mov|sub|call)_r")


def gecerli_ad(ad, sinir=80):
    """Model tahminini taşınabilir bir ASCII tanımlayıcıya indirger."""
    ad = "".join(TURKCE.get(harf, harf) for harf in metin(ad).strip())
    ad = re.sub(r"[^A-Za-z0-9_]+", "_", ad).strip("_").lower()
    ad = re.sub(r"_+", "_", ad)[:sinir].rstrip("_")
    if not ad:
        return ""
    if ad[0].isdigit():
        ad = "fonk_" + ad
    if keyword.iskeyword(ad):
        ad = "fonk_" + ad
    if ANLAMSIZ.search(ad):
        return ""
    return ad
