import hashlib
import json

import pytest

import dogrulama_guvencesi as dg
import opt_eslesme as oe


def _yaz(yol, satirlar):
    yol.write_text("".join(json.dumps(r) + "\n" for r in satirlar), encoding="utf-8")
    return yol


@pytest.fixture
def girdiler(tmp_path, monkeypatch):
    veri, tahmin = [], []
    for no, (ad, opt, asm, komut, uretilen) in enumerate(
        [
            ("read_item", "-O0", "xor eax, eax", 3, "read_item"),
            ("read_item", "-O2", 'lea rax, [rip + "x"]', 2, "write_item"),
            ("hash_data", "-O0", "mov eax, 1", 5, "data_hash"),
            ("hash_data", "-O2", "mov eax, 2", 4, "hash_data"),
            ("close_file", "-O0", "ret", 1, "open_file"),
        ]
    ):
        k = f"sentetik/{no}"
        veri.append(
            {
                "id": k,
                "proje": "p",
                "dosya": "x.c",
                "ad": ad,
                "kip": "tam",
                "opt": opt,
                "asm": asm,
                "komut_sayisi": komut,
            }
        )
        tahmin.append({"id": k, "gercek": ad, "tahmin": uretilen, "f1": oe.f1(uretilen, ad)})
    sabit = {r["id"]: {"gercek": r["ad"], "proje": r["proje"], "opt": r["opt"]} for r in veri}
    monkeypatch.setattr(dg, "dayanaklar", lambda: (sabit, {"test/1", "eval/1"}))
    monkeypatch.setattr(dg, "manifest_oku", lambda: {"tam_dogrulama_sha256": "0" * 64})
    return _yaz(tmp_path / "validation.jsonl", veri), _yaz(tmp_path / "tahmin.jsonl", tahmin)


def test_esli_ve_eslenmemis_ozetler(girdiler):
    sonuc = oe.denetle(oe.girdileri_yukle(*girdiler), tohum=7, tekrar=200)
    assert (sonuc["satir"], sonuc["kaynak_islev_kip_grubu"], sonuc["birden_cok_opt_grubu"]) == (5, 3, 2)
    assert sonuc["opt"]["-O0"]["n"] == 3
    assert sonuc["opt"]["-O2"]["string_var"] == 1
    cift = sonuc["esli_cift"]["-O0 -> -O2"]
    assert cift["n"] == 2
    assert cift["ortalama_f1_farki"] == pytest.approx(-0.25)
    assert cift["esli_bootstrap_ga95"] == [-0.5, 0.0]


def test_ayni_kaynak_opt_yinelemesi_reddedilir(girdiler):
    rs = oe.girdileri_yukle(*girdiler)
    with pytest.raises(ValueError, match="birden çok"):
        oe.denetle(rs + [rs[0]])


@pytest.mark.parametrize("degisiklik", ["gercek", "f1", "gercek_ve_f1"])
def test_kanonik_etiket_ve_skor_tahrifi(girdiler, degisiklik):
    veri, tahmin = girdiler
    rs = oe.jsonl_oku(tahmin)
    if "gercek" in degisiklik:
        rs[0]["gercek"] = "baska_ad"
    if degisiklik == "f1":
        rs[0]["f1"] = 0.123
    elif degisiklik == "gercek_ve_f1":
        rs[0]["f1"] = oe.f1(rs[0]["tahmin"], rs[0]["gercek"])
    _yaz(tahmin, rs)
    with pytest.raises(ValueError, match="kanonik"):
        oe.girdileri_yukle(veri, tahmin)


@pytest.mark.parametrize("kimlik", ["test/1", "eval/1", "dis/1"])
def test_guvenli_adla_gizlenen_test_ve_dis_kimlik(girdiler, kimlik):
    veri, tahmin = girdiler
    rs = oe.jsonl_oku(veri)
    rs[0]["id"] = kimlik
    _yaz(veri, rs)
    with pytest.raises(ValueError):
        oe.girdileri_yukle(veri, tahmin)


def test_json_baytlari_siradan_bagimsiz_ve_golden(girdiler):
    rs = oe.girdileri_yukle(*girdiler)
    a = dg.json_metni(oe.denetle(rs, 42, 200)).encode("utf-8")
    b = dg.json_metni(oe.denetle(list(reversed(rs)), 42, 200)).encode("utf-8")
    assert a == b
    assert hashlib.sha256(a).hexdigest() == "a8aaef493cc8e29fe053fcffbf245edb95c01e64e2a8b272c58073765c8dbf65"
    assert b"read_item" not in a and b"sentetik/0" not in a and b"xor eax" not in a


def test_cli_json_tasinabilir(girdiler, tmp_path, monkeypatch):
    monkeypatch.setattr(dg, "git_izi", lambda: {"commit": "1" * 40, "tree": "2" * 40})
    veri, tahmin = girdiler
    cikti = tmp_path / "sonuc.json"
    oe.main(["--veri", str(veri), "--tahmin", str(tahmin), "--bootstrap", "200", "-o", str(cikti)])
    metin = cikti.read_text(encoding="utf-8")
    assert str(tmp_path) not in metin
    assert json.loads(metin)["girdi"]["tahmin"]["dosya"] == tahmin.name
