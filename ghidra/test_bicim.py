# -*- coding: utf-8 -*-
import json
import unittest

from bicim import (asm_bicimle, cevap_ayristir, fonksiyon_ozeti,
                   gecerli_ad, ic_cagrilar, model_girdisi,
                   model_yorumu_birlestir, string_goster)


class BicimTesti(unittest.TestCase):
    def test_assembly_dal_cagri_string(self):
        komutlar = [
            {"adres": 0x1000, "mnemonik": "MOV", "islenenler": "RAX,qword ptr [DAT_00402000]"},
            {"adres": 0x1007, "mnemonik": "JNE", "islenenler": "LAB_00401020", "dal": 0x1020},
            {"adres": 0x1009, "mnemonik": "CALL", "islenenler": "FUN_00401100", "cagri": "sub_0007"},
            {"adres": 0x100e, "mnemonik": "CALL", "islenenler": "puts", "cagri": "puts",
             "string": "hata\n"},
            {"adres": 0x1020, "mnemonik": "RET", "islenenler": ""},
        ]
        self.assertEqual(
            asm_bicimle(komutlar),
            "mov\trax, qword ptr [veri]\n"
            "jne\tloc_1\n"
            "call\tsub_0007\n"
            "call\tputs    ; -> \"hata\\n\"\n"
            "loc_1:\nret")

    def test_string_kacislari_ve_sinir(self):
        self.assertEqual(string_goster('a"b\\c\t'), '"a\\"b\\\\c\\t"')
        self.assertEqual(string_goster("abcdef", 3), '"abc…"')

    def test_baglam_ozeti(self):
        asm = ('call\tmalloc\ncall\tsub_0002\ncall\tsub_0002\n'
               'lea\trdi, [rip]    ; -> "bellek yok"')
        self.assertEqual(ic_cagrilar(asm), ["sub_0002"])
        self.assertEqual(fonksiyon_ozeti("sub_0001", 4, asm),
                         'sub_0001 (4 komut): çağırır malloc, sub_0002; string "bellek yok"')

    def test_cevap_ve_tanimlayici(self):
        ham = {"choices": [{"message": {"content":
               'Açıklama\n```json\n{"ad":"Şifre Çöz!", "aciklama":"Veriyi çözer."}\n```'}}]}
        self.assertEqual(cevap_ayristir(ham),
                         {"ad": "Şifre Çöz!", "aciklama": "Veriyi çözer."})
        self.assertEqual(gecerli_ad("  Şifre Çöz!  "), "sifre_coz")
        self.assertEqual(gecerli_ad("12 giriş"), "fonk_12_giris")
        self.assertEqual(gecerli_ad("class"), "fonk_class")
        self.assertEqual(gecerli_ad("---"), "")
        for ad in ("sub_0016", "sub_401000", "FUN_00001050", "fonksiyon_adi", "push_rbp"):
            self.assertEqual(gecerli_ad(ad), "")
        self.assertEqual(gecerli_ad("subscribe_event"), "subscribe_event")

    def test_json_olmayan_cevap(self):
        ham = {"choices": [{"message": {"content": "paket_ayristir"}}]}
        self.assertEqual(cevap_ayristir(ham), {"ad": "paket_ayristir", "aciklama": ""})

    def test_sonraki_model_girdisi(self):
        girdi, kesildi = model_girdisi("ret", "sub_0001 (1 komut)", 100)
        self.assertEqual(girdi, "ret\n\n; --- çağrılan fonksiyonlar ---\nsub_0001 (1 komut)")
        self.assertFalse(kesildi)

        girdi, kesildi = model_girdisi(
            "ret", "sub_0001 (10 komut)\nsub_0002 (20 komut)\nsub_0003 (30 komut)", 80)
        self.assertTrue(kesildi)
        self.assertLessEqual(len(girdi), 80)
        self.assertTrue(girdi.endswith("; ... bağlam kesildi"))
        self.assertIn("sub_0001", girdi)
        self.assertNotIn("sub_0003", girdi)

    def test_model_yorumu_analist_satirlarini_korur(self):
        eski = ("Analistin ilk notu\n[asm-adlandirma] Eski açıklama.\n"
                "Analistin ikinci notu\n[asm-adlandirma] Yinelenmiş eski satır.")
        self.assertEqual(
            model_yorumu_birlestir(eski, "Yeni açıklama."),
            "Analistin ilk notu\nAnalistin ikinci notu\n[asm-adlandirma] Yeni açıklama.")
        self.assertEqual(model_yorumu_birlestir("", "İlk açıklama."),
                         "[asm-adlandirma] İlk açıklama.")


if __name__ == "__main__":
    unittest.main()
