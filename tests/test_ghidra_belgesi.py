"""Belge düzeltmesinin Ghidra çalışma kodunu değiştirmediğini denetle."""

import hashlib
import json
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def test_ghidra_kodu_bayt_bayt_korundu():
    kanit = json.loads((KOK / "rapor/arastirma/GHIDRA_KANIT.json").read_text(encoding="utf-8"))
    for yol, beklenen in kanit["kod_bloblari"].items():
        veri = (KOK / yol).read_bytes()
        assert hashlib.sha1(b"blob " + str(len(veri)).encode() + b"\0" + veri).hexdigest() == beklenen


def test_ghidra_belgesi_manuel_kapsami_soyler():
    metin = (KOK / "ghidra/README.md").read_text(encoding="utf-8")
    assert "Bu test CI'da koşmaz" in metin
    assert "elle koşulan isteğe bağlı" in metin
    assert len(metin.splitlines()) < 90


def test_ghidra_kaniti_tasinabilir_ve_acik_kaynakli():
    metin = (KOK / "rapor/arastirma/GHIDRA_KANIT.json").read_text(encoding="utf-8")
    assert "/workspace/" not in metin
    assert "sys.executable" not in metin
    kanit = json.loads(metin)
    assert len(kanit["uygulama_commit"]) == len(kanit["uygulama_tree"]) == 40
    assert kanit["kaynak"].endswith(kanit["uygulama_commit"])
    assert kanit["manuel_duman"].startswith("not run")
