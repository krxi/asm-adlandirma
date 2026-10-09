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
    s = subprocess.run(
        [sys.executable, str(KOK / "test_seti.py"), "-k", str(k)], cwd=ornek_kok, capture_output=True, text=True
    )
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


def test_taban_idler_dosya_sirasini_korur_ve_n_yok_sayar(ornek_kok, monkeypatch):
    secilen = olcum_seti(ornek_kok, k=3)
    sira = [r["id"] for r in reversed(secilen[:4])]
    idler = ornek_kok / "idler.txt"
    idler.write_text("\n".join(sira) + "\n")
    monkeypatch.chdir(ornek_kok)
    monkeypatch.setattr(taban, "sor", sahte_sor)
    monkeypatch.setattr(sys, "argv", ["taban.py", "veri/test.jsonl", "-n", "1", "-m", "sahte",
                                       "--idler", str(idler)])
    taban.main()
    sonuc = oku_jsonl(ornek_kok / "sonuc" / f"test{len(sira)}-sahte.jsonl")
    assert [r["id"] for r in sonuc] == sira


def test_taban_kuru_istek_atmaz_ve_token_tahmini_yazar(ornek_kok, monkeypatch, capsys):
    secilen = olcum_seti(ornek_kok, k=1)
    idler = ornek_kok / "idler.txt"
    idler.write_text(secilen[0]["id"] + "\n")
    monkeypatch.chdir(ornek_kok)
    monkeypatch.setattr(taban, "sor", lambda *a, **k: pytest.fail("kuru kip istek atmamalı"))
    monkeypatch.setattr(sys, "argv", ["taban.py", "veri/test.jsonl", "--idler", str(idler),
                                       "--baglam", "--kuru"])
    taban.main()
    cikti = capsys.readouterr().out
    assert "tahmini toplam girdi tokenı" in cikti
    assert "test1-deepseek-v4.1-flash-baglam.jsonl" in cikti
    assert not (ornek_kok / "sonuc").exists()


def test_ozet_tablosu(ornek_kok, monkeypatch):
    olcum_seti(ornek_kok, k=2)
    monkeypatch.chdir(ornek_kok)
    monkeypatch.setattr(taban, "sor", sahte_sor)
    monkeypatch.setattr(sys, "argv", ["taban.py", "veri/test.jsonl", "-n", "1000", "-m", "sahte"])
    taban.main()
    s = subprocess.run(
        [sys.executable, str(KOK / "ozet.py"), "--md", "test"],
        cwd=ornek_kok,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(KOK), "PATH": ""},
    )
    assert s.returncode == 0, s.stderr
    assert "| test-sahte |" in s.stdout


def test_taban_oneksiz_iki_f1(ornek_kok, monkeypatch, capsys):
    secilen = olcum_seti(ornek_kok, k=3)
    monkeypatch.chdir(ornek_kok)
    import ozet

    monkeypatch.setattr(ozet, "ONEK", {"tomlc17": {"toml"}, "picomatch": {"pm"}})
    # Model gerçek adı öneksiz biliyor: gerçek ad F1 < 1, öneksiz F1 = 1 olmalı.
    gercek = {r["asm"]: r["ad"] for r in secilen}
    monkeypatch.setattr(
        taban,
        "sor",
        lambda model, asm, *a, **k: {
            "ad": "_".join(w for w in taban.kelimeler(gercek[asm]) if w not in ("toml", "pm")) or gercek[asm],
            "aciklama": "",
            "token": 1,
            "bitis": "stop",
        },
    )
    monkeypatch.setattr(sys, "argv", ["taban.py", "veri/test.jsonl", "-n", "1000", "-m", "sahte", "--oneksiz"])
    taban.main()
    sonuc = oku_jsonl(ornek_kok / "sonuc" / "test-sahte.jsonl")
    assert all(r["f1_oneksiz"] == 1.0 for r in sonuc)
    onekli = [
        r for r in sonuc if taban.kelimeler(r["gercek"])[0] in ("toml", "pm") and len(taban.kelimeler(r["gercek"])) > 1
    ]
    assert onekli and all(r["f1"] < 1.0 for r in onekli)
    assert "öneksiz F1 1.00" in capsys.readouterr().out


def test_taban_oneksiz_yokken_alan_eklenmez(ornek_kok, monkeypatch):
    olcum_seti(ornek_kok, k=1)
    monkeypatch.chdir(ornek_kok)
    monkeypatch.setattr(taban, "sor", sahte_sor)
    monkeypatch.setattr(sys, "argv", ["taban.py", "veri/test.jsonl", "-n", "1000", "-m", "sahte"])
    taban.main()
    assert all("f1_oneksiz" not in r for r in oku_jsonl(ornek_kok / "sonuc" / "test-sahte.jsonl"))


def test_iki_f1_oneksiz_hedefi_yakalar_ve_gercek_adla_puanlar(ornek_kok, monkeypatch):
    import iki_f1, ozet

    monkeypatch.setattr(ozet, "ONEK", {"tomlc17": {"toml"}})
    adlar = iki_f1.gercek_adlar(ornek_kok / "veri")
    satir = next(
        r
        for p in (ornek_kok / "veri" / "test").glob("tomlc17.jsonl")
        for r in oku_jsonl(p)
        if r["ad"].startswith("toml_")
    )
    oneksiz = satir["ad"][len("toml_") :]
    # Hedefi öneksiz yazılmış bir LoRA koşusu: dosyadaki f1 = 1, ama gerçek ad F1 < 1.
    kayit = {"id": satir["id"], "gercek": oneksiz, "tahmin": oneksiz, "f1": 1.0, "opt": satir["opt"]}
    p = iki_f1.puanla([kayit], adlar)
    assert p["hedef_farkli"] == 1 and p["bilinmeyen"] == 0 and p["kayitli_uyumsuz"] == 0
    assert p["gercek"]["hepsi"] == pytest.approx(f1(oneksiz, satir["ad"])) and p["gercek"]["hepsi"] < 1
    assert p["oneksiz"]["hepsi"] == pytest.approx(1.0)
    assert (p["isabet_gercek"], p["isabet_oneksiz"]) == (0, 1)


def test_iki_f1_rapor(ornek_kok, monkeypatch):
    olcum_seti(ornek_kok, k=2)
    monkeypatch.chdir(ornek_kok)
    monkeypatch.setattr(taban, "sor", sahte_sor)
    monkeypatch.setattr(sys, "argv", ["taban.py", "veri/test.jsonl", "-n", "1000", "-m", "sahte"])
    taban.main()
    s = subprocess.run(
        [sys.executable, str(KOK / "iki_f1.py"), "-o", "rapor/r.md"], cwd=ornek_kok, capture_output=True, text=True
    )
    assert s.returncode == 0, s.stderr
    md = (ornek_kok / "rapor" / "r.md").read_text()
    assert "| test-sahte |" in md and "gerçek ad |" in md
    assert "her satırda tutuyor" in md
    assert "## Önek tanımları test projelerinde" in md


def test_rapor_guncel(tmp_path):
    """rapor/F1_IKI_TANIM.md, sonuc/ değişince `python3 iki_f1.py` ile yeniden üretilmeli."""
    s = subprocess.run(
        [sys.executable, str(KOK / "iki_f1.py"), "-o", str(tmp_path / "r.md")], cwd=KOK, capture_output=True, text=True
    )
    assert s.returncode == 0, s.stderr
    assert (tmp_path / "r.md").read_text() == (KOK / "rapor" / "F1_IKI_TANIM.md").read_text(), (
        "rapor eski: python3 iki_f1.py çalıştırın"
    )
