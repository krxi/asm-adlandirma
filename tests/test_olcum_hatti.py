"""Ölçüm hattı: test_seti.py → taban.py (model çağrısı sahte) → ozet.py, örnek veri üzerinde."""
import json, subprocess, sys
from pathlib import Path

import pytest

import taban
from taban import f1

KOK = Path(__file__).resolve().parent.parent


def oku_jsonl(yol):
    return [json.loads(l) for l in Path(yol).open() if l.strip()]


def olcum_seti(ornek_kok, k=3):
    s = subprocess.run([sys.executable, str(KOK / "test_seti.py"), "-k", str(k)], cwd=ornek_kok,
                       capture_output=True, text=True)
    assert s.returncode == 0, s.stderr
    return oku_jsonl(ornek_kok / "veri" / "test.jsonl")


def test_test_seti_sizintisiz_ve_sinirli(ornek_kok):
    secilen = olcum_seti(ornek_kok, k=3)
    assert secilen and not any(r["sizinti"] for r in secilen)
    sayi = {}
    for r in secilen:
        sayi[(r["proje"], r["opt"])] = sayi.get((r["proje"], r["opt"]), 0) + 1
    assert max(sayi.values()) <= 3
    assert {p for p, _ in sayi} == {"tomlc17", "picomatch"}
    # Belirlenimci: aynı tohum aynı seti verir.
    assert [r["id"] for r in olcum_seti(ornek_kok, k=3)] == [r["id"] for r in secilen]


def sahte_sor(model, asm, dusunme=False, tavan=4096, baglam=False):
    # Gerçek adı asm'den bilemeyen "model": bağlam görürse "toml_parse", görmezse "parse_value" döner.
    ad = "parse_value" if "--- çağrılan fonksiyonlar ---" not in asm else "toml_parse"
    return {"ad": ad, "aciklama": "sahte", "token": 10, "bitis": "stop"}


@pytest.mark.parametrize("baglam", [False, True])
def test_taban_uctan_uca_sahte_model(ornek_kok, monkeypatch, capsys, baglam):
    secilen = olcum_seti(ornek_kok, k=2)
    monkeypatch.chdir(ornek_kok)
    monkeypatch.setattr(taban, "sor", sahte_sor)
    argv = ["taban.py", "veri/test.jsonl", "-n", "1000", "-m", "sahte", "-j", "2"] + (["--baglam"] if baglam else [])
    monkeypatch.setattr(sys, "argv", argv)
    taban.main()
    sonuc = oku_jsonl(ornek_kok / "sonuc" / f"test-sahte{'-baglam' if baglam else ''}.jsonl")
    assert len(sonuc) == len(secilen)
    assert not list((ornek_kok / "sonuc").glob("*.ara"))
    gercek = {r["id"]: r for r in secilen}
    for r in sonuc:
        assert r["gercek"] == gercek[r["id"]]["ad"]
        assert r["opt"] == gercek[r["id"]]["opt"]
        assert r["f1"] == round(f1(r["tahmin"], r["gercek"]), 3)
        bekl = "toml_parse" if baglam and gercek[r["id"]].get("baglam") else "parse_value"
        assert r["tahmin"] == bekl
    cikti = capsys.readouterr().out
    assert "ortalama F1" in cikti


def test_taban_devam_saglam_satirlari_korur(ornek_kok, monkeypatch):
    olcum_seti(ornek_kok, k=2)
    monkeypatch.chdir(ornek_kok)
    monkeypatch.setattr(sys, "argv", ["taban.py", "veri/test.jsonl", "-n", "1000", "-m", "sahte"])
    monkeypatch.setattr(taban, "sor", sahte_sor)
    taban.main()
    yol = ornek_kok / "sonuc" / "test-sahte.jsonl"
    satirlar = oku_jsonl(yol)
    # Bir satırı HATA'ya çevir; --devam yalnız onu yeniden sormalı.
    satirlar[0]["aciklama"] = "HATA: zaman aşımı"
    yol.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in satirlar))
    sorulan = []
    monkeypatch.setattr(taban, "sor", lambda *a, **k: sorulan.append(a[1]) or sahte_sor(*a, **k))
    monkeypatch.setattr(sys, "argv", ["taban.py", "veri/test.jsonl", "-n", "1000", "-m", "sahte", "--devam"])
    taban.main()
    assert len(sorulan) == 1
    assert not any(str(r["aciklama"]).startswith("HATA") for r in oku_jsonl(yol))


def test_ozet_tablosu(ornek_kok, monkeypatch):
    olcum_seti(ornek_kok, k=2)
    monkeypatch.chdir(ornek_kok)
    monkeypatch.setattr(taban, "sor", sahte_sor)
    monkeypatch.setattr(sys, "argv", ["taban.py", "veri/test.jsonl", "-n", "1000", "-m", "sahte"])
    taban.main()
    s = subprocess.run([sys.executable, str(KOK / "ozet.py"), "--md", "test"], cwd=ornek_kok,
                       capture_output=True, text=True, env={"PYTHONPATH": str(KOK), "PATH": ""})
    assert s.returncode == 0, s.stderr
    assert "| test-sahte |" in s.stdout
