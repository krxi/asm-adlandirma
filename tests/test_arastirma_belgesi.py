from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[1]
BELGE = KOK / "rapor/arastirma/ONCEKI_CALISMALAR.md"
MSR_ANA = KOK / "makale/msr2027/main.tex"
MSR_KAYNAKLAR = KOK / "makale/msr2027/refs.bib"


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
        "BLens",
        "SymGen",
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


def test_msr_blens_ve_symgen_kaynaklari_dogrulandi():
    refs = MSR_KAYNAKLAR.read_text(encoding="utf-8")
    ana = MSR_ANA.read_text(encoding="utf-8")

    assert "TODO" not in refs
    for ifade in (
        "Benoit, Tristan and Wang, Yunru and Dannehl, Moritz and Kinder, Johannes",
        "34th USENIX Security Symposium (USENIX Security 25)",
        "pages     = {6877--6896}",
        "Jiang, Linxi and Jin, Xin and Lin, Zhiqiang",
        "Beyond Classification: Inferring Function Names in Stripped Binaries",
        "doi       = {10.14722/ndss.2025.240797}",
    ):
        assert ifade in refs

    assert "excludes 20 common names" not in ana
    assert "twenty static-analysis-identifiable functions" in ana
    assert "binary-level split" in ana and "2.94\\times" in ana
