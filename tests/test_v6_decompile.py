import json

from dogrula_v6 import ciktilari_yaz, dogrula, kisitli_idleri_yaz
from olcekle import cikar_tamam, pilot_sec


def yaz_jsonl(yol, satirlar):
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text("".join(json.dumps(x) + "\n" for x in satirlar))


def test_besli_pilot_uc_sabit_iki_aday():
    projeler = [
        {"ad": "zlib"}, {"ad": "baska"}, {"ad": "lua"}, {"ad": "tomlc17"},
        {"ad": "aday1", "kok": "kaynak/aday/aday1"},
        {"ad": "aday2", "kok": "kaynak/aday/aday2"},
        {"ad": "aday3", "kok": "kaynak/aday/aday3"},
    ]
    assert [p["ad"] for p in pilot_sec(projeler, 5)] == [
        "zlib", "lua", "tomlc17", "aday1", "aday2"]


def test_cikar_checkpoint_ikili_artefaktlarini_da_ister(tmp_path):
    cikti = tmp_path / "olcek" / "ham" / "egitim" / "p.jsonl"
    yaz_jsonl(cikti, [])
    cikti.with_suffix(".rapor.json").write_text(json.dumps({
        "optimizasyonlar": {"-O0": {}}, "atlanan_opt": {"-O1": "hata"}}))
    ikili = tmp_path / "ikili"
    (ikili / "p").mkdir(parents=True)
    (ikili / "p" / "O0.dylib").write_bytes(b"x")
    assert not cikar_tamam(cikti, ikili, "p", "-O0,-O1")
    yaz_jsonl(ikili / "p" / "O0.jsonl", [])
    (ikili / "p" / "O0.ithal.json").write_text("{}\n")
    assert cikar_tamam(cikti, ikili, "p", "-O0,-O1")
    assert not cikar_tamam(cikti, ikili, "p", "-O0,-O1,-O2")


def test_v6_dogrulama_ve_guvenli_decompile_idleri(tmp_path):
    hedef = tmp_path / "hedef"
    for rol in ("egitim", "dogrulama", "test"):
        yaz_jsonl(hedef / f"{rol}.jsonl", [] if rol != "egitim" else [
            {"id": "p:1", "proje": "p", "asm": "ret"},
            {"id": "p:2", "proje": "p", "asm": "mov eax, 1"},
            {"id": "p:3", "proje": "p", "asm": "nop"},
        ])
    ham = tmp_path / "yeni"
    yaz_jsonl(ham / "ham" / "egitim" / "p.jsonl", [
        {"id": "p:1", "proje": "p", "asm": "ret"},
        {"id": "p:2", "proje": "p", "asm": "mov eax, 2"},
    ])
    ikili = tmp_path / "ikili"
    yaz_jsonl(ikili / "p" / "O0.jsonl", [
        {"id": "p:1"}, {"id": "p:2"},
    ])

    veriler = dogrula(hedef, ham, ikili)
    sonuc = veriler[0]
    assert sonuc["hedef_satir"] == 3
    assert sonuc["eslesen_id"] == 2
    assert sonuc["asm_birebir_ayni"] == 1
    assert sonuc["esleme_bulunamayan_id"] == 1
    assert sonuc["decompile_hazir"] == 1

    rapor = tmp_path / "rapor.json"
    uyusmaz = tmp_path / "uyusmaz.jsonl"
    idler = tmp_path / "idler"
    sira = tmp_path / "sira.txt"
    ciktilari_yaz(*veriler, rapor, uyusmaz, idler, sira)
    assert json.loads(uyusmaz.read_text())["id"] == "p:2"
    assert (idler / "p.txt").read_text() == "p:1\n"
    assert sira.read_text() == "p\n"
    kisit = tmp_path / "kisit.txt"
    kisit.write_text("p:1\n")
    alt = tmp_path / "alt"
    alt_sira = tmp_path / "alt-sira.txt"
    kisitli_idleri_yaz(kisit, idler, alt, alt_sira)
    assert (alt / "p.txt").read_text() == "p:1\n"
    assert alt_sira.read_text() == "p\n"
