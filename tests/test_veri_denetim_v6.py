import json

import pytest

import veri_denetim_v6 as vd
from lora.hazirla import BAGLAM_BASLIK, DECOMPILE_BASLIK


def satir(kimlik, proje, ad, asm, baglam="", decompile="", hedef=None):
    user = asm + (BAGLAM_BASLIK + baglam if baglam else "") + (DECOMPILE_BASLIK + decompile if decompile else "")
    cevap = {"aciklama_en": "x", "ad": hedef or ad, "aciklama": "x"}
    return {
        "id": f"{proje}/{kimlik}.c:-O0:tam:sub_{kimlik}:{ad}",
        "proje": proje,
        "gercek_ad": ad,
        "messages": [
            {"role": "system", "content": "s"},
            {"role": "user", "content": user},
            {"role": "assistant", "content": json.dumps(cevap)},
        ],
    }


def yaz(dizin, bolumler):
    for bolum in vd.BOLUMLER:
        with (dizin / f"{bolum}.jsonl").open("w", encoding="utf-8") as dosya:
            for r in bolumler.get(bolum, []):
                dosya.write(json.dumps(r, ensure_ascii=False) + "\n")


ORTAK = "push\trbp\nmov\trbp, rsp\nmov\teax, 0x2a\npop\trbp\nret"
ORTAK_C = "int sub_00aa(void)\n{\n  return 0x2a;\n}"


@pytest.fixture
def veri(tmp_path):
    train = [
        satir("0001", "sqlite", "sqlite3BitvecClear", "mov\teax, 1\nret", decompile="int sub_0001(void) { return 1; }"),
        satir("0002", "sqlite", "sqlite3PagerClose", "mov\teax, 2\nret"),
        satir("0003", "janet", "janet_asin", "call\tasin    ; -> asin\nret", hedef="asin"),
        satir("0004", "lib", "answer_value", ORTAK, decompile=ORTAK_C),
    ]
    test = [
        # snkv, sqlite'ı gömer: aynı adlı satır ve train'de aynı decompile.
        satir(
            "0101",
            "snkv",
            "sqlite3BitvecClear",
            "xor\teax, eax\ninc\teax\nret",
            decompile="int sub_0f00(void) { return 1; }",
        ),
        satir("0102", "snkv", "kv_open_store", "mov\teax, 3\nret"),
        # Adı yalnız string sabitinde geçer: izinli sinyal, kimlik sızıntısı değil.
        satir("0103", "toml", "toml_parse_file", 'lea\trdi, [rip + dat_0001]    ; -> "toml_parse_file failed"\nret'),
        # Aynı normalize asm (yalnız sub_/dat_ kimlikleri farklı).
        satir("0104", "toml", "toml_answer", ORTAK, decompile=ORTAK_C.replace("sub_00aa", "sub_0bbb")),
    ]
    yaz(tmp_path, {"train": train, "valid": [], "test": test, "test_sabit": test[:2], "valid_300": [], "eval115": []})
    return tmp_path


def test_kisimlar_ve_normalize():
    asm, baglam, decompile = vd.kisimlar("a" + BAGLAM_BASLIK + "b" + DECOMPILE_BASLIK + "c")
    assert (asm, baglam, decompile) == ("a", "b", "c")
    assert vd.kisimlar("yalniz asm") == ("yalniz asm", "", "")
    assert vd.normalize("call  sub_00a1\n  mov eax, dat_0042  FUN_00401a30") == "call sub_ mov eax, dat_ ghidra_"


def test_sizinti_turleri():
    assert vd.sizinti("asin", "call\tasin    ; -> asin") == "kimlik"
    assert vd.sizinti("toml_parse", '; -> "toml_parse failed"') == "string"
    assert vd.sizinti("parse", "call\tparse_header") == "alt_dizgi"
    assert vd.sizinti("get", "call\tget") is None  # MIN_AD altı
    assert vd.sizinti("missing", "ret") is None


def test_denetim_raporu(veri):
    rapor = vd.denetle(veri)
    assert rapor["satir"]["train"] == 4 and rapor["satir"]["test"] == 4
    assert rapor["ayriklik"]["train~test"] == {"proje": [], "kimlik": 0, "kaynak_fonksiyon": 0}
    assert rapor["alt_kume"]["test_sabit⊂test"] is True
    # janet_asin hedefi "asin" import'un kendisi: kimlik eşleşmesi train'de raporlanır.
    assert rapor["sizinti"]["train"]["asm.kimlik"] == 1
    assert rapor["sizinti"]["test"] == {"asm.string": 1}
    assert rapor["kopya"]["test"]["asm"]["satir"] == 1
    assert rapor["kopya"]["test"]["decompile"]["satir"] == 2
    gomulu = rapor["gomulu"]["test"]["ciftler"]["snkv"]
    assert gomulu["train_projesi"] == "sqlite" and gomulu["ayni_adli_satir"] == 1
    assert rapor["gomulu"]["test_sabit"]["satir"] == 1


def test_tahmin_tanisal_gruplari(veri, tmp_path):
    tahmin = tmp_path / "tahmin.jsonl"
    rows = [
        {"id": "snkv/0101.c:-O0:tam:sub_0101:sqlite3BitvecClear", "tahmin": "sqlite3BitvecClear"},
        {"id": "snkv/0102.c:-O0:tam:sub_0102:kv_open_store", "tahmin": "open_store"},
    ]
    tahmin.write_text("".join(json.dumps(r) + "\n" for r in rows))
    s = vd.denetle(veri, {"test_sabit": tahmin})["tahmin_tanisal"]["test_sabit"]
    assert s["hepsi"]["n"] == 2
    assert s["gomulu_ad"] == {"n": 1, "f1": 1.0}
    assert s["gomulu_ad_degil"]["n"] == 1 and s["gomulu_ad_degil"]["f1"] == pytest.approx(0.8)


def test_tahmin_kimlikleri_bolumle_uyusmali(veri, tmp_path):
    tahmin = tmp_path / "yabanci.jsonl"
    tahmin.write_text(json.dumps({"id": "yok", "tahmin": "x"}) + "\n")
    with pytest.raises(ValueError, match="uyuşmuyor"):
        vd.denetle(veri, {"test_sabit": tahmin})


def test_cli_bolum_adi_dogrulanir(veri):
    with pytest.raises(SystemExit):
        vd.main(["--veri", str(veri), "--tahmin", "train=x.jsonl"])
