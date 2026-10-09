import itertools
import json

import pytest

from cikti import ad_ayikla


def test_anahtar_sirasindan_bagimsiz():
    alanlar = {"ad": "read_record", "aciklama_en": "Reads a record.", "aciklama": "Kayıt okur."}
    for sira in itertools.permutations(alanlar):
        metin = json.dumps({k: alanlar[k] for k in sira}, ensure_ascii=False)
        assert ad_ayikla(metin) == ("read_record", "Reads a record.", "Kayıt okur.", True)


@pytest.mark.parametrize("metin", ['{"ad": "oku"', '{"ad": "oku", "aciklama": "kesik',
                                  '{"aciklama_en": "Reads.", "ad": "oku",'])
def test_kesik_json(metin):
    ad, _, _, gecerli = ad_ayikla(metin)
    assert ad == "oku" and not gecerli


@pytest.mark.parametrize("metin, ad", [("read_record", "read_record"), ("`read_record()`", "read_record"),
                                       ("", ""), ("123 !!!", "")])
def test_duz_metin(metin, ad):
    assert ad_ayikla(metin) == (ad, "", "", False)


def test_kod_citi_ve_kacislar():
    assert ad_ayikla('```json\n{"ad":"oku"}\n```') == ("oku", "", "", True)
    assert ad_ayikla(r'{"ad":"read\u005frecord",') == ("read_record", "", "", False)
