"""taban.py kısmi isabet metrikleri (precision/recall, eş anlamlı) ve onek_denetim.py."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import onek_denetim
import taban
from taban import ESANLAM, ESANLAM_GRUPLARI, f1, harmonik, kelime_pr

KOK = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    "tahmin, gercek, p, r",
    [
        ("adler32_update", "adler32_update", 1.0, 1.0),
        ("update", "adler32_update", 1.0, 0.5),  # doğru ama eksik
        ("adler32_update_checksum_fast", "adler32_update", 0.5, 1.0),  # doğru ama fazla
        ("parse_value", "emit_scalar", 0.0, 0.0),
        ("", "emit_scalar", 0.0, 0.0),
    ],
)
def test_kelime_pr(tahmin, gercek, p, r):
    assert kelime_pr(tahmin, gercek) == pytest.approx((p, r))


@pytest.mark.parametrize(
    "tahmin, gercek",
    [("crc32_update", "update_crc"), ("readFile", "file_read_all"), ("a_b_c", "b_c_d"), ("x", "y")],
)
def test_f1_precision_recall_harmonik_ortalamasi(tahmin, gercek):
    assert harmonik(*kelime_pr(tahmin, gercek)) == pytest.approx(f1(tahmin, gercek))


@pytest.mark.parametrize(
    "tahmin, gercek, duz, esanlam",
    [
        ("fetch_length", "get_size", 0.0, 1.0),
        ("read_buffer", "load_buf", 0.0, 1.0),
        ("destroy_ctx", "free_context", 0.0, 1.0),
        ("string_compare", "str_cmp", 0.0, 1.0),
        ("get_value", "find_value", 0.5, 0.5),  # get ve find ayrı grupta
        ("get_size", "set_size", 0.5, 0.5),  # zıt anlamlılar birleşmez
    ],
)
def test_esanlam(tahmin, gercek, duz, esanlam):
    assert f1(tahmin, gercek) == pytest.approx(duz)
    assert harmonik(*kelime_pr(tahmin, gercek, esanlam=True)) == pytest.approx(esanlam)


def test_esanlam_gruplari_ayrik():
    sozcukler = [k for grup in ESANLAM_GRUPLARI for k in grup]
    assert len(sozcukler) == len(set(sozcukler)), "bir sözcük iki grupta olamaz"
    assert all(ESANLAM[grup[0]] == grup[0] for grup in ESANLAM_GRUPLARI)


def test_taban_kismi_ve_esanlam(ornek_kok, monkeypatch, capsys):
    s = subprocess.run(
        [sys.executable, str(KOK / "test_seti.py"), "-k", "2"], cwd=ornek_kok, capture_output=True, text=True
    )
    assert s.returncode == 0, s.stderr
    monkeypatch.chdir(ornek_kok)
    monkeypatch.setattr(
        taban, "sor", lambda *a, **k: {"ad": "get_value_size", "aciklama": "", "token": 1, "bitis": "stop"}
    )
    argv = ["taban.py", "veri/test.jsonl", "-n", "1000", "-m", "sahte", "--kismi", "--esanlam"]
    monkeypatch.setattr(sys, "argv", argv)
    taban.main()
    satirlar = [json.loads(x) for x in (ornek_kok / "sonuc" / "test-sahte.jsonl").open()]
    for r in satirlar:
        p, rc = kelime_pr(r["tahmin"], r["gercek"])
        assert (r["p"], r["r"]) == (round(p, 3), round(rc, 3))
        assert r["f1"] == round(f1(r["tahmin"], r["gercek"]), 3)  # ana F1 değişmez
        assert r["f1_es"] >= r["f1"] - 0.001
    cikti = capsys.readouterr().out
    assert "precision" in cikti and "eş anlamlı" in cikti


def test_onek_denetimi_yanlis_kirpmalari_bulur(tmp_path):
    satirlar = (
        [{"proje": "sajs", "ad": f"eat_x{i}"} for i in range(6)]
        + [{"proje": "sajs", "ad": "x0"}, {"proje": "sajs", "ad": "parse"}]
        + [{"proje": "cyaml", "ad": f"cyaml_f{i}"} for i in range(6)]
    )
    d = tmp_path / "v.jsonl"
    d.write_text("".join(json.dumps(r) + "\n" for r in satirlar))
    sonuc = {s["proje"]: s for s in onek_denetim.denetle(onek_denetim.oku([d]))}
    assert sonuc["sajs"]["siklik"] == ["eat"] and sonuc["sajs"]["proje_kurali"] == []
    assert len(sonuc["sajs"]["yanlis"]) == 6
    assert sonuc["sajs"]["cakisma"] == [("eat_x0", "x0")]  # kırpınca eat_x0 → x0
    assert sonuc["cyaml"]["yanlis"] == [] and sonuc["cyaml"]["proje_kurali"] == ["cyaml"]
    md = onek_denetim.rapor(list(sonuc.values()), [d])
    assert "| sajs | 8 | eat | - | 6 | 1 |" in md
    assert "`eat_x0` → `x0`" in md


def test_onek_denetim_raporu_guncel(tmp_path):
    # Yalnız git'teki dosyalar: Mac'te veri/egitim ve veri/bin/olcek de varsa rapor farklı olur.
    git_dosyalari = sorted(str(p.relative_to(KOK)) for p in [*KOK.glob("veri/*.jsonl"), *KOK.glob("veri/test/*.jsonl")])
    s = subprocess.run(
        [sys.executable, str(KOK / "onek_denetim.py"), *git_dosyalari, "-o", str(tmp_path / "r.md")],
        cwd=KOK,
        capture_output=True,
        text=True,
    )
    assert s.returncode == 0, s.stderr
    assert (tmp_path / "r.md").read_text() == (KOK / "rapor" / "ONEK_DENETIM.md").read_text(), (
        "rapor eski: python3 onek_denetim.py çalıştırın"
    )
