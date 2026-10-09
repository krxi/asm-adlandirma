"""lora/hazirla.py (v3 düzeni) ve lora/hazirla_olcek.py (v4 düzeni): sohbet biçimi ve proje bazlı bölme."""
import json, subprocess, sys
from collections import Counter
from pathlib import Path

import pytest

import hazirla as h
import hazirla_olcek as ho

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
    r = {"id": "p/a.c:-O0:p_oku", "proje": "p", "opt": "-O0", "ad": "p_oku", "sizinti": False,
         "asm": "push\trbp\nret", "baglam": "", "baglam_derin": ""}
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
    assert h.oneksiz(satir(proje="mbedtls", ad="mbedtls_mpi_core_read")) == "core_read"   # en uzun önek önce
    assert h.oneksiz(satir(proje="sqlite", ad="sqlite3VdbeMemSet")) == "VdbeMemSet"
    assert h.oneksiz(satir(proje="mbedtls", ad="mbedtls")) == "mbedtls"                   # ad boş kalmaz
    assert h.oneksiz(satir(proje="baska", ad="mbedtls_x")) == "mbedtls_x"


def test_baglam_metni_kipleri():
    r = satir(baglam="ozet", baglam_derin="derin")
    assert h.baglam_metni(r, "yok") == ""
    assert h.baglam_metni(r, "ozet") == "ozet"
    assert h.baglam_metni(r, "derin") == "derin"
    assert h.baglam_metni(satir(baglam="ozet"), "derin") == "ozet"   # derin yoksa özete düşer


def test_girdi_baglam_basligi():
    r = satir(baglam="sub_0001 (3 komut): çağırır free")
    assert h.girdi(r, "yok", 200) == r["asm"]
    assert h.girdi(r, "ozet", 200) == r["asm"] + h.BAGLAM_BASLIK + r["baglam"]
    assert h.girdi(satir(), "ozet", 200) == satir()["asm"]          # bağlamsız satırda başlık yok


def test_girdi_token_tavani_once_baglami_feda_eder(monkeypatch):
    monkeypatch.setattr(h, "TOK", KarakterTok())
    asm = "\n".join(f"mov\teax, {i}" for i in range(10))
    baglam = "\n".join(f"sub_{i:04x} (5 komut): çağırır malloc" for i in range(20))
    r = satir(asm=asm, baglam=baglam)
    tavan = len(asm) + 200
    sonuc = h.girdi(r, "ozet", 200, tavan)
    assert sonuc.startswith(asm + h.BAGLAM_BASLIK)                    # asm bütün kalır
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
    adlar = [f"cyaml_f{i}" for i in range(6)] + ["load", "save"]          # 6/8 ≥ %30, ≥5
    az = [f"mu_f{i}" for i in range(4)] + [f"g{i}" for i in range(2)]   # 4 < 5
    seyrek = [f"sj_f{i}" for i in range(5)] + [f"h{i}" for i in range(20)]  # 5/25 < %30
    satirlar = ([{"proje": "cyaml", "ad": a} for a in adlar] + [{"proje": "mu", "ad": a} for a in az]
                + [{"proje": "sj", "ad": a} for a in seyrek])
    assert ho.onekler(satirlar) == {"cyaml": {"cyaml"}}


# --- uçtan uca (alt süreç, örnek veri) ---------------------------------------------------------

def calistir(betik, *arg, cwd):
    return subprocess.run([sys.executable, str(KOK / betik), *map(str, arg)], cwd=cwd,
                          capture_output=True, text=True)


def test_hazirla_uctan_uca(ornek_kok):
    cikti = ornek_kok / "lora" / "veri"
    s = calistir("lora/hazirla.py", "--veri", "veri", "--cikti", cikti, "--token-tavan", 0,
                 "--baglam", "ozet", "--onek-at", "--aciklama", "--test-dosyasi", "yok.jsonl", cwd=ornek_kok)
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
    s = calistir("lora/hazirla.py", "--veri", "veri", "--egitim", "cyaml", "--test", "cyaml",
                 "--token-tavan", 0, cwd=ornek_kok)
    assert s.returncode != 0 and "sızıntı" in s.stderr


def test_hazirla_test_dosyasiyla_sinirlar(ornek_kok):
    secili = oku_jsonl(ornek_kok / "veri" / "test" / "tomlc17.jsonl")[:3]
    (ornek_kok / "secili.jsonl").write_text("".join(json.dumps(r) + "\n" for r in secili))
    s = calistir("lora/hazirla.py", "--veri", "veri", "--cikti", "c", "--token-tavan", 0,
                 "--test-dosyasi", "secili.jsonl", cwd=ornek_kok)
    assert s.returncode == 0, s.stderr
    assert {r["id"] for r in oku_jsonl(ornek_kok / "c" / "test.jsonl")} == {r["id"] for r in secili}


def test_hazirla_olcek_uctan_uca(ornek_kok):
    cikti = ornek_kok / "lora" / "veri-olcek"
    s = calistir("lora/hazirla_olcek.py", "--veri", "veri/bin/olcek", "--cikti", cikti,
                 "--token-tavan", 0, "--proje-tavan", 5, cwd=ornek_kok)
    assert s.returncode == 0, s.stderr
    ozet = json.loads((cikti / "ozet.json").read_text())
    tr = oku_jsonl(cikti / "train.jsonl")
    assert max(Counter(r["id"].split("/")[0] for r in tr).values()) <= 5
    assert ozet["train"]["satir"] == len(tr)
    assert {r["id"].split("/")[0] for r in oku_jsonl(cikti / "valid.jsonl")} == {"mu_json_x"}
    assert {r["id"].split("/")[0] for r in oku_jsonl(cikti / "test.jsonl")} == {"tomlc17", "picomatch"}
    # Aynı tohumla iki koşu birebir aynı dosyayı üretir.
    s2 = calistir("lora/hazirla_olcek.py", "--veri", "veri/bin/olcek", "--cikti", ornek_kok / "iki",
                  "--token-tavan", 0, "--proje-tavan", 5, cwd=ornek_kok)
    assert s2.returncode == 0, s2.stderr
    assert (cikti / "train.jsonl").read_bytes() == (ornek_kok / "iki" / "train.jsonl").read_bytes()


# --- önek kuralı ve test hedefi ----------------------------------------------------------------

@pytest.mark.parametrize("onek, proje, beklenen", [
    ("cyaml", "cyaml", True), ("mu", "mu_json_x", True), ("sqlite3", "sqlite", True),
    ("png", "libpng", True), ("pm", "picomatch", True), ("toml", "tomlc17", True),
    ("eat", "sajs", False), ("emit", "picomatch", False), ("get", "zlib", False),
])
def test_proje_ile_ilgili(onek, proje, beklenen):
    assert ho.proje_ile_ilgili(onek, proje) is beklenen


def test_onekler_proje_kurali_fiilleri_atmaz():
    satirlar = ([{"proje": "sajs", "ad": f"eat_x{i}"} for i in range(6)] + [{"proje": "sajs", "ad": "parse"}]
                + [{"proje": "cyaml", "ad": f"cyaml_f{i}"} for i in range(6)])
    assert ho.onekler(satirlar) == {"sajs": {"eat"}, "cyaml": {"cyaml"}}          # varsayılan: eski davranış
    assert ho.onekler(satirlar, "proje") == {"cyaml": {"cyaml"}}


def sentetik_olcek(kok):
    """sajs (eğitim, 'eat_' fiili) + cyaml (test, gerçek önek) ile küçük v4 ağacı."""
    def r(proje, ad, i):
        return {"id": f"{proje}/a.c:-O0:{ad}", "proje": proje, "opt": "-O0", "ad": ad, "sizinti": False,
                "asm": f"mov\teax, {i}\nret", "baglam": "", "baglam_derin": ""}
    roller = {"egitim": [r("sajs", f"eat_x{i}", i) for i in range(6)] + [r("sajs", "parse", 99)],
              "dogrulama": [r("mu_json_x", f"mu_f{i}", 100 + i) for i in range(6)],
              "test": [r("cyaml", f"cyaml_f{i}", 200 + i) for i in range(6)]}
    d = kok / "veri" / "bin" / "olcek"
    d.mkdir(parents=True)
    for rol, satirlar in roller.items():
        (d / f"{rol}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in satirlar))


def hedefler(yol):
    return sorted(json.loads(r["messages"][2]["content"])["ad"] for r in oku_jsonl(yol))


@pytest.mark.parametrize("bayraklar, egitim, test, ozet_test", [
    ([], ["parse"] + [f"x{i}" for i in range(6)], [f"f{i}" for i in range(6)], "oneksiz"),
    (["--test-ham-ad"], ["parse"] + [f"x{i}" for i in range(6)], [f"cyaml_f{i}" for i in range(6)], "gercek"),
    (["--onek-kurali", "proje"], ["parse"] + [f"eat_x{i}" for i in range(6)], [f"f{i}" for i in range(6)], "oneksiz"),
    (["--ham-ad"], ["parse"] + [f"eat_x{i}" for i in range(6)], [f"cyaml_f{i}" for i in range(6)], "gercek"),
])
def test_hazirla_olcek_hedef_bayraklari(tmp_path, bayraklar, egitim, test, ozet_test):
    sentetik_olcek(tmp_path)
    s = calistir("lora/hazirla_olcek.py", "--veri", "veri/bin/olcek", "--cikti", "c", "--token-tavan", 0,
                 *bayraklar, cwd=tmp_path)
    assert s.returncode == 0, s.stderr
    assert hedefler(tmp_path / "c" / "train.jsonl") == sorted(egitim)
    assert hedefler(tmp_path / "c" / "test.jsonl") == test
    assert json.loads((tmp_path / "c" / "ozet.json").read_text())["test_hedefi"] == ozet_test
