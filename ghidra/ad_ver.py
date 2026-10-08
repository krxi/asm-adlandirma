# -*- coding: utf-8 -*-
#@category asm-adlandirma
#@menupath Tools.asm-adlandirma.Fonksiyonlara Ad Ver
"""Stripped x86-64 fonksiyonlarını yerel bir OpenAI uyumlu modelle adlandır."""
from __future__ import print_function, unicode_literals

# --- Kullanıcı ayarları ----------------------------------------------------
SUNUCU = "http://127.0.0.1:8080/v1"
MODEL = "mlx-community/Qwen2.5-Coder-0.5B-Instruct-4bit"
ANAHTAR_DEGISKENI = "OPENAI_API_KEY"
KURU_CALIS = True
EN_COK = 20
BAGLAM = False
ZAMAN_ASIMI = 300
# --------------------------------------------------------------------------

import json
import os
import sys

try:
    from urllib.request import Request, urlopen
except ImportError:                         # Jython 2.7
    from urllib2 import Request, urlopen

BETIK_DIZINI = os.path.dirname(os.path.abspath(__file__))
if BETIK_DIZINI not in sys.path:
    sys.path.insert(0, BETIK_DIZINI)

from bicim import asm_bicimle, cevap_ayristir, fonksiyon_ozeti, gecerli_ad

from ghidra.program.model.listing import CodeUnit
from ghidra.program.model.symbol import SourceType


# taban.py:SISTEM ile aynı tutulur.
SISTEM = ("Sen deneyimli bir tersine mühendissin. Sana sembolleri silinmiş bir x86-64 fonksiyonu "
          "(Intel sözdizimi) verilecek. Projenin iç fonksiyonları sub_XXXX diye gizlendi; dış "
          "kütüphane çağrıları görünür. Fonksiyonun asıl kaynak koddaki adını tahmin et. "
          'Yalnız JSON dön: {"ad": "snake_case_tahmin", "aciklama": "tek cümle Türkçe"}')
SISTEM_BAGLAM = SISTEM + " Çağrılan iç fonksiyonların özetleri asm'nin altında verildi."
YORUM_ON_EKI = "[asm-adlandirma] "


def yineleyici(java_yineleyici):
    """Java Iterator'ı PyGhidra ve Jython'da aynı biçimde dolaş."""
    while java_yineleyici.hasNext():
        yield java_yineleyici.next()


def ayarlar(ham):
    """Script argümanlarıyla üstteki güvenli varsayılanları değiştir."""
    kuru, en_cok, baglam = KURU_CALIS, EN_COK, BAGLAM
    i = 0
    while i < len(ham):
        secenek = str(ham[i])
        if secenek == "--kuru":
            kuru = True
        elif secenek == "--uygula":
            kuru = False
        elif secenek == "--baglam":
            baglam = True
        elif secenek == "--baglamsiz":
            baglam = False
        elif secenek == "--en-cok":
            i += 1
            if i >= len(ham):
                raise ValueError("--en-cok için sayı eksik")
            en_cok = int(ham[i])
        elif secenek.startswith("--en-cok="):
            en_cok = int(secenek.split("=", 1)[1])
        else:
            raise ValueError("bilinmeyen seçenek: " + secenek)
        i += 1
    if en_cok < 1:
        raise ValueError("--en-cok en az 1 olmalı")
    return kuru, en_cok, baglam


def sub_haritasi(fonksiyon_yoneticisi):
    """İç fonksiyon adreslerini adlardan bağımsız, kısa kimliklere bağla."""
    sonuc = {}
    sira = 0
    for fonksiyon in yineleyici(fonksiyon_yoneticisi.getFunctions(True)):
        if fonksiyon.isExternal():
            continue
        sonuc[str(fonksiyon.getEntryPoint())] = "sub_%04x" % sira
        sira += 1
    return sonuc


def dis_fonksiyon(fonksiyon):
    """Fonksiyon bir import ya da importa giden thunk ise dış hedefi döndür."""
    if fonksiyon is None:
        return None
    asil = fonksiyon
    try:
        if fonksiyon.isThunk():
            cozulmus = fonksiyon.getThunkedFunction(True)
            if cozulmus is not None:
                asil = cozulmus
    except Exception:
        pass
    return asil if asil.isExternal() else None


def hedef_fonksiyon(program, adres):
    yonetici = program.getFunctionManager()
    fonksiyon = yonetici.getFunctionAt(adres)
    if fonksiyon is None:
        fonksiyon = yonetici.getFunctionContaining(adres)
    return fonksiyon


def cagri_hedefi(program, komut):
    """Doğrudan çağrının hedef adresini referanslardan ya da akıştan bul."""
    for referans in komut.getReferencesFrom():
        if referans.getReferenceType().isCall():
            return referans.getToAddress()
    akislar = komut.getFlows()
    return akislar[0] if akislar else None


def cagri_adi(program, adres, sub_adlari):
    if adres is None:
        return None, None
    fonksiyon = hedef_fonksiyon(program, adres)
    dis = dis_fonksiyon(fonksiyon)
    if dis is not None:
        return str(dis.getName()), None
    if fonksiyon is not None:
        giris = fonksiyon.getEntryPoint()
        return sub_adlari.get(str(giris), "sub_%04x" % (giris.getOffset() & 0xffff)), fonksiyon
    return "sub_%04x" % (adres.getOffset() & 0xffff), None


def string_referansi(program, komut):
    """Komutun doğrudan işaret ettiği ilk tanımlı string'i döndür."""
    liste = program.getListing()
    for referans in komut.getReferencesFrom():
        if referans.getReferenceType().isFlow():
            continue
        veri = liste.getDataContaining(referans.getToAddress())
        if veri is None:
            continue
        try:
            if veri.hasStringValue():
                return str(veri.getValue())
        except Exception:
            continue
    return None


def fonksiyonu_bicimle(program, fonksiyon, sub_adlari):
    """Bir Ghidra fonksiyonunu saf biçimleyicinin kayıtlarına çevir."""
    liste = program.getListing()
    govde = fonksiyon.getBody()
    kayitlar, cagrilanlar = [], []
    for komut in yineleyici(liste.getInstructions(govde, True)):
        monitor.checkCancelled()
        islenenler = []
        for i in range(komut.getNumOperands()):
            islenenler.append(str(komut.getDefaultOperandRepresentation(i)))
        kayit = {"adres": komut.getAddress().getOffset(),
                 "mnemonik": str(komut.getMnemonicString()),
                 "islenenler": ", ".join(islenenler)}

        akis_turu = komut.getFlowType()
        if akis_turu.isCall():
            adres = cagri_hedefi(program, komut)
            ad, ic_fonksiyon = cagri_adi(program, adres, sub_adlari)
            if ad:
                kayit["cagri"] = ad
            if ic_fonksiyon is not None and ic_fonksiyon != fonksiyon and ic_fonksiyon not in cagrilanlar:
                cagrilanlar.append(ic_fonksiyon)
        elif akis_turu.isJump():
            akislar = komut.getFlows()
            if akislar and govde.contains(akislar[0]):
                kayit["dal"] = akislar[0].getOffset()

        yazi = string_referansi(program, komut)
        if yazi is not None:
            kayit["string"] = yazi
        kayitlar.append(kayit)
    return asm_bicimle(kayitlar), cagrilanlar, len(kayitlar)


def baglam_uret(program, cagrilanlar, sub_adlari):
    satirlar = []
    for fonksiyon in cagrilanlar[:8]:
        asm, _, sayi = fonksiyonu_bicimle(program, fonksiyon, sub_adlari)
        kimlik = sub_adlari.get(str(fonksiyon.getEntryPoint()), "sub_????")
        satirlar.append(fonksiyon_ozeti(kimlik, sayi, asm))
    return "\n".join(satirlar)


def modele_sor(asm, baglam):
    girdi = asm
    if baglam:
        girdi += "\n\n; --- çağrılan fonksiyonlar ---\n" + baglam
    govde = {"model": MODEL, "temperature": 0, "max_tokens": 2048,
             "messages": [{"role": "system", "content": SISTEM_BAGLAM if baglam else SISTEM},
                          {"role": "user", "content": girdi}]}
    veri = json.dumps(govde, ensure_ascii=False).encode("utf-8")
    basliklar = {"Content-Type": "application/json"}
    anahtar = os.environ.get(ANAHTAR_DEGISKENI)
    if anahtar:
        basliklar["Authorization"] = "Bearer " + anahtar
    istek = Request(SUNUCU.rstrip("/") + "/chat/completions", data=veri, headers=basliklar)
    yanit = urlopen(istek, timeout=ZAMAN_ASIMI).read()
    if not isinstance(yanit, str):
        yanit = yanit.decode("utf-8")
    return cevap_ayristir(json.loads(yanit))


def aday_fonksiyonlar(program):
    """Seçim varsa seçimdekileri, yoksa FUN_ adlı fonksiyonları getir."""
    secim = currentSelection
    secim_var = secim is not None and not secim.isEmpty()
    sonuc = []
    for fonksiyon in yineleyici(program.getFunctionManager().getFunctions(True)):
        if fonksiyon.isExternal():
            continue
        if secim_var:
            if secim.intersects(fonksiyon.getBody()):
                sonuc.append(fonksiyon)
        elif str(fonksiyon.getName()).startswith("FUN_"):
            sonuc.append(fonksiyon)
    return sonuc


def plate_yorumu_yaz(program, adres, aciklama):
    """Analistin eski yorumunu koru, önceki model yorumunu güncelle."""
    liste = program.getListing()
    yeni = YORUM_ON_EKI + aciklama.strip()
    eski = liste.getComment(CodeUnit.PLATE_COMMENT, adres) or ""
    satirlar = [satir for satir in str(eski).splitlines()
                if not satir.startswith(YORUM_ON_EKI)]
    satirlar.append(yeni)
    liste.setComment(adres, CodeUnit.PLATE_COMMENT, "\n".join(satirlar).strip())


def uygula(program, fonksiyon, ad, aciklama):
    islem = program.startTransaction("asm-adlandirma")
    basarili = False
    try:
        if ad:
            try:
                fonksiyon.setName(ad, SourceType.USER_DEFINED)
            except Exception:
                # Aynı ad varsa tahmini kaybetmeden adresle benzersizleştir.
                ekli = "%s_%x" % (ad, fonksiyon.getEntryPoint().getOffset() & 0xffff)
                fonksiyon.setName(ekli, SourceType.USER_DEFINED)
                ad = ekli
        if aciklama.strip():
            plate_yorumu_yaz(program, fonksiyon.getEntryPoint(), aciklama)
        basarili = True
        return ad
    finally:
        program.endTransaction(islem, basarili)


def ana():
    kuru, en_cok, baglamli = ayarlar(list(getScriptArgs()))
    dil = str(currentProgram.getLanguage().getProcessor()).lower()
    bit = currentProgram.getAddressFactory().getDefaultAddressSpace().getSize()
    if dil != "x86" or bit != 64:
        raise RuntimeError("bu betik yalnız x86-64 programları destekliyor")

    adaylar = aday_fonksiyonlar(currentProgram)[:en_cok]
    if not adaylar:
        println("Seçimde veya FUN_ adlarında işlenecek fonksiyon yok.")
        return
    kip = "KURU" if kuru else "UYGULA"
    println("%s: %d fonksiyon, model=%s, bağlam=%s" %
            (kip, len(adaylar), MODEL, "açık" if baglamli else "kapalı"))

    sub_adlari = sub_haritasi(currentProgram.getFunctionManager())
    for sira, fonksiyon in enumerate(adaylar, 1):
        monitor.checkCancelled()
        eski_ad = str(fonksiyon.getName())
        try:
            asm, cagrilanlar, _ = fonksiyonu_bicimle(currentProgram, fonksiyon, sub_adlari)
            baglam = baglam_uret(currentProgram, cagrilanlar, sub_adlari) if baglamli else ""
            cevap = modele_sor(asm, baglam)
            yeni_ad = gecerli_ad(cevap.get("ad", ""))
            aciklama = cevap.get("aciklama", "").strip()
            if not yeni_ad:
                raise ValueError("model geçerli bir ad döndürmedi")
            if not kuru:
                yeni_ad = uygula(currentProgram, fonksiyon, yeni_ad, aciklama)
            println("[%d/%d] %s -> %s%s" %
                    (sira, len(adaylar), eski_ad, yeni_ad, "  [kuru]" if kuru else ""))
            if aciklama:
                println("  " + aciklama)
        except Exception as hata:
            printerr("[%d/%d] %s: HATA: %s" % (sira, len(adaylar), eski_ad, hata))


ana()
