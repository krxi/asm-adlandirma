"""Yalnız sentetik adlar: dar eşleme, eski skorlar ve validation sınırı."""

import copy
import itertools
import json
from pathlib import Path

import pytest

import ad_olcutleri as a
import taban
import dogrulama_guvencesi as dg

SABIT_SOZLUK_SHA256 = "40aa21783718337242b14eac81d913a71abaeda8405002a39081f2038393c32d"


def sentetik(ciftler):
    veri, tahmin, sabit = {}, {}, {}
    for i, (t, g) in enumerate(ciftler):
        k = f"sentetik/ozel-kimlik-{i}"
        veri[k] = {"id": k, "proje": "sentetik", "ad": g}
        tahmin[k] = {"id": k, "proje": "sentetik", "tahmin": t, "gercek": g, "f1": -999}
        sabit[k] = dict(tahmin[k])
    return veri, tahmin, sabit


def test_sozluk_sabit_ayrik_ve_salt_okunur():
    assert a.nesne_sha256(a.DAR_GRUPLAR) == SABIT_SOZLUK_SHA256
    sozcukler = [k for grup in a.DAR_GRUPLAR for k in grup]
    assert len(sozcukler) == len(set(sozcukler))
    assert dict(a.DAR_ESLEME) == {k: grup[0] for grup in a.DAR_GRUPLAR for k in grup}
    with pytest.raises(TypeError):
        a.DAR_ESLEME["read"] = "write"


@pytest.mark.parametrize(
    "tahmin,gercek,beklenen",
    [
        ("initBuf", "setup_buffer", 1.0),
        ("initialise", "initialize", 1.0),
        ("ptr-msg", "pointer_message", 1.0),
        ("init_initialize", "setup", 2 / 3),
        ("init_initialize_setup", "initialize_initialise", 4 / 5),
        ("buf_buf", "buffer", 1.0),
        ("buf32_init", "buffer64_setup", 0.5),
        ("buf_32", "buffer_64", 0.5),
        ("buffer2", "buffer", 0.0),
        ("read", "write", 0.0),
        ("encode", "decode", 0.0),
        ("free", "alloc", 0.0),
        ("size", "length", 0.0),
        ("unknown", "unlisted", 0.0),
        ("", "", 0.0),
        ("___", "init", 0.0),
        ("init", "", 0.0),
    ],
)
def test_esleme(tahmin, gercek, beklenen):
    assert a.dar_esleme_f1(tahmin, gercek) == pytest.approx(beklenen)
    assert a.dar_esleme_f1(gercek, tahmin) == pytest.approx(beklenen)
    assert 0 <= beklenen <= 1


def test_bir_hedef_bir_kere_kullanilir_ve_bijeksiyon_bulunur():
    assert a.dar_esleme_f1("init_initialize", "init") == pytest.approx(2 / 3)
    assert a.dar_esleme_f1("init_initialize", "initialize_setup") == 1.0
    assert taban.harmonik(*taban.kelime_pr("init_initialize", "init", esanlam=True)) == 1.0


def test_azami_esleme_bagimsiz_kucuk_tam_sayimla():
    sol = ("init", "initialize", "buf", "other")
    sag = ("setup", "initialise", "buffer", "other")
    for n in range(1, len(sol) + 1):
        for t in itertools.combinations(sol, n):
            for m in range(1, len(sag) + 1):
                for g in itertools.combinations(sag, m):
                    en_iyi = 0
                    for sira in itertools.permutations(g):
                        eslesen = sum(
                            x == y or a.DAR_ESLEME.get(x, x) == a.DAR_ESLEME.get(y, y) for x, y in zip(t, sira)
                        )
                        for secili in itertools.combinations(t, min(n, m)):
                            eslesen = max(
                                eslesen,
                                sum(
                                    x == y or a.DAR_ESLEME.get(x, x) == a.DAR_ESLEME.get(y, y)
                                    for x, y in zip(secili, sira)
                                ),
                            )
                        en_iyi = max(en_iyi, eslesen)
                    assert a.dar_esleme_f1("_".join(t), "_".join(g)) == pytest.approx(2 * en_iyi / (n + m))


def test_kanonik_bolme_ve_kayan_nokta_aynen_korunur():
    assert a.kelimeler is taban.kelimeler and a.f1 is taban.f1
    for t, g in (("Thing32Do", "thing32-do_more"), ("x_y", "y_z_w"), ("a_a_b", "a_c")):
        assert a.dar_esleme_f1(t, g) == taban.f1(t, g)


def test_dort_f1_ayri_ve_onbellek_puani_kullanilmaz(monkeypatch):
    monkeypatch.setattr(a.ozet, "ONEK", {"sentetik": {"sentetik"}})
    veri, tahmin, sabit = sentetik([("init_buf", "sentetik_setup_buffer")])
    once = copy.deepcopy((veri, tahmin, sabit))
    r = a.karsilastir(veri, tahmin, sabit)
    assert r["olcutler"] == {
        "ad_f1": 0.0,
        "oneksiz_f1": 0.0,
        "dar_esleme_f1": 0.8,
        "f1_es": 0.8,
        "tam_ad_dogrulugu": 0.0,
    }
    assert (veri, tahmin, sabit) == once
    assert r["tanim_farki"]["dar_esleme_f1"]["esli_yuzde95_ga"] == (0.8, 0.8)


def test_oneksiz_ve_eski_genis_esleme_ayni_skor_gibi_sunulmaz(monkeypatch):
    monkeypatch.setattr(a.ozet, "ONEK", {"sentetik": {"sentetik"}})
    r = a.karsilastir(*sentetik([("init_buf", "sentetik_init_buf")]))
    assert r["olcutler"]["ad_f1"] == 0.8 and r["olcutler"]["oneksiz_f1"] == 1.0
    r = a.karsilastir(*sentetik([("init_initialize", "setup")]))
    assert r["olcutler"]["f1_es"] == 1.0
    assert r["olcutler"]["dar_esleme_f1"] == pytest.approx(2 / 3)
    r = a.karsilastir(*sentetik([("size", "length")]))
    assert r["olcutler"]["f1_es"] == 1.0 and r["olcutler"]["dar_esleme_f1"] == 0.0


def test_yuvarlama_0001_farkini_silmez():
    veri, tahmin, sabit = sentetik([("init", "setup"), *([("a", "b")] * 999)])
    r = a.karsilastir(veri, tahmin, sabit)
    assert r["olcutler"]["dar_esleme_f1"] == 0.001
    assert r["tanim_farki"]["dar_esleme_f1"]["ad_f1_farki"] == 0.001
    assert r["tanim_farki"]["dar_esleme_f1"]["artan_satir_n"] == 1


def test_tam_ad_dogrulugu_kume_isabetinden_ayridir():
    r = a.karsilastir(*sentetik([("a_b", "b_a"), ("a_b", "a_b"), ("A_b", "a_b")]))
    assert r["olcutler"]["ad_f1"] == 1.0
    assert r["olcutler"]["tam_ad_dogrulugu"] == 1 / 3


@pytest.mark.parametrize("boz", ("hedef", "proje", "ham_proje", "ek_proje", "ham_ad", "gercek", "sabit_ad", "tur"))
def test_validation_ve_etiket_korumasi(boz):
    veri, tahmin, sabit = sentetik([("init", "setup")])
    k = next(iter(veri))
    if boz == "hedef":
        tahmin["heldout/ozel"] = tahmin.pop(k)
    elif boz == "proje":
        tahmin[k]["proje"] = "heldout"
    elif boz == "ham_proje":
        veri[k]["proje"] = "heldout"
    elif boz == "ek_proje":
        veri["heldout/ek"] = {"proje": "heldout"}
    elif boz == "ham_ad":
        veri[k]["ad"] = "degistirilmis"
    elif boz == "gercek":
        tahmin[k]["gercek"] = "degistirilmis"
    elif boz == "sabit_ad":
        veri[k]["ad"] = tahmin[k]["gercek"] = "degistirilmis"
    else:
        tahmin[k]["tahmin"] = None
    with pytest.raises(ValueError):
        a.karsilastir(veri, tahmin, sabit)


def test_cli_toplu_cikti_ve_degismeyen_girdiler(tmp_path, monkeypatch, capsys):
    veriler = sentetik([("initBuf", "setup_buffer"), ("ozel_gizli_tahmin", "ozel_gizli_hedef")])
    yollar = [tmp_path / f"girdi{i}.jsonl" for i in range(3)]
    for yol, veri in zip(yollar, veriler):
        yol.write_text("".join(json.dumps(r) + "\n" for r in veri.values()), encoding="utf-8")
    once = {p: p.read_bytes() for p in yollar}
    monkeypatch.setattr(a, "DOGRULAMA", yollar[2])
    monkeypatch.setattr(dg, "dayanaklar", lambda: (veriler[2], {"yasak/1"}))
    monkeypatch.setattr(
        dg,
        "manifest_oku",
        lambda: {
            "tam_dogrulama_sha256": a.sha256(yollar[0]),
            "dondurulmus_tahminler": {"v5": a.sha256(yollar[1])},
        },
    )
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
    a.main(["--veri", str(yollar[0]), "--tahmin", str(yollar[1])])
    metin = capsys.readouterr().out
    r = json.loads(metin)
    assert r["n"] == 2 and r["bolum"] == "valid300"
    assert r["iz"]["dar_esleme_sha256"] == SABIT_SOZLUK_SHA256
    assert r["iz"]["girdi_sha256"] == {
        rol: {"dosya": p.name, "sha256": a.sha256(p)} for rol, p in zip(("veri", "tahmin", "sabit"), yollar)
    }
    assert str(tmp_path) not in metin
    assert r["iz"]["komut"].startswith("python3 ")
    assert all(p.read_bytes() == b for p, b in once.items())
    assert not any(s in metin for s in ("ozel-kimlik", "initBuf", "setup_buffer", "ozel_gizli"))


@pytest.mark.parametrize("metin", ('{"id": "ozel-gizli"}\n{"id": "ozel-gizli"}\n', '{"id": "ozel-gizli"'))
def test_hata_satir_adini_yayimlamaz(tmp_path, metin):
    yol = tmp_path / "girdi.jsonl"
    yol.write_text(metin, encoding="utf-8")
    with pytest.raises(ValueError) as hata:
        a.jsonl_oku(yol)
    assert "ozel-gizli" not in str(hata.value)
