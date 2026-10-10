# -*- coding: utf-8 -*-
"""Ghidra kurulumu olmadan veritabanı yazma ve betik hata akışını sınar."""

import copy
import runpy
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from bicim import model_yorumu_birlestir
from uygulama import uygula


class AdCakismasi(Exception):
    pass


class Iptal(Exception):
    pass


class SahteFonksiyon:
    def __init__(self, program, adres):
        self.program = program
        self.adres = SimpleNamespace(getOffset=lambda: adres)
        self.ad_hatalari = {}

    def getName(self):
        return self.program.durum["ad"]

    def getEntryPoint(self):
        return self.adres

    def setName(self, ad, kaynak):
        self.program.yazmalar.append(("ad", ad, kaynak))
        if ad in self.ad_hatalari:
            raise self.ad_hatalari[ad]
        self.program.durum["ad"] = ad

    def getComment(self):
        return self.program.yorum_oku("fonksiyon")

    def setComment(self, yorum):
        self.program.yorum_yaz("fonksiyon", yorum)


class SahteProgram:
    """İç içe işlemlerde dış işlemin sonunu bekleyen küçük bir DB sözleşmesi."""

    def __init__(self, ortak_yorum=False, adres=0x123456789ABC1234):
        self.durum = {"ad": "FUN_sentetik", "plate": "Plate notu", "fonksiyon": "Fonksiyon notu"}
        self.ortak_yorum = ortak_yorum
        self.yazmalar = []
        self.sonlandirmalar = []
        self.undo_gecmisi = []
        self.yorum_hatasi = None
        self.islem_no = 0
        self.acik_islemler = set()
        self.fonksiyon = SahteFonksiyon(self, adres)

    def yorum_oku(self, hedef):
        return self.durum["plate" if self.ortak_yorum else hedef]

    def yorum_yaz(self, hedef, yorum):
        self.yazmalar.append((hedef, yorum))
        if hedef == self.yorum_hatasi:
            raise RuntimeError("yorum yazılamadı")
        self.durum["plate" if self.ortak_yorum else hedef] = yorum

    def getListing(self):
        return SimpleNamespace(
            getComment=lambda tur, adres: self.yorum_oku("plate"),
            setComment=lambda adres, tur, yorum: self.yorum_yaz("plate", yorum),
        )

    def startTransaction(self, aciklama):
        if not self.acik_islemler:
            self.once = copy.deepcopy(self.durum)
            self.geri_al = False
        self.islem_no += 1
        self.acik_islemler.add(self.islem_no)
        return self.islem_no

    def endTransaction(self, islem, basarili):
        self.sonlandirmalar.append((islem, basarili))
        self.acik_islemler.remove(islem)
        self.geri_al = self.geri_al or not basarili
        if not self.acik_islemler:
            if self.geri_al:
                self.durum = self.once
            else:
                self.undo_gecmisi.append(self.once)


def degistir(program, ad="kaydi_isle", aciklama="Kaydı işler.", hedef="ikisi", denetle=None):
    return uygula(program, program.fonksiyon, ad, aciklama, hedef, "kullanici", 3, AdCakismasi, denetle)


class UygulamaTesti(unittest.TestCase):
    def test_ad_ve_hedef_yorumlari_birlikte_yazilir(self):
        for hedef in ("plate", "fonksiyon", "ikisi"):
            with self.subTest(hedef=hedef):
                program = SahteProgram()
                self.assertEqual(degistir(program, hedef=hedef), "kaydi_isle")
                self.assertEqual(program.durum["ad"], "kaydi_isle")
                self.assertEqual(program.sonlandirmalar, [(1, True)])
                for yorum_hedefi in ("plate", "fonksiyon"):
                    self.assertEqual("[asmsense]" in program.durum[yorum_hedefi], hedef in (yorum_hedefi, "ikisi"))

    def test_yorum_hatasi_adi_ve_onceki_yorumu_geri_alir(self):
        program = SahteProgram()
        once = copy.deepcopy(program.durum)
        program.yorum_hatasi = "fonksiyon"
        with self.assertRaisesRegex(RuntimeError, "yorum yazılamadı"):
            degistir(program)
        self.assertEqual(program.durum, once)
        self.assertEqual(program.sonlandirmalar, [(1, False)])
        self.assertEqual(program.undo_gecmisi, [])

    def test_ad_cakismasi_tam_adresle_cozulur_ve_tekrar_degismez(self):
        program = SahteProgram()
        program.fonksiyon.ad_hatalari["kaydi_isle"] = AdCakismasi()
        sonuc = degistir(program)
        self.assertEqual(sonuc, "kaydi_isle_123456789abc1234")
        once = copy.deepcopy(program.durum)
        yazma_sayisi = len(program.yazmalar)
        self.assertEqual(degistir(program), sonuc)
        self.assertEqual(program.durum, once)
        self.assertEqual(len(program.yazmalar), yazma_sayisi)
        self.assertEqual(program.islem_no, 1)
        self.assertEqual(len(program.undo_gecmisi), 1)

    def test_isaretli_java_adresi_tum_64_biti_korur(self):
        program = SahteProgram(adres=-2)
        program.fonksiyon.ad_hatalari["kaydi_isle"] = AdCakismasi()
        self.assertEqual(degistir(program), "kaydi_isle_fffffffffffffffe")

    def test_ayni_alt_16_bit_farkli_sonek_uretir(self):
        sonuclar = []
        for adres in (0x12341234, 0x56781234):
            program = SahteProgram(adres=adres)
            program.fonksiyon.ad_hatalari["kaydi_isle"] = AdCakismasi()
            sonuclar.append(degistir(program))
        self.assertNotEqual(*sonuclar)

    def test_diger_ad_hatasi_sonek_denemeden_geri_alir(self):
        program = SahteProgram()
        once = copy.deepcopy(program.durum)
        program.fonksiyon.ad_hatalari["kaydi_isle"] = ValueError("geçersiz ad")
        with self.assertRaisesRegex(ValueError, "geçersiz ad"):
            degistir(program)
        self.assertEqual(program.durum, once)
        self.assertEqual(program.yazmalar, [("ad", "kaydi_isle", "kullanici")])
        self.assertEqual(program.sonlandirmalar, [(1, False)])

    def test_sonek_de_cakisinca_hata_yutulmaz(self):
        program = SahteProgram()
        for ad in ("kaydi_isle", "kaydi_isle_123456789abc1234"):
            program.fonksiyon.ad_hatalari[ad] = AdCakismasi()
        with self.assertRaises(AdCakismasi):
            degistir(program)
        self.assertEqual(program.durum["ad"], "FUN_sentetik")
        self.assertEqual(program.sonlandirmalar, [(1, False)])

    def test_iptal_yazimdan_once_islem_acmaz(self):
        program = SahteProgram()
        with self.assertRaises(Iptal):
            degistir(program, denetle=Mock(side_effect=Iptal()))
        self.assertEqual(program.islem_no, 0)
        self.assertEqual(program.yazmalar, [])

    def test_iptal_her_yazimdan_sonra_geri_alir(self):
        for yazma_sayisi in (1, 2, 3):
            with self.subTest(yazma_sayisi=yazma_sayisi):
                program = SahteProgram()
                once = copy.deepcopy(program.durum)

                def denetle():
                    if len(program.yazmalar) >= yazma_sayisi:
                        raise Iptal()

                with self.assertRaises(Iptal):
                    degistir(program, denetle=denetle)
                self.assertEqual(program.durum, once)
                self.assertEqual(program.sonlandirmalar, [(1, False)])

    def test_ad_cakismasi_sirasinda_iptal_soneke_gecmez(self):
        program = SahteProgram()
        program.fonksiyon.ad_hatalari["kaydi_isle"] = AdCakismasi()

        def denetle():
            if program.yazmalar:
                raise Iptal()

        with self.assertRaises(Iptal):
            degistir(program, denetle=denetle)
        self.assertEqual(len(program.yazmalar), 1)
        self.assertEqual(program.sonlandirmalar, [(1, False)])

    def test_ayni_tahmin_islem_ve_undo_kaydi_eklemez(self):
        program = SahteProgram()
        degistir(program)
        ilk_yazmalar = list(program.yazmalar)
        degistir(program)
        self.assertEqual(program.yazmalar, ilk_yazmalar)
        self.assertEqual(program.islem_no, 1)
        self.assertEqual(len(program.undo_gecmisi), 1)

    def test_ortak_yorum_deposuna_ikisi_kipinde_tek_yazim(self):
        program = SahteProgram(ortak_yorum=True)
        degistir(program)
        self.assertEqual([y[0] for y in program.yazmalar], ["ad", "plate"])
        self.assertEqual(program.fonksiyon.getComment(), program.durum["plate"])
        degistir(program)
        self.assertEqual(program.islem_no, 1)

    def test_ayni_ad_yeni_aciklama_yalniz_yorumu_degistirir(self):
        program = SahteProgram()
        program.durum["ad"] = "kaydi_isle"
        degistir(program, hedef="plate")
        self.assertEqual([y[0] for y in program.yazmalar], ["plate"])

    def test_bos_aciklama_varolan_model_yorumunu_korur(self):
        program = SahteProgram()
        program.durum["plate"] += "\n[asmsense] Önceki açıklama."
        once = copy.deepcopy(program.durum)
        degistir(program, aciklama=" \n ")
        self.assertEqual(program.durum["plate"], once["plate"])
        self.assertEqual(program.durum["fonksiyon"], once["fonksiyon"])
        self.assertEqual([y[0] for y in program.yazmalar], ["ad"])

    def test_gecersiz_hedef_islem_acilmadan_reddedilir(self):
        program = SahteProgram()
        with self.assertRaisesRegex(ValueError, "yorum_hedefi"):
            degistir(program, hedef="yanlis")
        self.assertEqual(program.islem_no, 0)

    def test_ic_islemin_hatasi_dis_islemi_de_geri_alir(self):
        program = SahteProgram()
        once = copy.deepcopy(program.durum)
        dis_islem = program.startTransaction("betik")
        degistir(program)
        program.yorum_hatasi = "fonksiyon"
        with self.assertRaises(RuntimeError):
            degistir(program, ad="baska_tahmin", aciklama="Yeni açıklama.")
        program.endTransaction(dis_islem, True)
        self.assertEqual(program.durum, once)
        self.assertEqual(program.undo_gecmisi, [])


class YorumTesti(unittest.TestCase):
    def test_cok_satirli_aciklama_tekrarda_birikmez(self):
        ilk = model_yorumu_birlestir("Analistin notu", "İlk satır.\nİkinci satır.")
        self.assertEqual(ilk, "Analistin notu\n[asmsense] İlk satır.\n[asmsense] İkinci satır.")
        self.assertEqual(model_yorumu_birlestir(ilk, "İlk satır.\nİkinci satır."), ilk)
        self.assertEqual(model_yorumu_birlestir(ilk, "Yeni açıklama."), "Analistin notu\n[asmsense] Yeni açıklama.")

    def test_analist_bosluklari_ve_satir_sonlari_korunur(self):
        eski = "  Analistin notu  \r\n\r\n[asmsense] Eski.\r\n\tSon not  \r\n"
        beklenen = "  Analistin notu  \r\n\r\n\tSon not  \r\n[asmsense] Bir.\r\n[asmsense] İki."
        self.assertEqual(model_yorumu_birlestir(eski, "Bir.\nİki."), beklenen)
        self.assertEqual(model_yorumu_birlestir(beklenen, "Bir.\nİki."), beklenen)

    def test_bos_aciklama_yorumu_bayt_bayt_korur(self):
        eski = "  Not\r\n[asmsense] Eski.\r\n"
        self.assertEqual(model_yorumu_birlestir(eski, " \n\t"), eski)

    def test_eski_isaretsiz_devam_satiri_silinmez(self):
        eski = "[asmsense] Eski.\nKime ait olduğu bilinmeyen satır.\nAnalistin notu."
        self.assertEqual(
            model_yorumu_birlestir(eski, "Yeni."),
            "Kime ait olduğu bilinmeyen satır.\nAnalistin notu.\n[asmsense] Yeni.",
        )


def betik_yukle():
    """Gerçek betiği boş programda başlat; yalnız Java importlarını taklit et."""
    moduller = {}
    for ad in (
        "ghidra",
        "ghidra.program",
        "ghidra.program.model",
        "ghidra.program.model.listing",
        "ghidra.program.model.symbol",
        "ghidra.util",
        "ghidra.util.exception",
    ):
        moduller[ad] = ModuleType(ad)
    moduller["ghidra.program.model.listing"].CodeUnit = SimpleNamespace(PLATE_COMMENT=3)
    moduller["ghidra.program.model.symbol"].SourceType = SimpleNamespace(USER_DEFINED="kullanici")
    moduller["ghidra.util.exception"].CancelledException = Iptal
    moduller["ghidra.util.exception"].DuplicateNameException = AdCakismasi
    bos_yineleyici = SimpleNamespace(hasNext=lambda: False)
    program = SimpleNamespace(
        getLanguage=lambda: SimpleNamespace(getProcessor=lambda: "x86"),
        getAddressFactory=lambda: SimpleNamespace(getDefaultAddressSpace=lambda: SimpleNamespace(getSize=lambda: 64)),
        getFunctionManager=lambda: SimpleNamespace(getFunctions=lambda _: bos_yineleyici),
    )
    ortam = {
        "currentProgram": program,
        "currentSelection": None,
        "getScriptArgs": lambda: ["--uygula"],
        "println": Mock(),
        "printerr": Mock(),
        "monitor": SimpleNamespace(checkCancelled=lambda: None),
    }
    with patch.dict(sys.modules, moduller):
        sonuc = runpy.run_path(str(Path(__file__).with_name("ad_ver.py")), init_globals=ortam)
    alan = sonuc["ana"].__globals__
    fonksiyonlar = [SimpleNamespace(getName=lambda: "FUN_sentetik") for _ in range(3)]
    alan.update(
        {
            "aday_fonksiyonlar": lambda _: fonksiyonlar,
            "sub_haritasi": lambda _: {},
            "fonksiyonu_bicimle": lambda *_: ("ret", [], 1),
            "baglam_uret": lambda *_: "",
            "modele_sor": Mock(return_value=({"ad": "kaydi_isle", "aciklama": "Kaydı işler."}, False)),
            "uygula": Mock(return_value="kaydi_isle"),
        }
    )
    return alan


class BetikHataAkisiTesti(unittest.TestCase):
    def test_uygulama_hatasi_sonraki_fonksiyona_gecmez(self):
        alan = betik_yukle()
        alan["uygula"].side_effect = RuntimeError("yazım hatası")
        with self.assertRaisesRegex(RuntimeError, "yazım hatası"):
            alan["ana"]()
        self.assertEqual(alan["modele_sor"].call_count, 1)
        self.assertEqual(alan["uygula"].call_count, 1)
        self.assertIn("Betik durduruldu", alan["printerr"].call_args[0][0])

    def test_yazimdan_once_model_hatasi_diger_fonksiyona_engel_degil(self):
        alan = betik_yukle()
        cevap = ({"ad": "kaydi_isle", "aciklama": "Kaydı işler."}, False)
        alan["modele_sor"].side_effect = [RuntimeError("model yanıtlamadı"), cevap, cevap]
        alan["ana"]()
        self.assertEqual(alan["modele_sor"].call_count, 3)
        self.assertEqual(alan["uygula"].call_count, 2)

    def test_iptal_hazirlikta_ve_uygulamada_yutulmaz(self):
        for asama in ("modele_sor", "uygula"):
            with self.subTest(asama=asama):
                alan = betik_yukle()
                alan[asama].side_effect = Iptal()
                with self.assertRaises(Iptal):
                    alan["ana"]()
                self.assertEqual(alan["modele_sor"].call_count, 1)


if __name__ == "__main__":
    unittest.main()
