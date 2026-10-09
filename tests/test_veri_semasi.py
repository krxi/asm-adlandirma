"""Repodaki ölçüm verisinin bütünlüğü: README'deki sayılar ve sızıntı/ayrım garantileri."""
import json
from pathlib import Path

import pytest

from cikar import sizar_mi

KOK = Path(__file__).resolve().parent.parent
ALANLAR = {"id", "proje", "surum", "dosya", "opt", "ad", "komut_sayisi", "sizinti", "asm", "baglam", "baglam_derin"}
TEST_DOSYALARI = sorted((KOK / "veri" / "test").glob("*.jsonl"))


def oku_jsonl(yol):
    return [json.loads(l) for l in Path(yol).open() if l.strip()]


@pytest.fixture(scope="module")
def test_satirlari():
    return [r for p in TEST_DOSYALARI for r in oku_jsonl(p)]


@pytest.fixture(scope="module")
def olcum_seti():
    return oku_jsonl(KOK / "veri" / "test.jsonl")


def test_test_projeleri_ve_sayilar(test_satirlari, olcum_seti):
    assert {p.stem for p in TEST_DOSYALARI} == {"tomlc17", "cyaml", "mu_json_x", "sajs", "picomatch"}
    assert len(test_satirlari) == 777          # README: test 777
    assert len(olcum_seti) == 115              # README: eval_115


@pytest.mark.parametrize("yol", TEST_DOSYALARI + [KOK / "veri" / "test.jsonl"], ids=lambda p: p.name)
def test_satir_semasi(yol):
    for r in oku_jsonl(yol):
        assert ALANLAR <= set(r), r.get("id")
        assert r["opt"] in ("-O0", "-O2")
        assert r["id"] == f"{r['proje']}/{r['dosya']}:{r['opt']}:{r['ad']}"
        assert r["asm"].strip() and r["komut_sayisi"] > 0
        if yol.parent.name == "test":
            assert r["proje"] == yol.stem


def test_kimlikler_tekil(test_satirlari):
    ids = [r["id"] for r in test_satirlari]
    assert len(ids) == len(set(ids))


def test_sizinti_bayragi_tutarli(test_satirlari):
    # cikar.py: ad asm'de ya da bağlamlarda ayrı sözcük olarak geçiyorsa sizinti.
    for r in test_satirlari:
        beklenen = any(sizar_mi(r["ad"], r[a]) for a in ("asm", "baglam", "baglam_derin"))
        assert r["sizinti"] is beklenen, r["id"]


def test_olcum_seti_alt_kume_ve_sizintisiz(test_satirlari, olcum_seti):
    tum = {r["id"]: r for r in test_satirlari}
    for r in olcum_seti:
        assert r["id"] in tum
        assert not r["sizinti"]
        assert r["asm"] == tum[r["id"]]["asm"]
    sayi = {}
    for r in olcum_seti:
        sayi[(r["proje"], r["opt"])] = sayi.get((r["proje"], r["opt"]), 0) + 1
    assert max(sayi.values()) <= 12            # test_seti.py -k 12


def test_asmde_gercek_ic_ad_yok(test_satirlari):
    """Anonimleştirme: projenin kendi fonksiyon adları asm'de değil, sub_XXXX olarak görünmeli.

    Proje bazında bakılır: mu_json_x'in kendi strlen'i başka projede libc importu olarak görünebilir."""
    from cikar import gercek_sembol_deseni
    projeler = {}
    for r in test_satirlari:
        projeler.setdefault(r["proje"], []).append(r)
    for proje, satirlar in projeler.items():
        desen = gercek_sembol_deseni({r["ad"] for r in satirlar})
        for r in satirlar:
            if r["sizinti"]:
                continue
            # String yorumları (; -> "...") gerçek binary'de de görünür; yalnız kod/çağrı kısmına bak.
            kod = "\n".join(s.split('; -> "')[0] for s in r["asm"].splitlines())
            bulunan = desen.search(kod)
            assert bulunan is None, f"{r['id']}: {bulunan.group(0)}"
