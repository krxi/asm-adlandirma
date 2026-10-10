import json

import inceleme_v5 as iv


def kayit(
    i,
    *,
    ad="read_value",
    en="Reads the stored value safely.",
    tr="Saklanan değeri güvenle okur.",
    hedef_tur="tam",
    asm="mov eax, edi\nret",
    baglam="",
):
    hedef = {"ad": ad}
    if hedef_tur == "tam":
        hedef.update(aciklama_en=en, aciklama=tr)
    girdi = asm + (iv.BAGLAM_BASLIK + baglam if baglam else "")
    return {
        "id": f"p/{i}",
        "proje": "p",
        "opt": "-O2",
        "hedef_tur": hedef_tur,
        "messages": [
            {"role": "system", "content": "s"},
            {"role": "user", "content": girdi},
            {"role": "assistant", "content": json.dumps(hedef, ensure_ascii=False)},
        ],
    }


def ozet():
    bolum = {
        "satir": 80,
        "proje": 1,
        "fonksiyon": 80,
        "opt": {"-O2": 80},
        "hedef_tur": {"tam": 80},
        "token": {"girdi": {"p50": 10, "p90": 20, "p99": 30, "maks": 40}},
    }
    return {
        "train": bolum,
        "valid_300": bolum,
        "test_sabit": bolum,
        "eval115": bolum,
        "filtreler": {"train": {"girdi": 90, "jenerik": 10}},
        "secim": {"tavan_asan_projeler": {"buyuk": 1501}},
    }


def test_bayrak_mantigi():
    r = kayit(
        1,
        ad="parse_item",
        en="parse_item does it",
        tr="Ögeyi işler.",
        asm="mov eax, edi\n; ... kesildi",
        baglam="sub_1 (2 komut)",
    )
    ham = {
        "komut_sayisi": 7,
        "sizinti": True,
        "asm": 'lea rdi, [rip] ; -> "parse_item"\n' + "\n".join("nop" for _ in range(20)),
    }
    assert set(iv.bayraklari_bul(r, ham)) == {"ad_string", "cok_kisa", "cok_uzun", "en_ad_iceriyor", "kisa_aciklama"}
    assert iv.bayraklari_bul(kayit(2, hedef_tur="ad"), {"komut_sayisi": 10, "asm": "ret"}) == ["aciklama_yok"]


def test_html_uretimi_ornek_sayilari_ve_kacis(tmp_path):
    veri = tmp_path / "v5"
    veri.mkdir()
    satirlar = [kayit(i, ad="danger" if i == 0 else f"func_{i}") for i in range(100)]
    (veri / "train.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in satirlar))
    (veri / "ozet.json").write_text(json.dumps(ozet()))
    ham = tmp_path / "ham.jsonl"
    ham.write_text(
        "".join(
            json.dumps(
                {
                    "id": r["id"],
                    "komut_sayisi": 4 if i < 30 else 12,
                    "sizinti": i == 0,
                    "asm": 'lea rax, [rip] ; -> "<danger>"' if i == 0 else "ret",
                }
            )
            + "\n"
            for i, r in enumerate(satirlar)
        )
    )
    cikti = tmp_path / "rapor" / "inceleme.html"
    sonuc = iv.html_uret(veri, cikti, tohum=42, ham_yolu=ham)
    metin = cikti.read_text()
    assert sonuc == {"rastgele": 60, "bayrakli": 20, "toplam": 80}
    assert metin.count('<article class="card"') == 80
    tehlikeli = iv.kart_html(kayit(999, ad="<danger>"), "rastgele", {"komut_sayisi": 10, "asm": "ret"})
    assert "&lt;danger&gt;" in tehlikeli and "<danger>" not in tehlikeli
    assert "localStorage" in metin and "veri-v5-isaretler.json" in metin
    assert "Tavanı aşan projeler" in metin and "Token yüzdelikleri" in metin


def test_kucuk_veri_ve_belirlenimcilik(tmp_path):
    train = [kayit(i) for i in range(3)]
    hamlar = {r["id"]: {"komut_sayisi": 10, "asm": "ret"} for r in train}
    a = iv.ornekleri_sec(train, hamlar, 42)
    b = iv.ornekleri_sec(train, hamlar, 42)
    assert [r["id"] for r, _ in a] == [r["id"] for r, _ in b]
    assert len(a) == 3


def test_cli_ozel_yollar(tmp_path, monkeypatch):
    veri = tmp_path / "v"
    veri.mkdir()
    r = kayit(1)
    (veri / "train.jsonl").write_text(json.dumps(r) + "\n")
    (veri / "ozet.json").write_text(json.dumps(ozet()))
    ham = tmp_path / "veri/bin/olcek/egitim.jsonl"
    ham.parent.mkdir(parents=True)
    ham.write_text(json.dumps({"id": r["id"], "komut_sayisi": 10, "sizinti": False, "asm": "ret"}) + "\n")
    monkeypatch.chdir(tmp_path)
    cikti = tmp_path / "x.html"
    iv.main(["--veri", str(veri), "--cikti", str(cikti), "--tohum", "7"])
    assert cikti.exists() and "TOHUM 7" in cikti.read_text()


def test_v6_decompile_bolumu_bayraklari_ve_tokenlari():
    r = kayit(1)
    r["messages"][1]["content"] += iv.DECOMPILE_BASLIK + "int sub_0001(void) {\n/* ... kırpıldı */"
    r.update(
        {
            "decompile_var": True,
            "decompile_kirpildi": True,
            "decompile_sizinti": False,
            "decompile_yok_neden": None,
            "token": {"girdi": 123, "hedef": 17, "toplam": 180},
        }
    )
    asm, baglam, decompile = iv.girdi_bol(r)
    assert asm.startswith("mov") and baglam == "" and "sub_0001" in decompile
    assert "decompile_kirpildi" in iv.bayraklari_bul(r, {"komut_sayisi": 10, "asm": asm})
    kart = iv.kart_html(r, "bayraklı", {"komut_sayisi": 10, "asm": asm})
    assert "Ghidra decompile" in kart and "girdi 123" in kart and "kırpıldı" in kart
