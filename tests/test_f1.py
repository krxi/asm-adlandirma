"""taban.py ad F1'i: bütün ölçümler (taban.py, lora/olc.py, ozet.py, Colab) bu tanıma dayanır."""

import ast, json
from pathlib import Path

import pytest

import ozet
import taban
from taban import f1, kelimeler

KOK = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    "ad, beklenen",
    [
        ("adler32_update", ["adler32", "update"]),
        ("crc32Update", ["crc32", "update"]),
        ("sqlite3VdbeMemSet", ["sqlite3", "vdbe", "mem", "set"]),
        ("__stack_chk_fail", ["stack", "chk", "fail"]),
        ("ParseJSON", ["parse", "json"]),
        ("XMLParser", ["xmlparser"]),  # ardışık büyük harf bölünmez: bilinen sınır
        ("toml.parse-file", ["toml", "parse", "file"]),
        ("", []),
        ("___", []),
    ],
)
def test_kelimeler(ad, beklenen):
    assert kelimeler(ad) == beklenen


@pytest.mark.parametrize(
    "tahmin, gercek, beklenen",
    [
        ("adler32_update", "adler32_update", 1.0),
        ("ADLER32_UPDATE", "adler32_update", 1.0),  # büyük/küçük harf duyarsız
        ("adler32Update", "adler32_update", 1.0),  # camel ~ snake
        ("update_crc", "crc_update", 1.0),  # sözcük sırası puanı etkilemez (küme örtüşmesi)
        ("crc32_update", "update_crc", 0.5),  # p=1/2, r=1/2
        ("adler32", "adler32_update", 2 / 3),  # p=1, r=1/2
        ("get_get_value", "get_value", 1.0),  # tekrar eden sözcük ödüllenmez/cezalanmaz
        ("parse_value", "emit_scalar", 0.0),
        ("", "emit_scalar", 0.0),
        ("emit_scalar", "", 0.0),
    ],
)
def test_f1_degerleri(tahmin, gercek, beklenen):
    assert f1(tahmin, gercek) == pytest.approx(beklenen)


def test_f1_simetrik_ve_sinirli():
    ciftler = [("a_b_c", "b_c_d"), ("readFile", "file_read_all"), ("x", "x_y_z_w")]
    for t, g in ciftler:
        assert f1(t, g) == pytest.approx(f1(g, t))
        assert 0.0 <= f1(t, g) <= 1.0


def test_olc_ayni_f1_kullanir():
    import olc

    assert olc.f1 is taban.f1


def _fonksiyon_kaynagi(kod: str, ad: str) -> str:
    for dugum in ast.parse(kod).body:
        if isinstance(dugum, ast.FunctionDef) and dugum.name == ad:
            return ast.dump(dugum)
    return ""


@pytest.mark.parametrize("defter", sorted(KOK.glob("colab/*.ipynb")), ids=lambda p: p.name)
def test_colab_f1_taban_ile_ayni(defter):
    """Notebook'lar F1'i kopya olarak taşır; kopya taban.py'den ayrışırsa sonuçlar karşılaştırılamaz."""
    taban_kodu = (KOK / "taban.py").read_text()
    hucreler = ["".join(h["source"]) for h in json.loads(defter.read_text())["cells"] if h["cell_type"] == "code"]
    bulundu = False
    for kod in hucreler:
        # IPython satırları (%pip, !ls) AST'yi bozar; yalnız f1 tanımı olan hücrelere bak.
        if "def f1(" not in kod:
            continue
        kod = "\n".join(s for s in kod.splitlines() if not s.lstrip().startswith(("%", "!")))
        for ad in ("kelimeler", "f1"):
            kopya = _fonksiyon_kaynagi(kod, ad)
            if kopya:
                bulundu = True
                assert kopya == _fonksiyon_kaynagi(taban_kodu, ad), f"{defter.name}: {ad} taban.py'den farklı"
    if not bulundu:
        pytest.skip(f"{defter.name} F1 tanımlamıyor")


def test_ozet_oneksiz_f1(monkeypatch):
    monkeypatch.setattr(ozet, "ONEK", {"cyaml": {"cyaml"}})
    r = {"id": "cyaml/src/cyaml.c:-O0:cyaml_pool_alloc", "gercek": "cyaml_pool_alloc", "tahmin": "pool_alloc"}
    assert ozet.f1_oneksiz(r) == pytest.approx(1.0)
    assert f1(r["tahmin"], r["gercek"]) == pytest.approx(0.8)
    # Öneki bilinmeyen proje: düz F1.
    r3 = {"id": "baska/x.c:-O0:read_all", "gercek": "read_all", "tahmin": "read"}
    assert ozet.f1_oneksiz(r3) == pytest.approx(f1("read", "read_all"))
