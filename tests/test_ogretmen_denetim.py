import json
from collections import Counter

import pytest

import ogretmen_denetim as od


def _kayit(proje, no, kategori):
    return {"anahtar": f"{proje}/x.c:f{no}", "proje": proje, "kategori": kategori}


def test_orneklem_proje_dengeli_kategori_katmanli_ve_belirlenimci():
    kayitlar = (
        [_kayit("a", i, "dize" if i % 2 else "ag") for i in range(10)]
        + [_kayit("b", i, "bellek" if i % 2 else "ag") for i in range(8)]
        + [_kayit("c", i, "diger") for i in range(2)]
    )
    secilen, tavan = od.ornekle(kayitlar, 11, 42)
    yine, yine_tavan = od.ornekle(kayitlar, 11, 42)
    assert [r["anahtar"] for r in secilen] == [r["anahtar"] for r in yine]
    assert tavan == yine_tavan and len(secilen) == 11
    sayi = Counter(r["proje"] for r in secilen)
    assert max(sayi.values()) <= tavan
    assert sayi["c"] == 2
    assert len({r["kategori"] for r in secilen if r["proje"] == "a"}) == 2


def test_hakem_json_ayristirma_kod_blogu_ve_dogrulama():
    metin = """```json
    {"puanlar":{"aciklama":2,"kategori":1,"girdiler":0,"donus":2,
    "yan_etki":1,"aciklama_en":2},"aciklama_uyumu":"hayir","gerekce":"girdi yanlış"}
    ```"""
    sonuc = od.hakem_sonucunu_ayristir(metin)
    assert sonuc["puanlar"]["girdiler"] == 0
    assert sonuc["aciklama_uyumu"] == "hayır"
    with pytest.raises(ValueError, match="kategori"):
        od.hakem_sonucunu_ayristir(metin.replace('"kategori":1', '"kategori":7'))


def test_bozuk_json_sahte_istekle_yeniden_sorulur(monkeypatch):
    cevaplar = iter([
        {"choices": [{"message": {"content": "JSON değil"}, "finish_reason": "stop"}],
         "usage": {"total_tokens": 5}},
        {"choices": [{"message": {"content": json.dumps({
            "puanlar": {alan: 2 for alan in od.ALANLAR},
            "aciklama_uyumu": "evet", "gerekce": "uygun",
        })}, "finish_reason": "stop"}], "usage": {"total_tokens": 7}},
    ])
    cagrilar = []

    def sahte(*args, **kwargs):
        cagrilar.append((args, kwargs))
        return next(cevaplar)

    monkeypatch.setattr(od, "evren_istek", sahte)
    sonuc = od.hakeme_sor("sahte", "istem")
    assert len(cagrilar) == 2
    assert sonuc["puanlar"] == {alan: 2 for alan in od.ALANLAR}
    assert sonuc["token"] == 12
    assert cagrilar[0][0][1][0]["content"] == od.SISTEM


def test_rapor_puan_bootstrap_kirim_ve_sifir_ornegi():
    satirlar = []
    for no, (puan, model, kategori, token) in enumerate([
        (0, "codex/gpt-5.6-luna", "dize", 500),
        (2, "codex/gpt-5.6-sol", "ag", 7000),
    ]):
        satirlar.append({
            "anahtar": f"p{no}/x.c:f", "proje": f"p{no}", "kategori": kategori,
            "ogretmen_model": model, "puanlar": {alan: puan for alan in od.ALANLAR},
            "aciklama_uyumu": "evet" if puan else "hayır", "gerekce": "somut gerekçe",
            "etiketler": {alan: f"etiket {alan}" for alan in od.ALANLAR},
            "kaynak_token_tahmini": token,
        })
    rapor = od.rapor_metni(satirlar)
    assert "%95 bootstrap GA" in rapor
    assert "codex/gpt-5.6-luna" in rapor and "codex/gpt-5.6-sol" in rapor
    assert ">6K (kesildi)" in rapor
    assert "p0/x.c:f" in rapor and "somut gerekçe" in rapor


def test_uzun_kaynak_hedef_fonksiyon_cevresinde_kesilir():
    kaynak = "A" * 30000 + "\nint hedef(void) { return 1; }\n" + "B" * 30000
    parca, token, kesildi = od.kaynak_kisalt(kaynak, "p/x.c:hedef", tavan=100)
    assert kesildi and token > 100
    assert "hedef" in parca and "KESİLDİ" in parca
    assert od.token_tahmini(parca) <= 101
