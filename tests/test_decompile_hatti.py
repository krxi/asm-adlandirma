import json
from pathlib import Path

import pytest

from cikar_bin import ikili_artefaktlarini_yaz
from decompile_ghidra import anonimlestir_decompile, eslemeleri_oku, ithal_haritasi
from taban import model_girdisi


def test_decompile_anonimlestirme_sizinti_ve_string_koruma():
    ham = '''int parse_packet(char *p) {
  project_helper(p);
  FUN_100001234();
  puts("parse_packet project_helper");
  return DAT_100004000;
}'''
    metin, sizinti = anonimlestir_decompile(
        ham, "parse_packet", {"parse_packet": "sub_0001", "project_helper": "sub_0002"}, "sub_0001")
    assert sizinti
    assert "int sub_0001" in metin
    assert "sub_0002(p)" in metin
    assert "FUN_100001234" in metin and "DAT_100004000" in metin
    assert "puts" in metin
    assert '"parse_packet project_helper"' in metin  # string sabiti ipucu olarak kalır
    kod = metin.replace('"parse_packet project_helper"', '""')
    assert "parse_packet" not in kod and "project_helper" not in kod


def test_decompile_sizinti_yoksa_yanlis_isaretlemez():
    metin, sizinti = anonimlestir_decompile(
        "int FUN_1000(void) { return strlen(\"packet\"); }",
        "parse_packet", {}, "sub_0001")
    assert not sizinti
    assert "strlen" in metin and "FUN_1000" in metin
    metin, _ = anonimlestir_decompile(
        "DAT_4010(p, n);", "hedef", {"DAT_4010": "memcpy"}, "sub_0001")
    assert metin == "memcpy(p, n);"


def test_ikili_sakla_ve_esleme_yolu(tmp_path):
    stripped = tmp_path / "stripped.dylib"
    stripped.write_bytes(b"stripped")
    satir = {"id": "p/a.c:-O0:tam:sub_0001:f", "proje": "p", "opt": "-O0",
             "adres": 0x1000, "boyut": 17, "dosya_ofseti": 512, "kimlik": "sub_0001"}
    hedef = tmp_path / "ikili"
    ikili_artefaktlarini_yaz(hedef, "p", "-O0", stripped, [satir], {0x2000: "puts"})
    assert (hedef / "p" / "O0.dylib").read_bytes() == b"stripped"
    kayit = json.loads((hedef / "p" / "O0.jsonl").read_text())
    assert kayit == {**satir, "ikili": "O0.dylib"}
    assert json.loads((hedef / "p" / "O0.ithal.json").read_text()) == {"8192": "puts"}
    gruplar = eslemeleri_oku(hedef, [satir["id"]])
    assert list(gruplar) == [(hedef / "p" / "O0.dylib").resolve()]
    assert list(gruplar.values())[0][0]["adres"] == 0x1000
    harita = ithal_haritasi(hedef / "p" / "O0.dylib")
    assert harita["FUN_2000"] == "puts"
    assert harita["DAT_0000000000002000"] == "puts"


@pytest.mark.parametrize(
    "kip,beklenen",
    [
        ("asm", "mov eax, 1\n\n; --- çağrılan fonksiyonlar ---\nsub_0002 (1 komut)"),
        ("decompile", "int FUN_1(void) { return 1; }"),
        ("ikisi", "mov eax, 1\n\n; --- çağrılan fonksiyonlar ---\nsub_0002 (1 komut)\n\n"
                   "/* --- Ghidra decompile --- */\nint FUN_1(void) { return 1; }"),
    ],
)
def test_taban_girdi_secenekleri(kip, beklenen):
    r = {"id": "p/a.c:-O0:tam:sub_1:f", "asm": "mov eax, 1",
         "baglam": "sub_0002 (1 komut)"}
    assert model_girdisi(r, baglam=True, girdi=kip,
                         decompile="int FUN_1(void) { return 1; }") == beklenen


def test_decompile_girdisi_eksikse_hata():
    with pytest.raises(ValueError, match="decompile yok"):
        model_girdisi({"id": "x", "asm": "ret"}, girdi="decompile")
