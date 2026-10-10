"""GPU/ağ olmadan sürümlü molab notebook sözleşmesini denetle."""

import ast
import importlib.util
import json
import math
import os
import random
import re
import shutil
from pathlib import Path

import pytest

import taban

KOK = Path(__file__).resolve().parents[1]
SAF = {
    "ad_ayikla",
    "kelimeler",
    "f1",
    "hf_klasoru",
    "veri_sirasi",
    "sablon_ids",
    "kodla",
    "egitim_ayarlari",
    "hf_paketle",
}


def molab_kaynagi():
    agac = ast.parse((KOK / "molab/egit.py").read_text())
    hucre = next(
        n
        for n in agac.body
        if isinstance(n, ast.FunctionDef) and any(isinstance(f, ast.FunctionDef) and f.name == "egit" for f in n.body)
    )
    return ast.Module(body=hucre.body[:-1], type_ignores=[])


@pytest.fixture
def yardimci():
    agac = molab_kaynagi()
    govde = [n for n in agac.body if isinstance(n, ast.FunctionDef) and n.name in SAF]
    alan = {"json": json, "re": re, "random": random, "os": os, "Path": Path, "math": math, "shutil": shutil}
    exec(compile(ast.Module(body=govde, type_ignores=[]), "notebook-saf", "exec"), alan)
    return alan


def test_molab_notebook_motoru_ayristirilabilir():
    assert any(isinstance(n, ast.FunctionDef) and n.name == "egit" for n in molab_kaynagi().body)


@pytest.mark.parametrize(
    "tahmin,gercek",
    [
        ("", ""),
        ("foo", "foo_foo"),
        ("SSLRead", "SSL_read"),
        ("avCodecOpen", "av_codec_open2"),
        ("_fooBar", "foo_bar"),
        ("get-name", "get_name"),
        ("foo", "bar"),
        ("çözüm_adı", "ÇözümAdı"),
    ],
)
def test_f1_taban_ile_ayni(yardimci, tahmin, gercek):
    assert yardimci["f1"](tahmin, gercek) == taban.f1(tahmin, gercek)


@pytest.mark.parametrize(
    "metin,ad,en,tr,gecerli",
    [
        ('{"aciklama_en":"Read.","ad":"read_data","aciklama":"Oku."}', "read_data", "Read.", "Oku.", True),
        ('{"ad":"open_file"}', "open_file", "", "", True),
        ('{"aciklama":"Oku.","ad":"read","aciklama_en":"Read."}', "read", "Read.", "Oku.", True),
        ('```json\n{"ad":"open_file"}\n```', "open_file", "", "", True),
        ('{"aciklama_en":"Read.","ad":"read_data",', "read_data", "Read.", "", False),
        ('{"ad":"read_da', "ad", "", "", False),
        ("read_data", "read_data", "", "", False),
        ("", "", "", "", False),
    ],
)
def test_ayristirma(yardimci, metin, ad, en, tr, gecerli):
    assert yardimci["ad_ayikla"](metin) == (ad, en, tr, gecerli)


def test_ayristirma_asil_modulle_ayni(yardimci):
    yol = KOK / "lora/cikti.py"
    if not yol.exists():
        pytest.skip("lora/cikti.py paralel veri işinde hazırlanıyor")
    asil = next(n for n in ast.parse(yol.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == "ad_ayikla")
    kopya = next(n for n in molab_kaynagi().body if isinstance(n, ast.FunctionDef) and n.name == "ad_ayikla")
    assert ast.dump(kopya) == ast.dump(asil)
    spec = importlib.util.spec_from_file_location("v5_cikti_sozlesme", yol)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    ornekler = [
        '{"ad":"foo_bar"}',
        '{"aciklama":"TR","ad":"foo","aciklama_en":"EN"}',
        '```json\n{"ad":"foo"}\n```',
        '{"aciklama_en":"a","ad":"foo",',
        '{"ad":"foo',
        "foo_bar",
        "",
        "!!!",
        '{"ad":"foo\\u005fbar"}',
        '{"aciklama_en":"brace { in string","ad":"foo"}',
    ]
    for metin in ornekler:
        assert yardimci["ad_ayikla"](metin) == modul.ad_ayikla(metin), metin


@pytest.mark.parametrize(
    "adim,ad",
    [(0, "adim-00000"), (20, "adim-00020"), (500, "adim-00500"), (5938, "adim-05938"), (100000, "adim-100000")],
)
def test_hf_klasoru(yardimci, adim, ad):
    assert yardimci["hf_klasoru"](adim) == ad


@pytest.mark.parametrize("adim", [-1, True, 1.5, "500"])
def test_hf_klasoru_gecersiz(yardimci, adim):
    with pytest.raises(ValueError):
        yardimci["hf_klasoru"](adim)


def test_sira_tum_veriyi_korur_ve_mikro_batchten_bagimsiz(yardimci):
    satirlar = [{"messages": [{"content": "x" * (i % 100)}]} for i in range(1635)]
    sira = yardimci["veri_sirasi"](satirlar)
    assert sorted(sira) == list(range(len(satirlar)))
    assert sira == yardimci["veri_sirasi"](satirlar)
    assert sira != yardimci["veri_sirasi"](satirlar, 8)
    # İki mikro batch seçimi optimizer adımı başına aynı 16 örneği tüketir.
    for mikro in (1, 4, 8):
        gruplar = [sira[i : i + mikro] for i in range(0, len(sira), mikro)]
        assert [i for grup in gruplar[: 16 // mikro] for i in grup] == sira[:16]


class SahteTokenizer:
    def apply_chat_template(self, mesajlar, *, tokenize, add_generation_prompt, enable_thinking, return_dict=True):
        assert tokenize and not enable_thinking
        ids = [1, 2, 3] if add_generation_prompt else [1, 2, 3, 4, 5, 6]
        # transformers 5 gibi: return_dict yoksa sözlük döner
        return ids if return_dict is False else {"input_ids": ids, "attention_mask": [1] * len(ids)}


class SozlukTokenizer(SahteTokenizer):
    def apply_chat_template(self, *a, **k):
        k["return_dict"] = True
        return super().apply_chat_template(*a, **k)


def test_yalniz_assistant_kaybi_ve_json_hedef(yardimci):
    satir = {
        "id": "a",
        "messages": [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "u"},
            {"role": "assistant", "content": '{"aciklama_en":"Read.","ad":"read","aciklama":"Oku."}'},
        ],
    }
    kod = yardimci["kodla"](satir, SahteTokenizer())
    assert kod["labels"] == [-100, -100, -100, 4, 5, 6]
    assert yardimci["kodla"](satir, SozlukTokenizer())["labels"] == [-100, -100, -100, 4, 5, 6]
    assert len(kod["attention_mask"]) == len(kod["input_ids"]) == 6
    with pytest.raises(ValueError, match="veriyi bu tokenizer"):
        yardimci["kodla"](satir, SahteTokenizer(), 5)


def test_tokensiz_tam_egitim_engellenir(yardimci, monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("MAX_ADIM", "0")
    with pytest.raises(RuntimeError, match="HF_TOKEN eksik"):
        yardimci["egitim_ayarlari"]("molab")
    monkeypatch.setenv("MAX_ADIM", "20")
    monkeypatch.setenv("DEVAM", "0")
    assert yardimci["egitim_ayarlari"]("molab")["max_adim"] == 20


def test_v6_varsayilanlari_ve_v5_yeniden_uretim_ayari(yardimci, monkeypatch):
    for ad in ("VERI_SURUM", "VERI_URL", "HF_REPO", "ASM_KOK", "MIKRO_BATCH", "GRAD_CKPT"):
        monkeypatch.delenv(ad, raising=False)
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    monkeypatch.setenv("MAX_ADIM", "0")
    v6 = yardimci["egitim_ayarlari"]("molab")
    assert v6["surum"] == "v6"
    assert v6["veri_url"].endswith("/download/v6/veri-v6.zip")
    assert v6["repo"] == "krxi123/asmsense-lora-v6"
    assert v6["kok"].name == "asm-calisma-v6"
    assert v6["mikro"] == 2 and not v6["grad_ckpt"]

    monkeypatch.setenv("VERI_SURUM", "v5")
    v5 = yardimci["egitim_ayarlari"]("molab")
    assert v5["veri_url"].endswith("/download/v5/veri-v5.zip")
    assert v5["repo"] == "krxi123/asmsense-lora-v5"
    assert v5["kok"].name == "asm-calisma-v5"
    monkeypatch.setenv("VERI_SURUM", "v7")
    with pytest.raises(ValueError, match="v5 veya v6"):
        yardimci["egitim_ayarlari"]("molab")


def test_molab_hiperparametreleri_ve_devam_durumu_sabit():
    kaynak = (KOK / "molab/egit.py").read_text()
    for parca in (
        "r=16, lora_alpha=32, lora_dropout=0.05",
        'target_modules="all-linear"',
        "learning_rate=1e-4",
        'lr_scheduler_type="cosine"',
        "warmup_steps=math.ceil(toplam_adim * 0.03)",
        'gradient_accumulation_steps=16 // ayar["mikro"]',
        "num_train_epochs=1",
        "seed=7, data_seed=7",
        "eval_steps=500",
        "save_steps=500",
        "enable_thinking=False, return_dict=False",
        'for ad in ("optimizer.pt", "scheduler.pt", "rng_state.pth", "trainer_state.json")',
        "resume_from_checkpoint=str(devam_yolu)",
    ):
        assert parca in kaynak


def test_token_ayarlara_ve_ciktiya_sizmaz(yardimci, monkeypatch, capsys):
    monkeypatch.setenv("HF_TOKEN", "hf_test_gizli_deger")
    monkeypatch.setenv("MAX_ADIM", "0")
    ayar = yardimci["egitim_ayarlari"]("molab")
    assert "hf_test_gizli_deger" not in repr(ayar) + capsys.readouterr().out


def test_notebook_kod_hucreleri_gecerli():
    notebook = json.loads((KOK / "colab/egit_sonraki.ipynb").read_text())
    for hucre in notebook["cells"]:
        if hucre["cell_type"] == "code":
            kod = "".join(s for s in hucre["source"] if not s.startswith("%"))
            ast.parse(kod)
            assert not hucre["outputs"]



def test_colab_motoru_molab_ile_ayni():
    notebook = json.loads((KOK / "colab/egit_sonraki.ipynb").read_text())
    motor = ast.parse("".join(notebook["cells"][5]["source"]))
    assert ast.dump(motor) == ast.dump(molab_kaynagi())


@pytest.fixture
def colab_ortami(monkeypatch):
    for ad in ("VERI_SURUM", "VERI_URL", "HF_REPO", "MODEL", "ASM_KOK", "DRIVE_KOK",
               "MIKRO_BATCH", "GRAD_CKPT", "DEVAM", "MAX_ADIM", "HF_TOKEN"):
        monkeypatch.delenv(ad, raising=False)
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    notebook = json.loads((KOK / "colab/egit_sonraki.ipynb").read_text())
    ayarlar = ast.parse("".join(notebook["cells"][3]["source"]))
    # Drive ve secrets API'sini çağırmadan gerçek notebook varsayılanlarını çalıştır.
    govde = [n for n in ayarlar.body if isinstance(n, ast.Assign) or (
        isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
        and ast.unparse(n.value.func) == "os.environ.setdefault"
    )]
    return compile(ast.Module(body=govde, type_ignores=[]), "colab-ayarlar", "exec")


@pytest.mark.parametrize("surum", ["v5", "v6"])
def test_colab_surumu_yollari_ve_molab_hiperparametreleri(yardimci, colab_ortami, monkeypatch, surum):
    if surum == "v5":
        monkeypatch.setenv("VERI_SURUM", surum)
    exec(colab_ortami, {"os": os})
    ayar = yardimci["egitim_ayarlari"]("colab")
    assert ayar["surum"] == surum
    assert ayar["repo"] == f"krxi123/asmsense-lora-{surum}"
    assert ayar["veri_url"] == f"https://github.com/krxi/asmsense-data/releases/download/{surum}/veri-{surum}.zip"
    assert ayar["kok"].name == f"asm-{surum}-Qwen3-8B"
    assert str(ayar["drive"]).endswith(f"asm-adlandirma-{surum}/Qwen3-8B")
    assert ayar["model"] == "Qwen/Qwen3-8B"
    assert ayar["mikro"] == 2 and not ayar["grad_ckpt"]
    assert ayar["max_adim"] == 20 and not ayar["devam"]


def test_colab_devam_ortam_ayarlarini_korur(yardimci, colab_ortami, monkeypatch):
    for ad, deger in (("MAX_ADIM", "0"), ("DEVAM", "1"), ("MIKRO_BATCH", "1"), ("GRAD_CKPT", "1"),
                      ("MODEL", "Qwen/Qwen3.5-9B"), ("HF_REPO", "test/asmsense-v6-9b")):
        monkeypatch.setenv(ad, deger)
    exec(colab_ortami, {"os": os})
    ayar = yardimci["egitim_ayarlari"]("colab")
    assert ayar["devam"] and ayar["max_adim"] == 0
    assert ayar["model"] == "Qwen/Qwen3.5-9B" and ayar["repo"] == "test/asmsense-v6-9b"
    assert ayar["mikro"] == 1 and ayar["grad_ckpt"]

def test_hf_paketi_adaptor_ve_tam_durumu_ayirir(yardimci, tmp_path):
    kaynak, paket = tmp_path / "checkpoint-500", tmp_path / "paket"
    kaynak.mkdir()
    dosyalar = (
        "adapter_model.safetensors",
        "adapter_config.json",
        "optimizer.pt",
        "scheduler.pt",
        "rng_state.pth",
        "trainer_state.json",
        "training_args.bin",
        "tokenizer.json",
        "model.safetensors",
    )
    for ad in dosyalar:
        (kaynak / ad).write_text(ad)
    yardimci["hf_paketle"](kaynak, paket, 500)
    for ad in ("adim-00500", "son"):
        assert {p.name for p in (paket / ad).iterdir()} == {"adapter_model.safetensors", "adapter_config.json"}
    assert {p.name for p in (paket / "durum/son").iterdir()} == {
        "optimizer.pt",
        "scheduler.pt",
        "rng_state.pth",
        "trainer_state.json",
        "training_args.bin",
    }
    assert not list(paket.rglob("tokenizer.json"))
    assert not list(paket.rglob("model.safetensors"))


def test_hf_paketi_eksik_optimizer_ile_basari_sayilmaz(yardimci, tmp_path):
    kaynak = tmp_path / "kaynak"
    kaynak.mkdir()
    for ad in ("adapter_model.safetensors", "adapter_config.json"):
        (kaynak / ad).write_text("test")
    with pytest.raises(FileNotFoundError):
        yardimci["hf_paketle"](kaynak, tmp_path / "paket", 20)
