"""Dondurulmuş tahmin ve çalışma dizininden bağımsız önek regresyonları."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import ad_olcutleri as a
import dogrulama_guvencesi as dg
import ozet

KOK = Path(__file__).resolve().parent.parent


def test_degistirilmis_tahmin_cli_tarafindan_reddedilir(tmp_path, monkeypatch, capsys):
    yol = tmp_path / "tahmin.jsonl"
    ozgun = json.dumps({"id": "v/1", "tahmin": "oku"}) + "\n"
    beklenen = hashlib.sha256(ozgun.encode()).hexdigest()
    monkeypatch.setattr(dg, "manifest_oku", lambda: {"dondurulmus_tahminler": {"v5": beklenen}})
    yol.write_text(ozgun, encoding="utf-8")
    dg.tahmin_ozetini_dogrula(yol)
    yol.write_text(ozgun.replace('"oku"', '"yaz"'), encoding="utf-8")
    with pytest.raises(SystemExit) as hata:
        a.main(["--veri", str(tmp_path / "veri.jsonl"), "--tahmin", str(yol)])
    assert hata.value.code == 2
    cikti = capsys.readouterr()
    assert "SHA-256" in cikti.err and not cikti.out


def test_onekler_acik_kokle_ayni_ve_farkli_cwdde_kararli(tmp_path):
    assert ozet.onekler() == ozet.onekler(KOK / "veri")
    kod = "import json,ozet; print(json.dumps({k:sorted(v) for k,v in sorted(ozet.ONEK.items())},sort_keys=True))"
    ortam = dict(os.environ, PYTHONPATH=str(KOK))

    def calistir(cwd):
        return subprocess.check_output([sys.executable, "-c", kod], cwd=cwd, env=ortam)

    assert calistir(KOK) == calistir(tmp_path)
