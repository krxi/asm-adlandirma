import json
from pathlib import Path

import pytest

import aciklama_degerlendir as ad
import dogrulama_guvencesi as dg


def _jsonl(yol, satirlar):
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in satirlar), encoding="utf-8")
    return yol


@pytest.fixture
def girdiler(tmp_path, monkeypatch):
    veri, a, b, kaynak = [], [], [], []
    for no in range(6):
        proje = "p1" if no < 4 else "p2"
        kimlik = f"{proje}/x.c:-O{no % 2}:tam:sub_{no:04x}:synthetic_f{no}"
        veri.append(
            {
                "id": kimlik,
                "proje": proje,
                "dosya": "x.c",
                "ad": f"synthetic_f{no}",
                "opt": f"-O{no % 2}",
                "asm": 'lea rax, [rip + "x"]' if no % 2 else "xor eax, eax",
            }
        )
        a.append({"id": kimlik, "aciklama_en": f"A description {no}"})
        b.append({"id": kimlik, "aciklama_en": f"B description {no}"})
        kaynak.append({"anahtar": f"{proje}/x.c:synthetic_f{no}", "kaynak": f"int synthetic_f{no}(void) {{ return {no}; }}"})
    sabit = {r["id"]: {"gercek": r["ad"], "proje": r["proje"], "opt": r["opt"]} for r in veri}
    monkeypatch.setattr(dg, "dayanaklar", lambda: (sabit, {"sentetik-test", "sentetik-eval"}))
    monkeypatch.setattr(dg, "git_izi", lambda: {"commit": "sentetik-commit", "tree": "sentetik-tree"})
    kok = tmp_path / "repo"
    kok.mkdir()
    monkeypatch.setattr(ad, "KOK", kok)
    return (
        _jsonl(tmp_path / "validation.jsonl", veri),
        [("a", _jsonl(tmp_path / "a.jsonl", a)), ("b", _jsonl(tmp_path / "b.jsonl", b))],
        _jsonl(tmp_path / "kaynak.jsonl", kaynak),
    )


def hazir_paket(girdiler, tmp_path, n=4):
    veri, tahminler, kaynak = girdiler
    manifest, secilen, gs = ad.plan_hazirla(veri, tahminler, n, 42)
    paket, anahtar = tmp_path / "paket.jsonl", tmp_path / "anahtar.json"
    ad.paketle(manifest, secilen, gs, kaynak, paket, anahtar)
    return paket, anahtar, json.loads(anahtar.read_text())


def _etiketler(anahtar, degistir=False):
    return [
        {
            "ornek": r["ornek"],
            "paket_sha256": anahtar["paket_sha256"],
            "ana_islem": "yanlis" if degistir and no == 0 else "dogru",
            "girdi_cikti": "kismi",
            "yan_etki": "bilinmiyor",
            "uydurma": "yok",
        }
        for no, r in enumerate(anahtar["esleme"])
    ]


def test_plan_belirlenimci_dengeli_ve_tam_kapsamli(girdiler):
    veri, tahminler, _ = girdiler
    plan, secilen, _ = ad.plan_hazirla(veri, tahminler, 4, 42)
    yine, yine_secilen, _ = ad.plan_hazirla(veri, tahminler, 4, 42)
    assert plan == yine and secilen == yine_secilen
    assert plan["bolum"] == "valid300" and plan["n"] == 4
    assert plan["dagilim"]["proje"] == {"p1": 2, "p2": 2}
    assert plan["asgari_aday_kapsami"] == 1.0
    assert plan["aday_kapsami"]["a"] == {"beklenen": 6, "mevcut": 6, "oran": 1.0}
    assert all(k not in json.dumps(plan) for k in secilen)
    assert str(veri.parent) not in json.dumps(plan)


@pytest.mark.parametrize("degisim", ["satir_sil", "bos_aciklama", "olmayan_aciklama", "yanlis_tur"])
def test_aday_zor_ornekleri_sessiz_atamaz(girdiler, tmp_path, degisim):
    veri, tahminler, _ = girdiler
    rs = ad.jsonl_oku(tahminler[1][1])
    if degisim == "satir_sil":
        rs.pop()
    else:
        rs[0]["aciklama_en"] = {"bos_aciklama": "", "olmayan_aciklama": None, "yanlis_tur": 123}[degisim]
    yol = _jsonl(tmp_path / "eksik.jsonl", rs)
    with pytest.raises(ValueError, match="beklenen=6.*gerekli_oran=1.0"):
        ad.plan_hazirla(veri, [tahminler[0], ("b", yol)], 2, 42)


@pytest.mark.parametrize("kimlik", ["sentetik-test", "sentetik-eval"])
def test_test_ve_eval115_icerigi_yeniden_adlandirilsa_da_reddedilir(girdiler, tmp_path, kimlik):
    veri, tahminler, _ = girdiler
    rs = ad.jsonl_oku(veri)
    rs[0]["id"] = kimlik
    yol = _jsonl(tmp_path / "lora/veri-v5/eval115.jsonl", rs)
    with pytest.raises(ValueError, match="test|Test|eval115"):
        ad.plan_hazirla(yol, tahminler, 2, 42)
    rs = ad.jsonl_oku(tahminler[1][1])
    rs[0]["id"] = kimlik
    with pytest.raises(ValueError, match="Test|eval115"):
        ad.plan_hazirla(veri, [tahminler[0], ("b", _jsonl(tmp_path / "masum.jsonl", rs))], 2, 42)


def test_izinli_icerik_dosya_adindan_bagimsiz(girdiler, tmp_path):
    veri, tahminler, _ = girdiler
    yol = tmp_path / "test.jsonl"
    yol.write_bytes(veri.read_bytes())
    plan, _, _ = ad.plan_hazirla(yol, tahminler, 2, 42)
    assert plan["bolum"] == "valid300"


def test_paket_kor_ayni_fonksiyonlar_ve_hash_bagi(girdiler, tmp_path):
    paket, anahtar, key = hazir_paket(girdiler, tmp_path)
    rs = ad.jsonl_oku(paket)
    assert len(rs) == 8 and all(set(r) == {"ornek", "c_kaynagi", "aciklama_en"} for r in rs)
    assert key["paket_sha256"] == ad.dosya_ozeti(paket)
    say = {}
    for r in key["esleme"]:
        say.setdefault(r["id"], set()).add(r["sistem"])
    assert len(say) == 4 and all(s == {"a", "b"} for s in say.values())
    sablon = ad.jsonl_oku(paket.with_name(paket.name + ".etiket-sablonu.jsonl"))
    assert all(r["paket_sha256"] == key["paket_sha256"] for r in sablon)
    assert anahtar.stat().st_mode & 0o777 == 0o600


def test_varsayilan_anahtar_repo_disinda_ve_gitignore_kurali(girdiler, tmp_path):
    veri, tahminler, kaynak = girdiler
    m, ids, gs = ad.plan_hazirla(veri, tahminler, 2, 42)
    sonuc = ad.paketle(m, ids, gs, kaynak, tmp_path / "paket.jsonl")
    dosyalar = list((ad.KOK.parent / "asmsense-ozel").glob("*.asmsense-kor-anahtar.json"))
    assert len(dosyalar) == 1 and ad.KOK not in dosyalar[0].parents
    assert sonuc["anahtar"]["dosya"] == dosyalar[0].name
    gercek_kok = Path(__file__).resolve().parents[1]
    assert "*.asmsense-kor-anahtar.json" in (gercek_kok / ".gitignore").read_text()
    with pytest.raises(ValueError, match="repo dışında"):
        ad.paketle(m, ids, gs, kaynak, tmp_path / "yeni.jsonl", ad.KOK / "anahtar.json")


def test_puanla_alan_oranlari_kappa_ve_sabit_payda(girdiler, tmp_path):
    paket, anahtar, key = hazir_paket(girdiler, tmp_path)
    ilk = _jsonl(tmp_path / "ilk.jsonl", _etiketler(key))
    ikinci = _jsonl(tmp_path / "ikinci.jsonl", _etiketler(key, True))
    uzlasi = _jsonl(tmp_path / "uzlasi.jsonl", _etiketler(key))
    sonuc = ad.puanla(anahtar, [ilk, ikinci], uzlasi, 42, paket)
    assert sonuc["uyum"]["ana_islem"]["ham"] == pytest.approx(7 / 8)
    assert sonuc["uyum"]["girdi_cikti"]["kappa"] is None
    assert "tanımsız" in sonuc["uyum"]["girdi_cikti"]["kappa_nedeni"]
    s = sonuc["sistemler"]["a"]
    assert s["n"] == 4 and s["ortalama"] == (1 + 0.5 + 0 + 1) / 4 and s["karar_kapsami"] == 0.75
    assert s["alan_oranlari"]["yan_etki"]["bilinmiyor"] == 1.0
    assert sonuc["eslenik_farklar"]["b - a"]["n"] == 4
    assert sonuc["eslenik_farklar"]["b - a"]["ga95"] == [0.0, 0.0]
    assert sonuc["aday_kapilari"]["b"]["guvenlik_kapisi"] is True
    assert ad.puanla(anahtar, [ilk, ikinci], None, 42, paket)["aday_kapilari"] is None


@pytest.mark.parametrize("alan,deger", [("ana_islem", "bilinmiyor"), ("uydurma", "var"), ("uydurma", "bilinmiyor")])
def test_bilinmeyen_ve_uydurma_kapisi_kapsami_azaltarak_gecilemez(girdiler, tmp_path, alan, deger):
    paket, anahtar, key = hazir_paket(girdiler, tmp_path)
    rs = _etiketler(key)
    for r, esleme in zip(rs, key["esleme"]):
        if esleme["sistem"] == "b":
            r[alan] = deger
    ilk = _jsonl(tmp_path / "ilk.jsonl", rs)
    ikinci = _jsonl(tmp_path / "ikinci.jsonl", rs)
    uzlasi = _jsonl(tmp_path / "uzlasi.jsonl", rs)
    sonuc = ad.puanla(anahtar, [ilk, ikinci], uzlasi, 42, paket)
    assert sonuc["sistemler"]["b"]["n"] == sonuc["sistemler"]["a"]["n"] == 4
    assert sonuc["aday_kapilari"]["b"]["guvenlik_kapisi"] is False
    if alan == "uydurma":
        assert sonuc["sistemler"]["b"]["alan_oranlari"][alan][deger] == 1.0


def test_tamamen_bilinmeyen_ornekler_silinmez(girdiler, tmp_path):
    paket, anahtar, key = hazir_paket(girdiler, tmp_path)
    rs = _etiketler(key)
    for r in rs:
        r.update(dict.fromkeys(ad.ALANLAR, "bilinmiyor"))
    ilk, ikinci, uzlasi = (_jsonl(tmp_path / f"{ad}.jsonl", rs) for ad in ("ilk", "ikinci", "uzlasi"))
    sonuc = ad.puanla(anahtar, [ilk, ikinci], uzlasi, 42, paket)
    assert all(s["n"] == 4 and s["ortalama"] == 0 and s["karar_kapsami"] == 0 for s in sonuc["sistemler"].values())
    assert sonuc["eslenik_farklar"]["b - a"]["n"] == 4


@pytest.mark.parametrize("bozuk", ["etiket_hash", "paket_baytlari", "anahtar_hash", "eksik_etiket", "eksik_uzlasi"])
def test_farkli_paket_ve_eksik_degerlendirme_reddedilir(girdiler, tmp_path, bozuk):
    paket, anahtar, key = hazir_paket(girdiler, tmp_path)
    rs = _etiketler(key)
    ilk = _jsonl(tmp_path / "ilk.jsonl", rs)
    ikinci = _jsonl(tmp_path / "ikinci.jsonl", rs)
    uzlasi = _jsonl(tmp_path / "uzlasi.jsonl", rs)
    if bozuk == "etiket_hash":
        rs[0]["paket_sha256"] = "0" * 64
        _jsonl(ikinci, rs)
    elif bozuk == "paket_baytlari":
        paket.write_bytes(paket.read_bytes() + b"\n")
    elif bozuk == "anahtar_hash":
        key["paket_sha256"] = "0" * 64
        anahtar.write_text(json.dumps(key))
    elif bozuk == "eksik_etiket":
        _jsonl(ikinci, rs[1:])
    else:
        _jsonl(uzlasi, rs[1:])
    with pytest.raises(ValueError, match="SHA-256|kapsam"):
        ad.puanla(anahtar, [ilk, ikinci], uzlasi, 42, paket)


def test_eksik_kaynak_ve_varolan_cikti_uzerine_yazilmaz(girdiler, tmp_path):
    veri, tahminler, kaynak = girdiler
    m, ids, gs = ad.plan_hazirla(veri, tahminler, 2, 42)
    rs = [r for r in ad.jsonl_oku(kaynak) if r["anahtar"] != ad.kaynak_anahtari(gs["veri"][ids[0]])]
    eksik = _jsonl(tmp_path / "eksik-kaynak.jsonl", rs)
    with pytest.raises(ValueError, match="C kaynağı yok"):
        ad.paketle(m, ids, gs, eksik, tmp_path / "paket", tmp_path / "anahtar")
    with pytest.raises(ValueError, match="zaten var"):
        ad.paketle(m, ids, gs, kaynak, veri, tmp_path / "anahtar")


def test_kappa_tek_sinif_ve_normal_durum():
    assert ad.cohen_kappa(["dogru"] * 3, ["dogru"] * 3) is None
    assert ad.cohen_kappa(["dogru", "yanlis"], ["dogru", "yanlis"]) == 1.0
    assert ad.cohen_kappa(["dogru"] * 3, ["yanlis"] * 3) == 0.0
    assert ad.cohen_kappa([], []) is None
