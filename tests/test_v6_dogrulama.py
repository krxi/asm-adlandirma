"""Ana v6 çıktısı, önceden sabitlenen hash'ler ve sentetik pilot sınırları."""

import builtins
import copy
import json
import socket
from types import SimpleNamespace

import pytest

import dogrula_v6 as ikili
import v6_dogrulama as v6


def yaz(yol, rs):
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text("".join(json.dumps(r) + "\n" for r in rs), encoding="utf-8")


def satir(i, proje):
    hedef = {
        "aciklama_en": "Returns a synthetic value.",
        "ad": f"synthetic_label_{i}",
        "aciklama": "Yapay değer döndürür.",
    }
    return {
        "messages": [
            {"role": "system", "content": v6.SISTEM_V5},
            {"role": "user", "content": f"mov eax, {i}\nret"},
            {"role": "assistant", "content": json.dumps(hedef)},
        ],
        "id": f"{proje}/synthetic:{i}:synthetic_label_{i}",
        "proje": proje,
        "opt": "-O2",
        "gercek_ad": hedef["ad"],
        "baglam_var": False,
        "oneksiz_onek": [],
        "hedef_tur": "tam",
    }


class HazirlamaTokenizer:
    def encode(self, s):
        return list(s.encode())

    def apply_chat_template(self, messages, **kwargs):
        return list(range(sum(len(m["content"]) for m in messages)))


def hazir_v6(rs):
    # Taklit edilmiş ayrı hazırlayıcı yerine üretimdeki satir_v6 çalışır.
    a = SimpleNamespace(max_uzunluk=4096, decompile_alt_token=1)
    sonuc = []
    for i, r in enumerate(rs):
        ham = {"id": r["id"], "ad": r["gercek_ad"], "proje": r["proje"], "asm": r["messages"][1]["content"]}
        dc = {"id": r["id"], "decompile": f"int sub_{i:04x}(void) {{ return {i}; }}", "sizinti": False}
        s = v6.hs.satir_v6(ham, None, None, a, dc, taban_satir=r)
        s["token"] = {"girdi": 50, "hedef": 20, "toplam": 100}
        sonuc.append(s)
    return sonuc


def muhurlu_manifest(a):
    # Yalnız sentetik testin beklenenleri; ürün CLI'ında otomatik mühürleme yolu yok.
    iz = {k: v6.dosya_sha(getattr(a, k)) for k in ("train", "valid", "train_v6", "valid_v6", "dogrulama_raporu")}
    _, iz["dogrulanmis_idler"] = v6.id_dizini_oku(a.dogrulanmis_idler)
    tr, _ = v6.jsonl_oku(a.train)
    m = {
        "beklenen_sha256": iz,
        "train_sira_sha256": v6.ozet([tr[i]["id"] for i in v6.veri_sirasi(tr)]),
        "ana_hat_bloblari": {p: v6.git_blob(v6.KOK / p) for p in ("lora/hazirla_sonraki.py", "dogrula_v6.py")},
    }
    v6.GIRDI_MANIFESTI.write_text(json.dumps(m), encoding="utf-8")
    return m


@pytest.fixture
def girdi(tmp_path, monkeypatch):
    monkeypatch.setattr(v6.hs.h, "TOK", HazirlamaTokenizer())
    monkeypatch.setattr(v6, "GIRDI_MANIFESTI", tmp_path / "onceden-beklenen.json")
    tr = [satir(i, "synthetic_train") for i in range(32)]
    va = [satir(100 + i, "synthetic_valid") for i in range(2)]
    a = SimpleNamespace(
        train=tmp_path / "train.jsonl",
        valid=tmp_path / "valid.jsonl",
        train_v6=tmp_path / "train-v6.jsonl",
        valid_v6=tmp_path / "valid-v6.jsonl",
        dogrulama_raporu=tmp_path / "dogrulama-raporu.json",
        dogrulanmis_idler=tmp_path / "dogrulanmis-idler",
        output=tmp_path / "output",
        steps=1,
        micro_batch=1,
        max_length=256,
        max_new_tokens=16,
        max_train_tokens=8000000,
    )
    for yol, rs in ((a.train, tr), (a.valid, va), (a.train_v6, hazir_v6(tr)), (a.valid_v6, hazir_v6(va))):
        yaz(yol, rs)
    hedef, ham, binary = tmp_path / "hedef", tmp_path / "ham", tmp_path / "ikili"
    for rol, rs in (("egitim", tr), ("dogrulama", va), ("test", [])):
        raw = [{"id": r["id"], "proje": r["proje"], "asm": r["messages"][1]["content"]} for r in rs]
        yaz(hedef / f"{rol}.jsonl", raw)
        if raw:
            yaz(ham / "ham/tam" / f"{raw[0]['proje']}.jsonl", raw)
            yaz(binary / f"{raw[0]['proje']}.jsonl", [{"id": r["id"]} for r in raw])
    # Gerçek ana doğrulayıcı, yalnız bu fixture'ın sentetik kaynak/eşlemeleri üzerinde.
    kanit = ikili.dogrula(hedef, ham, binary)
    ikili.ciktilari_yaz(*kanit, a.dogrulama_raporu, tmp_path / "uyusmaz.jsonl", a.dogrulanmis_idler)
    muhurlu_manifest(a)
    capa = [{"id": r["id"], "proje": r["proje"], "opt": r["opt"], "gercek": r["gercek_ad"]} for r in va]
    return a, tr, va, capa


def test_sabit_dogrulama_ve_proje_capalari():
    capa = v6.valid_capasi()
    assert len(capa) == 300 and len({r["proje"] for r in capa}) == 23
    assert not ({r["id"] for r in capa} & v6.yasak_idler())
    assert len(v6.proje_capasi()) == 51


def test_capa_ve_proje_manifest_degisikligi_reddedilir(tmp_path, monkeypatch):
    yol = tmp_path / "degismis.jsonl"
    yaz(yol, [{"id": "sentetik"}])
    monkeypatch.setattr(v6, "VALID_CACHE", yol)
    with pytest.raises(ValueError, match="sabit valid300"):
        v6.valid_capasi()
    monkeypatch.setattr(v6, "PROJECT_GUARD", yol)
    with pytest.raises(ValueError, match="proje manifest"):
        v6.proje_capasi()


@pytest.mark.parametrize("kol", ["v5", "v6"])
@pytest.mark.parametrize("sizan", ["lfs_dir_compact", "dir_compact", "_dir_compact"])
def test_ham_ve_oneksiz_hedef_sizintisi_reddedilir(girdi, kol, sizan):
    _, _, va, _ = girdi
    r = copy.deepcopy(va[0])
    r["gercek_ad"] = "lfs_dir_compact"
    hedef = json.loads(r["messages"][2]["content"])
    hedef["ad"] = "dir_compact"
    r["messages"][2]["content"] = json.dumps(hedef)
    if kol == "v6":
        r = hazir_v6([r])[0]
        r["messages"][1]["content"] += f"\nreturn {sizan}();"
    else:
        r["messages"][1]["content"] += f"\ncall {sizan}"
    with pytest.raises(ValueError, match="öneksiz hedef"):
        v6.sema_dogrula(r, kol)


def test_ana_sizinti_yardimcisi_kullanilir(girdi, monkeypatch):
    _, _, va, _ = girdi
    gorulen = []
    asil = v6.hs.ad_sizintisi

    def izle(metin, adlar):
        gorulen.append(tuple(adlar))
        return asil(metin, adlar)

    monkeypatch.setattr(v6.hs, "ad_sizintisi", izle)
    v6.sema_dogrula(va[0])
    assert gorulen and va[0]["gercek_ad"] in gorulen[-1]


@pytest.mark.parametrize("rol", ["train", "valid", "train_v6", "valid_v6", "dogrulama_raporu"])
def test_beklenen_hash_okumadan_once_zorunlu(girdi, rol):
    a, _, _, capa = girdi
    with getattr(a, rol).open("a") as f:
        f.write(" ")
    with pytest.raises(ValueError, match="SHA-256 manifest"):
        v6.girdileri_oku(a, capa, set())


def test_bos_beklenen_hash_ve_sira_otomatik_kabul_edilmez(girdi):
    a, _, _, capa = girdi
    m = muhurlu_manifest(a)
    m["beklenen_sha256"]["train"] = None
    v6.GIRDI_MANIFESTI.write_text(json.dumps(m))
    with pytest.raises(ValueError, match="önceden sabitlenmeli"):
        v6.girdileri_oku(a, capa, set())
    m = muhurlu_manifest(a)
    m["train_sira_sha256"] = "0" * 64
    v6.GIRDI_MANIFESTI.write_text(json.dumps(m))
    with pytest.raises(ValueError, match="Eğitim sırası"):
        v6.girdileri_oku(a, capa, set())


@pytest.mark.parametrize("degisim", ["eksik_id", "yanlis_rol", "sayac", "kod"])
def test_ana_ikili_dogrulama_kaniti_zorunlu(girdi, degisim):
    a, _, _, capa = girdi
    if degisim == "eksik_id":
        yol = a.dogrulanmis_idler / "synthetic_valid.txt"
        yol.write_text("\n".join(yol.read_text().splitlines()[1:]) + "\n")
    else:
        rapor = json.loads(a.dogrulama_raporu.read_text())
        if degisim == "yanlis_rol":
            rapor["proje"]["synthetic_valid"]["rol"] = "test"
        elif degisim == "sayac":
            rapor["proje"]["synthetic_valid"]["decompile_hazir"] += 1
        a.dogrulama_raporu.write_text(json.dumps(rapor))
    m = muhurlu_manifest(a)
    if degisim == "kod":
        m["ana_hat_bloblari"]["dogrula_v6.py"] = "0" * 40
        v6.GIRDI_MANIFESTI.write_text(json.dumps(m))
    with pytest.raises(ValueError, match="Ana|ana"):
        v6.girdileri_oku(a, capa, set())


@pytest.mark.parametrize("alan", ["id", "proje", "opt", "gercek_ad", "sira"])
def test_sabit_valid_ve_v6_eslemesi_degisemez(girdi, alan):
    a, _, va, capa = girdi
    if alan == "sira":
        va.reverse()
    else:
        va[0][alan] += "_degismis"
    yaz(a.valid, va)
    muhurlu_manifest(a)
    with pytest.raises(ValueError, match="v5/v6|sabit commit"):
        v6.girdileri_oku(a, capa, set())


def test_yeniden_adlandirilmis_test_kimligi_reddedilir(girdi, monkeypatch):
    a, _, va, capa = girdi
    monkeypatch.setattr(v6, "yasak_idler", lambda: {va[0]["id"]})
    with pytest.raises(ValueError, match="test_sabit/eval115"):
        v6.girdileri_oku(a, capa, set())


def test_test_projesi_egitime_giremez(girdi):
    a, tr, _, capa = girdi
    with pytest.raises(ValueError, match="test/validation proje"):
        v6.girdileri_oku(a, capa, {v6.sha256(tr[0]["proje"].encode())})


def test_harici_decompile_cache_ana_hat_ciktisi_sayilmaz(girdi):
    a, _, va, capa = girdi
    yaz(a.valid_v6, [{"id": r["id"], "decompile": "return 1;", "sizinti": False} for r in va])
    muhurlu_manifest(a)
    with pytest.raises(ValueError, match="Ana hazırlayıcı"):
        v6.girdileri_oku(a, capa, set())


def test_ana_hat_anonimlestirme_ve_girdi_sozlesmesi(girdi):
    a, _, _, capa = girdi
    veriler, iz = v6.girdileri_oku(a, capa, set())
    once = copy.deepcopy(veriler)
    p1, secili = v6.planla(a, veriler, iz)
    for r in secili:
        kontrol = v6.mesajlar(r, veriler["train"][1], "asm")
        combined = v6.mesajlar(r, veriler["train"][1], "combined")
        assert kontrol[0]["content"] == v6.SISTEM_V6 and kontrol[0] == combined[0]
        assert kontrol[2] == combined[2] == r["messages"][2]
        assert kontrol[1] == r["messages"][1]
        assert combined == veriler["train"][1][r["id"]]["messages"]
    a.micro_batch = 4
    p2, secili2 = v6.planla(a, veriler, iz)
    assert p1["train_order_sha256"] == p2["train_order_sha256"] and secili == secili2
    assert veriler == once


@pytest.mark.parametrize(
    "alan,deger",
    [
        ("steps", 0),
        ("steps", 3),
        ("micro_batch", 3),
        ("max_length", 257),
        ("max_new_tokens", 256),
        ("max_train_tokens", 1),
    ],
)
def test_hesap_sinirlari(girdi, alan, deger):
    a, _, _, capa = girdi
    veriler, iz = v6.girdileri_oku(a, capa, set())
    setattr(a, alan, deger)
    with pytest.raises(ValueError):
        v6.planla(a, veriler, iz)


def test_cpu_plan_gpu_ag_ve_ozel_yol_kullanmaz(girdi, monkeypatch, capsys):
    a, tr, va, capa = girdi
    asil = builtins.__import__

    def sinirli(ad, *args, **kwargs):
        if ad.split(".")[0] in {"torch", "transformers", "peft", "datasets", "accelerate", "molab"}:
            raise AssertionError("CPU plan GPU bağımlılığı açtı")
        return asil(ad, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", sinirli)
    monkeypatch.setattr(socket.socket, "connect", lambda *args: pytest.fail("ağ kullanılmamalı"))
    monkeypatch.setattr(v6, "valid_capasi", lambda: capa)
    argv = ["plan", "--steps", "1", "--max-length", "256", "--max-new-tokens", "16"]
    for alan in ("train", "valid", "train_v6", "valid_v6", "dogrulama_raporu", "dogrulanmis_idler", "output"):
        argv.extend(["--" + alan.replace("_", "-"), str(getattr(a, alan))])
    v6.main(argv)
    metin = capsys.readouterr().out
    plan = json.loads(metin)
    assert plan["train_rows_per_arm"] == 16 and plan["api_calls"] == 0 and plan["gpu_seconds"] is None
    assert plan["system_sha256"] == v6.sha256(v6.SISTEM_V6.encode())
    assert str(a.output.parent) not in metin
    for r in tr + va:
        assert r["id"] not in metin and r["gercek_ad"] not in metin


def test_mevcut_cikti_ve_ayni_fiziksel_girdi_reddedilir(girdi):
    a, _, _, capa = girdi
    a.valid.unlink()
    a.valid.symlink_to(a.train)
    with pytest.raises(ValueError, match="ayrı dosya"):
        v6.girdileri_oku(a, capa, set())
    with pytest.raises(FileExistsError):
        v6.yeni_cikti(a.train.parent)
    with pytest.raises(ValueError, match="repo dışında"):
        v6.yeni_cikti(v6.KOK / "pilot-cikti")


class Tokenizer:
    def __init__(self):
        self.cagrilar = []

    def apply_chat_template(self, m, *, tokenize, add_generation_prompt, enable_thinking, return_dict):
        assert tokenize and not enable_thinking and return_dict is False
        self.cagrilar.append((copy.deepcopy(m), add_generation_prompt))
        ids = [1] + list(m[1]["content"].encode()) + [2]
        return ids if add_generation_prompt else ids + list(m[2]["content"].encode()) + [3]


def test_token_ve_uretim_siniri(girdi):
    a, _, _, capa = girdi
    veriler, _ = v6.girdileri_oku(a, capa, set())
    r, tok = veriler["valid"][0][0], Tokenizer()
    a.max_length = 1024
    kod = v6.kodla(r, veriler["valid"][1], "combined", tok, a)
    assert [m["role"] for m in tok.cagrilar[0][0]] == ["system", "user"]
    assert r["gercek_ad"] not in json.dumps(tok.cagrilar[0][0])
    a.max_length = len(kod["input_ids"]) - 1
    with pytest.raises(ValueError, match="kesilmedi"):
        v6.kodla(r, veriler["valid"][1], "combined", tok, a)


def test_kanonik_skor_ve_paired_proje_bootstrap():
    capa = [{"id": f"synthetic:{i}", "proje": f"p{i % 2}", "opt": "-O2", "gercek": "synthetic_alpha"} for i in range(6)]
    kontrol = [{**r, "tahmin": "alpha", "f1": v6.f1("alpha", r["gercek"]), "gecerli_json": True} for r in capa]
    birlesik = [{**r, "tahmin": r["gercek"], "f1": 1.0, "gecerli_json": True} for r in capa]
    sonuc = v6.karsilastir(kontrol, birlesik, capa)
    assert sonuc["canonical_f1_delta"] == pytest.approx(1 / 3)
    assert sonuc["paired_project_bootstrap_95"] == pytest.approx([1 / 3, 1 / 3])
    assert sonuc["pilot_pass"] and not v6.karsilastir(kontrol, kontrol, capa)["pilot_pass"]
    birlesik[0]["f1"] -= 0.001
    with pytest.raises(ValueError, match="kanonik"):
        v6.karsilastir(kontrol, birlesik, capa)


def _hedefli(i, gercek, hedef_ad, user):
    r = satir(i, "wrap")
    hedef = json.loads(r["messages"][2]["content"])
    hedef["ad"] = hedef_ad
    r["gercek_ad"] = gercek
    r["id"] = f"wrap/synthetic:{i}:{gercek}"
    r["messages"][1]["content"] = user
    r["messages"][2]["content"] = json.dumps(hedef)
    return r


BAGLAM = v6.hs.h.BAGLAM_BASLIK


@pytest.mark.parametrize(
    "gercek,hedef_ad,user",
    [
        # Gerçek release'teki sabit valid satırı: öneksiz hedef sarmalanan import'un kendisi.
        ("sigar_statvfs", "statvfs", "push\trbp\ncall\tstatvfs    ; -> statvfs\npop\trbp\nret"),
        ("janet_asin", "asin", "jmp\tasin    ; -> asin"),
        # Hedef bir komut adıyla çakışıyor; komut program tanımlayıcısı değildir.
        ("stack_push", "push", "push\trbp\nmov\trbp, rsp\nret"),
        # Bağlamın sabit `string` etiketi hedef değildir.
        ("janet_string", "string", "call\tsub_0001\nret" + BAGLAM + 'sub_0001 (3 komut): çağırır abort; string "x"'),
        # Ham addan farklı dış semboller: tanımlı fonksiyonun kendisi olamaz.
        ("Abort", "Abort", "call\tabort    ; -> abort"),
        ("mi_is_redirected", "is_redirected", "call\t_mi_is_redirected    ; -> _mi_is_redirected"),
    ],
)
def test_stripped_binaryde_gorunen_adlar_sizinti_sayilmaz(gercek, hedef_ad, user):
    v6.sema_dogrula(_hedefli(1, gercek, hedef_ad, user))


@pytest.mark.parametrize(
    "user",
    [
        "call\tsigar_statvfs",  # import yorumu olmayan ham ad
        "call\tstatvfs    ; -> statvfs" + BAGLAM + "sub_0002 (4 komut): çağırır sigar_statvfs_impl\nsigar_statvfs",
        "lea\trdi, [rip + sigar_statvfs]",
    ],
)
def test_ham_ad_import_disinda_hala_reddedilir(user):
    with pytest.raises(ValueError, match="öneksiz hedef"):
        v6.sema_dogrula(_hedefli(2, "sigar_statvfs", "statvfs", user))


def test_decompile_basliginda_ham_ad_import_olsa_da_reddedilir(monkeypatch):
    monkeypatch.setattr(v6.hs.h, "TOK", HazirlamaTokenizer())
    r = _hedefli(3, "sigar_statvfs", "statvfs", "call\tstatvfs    ; -> statvfs\nret")
    s = hazir_v6([r])[0]
    s["messages"][1]["content"] += "\nint _sigar_statvfs(void) { return 0; }"
    with pytest.raises(ValueError, match="öneksiz hedef"):
        v6.sema_dogrula(s, "v6")


def test_ana_hattin_cikardigi_sizintili_decompile_kabul_kirli_olan_red(monkeypatch):
    monkeypatch.setattr(v6.hs.h, "TOK", HazirlamaTokenizer())
    r = _hedefli(4, "wrap_open", "open_thing", "mov\teax, 1\nret")
    a = SimpleNamespace(max_uzunluk=4096, decompile_alt_token=1)
    ham = {"id": r["id"], "ad": r["gercek_ad"], "proje": r["proje"], "asm": r["messages"][1]["content"]}
    dc = {"id": r["id"], "decompile": "int sub_0004(void) { return wrap_open(); }", "sizinti": True}
    s = v6.hs.satir_v6(ham, None, None, a, dc, taban_satir=r)
    s["token"] = {"girdi": 50, "hedef": 20, "toplam": 100}
    # Ana hat sızıntıyı bulup decompile'ı girdiden çıkardı: satır temiz.
    assert s["decompile_sizinti"] and not s["decompile_var"] and v6.EK not in s["messages"][1]["content"]
    v6.sema_dogrula(s, "v6")
    kirli = copy.deepcopy(hazir_v6([r])[0])
    kirli["decompile_sizinti"] = True
    with pytest.raises(ValueError, match="bayrakları"):
        v6.sema_dogrula(kirli, "v6")
