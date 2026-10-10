# -*- coding: utf-8 -*-
"""Ghidra değişikliklerini tek işlemde uygulayan, bağımlılıkları dışarıdan alan yardımcı.

Ghidra sınıfları burada içe aktarılmaz; aynı akış sahte nesnelerle sınanabilir.
PyGhidra yanında eski Jython için Python 2.7 sözdizimi korunur.
"""

from __future__ import unicode_literals

from bicim import metin, model_yorumu_birlestir


def _yorum_oku(program, fonksiyon, hedef, plate_turu):
    if hedef == "plate":
        return metin(program.getListing().getComment(plate_turu, fonksiyon.getEntryPoint()))
    return metin(fonksiyon.getComment())


def _yorum_yaz(program, fonksiyon, hedef, plate_turu, yorum):
    if hedef == "plate":
        program.getListing().setComment(fonksiyon.getEntryPoint(), plate_turu, yorum)
    else:
        fonksiyon.setComment(yorum)


def uygula(
    program,
    fonksiyon,
    ad,
    aciklama,
    yorum_hedefi,
    kaynak_turu,
    plate_turu,
    cakisma_hatasi,
    iptal_kontrolu=None,
    yorum_on_eki="[asmsense] ",
):
    """Adı ve yorumları uygula; hata/iptalde geri al, aynı sonuçta işlem açma.

    ``cakisma_hatasi`` yalnız Ghidra'nın DuplicateNameException sınıfıdır.
    Başka adlandırma hatası ad çakışması sanılmaz. İç içe Ghidra işlemleri
    bağımsız değildir: geri alma dış işlemi de etkileyebilir; çağıran betik
    uygulama hatasını yutup sonraki fonksiyona devam etmemelidir.
    """
    if yorum_hedefi not in ("ikisi", "plate", "fonksiyon"):
        raise ValueError("yorum_hedefi ikisi|plate|fonksiyon olmalı")
    denetle = iptal_kontrolu or (lambda: None)
    denetle()
    hedefler = ("plate", "fonksiyon") if yorum_hedefi == "ikisi" else (yorum_hedefi,)
    eski_ad = metin(fonksiyon.getName())
    ad = metin(ad)
    # Java long işaretli olabilir; tam x86-64 adresi kararlı bir sonek yapar.
    ekli_ad = "%s_%016x" % (ad, fonksiyon.getEntryPoint().getOffset() & 0xFFFFFFFFFFFFFFFF)
    ad_degisecek = bool(ad) and eski_ad not in (ad, ekli_ad)
    sonuc_ad = eski_ad if ad and not ad_degisecek else ad
    yorum_degisecek = False
    for hedef in hedefler:
        eski = _yorum_oku(program, fonksiyon, hedef, plate_turu)
        if model_yorumu_birlestir(eski, aciklama, yorum_on_eki) != eski:
            yorum_degisecek = True
    if not ad_degisecek and not yorum_degisecek:
        return sonuc_ad

    islem = program.startTransaction("asmsense")
    basarili = False
    try:
        denetle()
        if ad_degisecek:
            try:
                fonksiyon.setName(ad, kaynak_turu)
            except cakisma_hatasi:
                denetle()
                fonksiyon.setName(ekli_ad, kaynak_turu)
                sonuc_ad = ekli_ad
            denetle()
        for hedef in hedefler:
            denetle()
            # Function yorumu ile plate aynı depoyu kullanabilir. İlk yazımdan
            # sonra yeniden okuyarak ikisi kipinde yinelenen yazmayı önle.
            eski = _yorum_oku(program, fonksiyon, hedef, plate_turu)
            yeni = model_yorumu_birlestir(eski, aciklama, yorum_on_eki)
            if yeni != eski:
                _yorum_yaz(program, fonksiyon, hedef, plate_turu, yeni)
                denetle()
        denetle()
        basarili = True
        return sonuc_ad
    finally:
        program.endTransaction(islem, basarili)
