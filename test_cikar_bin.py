#!/usr/bin/env python3
"""Yerel Mach-O regresyonları: python3 -m unittest -v test_cikar_bin"""
import contextlib, io, json, struct, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

from cikar_bin import (Bolum, Gorunum, Komut, MachO, ayristir, calistir, cikar,
                       kod_araliklari, sizinti_kontrolu, uleb)


class MetaveriTesti(unittest.TestCase):
    def test_uleb_ve_veri_araliklari(self):
        self.assertEqual(uleb(bytes([0xe5, 0x8e, 0x26]), 0), (624485, 3))
        with self.assertRaises(ValueError):
            uleb(b"\x80", 0)
        self.assertEqual(list(kod_araliklari(10, 50, [(15, 20, 4), (20, 25, 1), (40, 60, 2)])),
                         [(10, 15), (25, 40)])

    def test_unwind_regular_compressed_ve_ara_aralik(self):
        for tur in (2, 3):
            with self.subTest(tur=tur):
                b = bytearray(160)
                struct.pack_into("<7I", b, 0, 1, 28, 2, 36, 0, 36, 2)
                struct.pack_into("<2I", b, 28, 0x01000000, 0x81000000)
                struct.pack_into("<3I", b, 36, 0x100, 64, 0)
                struct.pack_into("<3I", b, 48, 0x200, 0, 0)  # sentinel
                if tur == 2:
                    struct.pack_into("<IHH", b, 64, 2, 8, 3)
                    struct.pack_into("<6I", b, 72, 0x100, 0x01000000,
                                     0x110, 0x81000000, 0x120, 0x01000000)
                else:
                    struct.pack_into("<I4H", b, 64, 3, 12, 3, 24, 0)
                    struct.pack_into("<3I", b, 76, 0, 0x01000010, 0x20)
                m = MachO.__new__(MachO)
                m.bayt, m.taban = bytes(b), 0x1000
                m.kod = [Bolum("__text", "__TEXT", 0x1100, 0x200, 0, 0, 1, 0, 0)]
                m.bolumler = [Bolum("__unwind_info", "__TEXT", 0, len(b), 0, 0, 2, 0, 0)]
                self.assertEqual(m.unwind(), {0x1100, 0x1120})

    def test_dwarf_fde(self):
        m = MachO.__new__(MachO)
        m.yol = Path("stripped.dylib")
        m.kod = [Bolum("__text", "__TEXT", 0x100, 0x100, 0, 0, 1, 0, 0)]
        m.bolumler = [Bolum("__eh_frame", "__TEXT", 0, 64, 0, 0, 2, 0, 0)]
        with patch("cikar_bin.calistir", return_value="00000018 00000024 0000001c FDE cie=00000000 pc=00000120...00000150\n"):
            self.assertEqual(m.unwind(), {0x120})

    def test_sayisal_hedef_ve_stringler(self):
        class Sahte:
            def tanimli(self):
                return [(0x200, "acik_fonk", 0xf, 1), (0x800, "acik_veri", 0xf, 2)]
            def stringler(self):
                return {0x600: "merhaba"}
            def kodda(self, a):
                return 0x100 <= a < 0x300
        ks = [Komut(0x100, 5, "call\t0x200 <_yanlis_export+0x200>"),
              Komut(0x105, 5, "call\t0x500 <_yanlis_export+0x500>"),
              Komut(0x10a, 7, "lea\trdi, [rip + 0x4ef] ## 0x600 <_yanlis>"),
              Komut(0x111, 2, "jne\t0x100 <_yanlis>"),
              Komut(0x113, 7, "mov\trax, [rip + 0x6e6] ## 0x800"),
              Komut(0x11a, 5, "mov\teax, 0x12345678")]
        for kip in ("yerel", "tam"):
            gor = Gorunum(Sahte(), [0x100, 0x200], {0x500: "puts"}, "test", "-O0", kip, 7)
            gor.veri_adlari([0x600, 0x800], "test", "-O0", 7)
            asm = gor.anonimlestir(ks)
            self.assertIn("loc_1:", asm)
            self.assertIn("jne\tloc_1", asm)
            self.assertIn('; -> "merhaba"', asm)
            self.assertIn("; -> puts", asm)
            self.assertIn("0x12345678", asm)             # algoritmik sabiti silme
            self.assertNotIn("yanlis", asm)
            self.assertNotIn("0x200", asm)
            self.assertNotIn("rip +", asm)
            self.assertEqual("acik_fonk" in asm, kip == "yerel")
            self.assertEqual("acik_veri" in asm, kip == "yerel")

    def test_sizinti_denetcisi(self):
        satir = {"id": "test", "asm": 'call\tgizli    ; -> gizli\nlea\trdi, [rip] ; -> "ipucu"',
                 "baglam": "", "kip": "tam"}
        r = sizinti_kontrolu([satir], ["gizli", "ipucu"], [], [])
        self.assertEqual(r["beklenmeyen_semboller"][0]["adlar"], ["gizli"])
        satir["kip"] = "yerel"
        self.assertFalse(sizinti_kontrolu([satir], ["gizli"], ["gizli"], [])["beklenmeyen_semboller"])
        satir["asm"] = "call\t0x1234"
        self.assertEqual(sizinti_kontrolu([satir], [], [], [])["adres_bicim_ihlalleri"], ["test"])


class GercekLinkTesti(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gecici = tempfile.TemporaryDirectory(prefix="asm-bin-test-")
        cls.kok = Path(cls.gecici.name)
        (cls.kok / "a.c").write_text('''#include <stdio.h>
extern int dis_eksik(int);
volatile int dis_veri = 7;
static volatile int gizli_veri = 3;
__attribute__((noinline)) static int yardimci(int n) {
    puts("yardimci"); return n + gizli_veri;
}
__attribute__((noinline)) int acik_fonk(int n) {
    return yardimci(n) + dis_veri + dis_eksik(n);
}
int dallan(int n) {
    switch (n) {
    case 0: return acik_fonk(n + 31);
    case 1: return acik_fonk(n + 32) + 1;
    case 2: return acik_fonk(n + 34) + 2;
    case 3: return acik_fonk(n + 39) + 3;
    case 4: return acik_fonk(n + 44) + 4;
    case 5: return acik_fonk(n + 51) + 5;
    default: return -1;
    }
}
''')
        (cls.kok / "b.c").write_text('''extern int acik_fonk(int);
__attribute__((noinline)) static int yardimci(int n) { return n * 7; }
int ikinci(int n) { return yardimci(n) + acik_fonk(n); }
''')
        cls.cikti = cls.kok / "veri" / "test.jsonl"
        cls.ikili = cls.kok / "ikili"
        with contextlib.redirect_stdout(io.StringIO()):
            cikar(cls.kok, cls.cikti, proje="test", en_az=1, en_cok=1000,
                  ikili_sakla=cls.ikili)
        cls.satirlar = [json.loads(s) for s in cls.cikti.read_text().splitlines()]
        cls.rapor = json.loads(cls.cikti.with_suffix(".rapor.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.gecici.cleanup()

    def test_iki_kip_adres_esleme_ayni_static_ad(self):
        self.assertEqual(len({r["id"] for r in self.satirlar}), len(self.satirlar))
        for opt in ("-O0", "-O2"):
            for kip in ("yerel", "tam"):
                yardimcilar = [r for r in self.satirlar if (r["ad"], r["opt"], r["kip"]) == ("yardimci", opt, kip)]
                self.assertEqual({r["dosya"] for r in yardimcilar}, {"a.c", "b.c"})
                self.assertEqual(len({r["kimlik"] for r in yardimcilar}), 2)
                for r in yardimcilar:
                    self.assertEqual(r["sizinti"], r["dosya"] == "a.c")
            for kip in ("yerel", "tam"):
                r = next(r for r in self.satirlar if (r["ad"], r["opt"], r["kip"]) == ("ikinci", opt, kip))
                self.assertEqual("acik_fonk" in r["asm"], kip == "yerel")
                r = next(r for r in self.satirlar if (r["ad"], r["opt"], r["kip"]) == ("acik_fonk", opt, kip))
                self.assertIn("; -> dis_eksik", r["asm"])
        for o in self.rapor["optimizasyonlar"].values():
            self.assertTrue(o["dynamic_lookup"])
            self.assertEqual(o["sinir"], o["eslesen"])
            self.assertFalse(o["sinirsiz_semboller"])
            self.assertFalse(o["adsiz_baslangiclar"])
            for k in o["kipler"].values():
                self.assertFalse(k["beklenmeyen_semboller"])
                self.assertFalse(k["adres_bicim_ihlalleri"])

    def test_stripten_sinirlar_ve_veri_baytlari(self):
        asil, soyuk = self.kok / "asil.dylib", self.kok / "soyuk.dylib"
        calistir(["clang", "-target", "x86_64-apple-macos12", "-O0", "-dynamiclib",
                  self.kok / "a.c", "-Wl,-undefined,dynamic_lookup", "-o", asil])
        calistir(["strip", "-x", "-o", soyuk, asil])
        m, once = MachO(soyuk), MachO(asil)
        self.assertIn("yardimci", [ad for _, ad, _, _ in once.tanimli()])
        self.assertNotIn("yardimci", [ad for _, ad, _, _ in m.tanimli()])
        baslar = m.baslangiclar() | m.unwind()
        veriler = m.kod_verisi()
        self.assertTrue(veriler)
        ks = ayristir(m, baslar, veriler)
        self.assertFalse(any(k.adres < b and k.adres + k.boy > a for k in ks for a, b, _ in veriler))
        self.assertTrue(baslar <= {k.adres for k in ks})
        # Sembol tablosu olmadan da aynı sınırlar; LC_FUNCTION_STARTS yoksa unwind kalır.
        m.semboller = []
        self.assertEqual(baslar, m.baslangiclar() | m.unwind())
        del m.komutlar[0x26]
        self.assertFalse(m.baslangiclar())
        self.assertTrue(m.unwind())

    def test_ikili_sakla_eslemesi_satirlarla_birebir(self):
        eslemeler = [json.loads(s) for yol in sorted(self.ikili.rglob("*.jsonl"))
                     for s in yol.read_text().splitlines()]
        self.assertEqual({r["id"] for r in eslemeler}, {r["id"] for r in self.satirlar})
        for r in eslemeler:
            self.assertGreater(r["adres"], 0)
            self.assertGreater(r["boyut"], 0)
            self.assertGreaterEqual(r["dosya_ofseti"], 0)
            self.assertTrue((self.ikili / "test" / r["ikili"]).is_file())

    def test_derleme_hatasinda_eksik_veri_yazilmaz(self):
        kotu = self.kok / "kotu"
        kotu.mkdir()
        (kotu / "kotu.c").write_text("bu C degil;")
        cikti = kotu / "cikti.jsonl"
        with self.assertRaisesRegex(RuntimeError, "derlenemeyenler"):
            cikar(kotu, cikti)
        self.assertFalse(cikti.exists())

    def test_sizintida_saglam_cikti_korunur(self):
        cikti = self.kok / "korunacak.jsonl"
        cikti.write_text("önceki sağlam çıktı\n")
        with patch("cikar_bin.sizinti_kontrolu", return_value={
                "beklenmeyen_semboller": [{"id": "test", "adlar": ["gizli"]}], "adres_bicim_ihlalleri": []}):
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "denetimi başarısız"):
                cikar(self.kok, cikti, proje="test")
        self.assertEqual(cikti.read_text(), "önceki sağlam çıktı\n")
        self.assertTrue(cikti.with_suffix(".rapor.json").exists())


    def test_hosgoru_derlenemeyen_cift_sembol_ve_gizli_ithal(self):
        k = self.kok / "hosgoru"
        k.mkdir()
        (k / "a.c").write_text('''extern int kayip_fonk(int);
int main(void) { return 0; }
int kullanan_fonk(int n) { return kayip_fonk(n) + kayip_fonk(n + 1) + 3; }
''')
        (k / "b.c").write_text("int main(void) { return 1; }\nint ikinci_fonk(int n) { return n * 3 + 1; }\n")
        (k / "c.c").write_text("int kayip_fonk(int n) { return n; } bu C degil;")
        cikti = k / "cikti.jsonl"
        with contextlib.redirect_stdout(io.StringIO()):
            cikar(k, cikti, proje="hos", en_az=1, en_cok=1000, kipler=("tam",), opts=("-O0", "-O1"),
                  lisans="MIT", hosgoru=True)
        satirlar = [json.loads(s) for s in cikti.read_text().splitlines()]
        rapor = json.loads(cikti.with_suffix(".rapor.json").read_text())
        self.assertEqual({r["opt"] for r in satirlar}, {"-O0", "-O1"})
        self.assertTrue(all(r["lisans"] == "MIT" for r in satirlar))
        for o in rapor["optimizasyonlar"].values():
            self.assertEqual(o["derlenemeyen"], ["c.c"])
            self.assertEqual(o["cift_sembol_atilan"], ["b.c"])
            self.assertEqual(o["gizli_ithal"], 1)
        kullanan = [r for r in satirlar if r["ad"] == "kullanan_fonk"]
        self.assertTrue(kullanan)
        for r in kullanan:
            self.assertNotIn("kayip_fonk", r["asm"] + r["baglam"])
            self.assertIn("ext_0000", r["asm"])
        self.assertFalse([r for r in satirlar if r["ad"] == "ikinci_fonk"])


if __name__ == "__main__":
    unittest.main()
