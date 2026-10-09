"""cikar.py'nin derleyiciden bağımsız yardımcıları: anonimleştirme, sızıntı, çağrı bağlamı."""

import pytest

from cikar import (
    anonimlestir,
    csym,
    fonksiyon_ozeti,
    gercek_sembol_deseni,
    ic_cagrilar,
    sizar_mi,
    string_bul,
    string_goster,
    string_kisalt,
)


def test_csym():
    assert csym("_inflate") == "inflate"
    assert csym("___stack_chk_guard") == "__stack_chk_guard"
    assert csym("ltmp0") == "ltmp0"


@pytest.mark.parametrize(
    "ad, asm, beklenen",
    [
        ("parse_value", 'lea\trdi, [rip]    ; -> "parse_value failed"', True),
        ("parse_value", 'lea\trdi, [rip]    ; -> "PARSE_VALUE"', True),  # büyük/küçük harf duyarsız
        ("parse_value", 'lea\trdi, [rip]    ; -> "parse_values"', False),  # sözcük sınırı
        ("parse_value", "call\tsub_0001    ; -> my_parse_value", False),
        ("get", 'lea\trdi, [rip]    ; -> "get"', False),  # ≤3 harf sayılmaz
        ("toml_free", "mov\trax, rdi\nret", False),
    ],
)
def test_sizar_mi(ad, asm, beklenen):
    assert sizar_mi(ad, asm) is beklenen


def test_string_bul_bas_orta_ve_yok():
    strs = {0x100: "out of memory", 0x200: "ab"}
    assert string_bul(strs, 0x100) == "out of memory"
    assert string_bul(strs, 0x107) == "memory"  # derleyici kuyruk paylaşımı
    assert string_bul(strs, 0x300) is None
    assert string_bul(strs, None) is None


def test_string_goster_ve_kisalt():
    assert string_goster('a"b\n') == '"a\\"b\\n"'
    uzun = string_goster("x" * 100)
    assert uzun.endswith('…"') and len(uzun) == 83
    assert string_kisalt('"kisa"') == '"kisa"'
    k = string_kisalt('"' + "y" * 80 + '"')
    assert len(k) <= 60 and k.endswith('…"')


def test_ic_cagrilar_iki_bicim_tekil_ve_sinir():
    asm = "\n".join(
        [
            "call\tloc_1    ; -> sub_000a",
            "loc_1:",
            "call\tsub_000b",
            "jmp\tloc_2    ; -> sub_000a",  # tekrar: bir kez
            "call\tloc_3    ; -> memcpy",  # dış import iç çağrı değil
            "mov\trax, qword ptr [rip]    ; -> dat_0001",
            "callq\tloc_4    ; -> sub_000c",
        ]
    )
    assert ic_cagrilar(asm) == ["sub_000a", "sub_000b", "sub_000c"]
    assert ic_cagrilar(asm, sinir=2) == ["sub_000a", "sub_000b"]


def test_fonksiyon_ozeti():
    asm = "\n".join(
        [
            'lea\trdi, [rip]    ; -> "hata"',
            "call\tloc_1    ; -> malloc",
            "loc_1:",
            "call\tloc_2    ; -> sub_0003",
            "mov\trax, qword ptr [rip]    ; -> dat_0002",
            "lea\trsi, [rip]    ; -> veri",
        ]
    )
    assert fonksiyon_ozeti("sub_0001", 6, asm) == 'sub_0001 (6 komut): çağırır malloc, sub_0003; string "hata"'
    assert fonksiyon_ozeti("sub_0002", 2, "mov\teax, 0x1\nret") == "sub_0002 (2 komut)"


def test_anonimlestir_objdump_ciktisi():
    # objdump -d -r --no-show-raw-insn çıktısı (ayristir'in strip ettiği hâliyle).
    satirlar = [
        "0: push\trbp",
        "1: mov\trbp, rsp",
        "4: lea\trdi, [rip + 0x0]        ## 0x40 <_kendi+0x40>",
        "0000000000000007:  X86_64_RELOC_SIGNED\t__cstring",
        "b: jne\t0x20 <_kendi+0x20>",
        "d: call\t0x12 <_kendi+0x12>",
        "000000000000000e:  X86_64_RELOC_BRANCH\t_ic_yardimci",
        "12: call\t0x17 <_kendi+0x17>",
        "0000000000000013:  X86_64_RELOC_BRANCH\t_memcpy",
        "17: mov\trax, qword ptr [rip + 0x0]",
        "000000000000001a:  X86_64_RELOC_GOT_LOAD\t_gizli_tablo",
        "20: pop\trbp",
        "21: ret",
    ]
    adlar = {"ic_yardimci": "sub_0003", "kendi": "sub_0001", "gizli_tablo": "dat_0002"}
    asm = anonimlestir(satirlar, adlar, {0x40: "hata oldu\n"}, "kendi")
    assert asm.splitlines() == [
        "push\trbp",
        "mov\trbp, rsp",
        'lea\trdi, [rip]    ; -> "hata oldu\\n"',
        "jne\tloc_1",
        "call\tloc_2    ; -> sub_0003",
        "loc_2:",
        "call\tloc_3    ; -> memcpy",
        "loc_3:",
        "mov\trax, qword ptr [rip]    ; -> dat_0002",
        "loc_1:",
        "pop\trbp",
        "ret",
    ]
    # Gerçek iç adlar ve .o ofsetleri görünüme sızmamalı.
    for sizinti in ("kendi", "ic_yardimci", "gizli_tablo", "0x40", "0x12"):
        assert sizinti not in asm


def test_gercek_sembol_deseni():
    desen = gercek_sembol_deseni({"inflate_fast", "crc", "adler32"})
    assert desen.search("; -> inflate_fast")
    assert desen.search("ADLER32 ")
    assert not desen.search("crc")  # 5 harften kısa adlar desende yok
    assert not desen.search("my_inflate_fast_x")
    assert gercek_sembol_deseni({"a", "bc"}) is None
