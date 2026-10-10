from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[1]
BELGE = KOK / "rapor/arastirma/ONCEKI_CALISMALAR.md"


def test_literatur_guncel_main_ve_v6_onceligi():
    md = BELGE.read_text(encoding="utf-8")
    assert "15e3b28f1be387d0e8655edd838e1c32f9d348d5" in md
    assert "6f8d4781522bc7be45839071dc7231e12d0164e5" in md
    assert "İlk iş mevcut v6 hattını değerlendir" in md
    assert "Main'de karşılanan gereksinim" in md and "Kalan boşluklar" in md
    for yol in ("lora/hazirla_sonraki.py", "molab/egit.py", "decompile_ghidra.py", "dogrula_v6.py", "olcekle.py"):
        assert (KOK / yol).is_file() and yol in md
    assert "--surum v6" in md and "VERI_SURUM" in md


def test_testin_gelistirme_kullanimi_gizlenmez():
    md = BELGE.read_text(encoding="utf-8")
    assert "geliştirmede kullanılmış\nölçüt" in md
    assert "gerçekleşmiş bir özellik değildir" in md
    assert "Geleceğe yönelik öneri" in md
    assert "tam koşuların sonunda testi ölçer" in md
    assert "gerçek arşiv tahminlerini" in md


def test_kume_ve_coklu_karsilastirma_protokolu():
    md = BELGE.read_text(encoding="utf-8")
    for ifade in (
        "Birincil yeniden örnekleme birimi proje",
        "optimizasyon kopyaları",
        "Bonferroni",
        "%99",
        "0,005",
        "0,995",
    ):
        assert ifade in md
    assert "0,05 / 5" in md and "20.000" in md
    assert "yalnız raporlanan\nkazananlara değil" in md


@pytest.mark.parametrize(
    "yasak", ["/workspace/", "/Users/", "sys.executable", "58157e7", "eccf6b4", "1b4a0a7", "3b7aefe", "63e6ddc"]
)
def test_kisisel_yol_ve_eski_birincil_kaynak_yok(yasak):
    assert yasak not in BELGE.read_text(encoding="utf-8")


def test_kaynak_haritasi_temel_calisma_ve_sinirlari_korur():
    md = BELGE.read_text(encoding="utf-8")
    for ad in (
        "DIRE",
        "DIRTY",
        "NERO",
        "SymLM",
        "XFL",
        "HexT5",
        "AsmDepictor",
        "VarBERT",
        "ReSym",
        "LLM4Decompile",
        "BinSum",
    ):
        assert ad in md
    assert "unverified" in md and "not run" in md
    assert "https://" in md and "veri veya ağırlık lisansı yerine geçmez" in md
