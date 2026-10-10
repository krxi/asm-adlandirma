"""lora/hazirla.py (v3 düzeni) ve lora/hazirla_olcek.py (v4 düzeni): sohbet biçimi ve proje bazlı bölme."""

import hashlib, json, os, subprocess, sys
from collections import Counter
from pathlib import Path

import pytest

import hazirla as h
import hazirla_olcek as ho
import hazirla_sonraki as hs
from types import SimpleNamespace

KOK = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def temiz_durum(monkeypatch):
    # hazirla modül düzeyinde TOK/ONEK tutuyor; testler birbirine sızmasın.
    monkeypatch.setattr(h, "TOK", None)
    monkeypatch.setattr(h, "ONEK", {})


class KarakterTok:
    """Her karakter bir token: token tavanı mantığını transformers'sız sınamak için."""

    def encode(self, s):
        return list(s)


def satir(**alan):
    r = {
        "id": "p/a.c:-O0:p_oku",
        "proje": "p",
        "opt": "-O0",
        "ad": "p_oku",
        "sizinti": False,
        "asm": "push\trbp\nret",
        "baglam": "",
        "baglam_derin": "",
    }
    r.update(alan)
    return r


def oku_jsonl(yol):
    return [json.loads(l) for l in Path(yol).open() if l.strip()]


# --- birim -------------------------------------------------------------------------------------


def test_kes():
    assert h.kes("a\nb\nc", 5) == "a\nb\nc"
    assert h.kes("a\nb\nc", 2) == "a\nb\n; ... kesildi"


def test_oneksiz(monkeypatch):
    monkeypatch.setattr(h, "ONEK", {"mbedtls": {"mbedtls", "mbedtls_mpi"}, "sqlite": {"sqlite3"}})
    assert h.oneksiz(satir(proje="mbedtls", ad="mbedtls_mpi_core_read")) == "core_read"  # en uzun önek önce
    assert h.oneksiz(satir(proje="sqlite", ad="sqlite3VdbeMemSet")) == "VdbeMemSet"
    assert h.oneksiz(satir(proje="mbedtls", ad="mbedtls")) == "mbedtls"  # ad boş kalmaz
    assert h.oneksiz(satir(proje="baska", ad="mbedtls_x")) == "mbedtls_x"


def test_baglam_metni_kipleri():
    r = satir(baglam="ozet", baglam_derin="derin")
    assert h.baglam_metni(r, "yok") == ""
    assert h.baglam_metni(r, "ozet") == "ozet"
    assert h.baglam_metni(r, "derin") == "derin"
    assert h.baglam_metni(satir(baglam="ozet"), "derin") == "ozet"  # derin yoksa özete düşer


def test_girdi_baglam_basligi():
    r = satir(baglam="sub_0001 (3 komut): çağırır free")
    assert h.girdi(r, "yok", 200) == r["asm"]
    assert h.girdi(r, "ozet", 200) == r["asm"] + h.BAGLAM_BASLIK + r["baglam"]
    assert h.girdi(satir(), "ozet", 200) == satir()["asm"]  # bağlamsız satırda başlık yok


def test_girdi_token_tavani_once_baglami_feda_eder(monkeypatch):
    monkeypatch.setattr(h, "TOK", KarakterTok())
    asm = "\n".join(f"mov\teax, {i}" for i in range(10))
    baglam = "\n".join(f"sub_{i:04x} (5 komut): çağırır malloc" for i in range(20))
    r = satir(asm=asm, baglam=baglam)
    tavan = len(asm) + 200
    sonuc = h.girdi(r, "ozet", 200, tavan)
    assert sonuc.startswith(asm + h.BAGLAM_BASLIK)  # asm bütün kalır
    assert len(sonuc) <= tavan
    assert sonuc.endswith("; ... bağlam kesildi")
    # Asm tek başına tavanı aşıyorsa bağlam tamamen gider, asm kısalır.
    sonuc = h.girdi(r, "ozet", 200, 40)
    assert h.BAGLAM_BASLIK not in sonuc and len(sonuc) <= 40


def test_girdi_tek_satir_baglamda_takilmaz(monkeypatch):
    monkeypatch.setattr(h, "TOK", KarakterTok())
    r = satir(asm="ret", baglam="x" * 50)
    assert len(h.girdi(r, "ozet", 200, 30)) <= 30


def test_mesaj_hedefi_ve_sistem_istemi():
    r = satir(baglam="b")
    m = h.mesaj(r, 200)
    roller = [x["role"] for x in m["messages"]]
    assert roller == ["system", "user", "assistant"]
    assert m["messages"][0]["content"] == h.SISTEM
    assert json.loads(m["messages"][2]["content"]) == {"ad": "p_oku"}
    assert (m["id"], m["opt"], m["asm"], m["baglam"]) == (r["id"], "-O0", r["asm"], "b")

    m = h.mesaj(r, 200, aciklamalar={r["id"]: "Dosyayı okur."})
    assert m["messages"][0]["content"] == h.SISTEM_ACIKLAMA
    assert json.loads(m["messages"][2]["content"]) == {"ad": "p_oku", "aciklama": "Dosyayı okur."}
    assert h.SISTEM_ACIKLAMA.endswith('"aciklama": "tek cümle Türkçe"}')


def test_mesaj_ham_ad(monkeypatch):
    monkeypatch.setattr(h, "ONEK", {"p": {"p"}})
    assert json.loads(h.mesaj(satir(), 200)["messages"][2]["content"])["ad"] == "oku"
    assert json.loads(h.mesaj(satir(), 200, ham=True)["messages"][2]["content"])["ad"] == "p_oku"


def test_tekil_ayni_asmyi_bir_kez_alir():
    a, b, c = satir(id="1"), satir(id="2"), satir(id="3", asm="ret")
    assert [r["id"] for r in h.tekil([a, b, c])] == ["1", "3"]


def test_oku_ve_aciklamalar(ornek_kok):
    projeler = h.oku(ornek_kok / "veri")
    assert set(projeler) == {"cyaml", "sajs", "tomlc17", "picomatch"}
    aciklamalar = h.aciklamalari_oku(ornek_kok / "veri", ["cyaml", "sajs", "yok"])
    assert aciklamalar and all(v.endswith("örnek açıklama.") for v in aciklamalar.values())


def test_onekler_esik():
    adlar = [f"cyaml_f{i}" for i in range(6)] + ["load", "save"]  # 6/8 ≥ %30, ≥5
    az = [f"mu_f{i}" for i in range(4)] + [f"g{i}" for i in range(2)]  # 4 < 5
    seyrek = [f"sj_f{i}" for i in range(5)] + [f"h{i}" for i in range(20)]  # 5/25 < %30
    satirlar = (
        [{"proje": "cyaml", "ad": a} for a in adlar]
        + [{"proje": "mu", "ad": a} for a in az]
        + [{"proje": "sj", "ad": a} for a in seyrek]
    )
    assert ho.onekler(satirlar) == {"cyaml": {"cyaml"}}


# --- uçtan uca (alt süreç, örnek veri) ---------------------------------------------------------


def calistir(betik, *arg, cwd):
    return subprocess.run([sys.executable, str(KOK / betik), *map(str, arg)], cwd=cwd, capture_output=True, text=True)


def test_hazirla_uctan_uca(ornek_kok):
    cikti = ornek_kok / "lora" / "veri"
    s = calistir(
        "lora/hazirla.py",
        "--veri",
        "veri",
        "--cikti",
        cikti,
        "--token-tavan",
        0,
        "--baglam",
        "ozet",
        "--onek-at",
        "--aciklama",
        "--test-dosyasi",
        "yok.jsonl",
        cwd=ornek_kok,
    )
    assert s.returncode == 0, s.stderr
    tr, va, te = (oku_jsonl(cikti / f"{ad}.jsonl") for ad in ("train", "valid", "test"))
    assert tr and va and te
    proje = lambda rs: {r["id"].split("/")[0] for r in rs}
    assert proje(tr) | proje(va) <= {"cyaml", "sajs"}
    assert proje(te) == {"tomlc17", "picomatch"}
    # Eğitimde tekrar eden asm yok; test hedefi hep gerçek ad (büyük modellerle aynı puanlama).
    assert len({r["asm"] for r in tr + va}) == len(tr + va)
    asil = {r["id"]: r for p in (ornek_kok / "veri" / "test").glob("*.jsonl") for r in oku_jsonl(p)}
    for r in te:
        assert json.loads(r["messages"][2]["content"])["ad"] == asil[r["id"]]["ad"]
    # --aciklama: açıklaması olan satırların hedefinde açıklama var, istem buna göre.
    aciklamali = [r for r in tr + va if "aciklama" in json.loads(r["messages"][2]["content"])]
    assert aciklamali
    assert all(r["messages"][0]["content"] == h.SISTEM_ACIKLAMA for r in aciklamali)
    # --baglam ozet: bağlamı olan satırların girdisinde başlık var.
    assert any(h.BAGLAM_BASLIK in r["messages"][1]["content"] for r in tr + va + te)


def test_hazirla_sizintida_durur(ornek_kok):
    s = calistir(
        "lora/hazirla.py", "--veri", "veri", "--egitim", "cyaml", "--test", "cyaml", "--token-tavan", 0, cwd=ornek_kok
    )
    assert s.returncode != 0 and "sızıntı" in s.stderr


def test_hazirla_test_dosyasiyla_sinirlar(ornek_kok):
    secili = oku_jsonl(ornek_kok / "veri" / "test" / "tomlc17.jsonl")[:3]
    (ornek_kok / "secili.jsonl").write_text("".join(json.dumps(r) + "\n" for r in secili))
    s = calistir(
        "lora/hazirla.py",
        "--veri",
        "veri",
        "--cikti",
        "c",
        "--token-tavan",
        0,
        "--test-dosyasi",
        "secili.jsonl",
        cwd=ornek_kok,
    )
    assert s.returncode == 0, s.stderr
    assert {r["id"] for r in oku_jsonl(ornek_kok / "c" / "test.jsonl")} == {r["id"] for r in secili}


def test_hazirla_olcek_uctan_uca(ornek_kok):
    cikti = ornek_kok / "lora" / "veri-olcek"
    s = calistir(
        "lora/hazirla_olcek.py",
        "--veri",
        "veri/bin/olcek",
        "--cikti",
        cikti,
        "--token-tavan",
        0,
        "--proje-tavan",
        5,
        cwd=ornek_kok,
    )
    assert s.returncode == 0, s.stderr
    ozet = json.loads((cikti / "ozet.json").read_text())
    tr = oku_jsonl(cikti / "train.jsonl")
    assert max(Counter(r["id"].split("/")[0] for r in tr).values()) <= 5
    assert ozet["train"]["satir"] == len(tr)
    assert {r["id"].split("/")[0] for r in oku_jsonl(cikti / "valid.jsonl")} == {"mu_json_x"}
    assert {r["id"].split("/")[0] for r in oku_jsonl(cikti / "test.jsonl")} == {"tomlc17", "picomatch"}
    # Aynı tohumla iki koşu birebir aynı dosyayı üretir.
    s2 = calistir(
        "lora/hazirla_olcek.py",
        "--veri",
        "veri/bin/olcek",
        "--cikti",
        ornek_kok / "iki",
        "--token-tavan",
        0,
        "--proje-tavan",
        5,
        cwd=ornek_kok,
    )
    assert s2.returncode == 0, s2.stderr
    assert (cikti / "train.jsonl").read_bytes() == (ornek_kok / "iki" / "train.jsonl").read_bytes()


# --- önek kuralı ve test hedefi ----------------------------------------------------------------


@pytest.mark.parametrize(
    "onek, proje, beklenen",
    [
        ("cyaml", "cyaml", True),
        ("mu", "mu_json_x", True),
        ("sqlite3", "sqlite", True),
        ("png", "libpng", True),
        ("pm", "picomatch", True),
        ("toml", "tomlc17", True),
        ("eat", "sajs", False),
        ("emit", "picomatch", False),
        ("get", "zlib", False),
    ],
)
def test_proje_ile_ilgili(onek, proje, beklenen):
    assert ho.proje_ile_ilgili(onek, proje) is beklenen


def test_onekler_proje_kurali_fiilleri_atmaz():
    satirlar = (
        [{"proje": "sajs", "ad": f"eat_x{i}"} for i in range(6)]
        + [{"proje": "sajs", "ad": "parse"}]
        + [{"proje": "cyaml", "ad": f"cyaml_f{i}"} for i in range(6)]
    )
    assert ho.onekler(satirlar) == {"sajs": {"eat"}, "cyaml": {"cyaml"}}  # varsayılan: eski davranış
    assert ho.onekler(satirlar, "proje") == {"cyaml": {"cyaml"}}


def sentetik_olcek(kok):
    """sajs (eğitim, 'eat_' fiili) + cyaml (test, gerçek önek) ile küçük v4 ağacı."""

    def r(proje, ad, i):
        return {
            "id": f"{proje}/a.c:-O0:{ad}",
            "proje": proje,
            "opt": "-O0",
            "ad": ad,
            "sizinti": False,
            "asm": f"mov\teax, {i}\nret",
            "baglam": "",
            "baglam_derin": "",
        }

    roller = {
        "egitim": [r("sajs", f"eat_x{i}", i) for i in range(6)] + [r("sajs", "parse", 99)],
        "dogrulama": [r("mu_json_x", f"mu_f{i}", 100 + i) for i in range(6)],
        "test": [r("cyaml", f"cyaml_f{i}", 200 + i) for i in range(6)],
    }
    d = kok / "veri" / "bin" / "olcek"
    d.mkdir(parents=True)
    for rol, satirlar in roller.items():
        (d / f"{rol}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in satirlar))


def hedefler(yol):
    return sorted(json.loads(r["messages"][2]["content"])["ad"] for r in oku_jsonl(yol))


@pytest.mark.parametrize(
    "bayraklar, egitim, test, ozet_test",
    [
        ([], ["parse"] + [f"x{i}" for i in range(6)], [f"f{i}" for i in range(6)], "oneksiz"),
        (["--test-ham-ad"], ["parse"] + [f"x{i}" for i in range(6)], [f"cyaml_f{i}" for i in range(6)], "gercek"),
        (
            ["--onek-kurali", "proje"],
            ["parse"] + [f"eat_x{i}" for i in range(6)],
            [f"f{i}" for i in range(6)],
            "oneksiz",
        ),
        (["--ham-ad"], ["parse"] + [f"eat_x{i}" for i in range(6)], [f"cyaml_f{i}" for i in range(6)], "gercek"),
    ],
)
def test_hazirla_olcek_hedef_bayraklari(tmp_path, bayraklar, egitim, test, ozet_test):
    sentetik_olcek(tmp_path)
    s = calistir(
        "lora/hazirla_olcek.py",
        "--veri",
        "veri/bin/olcek",
        "--cikti",
        "c",
        "--token-tavan",
        0,
        *bayraklar,
        cwd=tmp_path,
    )
    assert s.returncode == 0, s.stderr
    assert hedefler(tmp_path / "c" / "train.jsonl") == sorted(egitim)
    assert hedefler(tmp_path / "c" / "test.jsonl") == test
    assert json.loads((tmp_path / "c" / "ozet.json").read_text())["test_hedefi"] == ozet_test


class SohbetTok(KarakterTok):
    def decode(self, ids):
        return "".join(ids)

    def apply_chat_template(self, messages, **kwargs):
        assert kwargs.get("return_dict") is False
        return self.encode("".join(m["content"] for m in messages) + "!" * 20)


def test_v5_hedef_sirasi_ve_ham_ad(monkeypatch):
    monkeypatch.setattr(h, "TOK", SohbetTok())
    monkeypatch.setattr(h, "ONEK", {"p": {"p"}})
    a = SimpleNamespace(satir_tavan=200, token_tavan=2500)
    r = satir(dosya="a.c")
    for ham, ad in ((False, "oku"), (True, "p_oku")):
        s = hs.satir_v5(r, "Okur.", "Reads.", a, ham)
        assert s["messages"][0]["content"] == h.SISTEM_V5
        hedef = json.loads(s["messages"][2]["content"])
        assert list(hedef) == ["aciklama_en", "ad", "aciklama"]
        assert hedef["ad"] == ad
        assert s["hedef_tur"] == "tam"
    for tr, en in ((None, None), ("Okur.", None), (None, "Reads.")):
        s = hs.satir_v5(r, tr, en, a)
        assert json.loads(s["messages"][2]["content"]) == {"ad": "oku"}
        assert s["hedef_tur"] == "ad"


@pytest.mark.parametrize("ad", ["MAIN", "init", "foo", "bar", "baz", "helper", "test", "f123", "Test_x", "SUB_0001"])
def test_v5_jenerik(ad):
    assert hs.JENERIK.fullmatch(ad)


@pytest.mark.parametrize("ad", ["main_loop", "initialize", "foo_reader", "f12x", "p_test", "testify"])
def test_v5_anlamli_ad(ad):
    assert not hs.JENERIK.fullmatch(ad)


def test_v5_kapsam_tavan_ve_belirlenimcilik():
    rs = [{"kaynak": f"{p}/a.c:oku{i}", "satir": {"id": f"{p}/{i}/{o}", "proje": p, "opt": o}}
          for p in ("a", "b") for i in range(10) for o in hs.OPT_AGIRLIK]
    sec, ozet = hs.egitim_sec_v5(rs, hedef=30, proje_tavan=15)
    assert len(sec) == 30
    assert {r["kaynak"] for r in sec} == {r["kaynak"] for r in rs}
    assert max(Counter(r["satir"]["proje"] for r in sec).values()) == 15
    for key in {r["kaynak"] for r in sec}:
        opts = [r["satir"]["opt"] for r in sec if r["kaynak"] == key]
        assert len(opts) == len(set(opts)) <= 2
    assert (sec, ozet) == hs.egitim_sec_v5(list(reversed(rs)), hedef=30, proje_tavan=15)
    kapsam, ozet = hs.egitim_sec_v5(rs, proje_tavan=5)
    assert len(kapsam) == 20 and ozet["tavan_asan_projeler"] == {"a": 10, "b": 10}
    tavan, ozet = hs.egitim_sec_v5(rs, proje_tavan=5, kapsam_onceligi=False)
    assert len(tavan) == 10 and ozet["tavandan_atilan_fonksiyon"] == 10


def test_v5_opt_agirligi():
    rs = [{"kaynak": f"p/{i}", "satir": {"id": f"{i}/{o}", "proje": "p", "opt": o}}
          for i in range(3000) for o in hs.OPT_AGIRLIK]
    sec, _ = hs.egitim_sec_v5(rs, hedef=3000, proje_tavan=0)
    say = Counter(r["satir"]["opt"] for r in sec)
    assert say["-O2"] > say["-O0"] and say["-O3"] > say["-O0"]


def test_v5_tam_akis(tmp_path, monkeypatch):
    monkeypatch.setattr(hs, "tokenizer_v5", lambda a: (SohbetTok(), {"kullanilan": "test"}))
    monkeypatch.setattr(hs, "OZET_ONEK", {})
    d = tmp_path / "veri" / "bin" / "olcek"
    d.mkdir(parents=True)
    train = [satir(id=f"p/{ad}/{opt}", dosya="a.c", ad=ad, opt=opt)
             for ad in ["main", "Test_x", "oku", "yaz"] for opt in ("-O0", "-O2")]
    # Aynı asm'ye sahip farklı kaynak fonksiyonlar da kapsamda kalmalı.
    valid = [satir(id=f"v/{i}", proje=f"v{i % 3}", dosya="a.c") for i in range(310)]
    test = [satir(id=f"t/{i}", proje="p", dosya="a.c", ad=f"p_oku{i}") for i in range(6)]
    for ad, rs in (("egitim", train), ("dogrulama", valid), ("test", test)):
        (d / f"{ad}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rs))
    tr, en = tmp_path / "tr.jsonl", tmp_path / "en.jsonl"
    tr.write_text(json.dumps({"anahtar": "p/a.c:oku", "aciklama": "x" * 3000}) + "\n")
    en.write_text(json.dumps({"anahtar": "p/a.c:oku", "aciklama_en": "Reads."}) + "\n")
    ev, ids = tmp_path / "eval.jsonl", tmp_path / "ids.txt"
    ev.write_text(json.dumps(test[0]) + "\n")
    ids.write_text("t/4\nt/1\n")
    a = SimpleNamespace(veri=d, aciklama=tr, aciklama_detay=en, eval115=ev, test_idler=ids,
                        token_tavan=2500, max_uzunluk=3072, satir_tavan=200, tohum=7,
                        proje_tavan=1500, hedef_satir=95000, kapsam_onceligi="kapsam", cikti=tmp_path / "c")
    hs.hazirla_v5(a)
    ilk = {p.name: p.read_bytes() for p in a.cikti.iterdir()}
    hs.hazirla_v5(a)
    assert ilk == {p.name: p.read_bytes() for p in a.cikti.iterdir()}
    o = json.loads((a.cikti / "ozet.json").read_text())
    assert o["filtreler"]["train"]["jenerik"] == 4
    assert o["filtreler"]["train"]["uzunluktan_atilan"] == 2
    assert o["filtreler"]["train"]["uzunluktan_kaybolan_fonksiyon"] == 1
    assert o["train"]["satir"] == 2 and o["train"]["uzunluk_asan"] == 0
    assert o["valid"]["satir"] == 310 and o["valid_300"]["satir"] == 300
    assert Counter(r["proje"] for r in oku_jsonl(a.cikti / "valid_300.jsonl")) == {"v0": 100, "v1": 100, "v2": 100}
    assert [r["id"] for r in oku_jsonl(a.cikti / "test_sabit.jsonl")] == ["t/4", "t/1"]
    for ad in ("test", "test_sabit", "eval115"):
        for r in oku_jsonl(a.cikti / f"{ad}.jsonl"):
            assert json.loads(r["messages"][2]["content"])["ad"] == r["gercek_ad"]
    ids.write_text("yok\n")
    with pytest.raises(ValueError, match="eksik id"):
        hs.hazirla_v5(a)


def test_v5_tek_satir_token_tavani(monkeypatch):
    monkeypatch.setattr(h, "TOK", SohbetTok())
    a = SimpleNamespace(satir_tavan=200, token_tavan=20)
    s = hs.satir_v5(satir(asm="x" * 100), None, None, a)
    assert len(s["messages"][1]["content"]) == 20


def test_v6_v5_yolunu_degistirmez_ve_eksikte_taban_girdiyi_korur(monkeypatch):
    monkeypatch.setattr(h, "TOK", SohbetTok())
    monkeypatch.setattr(h, "ONEK", {"p": {"p"}})
    a = SimpleNamespace(satir_tavan=200, token_tavan=2500, max_uzunluk=3072,
                        decompile_alt_token=20)
    r = satir(dosya="a.c", baglam="sub_0001: bir şey yapar")
    v5_once = hs.satir_v5(r, "Okur.", "Reads.", a)
    v5_sonra = hs.satir_v5(r, "Okur.", "Reads.", a)
    assert v5_once == v5_sonra
    v5_bayt = (json.dumps(v5_once, ensure_ascii=False) + "\n").encode()
    assert hashlib.sha256(v5_bayt).hexdigest() == \
        "5d180910c3d4d75d4cdd5849e33aa549b6184ccb0bd9a568361f0232639e668c"
    v6 = hs.satir_v6(r, "Okur.", "Reads.", a, None)
    assert v6["messages"][1]["content"] == v5_once["messages"][1]["content"]
    assert not v6["decompile_var"] and v6["decompile_yok_neden"] == "eksik"
    assert v6["messages"][0]["content"] == h.SISTEM_V6


def test_v6_decompile_satir_bazinda_sondan_kirpilir(monkeypatch):
    monkeypatch.setattr(h, "TOK", SohbetTok())
    a = SimpleNamespace(satir_tavan=200, token_tavan=2500, max_uzunluk=0,
                        decompile_alt_token=20)
    r = satir(dosya="a.c", ad="hedef")
    taban = hs.satir_v5(r, None, None, a)
    taban["messages"][0]["content"] = h.SISTEM_V6
    a.max_uzunluk = hs._toplam_token(taban) + len(h.DECOMPILE_BASLIK) + 95
    decompile = "\n".join(f"int local_{i} = param_{i};" for i in range(20))
    s = hs.satir_v6(r, None, None, a, {"decompile": decompile, "sizinti": False})
    assert s["decompile_var"] and s["decompile_kirpildi"]
    assert s["messages"][1]["content"].endswith(hs.DECOMPILE_KIRPMA)
    assert "local_0" in s["messages"][1]["content"]
    assert "local_19" not in s["messages"][1]["content"]
    assert hs._toplam_token(s) <= a.max_uzunluk


@pytest.mark.parametrize("metin", [
    "int p_oku(int x) { return x; }",
    "int _p_oku(int x) { return x; }",
    "int oku(int x) { return x; }",
    "int _oku(int x) { return x; }",
])
def test_v6_anonim_decompile_hedef_ad_sizintisi_atilir(monkeypatch, metin):
    monkeypatch.setattr(h, "TOK", SohbetTok())
    monkeypatch.setattr(h, "ONEK", {"p": {"p"}})
    a = SimpleNamespace(satir_tavan=200, token_tavan=2500, max_uzunluk=3072,
                        decompile_alt_token=20)
    s = hs.satir_v6(satir(dosya="a.c"), None, None, a,
                    {"decompile": metin, "sizinti": True})
    assert not s["decompile_var"] and s["decompile_sizinti"]
    assert s["decompile_ham_sizinti"]
    assert s["decompile_yok_neden"] == "hedef_ad_sizintisi"
    assert h.DECOMPILE_BASLIK not in s["messages"][1]["content"]


def test_v6_sizinti_tam_tanimlayici_eslesmesidir(monkeypatch):
    monkeypatch.setattr(h, "TOK", SohbetTok())
    monkeypatch.setattr(h, "ONEK", {"p": {"p"}})
    a = SimpleNamespace(satir_tavan=200, token_tavan=2500, max_uzunluk=3072,
                        decompile_alt_token=20)
    s = hs.satir_v6(satir(dosya="a.c"), None, None, a,
                    {"decompile": "int p_okuyucu(void) { return 1; }", "sizinti": True})
    assert s["decompile_var"] and not s["decompile_sizinti"]
    assert s["decompile_ham_sizinti"]


def test_v6_butce_alt_sinirinda_decompile_konmaz(monkeypatch):
    monkeypatch.setattr(h, "TOK", SohbetTok())
    a = SimpleNamespace(satir_tavan=200, token_tavan=2500, max_uzunluk=0,
                        decompile_alt_token=200)
    r = satir(dosya="a.c", ad="hedef")
    taban = hs.satir_v5(r, None, None, a)
    taban["messages"][0]["content"] = h.SISTEM_V6
    a.max_uzunluk = hs._toplam_token(taban) + len(h.DECOMPILE_BASLIK) + 100
    s = hs.satir_v6(r, None, None, a,
                    {"decompile": "\n".join("int x = 1;" for _ in range(100)), "sizinti": False})
    assert not s["decompile_var"] and s["decompile_yok_neden"] == "butce_alt_sinir"


def test_v6_decompile_dizini_yalniz_tamamlanmis_jsonl_okur(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    (d / "p.jsonl").write_text(json.dumps({"id": "p/1", "decompile": "int x;", "sizinti": False}) + "\n")
    (d / "yarim.ara").write_text(json.dumps({"id": "q/1", "decompile": "int y;", "sizinti": False}) + "\n")
    kayitlar, projeler, yinelenen = hs.decompile_dizinlerini_oku([d])
    assert set(kayitlar) == {"p/1"}
    assert projeler == {"p"} and yinelenen == 0


def test_v6_tam_zorunlu_eksik_projeyi_reddeder():
    assert hs.tamligi_denetle({"a", "b"}, {"a"}) == ["b"]
    with pytest.raises(ValueError, match=r"--tam-zorunlu: 1 proje"):
        hs.tamligi_denetle({"a", "b"}, {"a"}, True)


def test_v5_onek_esitligi_hash_tohumundan_bagimsiz():
    kod = (
        "import hazirla_olcek as ho; "
        "rs=[{'proje':'tinymaix','ad':f'{p}_f{i}'} for p in ('tm','tml') for i in range(5)]; "
        "print(ho.onekler(rs, 'proje', belirlenimci=True))"
    )
    for tohum in ("1", "2", "7", "42"):
        env = {**os.environ, "PYTHONHASHSEED": tohum, "PYTHONPATH": str(KOK / "lora")}
        assert subprocess.check_output([sys.executable, "-c", kod], env=env, text=True).strip() == "{'tinymaix': {'tm'}}"
