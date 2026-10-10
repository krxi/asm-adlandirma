"""Yalnız sentetik fonksiyonlar: salt okunurluk, kapsam ayrımı ve etiket bağımsızlığı."""

import copy
import hashlib
import inspect
import json

import pytest

import analiz
import dogrulama_guvencesi as dg
import sarmalayici_deneyi as sd


def kayit(i, asm="ret", n=10, **alanlar):
    return {
        "id": f"sentetik/ozel-kimlik-{i}",
        "proje": "sentetik",
        "surum": "commit-a",
        "opt": "-O2",
        "kip": "tam",
        "kimlik": f"sub_{i:04x}",
        "asm": asm,
        "komut_sayisi": n,
        "ad": "ozel_etiket",
        **alanlar,
    }


def veri(*satirlar):
    return {r["id"]: r for r in satirlar}


@pytest.mark.parametrize(
    "asm,n,beklenen",
    [
        ("call sub_0002", 25, True),
        ("call sub_0002", 26, False),
        ("call sub_0002\ncall sub_0002", 10, False),
        ("jmp sub_0002", 10, True),
        ("call loc_1 ; -> sub_0002", 10, True),
        ("call malloc", 10, False),
        ("call malloc\njmp sub_0002", 10, True),
        (" call sub_0002", 10, False),
    ],
)
def test_mevcut_siniflandirici_birebir(asm, n, beklenen):
    r = kayit(1, asm, n)
    assert sd.turler is analiz.turler
    assert sd.sayim(veri(r))["sarmalayici_n"] == int(beklenen)


@pytest.mark.parametrize("alan,deger", [("proje", "baska"), ("surum", "commit-b"), ("opt", "-O0"), ("kip", "yerel")])
def test_ikili_kapsami_karismaz(alan, deger):
    a, b = kayit(1, "call sub_0002"), kayit(2, **{alan: deger})
    temel = {a["id"]: "original"}
    aday, say = sd.tek_adim(veri(a, b), temel, {b["id"]: "callee_prediction"})
    assert aday == temel and say["bag_eksik"] == 1


def test_ozgun_bir_adim_siradan_ve_etiketten_bagimsiz():
    a, b, c = kayit(1, "call sub_0002"), kayit(2, "call sub_0003"), kayit(3)
    v = veri(a, b, c)
    temel = {a["id"]: "first", b["id"]: "second", c["id"]: "third"}
    once = copy.deepcopy((v, temel))
    aday, say = sd.tek_adim(v, temel, {})
    assert aday == {a["id"]: "second", b["id"]: "third", c["id"]: "third"}
    assert say["aktarilan"] == 2 and (v, temel) == once
    for r in v.values():
        r.update(ad="changed_ground_truth", gercek="secret", f1=99, aciklama="secret")
    ters, _ = sd.tek_adim(dict(reversed(list(v.items()))), dict(reversed(list(temel.items()))), {})
    assert ters == aday
    assert sd.tahminleri_al({a["id"]: {"tahmin": "first", "gercek": "secret", "f1": 99}}) == {a["id"]: "first"}


@pytest.mark.parametrize("asm", ["call sub_0001", "call sub_0002"])
def test_oz_cagri_ve_dongu_aktarilmaz(asm):
    a, b = kayit(1, asm), kayit(2, "jmp sub_0001")
    temel = {a["id"]: "first", b["id"]: "second"}
    aday, say = sd.tek_adim(veri(a, b), temel, {})
    assert aday == temel and say["dongu"] == 2


@pytest.mark.parametrize("ad", ["", "sub_0002", "FUN_000f", "ext_abc", "bad name", "x\nret", "x;injection"])
def test_gecersiz_cagri_tahmini_kullanilmaz(ad):
    a, b = kayit(1, "call sub_0002"), kayit(2)
    temel = {a["id"]: "original"}
    aday, say = sd.tek_adim(veri(a, b), temel, {b["id"]: ad})
    assert aday == temel and say["gecersiz"] == 1


def test_belirsiz_kimlik_v3_ve_yabanci_onbellek_reddedilir():
    a = kayit(1, "call sub_0002")
    temel = {a["id"]: "original"}
    with pytest.raises(ValueError, match="belirsiz"):
        sd.tek_adim(veri(a, kayit(2, kimlik=a["kimlik"])), temel, {})
    with pytest.raises(ValueError, match="v3"):
        sd.tek_adim(veri({k: v for k, v in a.items() if k != "kimlik"}), temel, {})
    with pytest.raises(ValueError, match="dışından"):
        sd.tek_adim(veri(a), temel, {"yabanci-kimlik": "prediction"})
    with pytest.raises(ValueError, match="çelişiyor"):
        sd.tek_adim(veri(a), temel, {a["id"]: "different"})


def test_dogrulama_sabittir_kapsam_yoksa_deney_yoktur():
    a, b = kayit(1, "call sub_0002"), kayit(2)
    v, temel = veri(a, b), {a["id"]: "original"}
    sabit = {a["id"]: {"proje": a["proje"]}}
    sonuc = sd.dogrulama_deneyi(v, temel, {}, sabit)
    assert sonuc["deney"] is None and sonuc["durum"].startswith("not run")
    assert sonuc["kapsam"]["tahmin_eksik"] == 1
    with pytest.raises(ValueError, match="sabit valid300"):
        sd.dogrulama_deneyi(v, {b["id"]: "prediction"}, {}, sabit)
    with pytest.raises(ValueError, match="Doğrulama projesi"):
        sd.dogrulama_deneyi(veri(a, {**b, "proje": "heldout"}), temel, {}, sabit)


def test_kanonik_iki_f1_esli_ga_ve_kusursuz_tavan():
    a, b = kayit(1, "call sub_0002", ad="read_value"), kayit(2, ad="label_never_used")
    v, temel = veri(a, b), {a["id"]: "wrong_name"}
    sonuc = sd.dogrulama_deneyi(v, temel, {b["id"]: "read_value"}, {a["id"]: {"proje": a["proje"]}})
    for ad in ("ad_f1", "oneksiz_f1"):
        assert sonuc["deney"][ad] == {"ortalama": 1, "esli_fark": 1, "esli_yuzde95_ga": (1, 1)}
    sayim = sd.sayim(veri(a), temel)
    assert sayim["mevcut"]["ad_f1"]["kusursuz_onarim_tavani"] == 1
    assert sayim["mevcut"]["ad_f1"]["kusursuz_onarim_azami_artis"] == 1
    with pytest.raises(ValueError, match="kısmi puanlama"):
        sd.sayim(v, temel)


def test_puanlanacak_onbellek_etiketi_ayrica_dogrulanir():
    a = kayit(1)
    sd.etiketleri_dogrula(veri(a), {a["id"]: {"gercek": a["ad"]}})
    for r in ({}, {"gercek": "wrong_target"}):
        with pytest.raises(ValueError, match="hedefleri"):
            sd.etiketleri_dogrula(veri(a), {a["id"]: r})


def test_cli_sadece_toplu_sonuc_ve_salt_okuma(tmp_path, capsys, monkeypatch):
    a = kayit(1, "call sub_0002")
    ham, tahmin = tmp_path / "data.jsonl", tmp_path / "predictions.jsonl"
    ham.write_text(json.dumps(a) + "\n", encoding="utf-8")
    tahmin.write_text(
        json.dumps({"id": a["id"], "gercek": a["ad"], "tahmin": "private_prediction"}) + "\n", encoding="utf-8"
    )
    sabit = {a["id"]: {"proje": a["proje"], "opt": a["opt"], "gercek": a["ad"]}}
    monkeypatch.setattr(dg, "dayanaklar", lambda: (sabit, {"test/1", "eval/1"}))
    monkeypatch.setattr(dg, "manifest_oku", lambda: {"tam_dogrulama_sha256": sd.sha256(ham)})
    once = {p: p.read_bytes() for p in (ham, tahmin)}
    sd.main(["say", "--veri", str(ham), "--tahmin", str(tahmin)])
    cikti = capsys.readouterr().out
    sonuc = json.loads(cikti)
    assert sonuc["n"] == 1 and sonuc["sarmalayici_n"] == 1
    assert sonuc["bolum"] == "valid300"
    assert sonuc["iz"]["girdi_sha256"]["veri"] == {"dosya": ham.name, "sha256": sd.sha256(ham)}
    assert str(tmp_path) not in cikti
    assert sonuc["iz"]["komut"].startswith("python3 sarmalayici_deneyi.py say ")
    assert len(sonuc["iz"]["tree"]) == 40
    assert {p: p.read_bytes() for p in once} == once
    assert all(s not in cikti for s in (a["id"], a["asm"], a["ad"], "private_prediction"))
    ham.write_text(json.dumps(a) + "\n" + json.dumps(a) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="yinelenen") as hata:
        sd.jsonl_oku([ham])
    assert a["id"] not in str(hata.value)


@pytest.mark.parametrize("kimlik", ["test/1", "eval/1", "yabanci/1"])
def test_say_guvenli_adli_test_girdisini_reddeder(tmp_path, monkeypatch, kimlik):
    sabit = {"v/1": {"proje": "v", "opt": "-O2", "gercek": "oku"}}
    monkeypatch.setattr(dg, "dayanaklar", lambda: (sabit, {"test/1", "eval/1"}))
    monkeypatch.setattr(dg, "manifest_oku", lambda: {"tam_dogrulama_sha256": "0" * 64})
    yol = tmp_path / "validation.jsonl"
    yol.write_text(json.dumps(kayit(1, id=kimlik)) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit) as hata:
        sd.main(["say", "--veri", str(yol)])
    assert hata.value.code == 2


def test_dogrulama_deneyi_korumasi_aynen_kaldi():
    kaynak = inspect.getsource(sd.dogrulama_deneyi)
    assert hashlib.sha256(kaynak.encode()).hexdigest() == "37d83218a0e6acab22267e5184018c51976ccd6c8669288e91885e1e261f909d"
