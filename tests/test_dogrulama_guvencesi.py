import hashlib
import json

import pytest

import dogrulama_guvencesi as dg


def _yaz(yol, satirlar):
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text("".join(json.dumps(r) + "\n" for r in satirlar), encoding="utf-8")
    return yol


@pytest.fixture
def sinir(tmp_path, monkeypatch):
    sabit = _yaz(tmp_path / "anchor.jsonl", [{"id": "v/1", "gercek": "oku", "proje": "v", "opt": "-O0"}])
    _yaz(tmp_path / "veri/test.jsonl", [{"id": "e/1"}])
    (tmp_path / "lora").mkdir()
    (tmp_path / "lora/test_sabit_idler.txt").write_text("t/1\n")
    m = tmp_path / "manifest.json"
    m.write_text(
        json.dumps(
            {
                "sabit_dogrulama": {"dosya": "anchor.jsonl", "sha256": dg.sha256(sabit)},
                "tam_dogrulama_sha256": "0" * 64,
                "dondurulmus_tahminler": {"v5": dg.sha256(sabit)},
            }
        )
    )
    monkeypatch.setattr(dg, "KOK", tmp_path)
    monkeypatch.setattr(dg, "MANIFEST", m)
    return tmp_path, sabit


@pytest.mark.parametrize("kimlik", ["t/1", "e/1", "baska/1"])
def test_yeniden_adlandirilmis_test_icerigi_reddedilir(sinir, kimlik):
    kok, _ = sinir
    yol = _yaz(kok / "lora/veri-v5/eval115.jsonl", [{"id": kimlik}])
    with pytest.raises(ValueError):
        dg.ham_dogrula(yol, dg.jsonl_oku(yol), [kimlik])


def test_sabit_ve_tahmin_degistirme_reddedilir(sinir):
    kok, sabit = sinir
    dg.kimlikleri_dogrula(["v/1"])
    dg.tahmin_ozetini_dogrula(sabit)
    degisen = kok / "tahmin.jsonl"
    degisen.write_bytes(sabit.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="SHA-256"):
        dg.tahmin_ozetini_dogrula(degisen)
    sabit.write_bytes(degisen.read_bytes())
    with pytest.raises(ValueError, match="SHA-256"):
        dg.kimlikleri_dogrula(["v/1"])


def test_bos_yinelenen_ve_yasak_izin_ortusmesi():
    for kimlikler, izinli, yasak in [([], {"v"}, set()), (["v", "v"], {"v"}, set()), (["v"], {"v"}, {"v"})]:
        with pytest.raises(ValueError):
            dg.kimlik_kumesi_dogrula(kimlikler, izinli, yasak)


def test_kanonik_hedef_korunur(sinir):
    kok, _ = sinir
    yol = _yaz(kok / "veri.jsonl", [{"id": "v/1", "ad": "yanlis", "proje": "v", "opt": "-O0"}])
    with pytest.raises(ValueError, match="Kanonik"):
        dg.ham_dogrula(yol, dg.jsonl_oku(yol), ["v/1"])


def test_tasinabilir_yol_ve_sabit_json(sinir, tmp_path):
    kok, sabit = sinir
    assert dg.dosya_izi(sabit)["dosya"] == "anchor.jsonl"
    dis = _yaz(kok.parent / "harici.jsonl", [{"id": "sentetik"}])
    assert dg.dosya_izi(dis)["dosya"] == dis.name
    metin = dg.json_metni({"z": -1e-12, "a": [1 / 3, "ı"]})
    beklenen = '{\n  "a": [\n    0.333333333,\n    "ı"\n  ],\n  "z": 0.0\n}\n'
    assert metin.encode("utf-8") == beklenen.encode("utf-8")
    assert hashlib.sha256(metin.encode()).digest() == hashlib.sha256(beklenen.encode()).digest()
    with pytest.raises(ValueError):
        dg.json_metni({"x": float("nan")})
