"""Yalnız kendi sentetik C programında gerçek Ghidra yazma/Undo duman denemesi.

Normal pytest akışına dahil değildir. Ghidra 12/PyGhidra 3, JDK 21 ve Linux
x86-64 gcc/binutils ister; model, ağ veya mevcut Ghidra projesi kullanmaz.
"""

import argparse
import hashlib
import json
import platform
import subprocess
import tempfile
from importlib.metadata import version
from pathlib import Path

from uygulama import uygula


KAYNAK = """static __attribute__((noinline)) unsigned sentetik_donustur(unsigned x) {
    return (x << 3) ^ 0x51U;
}
int main(void) {
    return sentetik_donustur(4U) != 0;
}
"""


def sentetik_ikili(dizin, derleyici):
    """Kaynağı burada üret; adresleri strip öncesi yalnız bu fixture için al."""
    kaynak = dizin / "sentetik.c"
    ikili = dizin / "sentetik"
    kaynak.write_text(KAYNAK, encoding="utf-8")
    komut = [derleyici, "-O0", "-fno-inline", "-fno-pie", "-no-pie", str(kaynak), "-o", str(ikili)]
    subprocess.run(komut, check=True, capture_output=True, text=True)
    simgeler = subprocess.run(["nm", "--defined-only", str(ikili)], check=True, capture_output=True, text=True).stdout
    adresler = {}
    for satir in simgeler.splitlines():
        alanlar = satir.split()
        if len(alanlar) == 3 and alanlar[2] in ("sentetik_donustur", "main"):
            adresler[alanlar[2]] = int(alanlar[0], 16)
    if set(adresler) != {"sentetik_donustur", "main"}:
        raise RuntimeError("sentetik fonksiyon adresleri bulunamadı")
    subprocess.run(["strip", "--strip-all", str(ikili)], check=True, capture_output=True, text=True)
    return ikili, [adresler["sentetik_donustur"], adresler["main"]]


class HataEnjekteEdenFonksiyon:
    def __init__(self, fonksiyon, yorum_hatasi=None, ad_hatasi=None):
        self.fonksiyon = fonksiyon
        self.yorum_hatasi = yorum_hatasi
        self.ad_hatasi = ad_hatasi
        self.ad_deneme_sayisi = 0

    def __getattr__(self, ad):
        return getattr(self.fonksiyon, ad)

    def setComment(self, yorum):
        if self.yorum_hatasi is not None:
            raise self.yorum_hatasi
        self.fonksiyon.setComment(yorum)

    def setName(self, ad, kaynak):
        self.ad_deneme_sayisi += 1
        if self.ad_hatasi is not None and self.ad_deneme_sayisi == 1:
            raise self.ad_hatasi
        self.fonksiyon.setName(ad, kaynak)


def dogrula(program, adresler):
    from ghidra.program.model.listing import CodeUnit
    from ghidra.program.model.symbol import SourceType
    from ghidra.util.exception import CancelledException, DuplicateNameException, InvalidInputException

    yonetici = program.getFunctionManager()
    adres_uzayi = program.getAddressFactory().getDefaultAddressSpace()
    adresler = [adres_uzayi.getAddress(adres) for adres in adresler]
    sonuclar = []

    def fonksiyon(sira=0):
        sonuc = yonetici.getFunctionAt(adresler[sira])
        if sonuc is None:
            raise AssertionError("Ghidra sentetik fonksiyon sınırını bulamadı")
        return sonuc

    def durum():
        return [(str(fonksiyon(i).getName()), str(fonksiyon(i).getComment() or "")) for i in range(2)]

    def yaz(ad, aciklama, hedef="ikisi", nesne=None, denetle=None):
        return uygula(
            program,
            nesne or fonksiyon(),
            ad,
            aciklama,
            hedef,
            SourceType.USER_DEFINED,
            CodeUnit.PLATE_COMMENT,
            DuplicateNameException,
            denetle,
        )

    assert program.getCurrentTransactionInfo() is None, "başlangıçta açık dış işlem var"
    islem = program.startTransaction("sentetik analist notu")
    try:
        fonksiyon().setComment("  Analistin sentetik notu  \n")
    finally:
        program.endTransaction(islem, True)
    once = durum()
    yaz("asmsense_duman_islem", "İlk satır.\nİkinci satır.")
    sonra = durum()
    assert sonra[0] == (
        "asmsense_duman_islem",
        "  Analistin sentetik notu  \n[asmsense] İlk satır.\n[asmsense] İkinci satır.",
    )
    plate = program.getListing().getComment(CodeUnit.PLATE_COMMENT, adresler[0])
    assert str(plate) == sonra[0][1]
    sonuclar.append("ad_ve_ortak_yorum_yazimi")

    degisiklik_no = program.getModificationNumber()
    undo_adlari = list(program.getAllUndoNames())
    yaz("asmsense_duman_islem", "İlk satır.\nİkinci satır.")
    assert durum() == sonra
    assert program.getModificationNumber() == degisiklik_no
    assert list(program.getAllUndoNames()) == undo_adlari
    sonuclar.append("ikinci_uygulama_yazmaz")

    assert program.canUndo()
    program.undo()
    assert durum() == once
    assert program.canRedo()
    program.redo()
    assert durum() == sonra
    sonuclar.append("gercek_undo_redo")

    bozuk = HataEnjekteEdenFonksiyon(fonksiyon(), yorum_hatasi=RuntimeError("sentetik yorum hatası"))
    try:
        yaz("asmsense_duman_hata", "Bu yazım geri alınmalı.", "fonksiyon", bozuk)
    except RuntimeError as hata:
        assert str(hata) == "sentetik yorum hatası"
    else:
        raise AssertionError("yorum hatası yutuldu")
    assert durum() == sonra
    sonuclar.append("yorum_hatasinda_gercek_rollback")

    def iptal_et():
        if str(fonksiyon().getName()) == "asmsense_duman_iptal":
            raise CancelledException("sentetik iptal")

    try:
        yaz("asmsense_duman_iptal", "Bu yazım iptal edilmeli.", denetle=iptal_et)
    except CancelledException:
        pass
    else:
        raise AssertionError("iptal yutuldu")
    assert durum() == sonra
    sonuclar.append("iptalde_gercek_rollback")

    bozuk = HataEnjekteEdenFonksiyon(fonksiyon(), ad_hatasi=InvalidInputException("sentetik geçersiz ad"))
    try:
        yaz("asmsense_duman_gecersiz", "Değişmemeli.", nesne=bozuk)
    except InvalidInputException:
        pass
    else:
        raise AssertionError("geçersiz ad hatası yutuldu")
    assert bozuk.ad_deneme_sayisi == 1
    assert durum() == sonra
    sonuclar.append("java_ad_hatasi_sonek_denemez")

    # Exception gerçek Ghidra sınıfıdır; çakışma koşulu kontrollü enjekte edilir.
    bozuk = HataEnjekteEdenFonksiyon(fonksiyon(), ad_hatasi=DuplicateNameException("sentetik çakışma"))
    sonekli = yaz("asmsense_duman_cakisma", "Çakışma açıklaması.", nesne=bozuk)
    assert sonekli == "asmsense_duman_cakisma_%016x" % (adresler[0].getOffset() & 0xFFFFFFFFFFFFFFFF)
    assert str(fonksiyon().getName()) == sonekli
    degisiklik_no = program.getModificationNumber()
    assert yaz("asmsense_duman_cakisma", "Çakışma açıklaması.") == sonekli
    assert program.getModificationNumber() == degisiklik_no
    sonuclar.append("java_cakisma_istisnasi_ve_kararli_sonek")

    once = durum()
    dis_islem = program.startTransaction("sentetik ortak dış işlem")
    ic_hata_goruldu = False
    try:
        yaz("asmsense_duman_dis", "Dış işlem geri alınmalı.")
        bozuk = HataEnjekteEdenFonksiyon(fonksiyon(1), yorum_hatasi=RuntimeError("sentetik iç hata"))
        try:
            yaz("asmsense_duman_ic", "İç işlem başarısız.", "fonksiyon", bozuk)
        except RuntimeError as hata:
            assert str(hata) == "sentetik iç hata"
            ic_hata_goruldu = True
    finally:
        # Dış işlem commit istese de başarısız alt işlem bütün değişiklikleri geri almalı.
        program.endTransaction(dis_islem, ic_hata_goruldu)
    assert ic_hata_goruldu
    assert durum() == once
    sonuclar.append("ic_hata_dis_islemi_geri_alir")
    return sonuclar


def ana():
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("--ghidra-kurulum", type=Path, required=True)
    ayristirici.add_argument("--derleyici", default="gcc")
    ayristirici.add_argument("--cikti", type=Path)
    args = ayristirici.parse_args()
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64"):
        ayristirici.error("bu sentetik derleme tarifi Linux x86-64 içindir")
    if not __debug__:
        ayristirici.error("doğrulamaları kaldıran python -O seçeneğini kullanmayın")
    import pyghidra

    pyghidra.start(install_dir=args.ghidra_kurulum.resolve())
    from ghidra.framework import Application
    from java.lang import System

    with tempfile.TemporaryDirectory(prefix="asmsense-ghidra-duman-") as gecici:
        dizin = Path(gecici)
        ikili, adresler = sentetik_ikili(dizin, args.derleyici)
        with pyghidra.open_project(dizin, "sentetik", create=True) as proje:
            with pyghidra.program_loader().source(str(ikili)).project(proje).load() as yuklenen:
                yuklenen.save(pyghidra.task_monitor())
            with pyghidra.program_context(proje, "/sentetik") as program:
                pyghidra.analyze(program, pyghidra.task_monitor(60))
                kontroller = dogrula(program, adresler)
    sonuc = {
        "durum": "gecti",
        "veri": "betigin_urettigi_sentetik_C",
        "ikili_sayisi": 1,
        "hedef_fonksiyon_sayisi": 2,
        "kaynak_sha256": hashlib.sha256(KAYNAK.encode("utf-8")).hexdigest(),
        "ghidra": str(Application.getApplicationVersion()),
        "pyghidra": version("pyghidra"),
        "java": str(System.getProperty("java.version")),
        "python": platform.python_version(),
        "derleyici": subprocess.run(
            [args.derleyici, "--version"], check=True, capture_output=True, text=True
        ).stdout.splitlines()[0],
        "kontroller": kontroller,
        "sinir": "GUI_ve_model_servisi_sinanmadi;_hatalar_kontrollu_enjekte_edildi",
    }
    yazi = json.dumps(sonuc, ensure_ascii=False, indent=2) + "\n"
    if args.cikti:
        args.cikti.write_text(yazi, encoding="utf-8")
    print(yazi, end="")


if __name__ == "__main__":
    ana()
