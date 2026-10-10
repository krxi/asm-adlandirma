"""Ölçüm hattı: sentetik model testleri ve arşivlenmiş gerçek sonuçların rapor denetimi."""

import json, os, re, subprocess, sys
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
    assert [r["id"] for r in olcum_seti(ornek_kok, k=3)] == [r["id"] for r in secilen]


def sahte_sor(model, asm, dusunme=False, tavan=4096, baglam=False):
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
    monkeypatch.setattr(sys, "argv", ["taban.py", "veri/test.jsonl", "-n", "1", "-m", "sahte", "--idler", str(idler)])
    taban.main()
    sonuc = oku_jsonl(ornek_kok / "sonuc" / f"test{len(sira)}-sahte.jsonl")
    assert [r["id"] for r in sonuc] == sira


def test_taban_kuru_istek_atmaz_ve_token_tahmini_yazar(ornek_kok, monkeypatch, capsys):
    secilen = olcum_seti(ornek_kok, k=1)
    idler = ornek_kok / "idler.txt"
    idler.write_text(secilen[0]["id"] + "\n")
    monkeypatch.chdir(ornek_kok)
    monkeypatch.setattr(taban, "sor", lambda *a, **k: pytest.fail("kuru kip istek atmamalı"))
    monkeypatch.setattr(sys, "argv", ["taban.py", "veri/test.jsonl", "--idler", str(idler), "--baglam", "--kuru"])
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


# Yalnız Git'te bulunmayan v4 ham hedeflerine ait mevcut koşular.
# İzin sayıları çıktıdan veya bozulan hedef okuyucusundan türetilmez.
TEMIZ_CHECKOUT_EKSIK = {
    "valid300-molab-qwen3-8b-v5": 300,
    "sabit500-lora15-v3-baglam-ozet": 500,
    "sabit500-lora15-v3-baglam-yok": 500,
    "test2000-deepseek-v4.1-flash-baglam": 2000,
    "test2000-mimo-v2.6-pro-baglam": 2000,
    "test2000-mimo-v2.6-pro-baglam-ikisi": 2000,
    "test2000-mimo-v2.6-pro-decompile": 2000,
    "test2000-molab-qwen3-8b": 2000,
    "test2000-molab-qwen3-8b-v5": 2000,
}
RAPOR_BASLIK = (
    "| koşu | n | gerçek ad F1 (-O0 / -O2 / hepsi) | öneksiz F1 (-O0 / -O2 / hepsi) | fark | "
    "tam isabet gerçek / öneksiz | dosyadaki f1 | hedef |"
)
RAPOR_AYRAC = "|---|---:|---|---|---:|---|---:|---|"


def bilinmeyenleri_dogrula(sonuclar, izinli):
    """Yapılandırılmış sayaçlar: izin dışı her koşuda tam hedef kapsamı gerekir."""
    for kosu, sonuc in sonuclar.items():
        eksik = sonuc["bilinmeyen"]
        beklenen = izinli.get(kosu, 0)
        assert type(eksik) is int and eksik == beklenen, (
            f"{kosu}: bilinmeyen={eksik}, beklenen={beklenen}; hedef okuyucusunu/veriyi denetleyin"
        )


def rapor_karsilastirma_metni(md, izinli=None):
    """Yalnız adı ve sayısı açıkça izinli uyarı ile fark sütunundaki işaretli sıfırı kaldır."""
    izinli = {} if izinli is None else izinli
    satirlar = md.splitlines(keepends=True)
    for i, satir in enumerate(satirlar[:-1]):
        if satir.rstrip("\n") != RAPOR_BASLIK or satirlar[i + 1].rstrip("\n") != RAPOR_AYRAC:
            continue
        for j in range(i + 2, len(satirlar)):
            if not satirlar[j].startswith("|"):
                break
            hucreler = satirlar[j].split("|")
            if len(hucreler) != 10 or hucreler[0] or hucreler[-1] not in ("", "\n"):
                continue
            if hucreler[5] == " -0.000 ":
                hucreler[5] = " +0.000 "
            eslesme = re.fullmatch(
                r"( gerçek ad| \*\*[1-9][0-9]* satırda öneksiz\*\*), ([1-9][0-9]*) id veri/'de yok ",
                hucreler[8],
            )
            if eslesme and izinli.get(hucreler[1].strip()) == int(eslesme.group(2)):
                hucreler[8] = eslesme.group(1) + " "
            satirlar[j] = "|".join(hucreler)
    return "".join(satirlar)


def ornek_f1_raporu(hucreler=None):
    if hucreler is None:
        hucreler = [
            "ornek-kosu",
            "4",
            "0.250 / 0.250 / 0.250",
            "0.250 / 0.250 / 0.250",
            "+0.000",
            "1 / 1",
            "0.250",
            "gerçek ad",
        ]
    return "\n".join(
        ["# Sentetik rapor", "", RAPOR_BASLIK, RAPOR_AYRAC, "| " + " | ".join(hucreler) + " |", "", "Dipnot.", ""]
    )


@pytest.mark.parametrize("hedef", ["gerçek ad", "**2 satırda öneksiz**"])
@pytest.mark.parametrize("fark", ["+0.000", "-0.000"])
def test_rapor_normalizasyonu_yalniz_tasinabilir_farklari_yoksayar(hedef, fark):
    beklenen = ornek_f1_raporu().replace("gerçek ad |", hedef + " |")
    uretilen = beklenen.replace("| +0.000 |", "| " + fark + " |")
    uretilen = uretilen.replace(hedef + " |", hedef + ", 4 id veri/'de yok |")
    assert rapor_karsilastirma_metni(uretilen, {"ornek-kosu": 4}) == rapor_karsilastirma_metni(beklenen)


@pytest.mark.parametrize("kosu,sayi", [("ornek-kosu", 3), ("ornek-kosu", 5), ("baska-kosu", 4)])
def test_izin_disindaki_eksik_hedef_gizlenmez(kosu, sayi):
    beklenen = ornek_f1_raporu().replace("ornek-kosu", kosu)
    uretilen = beklenen.replace("gerçek ad |", f"gerçek ad, {sayi} id veri/'de yok |")
    assert rapor_karsilastirma_metni(uretilen, {"ornek-kosu": 4}) != rapor_karsilastirma_metni(beklenen)
    with pytest.raises(AssertionError, match="bilinmeyen"):
        bilinmeyenleri_dogrula({kosu: {"bilinmeyen": sayi}}, {"ornek-kosu": 4})


def test_hedef_okuyucusunun_tamamen_bozulmasi_reddedilir():
    import iki_f1

    satir = {"id": "sentetik/a.c:-O0:tam:sub_0001:oku", "gercek": "oku", "tahmin": "oku", "opt": "-O0"}
    sonuc = iki_f1.puanla([satir], {})
    assert sonuc["bilinmeyen"] == 1
    with pytest.raises(AssertionError, match="bilinmeyen"):
        bilinmeyenleri_dogrula({"sentetik-tam-hedefli": sonuc}, TEMIZ_CHECKOUT_EKSIK)


def test_izin_listesi_tam_sayiyi_ve_tam_kapsami_zorunlu_kilar():
    assert len(TEMIZ_CHECKOUT_EKSIK) == 9
    bilinmeyenleri_dogrula({"ornek": {"bilinmeyen": 0}}, {})
    bilinmeyenleri_dogrula({"ornek": {"bilinmeyen": 4}}, {"ornek": 4})
    for sayi in (0, 1, 3, 5, True):
        with pytest.raises(AssertionError):
            bilinmeyenleri_dogrula({"ornek": {"bilinmeyen": sayi}}, {"ornek": 4})


@pytest.mark.parametrize(
    "eski,yeni",
    [
        ("ornek-kosu", "baska-kosu"),
        ("| 4 |", "| 5 |"),
        ("0.250 / 0.250 / 0.250", "0.251 / 0.250 / 0.250"),
        ("| +0.000 |", "| +0.001 |"),
        ("| +0.000 |", "| -0.001 |"),
        ("| 1 / 1 |", "| 2 / 1 |"),
        ("| 0.250 |", "| 0.251 |"),
        ("gerçek ad |", "**1 satırda öneksiz** |"),
    ],
)
def test_rapor_normalizasyonu_gercek_sonuc_degisimini_korur(eski, yeni):
    beklenen = ornek_f1_raporu()
    degismis = beklenen.replace(eski, yeni, 1)
    assert rapor_karsilastirma_metni(degismis) != rapor_karsilastirma_metni(beklenen)


@pytest.mark.parametrize("sutun", [2, 3, 6])
def test_rapor_normalizasyonu_diger_puan_hucrelerine_dokunmaz(sutun):
    hucreler = [
        "ornek-kosu",
        "4",
        "0.250 / 0.250 / 0.250",
        "0.250 / 0.250 / 0.250",
        "+0.000",
        "1 / 1",
        "0.250",
        "gerçek ad",
    ]
    beklenen = ornek_f1_raporu(hucreler)
    hucreler[sutun] = hucreler[sutun].replace("0.250", "0.251", 1)
    assert rapor_karsilastirma_metni(ornek_f1_raporu(hucreler)) != rapor_karsilastirma_metni(beklenen)
    hucreler[sutun] = "-0.000"
    degismis = ornek_f1_raporu(hucreler)
    assert rapor_karsilastirma_metni(degismis) == degismis


@pytest.mark.parametrize(
    "hedef",
    [
        "gerçek ad, 4 id veri/'de yok, beklenmedik uyarı",
        "gerçek ad, dört id veri/'de yok",
        "gerçek ad, 4 id veri'de yok",
        "gerçek ad, 0 id veri/'de yok",
        "gerçek ad, 04 id veri/'de yok",
        "beklenmedik hedef, 4 id veri/'de yok",
    ],
)
def test_rapor_normalizasyonu_beklenmedik_uyarilari_korur(hedef):
    md = ornek_f1_raporu().replace("gerçek ad |", hedef + " |")
    assert rapor_karsilastirma_metni(md, {"ornek-kosu": 4}) == md


def test_rapor_normalizasyonu_tablo_disina_ve_sema_degisimine_dokunmaz():
    md = ornek_f1_raporu().replace("| +0.000 |", "| -0.000 |")
    md = md.replace("gerçek ad |", "gerçek ad, 4 id veri/'de yok |")
    for degismis in (
        md.replace(RAPOR_BASLIK, "| başka başlık |"),
        md.replace(RAPOR_AYRAC, "|---|"),
        md.replace("| ornek-kosu |", "| ek sütun | ornek-kosu |"),
    ):
        assert rapor_karsilastirma_metni(degismis, {"ornek-kosu": 4}) == degismis
    dis_metin = "| -0.000 | gerçek ad, 4 id veri/'de yok |\n"
    assert rapor_karsilastirma_metni(dis_metin) == dis_metin
    md = ornek_f1_raporu().replace("Dipnot.", dis_metin)
    assert rapor_karsilastirma_metni(md) == md


@pytest.mark.parametrize("degisiklik", ["satir_sil", "satir_ekle", "sutun_sil", "dipnot"])
def test_rapor_normalizasyonu_eski_raporu_yakalar(degisiklik):
    beklenen = ornek_f1_raporu()
    satir = next(s for s in beklenen.splitlines(keepends=True) if s.startswith("| ornek-kosu |"))
    if degisiklik == "satir_sil":
        degismis = beklenen.replace(satir, "")
    elif degisiklik == "satir_ekle":
        degismis = beklenen.replace(satir, satir + satir)
    elif degisiklik == "sutun_sil":
        degismis = beklenen.replace("| 1 / 1 |", "|")
    else:
        degismis = beklenen.replace("Dipnot.", "Değişmiş dipnot.")
    assert rapor_karsilastirma_metni(degismis) != rapor_karsilastirma_metni(beklenen)


@pytest.mark.skipif(
    os.environ.get("ASMSENSE_ARCHIVE_REPORT") != "1",
    reason="Archived benchmark rescoring is an explicit publication check, not a unit test",
)
def test_rapor_guncel(tmp_path):
    """Gerçek sonuc/*.jsonl arşivini yeniden puanlar; yeni model çıkarımı çalıştırmaz."""
    import iki_f1

    # Temiz, yalnız sürüm kontrollü veri içeren checkout; harici ham veriyi bu testin
    # izinlerini kendiliğinden genişletmek için kullanmayın.
    adlar = iki_f1.gercek_adlar(KOK / "veri")
    sonuclar = {}
    for yol in sorted((KOK / "sonuc").glob("*.jsonl")):
        satirlar = oku_jsonl(yol)
        if satirlar and "gercek" in satirlar[0]:
            sonuclar[yol.stem] = iki_f1.puanla(satirlar, adlar)
    bilinmeyenleri_dogrula(sonuclar, TEMIZ_CHECKOUT_EKSIK)
    assert set(TEMIZ_CHECKOUT_EKSIK) <= set(sonuclar), "izin verilen bir arşiv koşusu kayıp"
    s = subprocess.run(
        [sys.executable, str(KOK / "iki_f1.py"), "-o", str(tmp_path / "r.md")], cwd=KOK, capture_output=True, text=True
    )
    assert s.returncode == 0, s.stderr
    assert rapor_karsilastirma_metni((tmp_path / "r.md").read_text(), TEMIZ_CHECKOUT_EKSIK) == (
        rapor_karsilastirma_metni((KOK / "rapor" / "F1_IKI_TANIM.md").read_text())
    ), "rapor eski: python3 iki_f1.py çalıştırın"


@pytest.mark.parametrize("kayitli,uyumsuz", [(1 / 3, 0), (0.333, 0), (0.334, 1)])
def test_iki_f1_kayitli_puan_hassasiyeti(kayitli, uyumsuz):
    import iki_f1

    r = {"id": "sentetik", "gercek": "a_b_c_d", "tahmin": "a_e", "opt": "-O0", "f1": kayitli}
    sonuc = iki_f1.puanla([r], {"sentetik": r["gercek"]})
    assert sonuc["kayitli_uyumsuz"] == uyumsuz
