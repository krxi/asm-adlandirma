# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "transformers",
#     "peft",
#     "bitsandbytes>=0.46.1",
#     "accelerate",
#     "datasets",
#     "torch",
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.15.2"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.md(
        r"""
        # Sembolsüz x86-64 fonksiyon adlandırma — QLoRA

        Bu notebook, v4 ölçek verisini Qwen2.5-Coder üzerinde 4-bit QLoRA ile
        yalnız `ad` hedefi için eğitir. Kayıp yalnız assistant yanıtında
        hesaplanır. Tam eğitimden sonra tohumlu en çok 2.000 test örneği ile
        sabit 115 örneklik eski küme ayrı ölçülür.

        Çalışma kökü `ASM_KOK` ortam değişkeniyle seçilebilir. Kısa bir hız
        denemesi için çalıştırmadan önce örneğin `MAX_ADIM=20` verin; bu modda
        değerlendirme ve kayıt adımları atlanır.
        """
    )
    return


@app.cell
def _():
    import gc
    import importlib.util
    import json
    import math
    import os
    import random
    import re
    import shutil
    import time
    import urllib.request
    import zipfile
    from pathlib import Path

    import marimo as mo
    import torch
    from datasets import load_dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from tqdm.auto import tqdm
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        DataCollatorForSeq2Seq,
        Trainer,
        TrainerCallback,
        TrainingArguments,
        set_seed,
    )
    from transformers.trainer_utils import get_last_checkpoint

    return (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        DataCollatorForSeq2Seq,
        LoraConfig,
        Path,
        Trainer,
        TrainerCallback,
        TrainingArguments,
        gc,
        get_last_checkpoint,
        get_peft_model,
        importlib,
        json,
        load_dataset,
        math,
        mo,
        os,
        prepare_model_for_kbit_training,
        random,
        re,
        set_seed,
        shutil,
        time,
        torch,
        tqdm,
        urllib,
        zipfile,
    )


@app.cell
def _(Path, importlib, os, torch):
    def ortam_tamsayisi(ad: str, varsayilan: int) -> int:
        ham = os.environ.get(ad)
        if ham is None:
            return varsayilan
        try:
            return int(ham)
        except ValueError as hata:
            raise ValueError(f"{ad} bir tamsayı olmalı; gelen değer: {ham!r}") from hata


    KOK = Path(os.environ.get("ASM_KOK", Path.cwd() / "asm-calisma")).expanduser().resolve()
    KOK.mkdir(parents=True, exist_ok=True)

    MODEL = os.environ.get("MODEL", "Qwen/Qwen2.5-Coder-7B-Instruct")
    L4_MODELI = os.environ.get("L4_MODELI", "Qwen/Qwen2.5-Coder-3B-Instruct")
    BELLEGE_GORE_MODEL_SEC = os.environ.get("BELLEGE_GORE_MODEL_SEC", "1") == "1"

    MAX_UZUNLUK = ortam_tamsayisi("MAX_UZUNLUK", 2304)
    ETKIN_BATCH = 16
    MIKRO_BATCH = ortam_tamsayisi("MIKRO_BATCH", 8)
    GRAD_CKPT = ortam_tamsayisi("GRAD_CKPT", 0)
    MAX_ADIM = ortam_tamsayisi("MAX_ADIM", 0)
    EPOCH = 2.0
    MAX_ORNEK = 41000
    VALID_TAVAN = 500
    TEST_TAVAN = 2000
    TOHUM = 7

    if GRAD_CKPT not in (0, 1):
        raise ValueError("GRAD_CKPT yalnız 0 veya 1 olabilir.")
    if MIKRO_BATCH <= 0 or ETKIN_BATCH % MIKRO_BATCH:
        raise ValueError("MIKRO_BATCH pozitif olmalı ve 16 değerini tam bölmeli.")
    if MAX_ADIM < 0:
        raise ValueError("MAX_ADIM negatif olamaz.")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU bulunamadı; molab oturumunda GPU seçin.")
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError("Bu notebook bf16 destekli bir GPU bekliyor.")

    _gpu = torch.cuda.get_device_properties(0)
    bellek_gb = _gpu.total_memory / 1024**3
    SECILEN_MODEL = (
        MODEL if not (BELLEGE_GORE_MODEL_SEC and bellek_gb < 35) else L4_MODELI
    )
    model_kisa = SECILEN_MODEL.rsplit("/", 1)[-1]
    BIRIKIM_ADIMI = ETKIN_BATCH // MIKRO_BATCH
    DENEME_MODU = MAX_ADIM > 0
    # molab'da flash-attn-4 kurulu; transformers'ın flash_attention_2 yolu onu kullanamıyor.
    ATTN_IMPLEMENTATION = os.environ.get("ATTN", "sdpa")

    print(f"Çalışma kökü: {KOK}")
    print(f"GPU: {_gpu.name} ({bellek_gb:.1f} GB)")
    print(f"Model: {SECILEN_MODEL}")
    print(f"Attention: {ATTN_IMPLEMENTATION}")
    print(f"Etkin batch: {MIKRO_BATCH} × {BIRIKIM_ADIMI} = {ETKIN_BATCH}")
    print(f"Gradient checkpointing: {bool(GRAD_CKPT)}")
    print(f"Mod: {'deneme' if DENEME_MODU else 'tam eğitim'}")

    return (
        ATTN_IMPLEMENTATION,
        BIRIKIM_ADIMI,
        DENEME_MODU,
        EPOCH,
        ETKIN_BATCH,
        GRAD_CKPT,
        KOK,
        MAX_ADIM,
        MAX_ORNEK,
        MAX_UZUNLUK,
        MIKRO_BATCH,
        SECILEN_MODEL,
        TEST_TAVAN,
        TOHUM,
        VALID_TAVAN,
        model_kisa,
    )


@app.cell
def _(KOK, Path, urllib, zipfile):
    VERI_URL = "https://github.com/krxi/asm-adlandirma-veri/releases/download/v4/veri-olcek-v4.zip"
    veri_zip_yolu = KOK / "veri-olcek-v4.zip"
    veri_acma_dizini = KOK / "veri-olcek-v4"
    zorunlu_dosyalar = ("train.jsonl", "valid.jsonl", "test.jsonl", "eval115.jsonl")

    def veri_dizinini_bul(kok: Path) -> Path | None:
        _adaylar = [kok]
        if kok.is_dir():
            _adaylar.extend(sorted({_p.parent for _p in kok.rglob("train.jsonl")}))
        for _aday in _adaylar:
            if all((_aday / _ad).is_file() for _ad in zorunlu_dosyalar):
                return _aday
        return None


    if veri_zip_yolu.is_file():
        print(f"Veri arşivi hazır, indirme atlandı: {veri_zip_yolu}")
    else:
        _gecici_zip = veri_zip_yolu.with_suffix(".zip.part")
        print(f"Veri indiriliyor: {VERI_URL}")
        with urllib.request.urlopen(VERI_URL) as _yanit, _gecici_zip.open("wb") as _cikti:
            while True:
                _parca = _yanit.read(1024 * 1024)
                if not _parca:
                    break
                _cikti.write(_parca)
        _gecici_zip.replace(veri_zip_yolu)

    VERI_DIZINI = veri_dizinini_bul(veri_acma_dizini)
    if VERI_DIZINI is None:
        veri_acma_dizini.mkdir(parents=True, exist_ok=True)
        print(f"Veri arşivi açılıyor: {veri_acma_dizini}")
        with zipfile.ZipFile(veri_zip_yolu) as _arsiv:
            _arsiv.extractall(veri_acma_dizini)
        VERI_DIZINI = veri_dizinini_bul(veri_acma_dizini)
    if VERI_DIZINI is None:
        raise FileNotFoundError(
            f"Arşivde gerekli JSONL dosyaları bulunamadı: {zorunlu_dosyalar}"
        )

    for _ad in ("train", "valid", "test", "eval115"):
        _yol = VERI_DIZINI / f"{_ad}.jsonl"
        with _yol.open(encoding="utf-8") as _dosya:
            _adet = sum(1 for _satir in _dosya if _satir.strip())
        print(f"{_ad:>7}: {_adet:>6} satır  ({_yol})")

    return VERI_DIZINI, VERI_URL, veri_zip_yolu


@app.cell
def _(
    ATTN_IMPLEMENTATION,
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    GRAD_CKPT,
    LoraConfig,
    SECILEN_MODEL,
    TOHUM,
    get_peft_model,
    os,
    prepare_model_for_kbit_training,
    set_seed,
    torch,
):
    set_seed(TOHUM)
    tokenizer = AutoTokenizer.from_pretrained(SECILEN_MODEL, use_fast=True)
    tokenizer.padding_side = "right"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    # NICELEME=0: 96 GB'lık kartta 4-bit'e gerek yok; bf16 taban + aynı LoRA çok daha hızlı.
    NICELEME = os.environ.get("NICELEME", "1") == "1"
    niceleme = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    ) if NICELEME else None
    model = AutoModelForCausalLM.from_pretrained(
        SECILEN_MODEL,
        quantization_config=niceleme,
        torch_dtype=torch.bfloat16,
        device_map={"": 0},
        attn_implementation=ATTN_IMPLEMENTATION,
    )
    model.config.use_cache = False
    if NICELEME:
        model = prepare_model_for_kbit_training(
            model,
            use_gradient_checkpointing=GRAD_CKPT,
            gradient_checkpointing_kwargs={"use_reentrant": False},
        )
    elif GRAD_CKPT:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
    print(f"4-bit niceleme: {NICELEME}")
    model = get_peft_model(
        model,
        LoraConfig(
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules="all-linear",
        ),
    )
    model.print_trainable_parameters()
    return model, tokenizer


@app.cell
def _(
    EPOCH,
    ETKIN_BATCH,
    MAX_ADIM,
    MAX_ORNEK,
    MAX_UZUNLUK,
    TOHUM,
    VALID_TAVAN,
    VERI_DIZINI,
    json,
    load_dataset,
    math,
    tokenizer,
):
    ham_veri = load_dataset(
        "json",
        data_files={
            "train": str(VERI_DIZINI / "train.jsonl"),
            "validation": str(VERI_DIZINI / "valid.jsonl"),
        },
    )
    if MAX_ORNEK and len(ham_veri["train"]) > MAX_ORNEK:
        ham_veri["train"] = ham_veri["train"].shuffle(seed=TOHUM).select(
            range(MAX_ORNEK)
        )
    ham_veri["validation"] = ham_veri["validation"].shuffle(seed=TOHUM).select(
        range(min(VALID_TAVAN, len(ham_veri["validation"])))
    )

    def kodla(ornek):
        _mesajlar = ornek["messages"]
        if [_m["role"] for _m in _mesajlar] != ["system", "user", "assistant"]:
            raise ValueError("Beklenen mesaj sırası: system, user, assistant")
        _hedef = json.loads(_mesajlar[2]["content"])
        if set(_hedef) != {"ad"}:
            raise ValueError(f"Hedef yalnız ad içermeli: {_hedef}")

        _istem = tokenizer.apply_chat_template(
            _mesajlar[:2], tokenize=True, add_generation_prompt=True, return_dict=False
        )
        _tumu = tokenizer.apply_chat_template(
            _mesajlar, tokenize=True, add_generation_prompt=False, return_dict=False
        )
        if _tumu[: len(_istem)] != _istem:
            raise ValueError("Sohbet şablonunda assistant başlangıcı belirlenemedi.")

        _tumu = _tumu[:MAX_UZUNLUK]
        _etiketler = [-100] * min(len(_istem), len(_tumu)) + _tumu[len(_istem) :]
        if not any(_x != -100 for _x in _etiketler):
            raise ValueError(
                "Yanıt MAX_UZUNLUK dışında kaldı; veri hazırlama tavanını düşürün."
            )
        return {
            "input_ids": _tumu,
            "attention_mask": [1] * len(_tumu),
            "labels": _etiketler,
            "uzunluk": len(_tumu),
        }


    tokenli_veri = ham_veri.map(
        kodla,
        remove_columns=ham_veri["train"].column_names,
        desc="Qwen sohbet şablonu uygulanıyor",
    )

    egitim_uzunluklari = tokenli_veri["train"]["uzunluk"]
    for _bolum in ("train", "validation"):
        _uzunluklar = tokenli_veri[_bolum]["uzunluk"]
        _p95 = sorted(_uzunluklar)[math.ceil(0.95 * len(_uzunluklar)) - 1]
        print(
            f"{_bolum:>10}: {len(_uzunluklar)} örnek; "
            f"ortalama {sum(_uzunluklar) / len(_uzunluklar):.0f}, "
            f"p95 {_p95}, en uzun {max(_uzunluklar)} token"
        )

    _ortalama_token = sum(egitim_uzunluklari) / len(egitim_uzunluklari)
    _adim_epoch = math.ceil(len(egitim_uzunluklari) / ETKIN_BATCH)
    _dogal_adim = math.ceil(_adim_epoch * EPOCH)
    _planlanan_adim = MAX_ADIM if MAX_ADIM > 0 else _dogal_adim
    _planlanan_token = round(_planlanan_adim * ETKIN_BATCH * _ortalama_token)
    print(
        f"Plan: {_planlanan_adim:,} adım, yaklaşık {_planlanan_token:,} token"
    )

    tokenli_veri = tokenli_veri.remove_columns("uzunluk")
    return ham_veri, kodla, tokenli_veri


@app.cell
def _(
    BIRIKIM_ADIMI,
    DENEME_MODU,
    DataCollatorForSeq2Seq,
    EPOCH,
    GRAD_CKPT,
    KOK,
    MAX_ADIM,
    MIKRO_BATCH,
    Path,
    TOHUM,
    Trainer,
    TrainerCallback,
    TrainingArguments,
    get_last_checkpoint,
    json,
    model,
    model_kisa,
    time,
    tokenizer,
    tokenli_veri,
):
    class DosyaLogCallback(TrainerCallback):
        """Eğitim kaybını dışarıdan tail edilebilen bir dosyaya yazar."""

        def __init__(self, log_yolu):
            self.log_yolu = log_yolu
            self.son_zaman = None
            self.son_adim = None

        def on_train_begin(self, args, state, control, **kwargs):
            self.son_zaman = time.monotonic()
            self.son_adim = state.global_step

        def on_log(self, args, state, control, logs=None, **kwargs):
            _loglar = logs or {}
            if "loss" not in _loglar or "learning_rate" not in _loglar:
                return
            _simdi = time.monotonic()
            _onceki_zaman = self.son_zaman if self.son_zaman is not None else _simdi
            _onceki_adim = self.son_adim if self.son_adim is not None else state.global_step
            _sure = max(_simdi - _onceki_zaman, 1e-9)
            _adim = max(state.global_step - _onceki_adim, 0)
            _it_s = _adim / _sure
            _satir = (
                f"step={state.global_step} "
                f"loss={float(_loglar['loss']):.6f} "
                f"lr={float(_loglar['learning_rate']):.8g} "
                f"it/s={_it_s:.4f}\n"
            )
            with self.log_yolu.open("a", encoding="utf-8") as _dosya:
                _dosya.write(_satir)
            self.son_zaman = _simdi
            self.son_adim = state.global_step


    DENETIM_DIZINI = KOK / f"denetim-{model_kisa}"
    DENETIM_DIZINI.mkdir(parents=True, exist_ok=True)
    EGITIM_LOGU = KOK / "egitim.log"

    _ayar = dict(
        output_dir=str(DENETIM_DIZINI),
        num_train_epochs=EPOCH,
        max_steps=MAX_ADIM if MAX_ADIM > 0 else -1,
        per_device_train_batch_size=MIKRO_BATCH,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=BIRIKIM_ADIMI,
        learning_rate=1e-4,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        optim="paged_adamw_8bit",
        bf16=True,
        tf32=True,
        gradient_checkpointing=GRAD_CKPT,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        max_grad_norm=0.3,
        eval_strategy="no" if DENEME_MODU else "steps",
        eval_steps=250,
        save_strategy="no" if DENEME_MODU else "steps",
        save_steps=250,
        save_total_limit=3,
        logging_steps=10,
        report_to="none",
        seed=TOHUM,
        data_seed=TOHUM,
        group_by_length=True,
        dataloader_num_workers=2,
        remove_unused_columns=False,
    )
    # transformers 5 bazı eski argümanları kaldırdı; kabul edilmeyenleri düşür ve yaz.
    import inspect as _inspect
    _kabul = set(_inspect.signature(TrainingArguments.__init__).parameters)
    if "warmup_ratio" not in _kabul and "warmup_ratio" in _ayar:
        _ayar["warmup_steps"] = _ayar.pop("warmup_ratio")  # v5: float oran kabul ediyor
    if "group_by_length" not in _kabul and "train_sampling_strategy" in _kabul:
        _ayar["train_sampling_strategy"] = "group_by_length" if _ayar.pop("group_by_length") else "random"
    _dusen = sorted(k for k in _ayar if k not in _kabul)
    if _dusen:
        print(f"TrainingArguments bu sürümde desteklemiyor, atlandı: {_dusen}")
    egitim_ayari = TrainingArguments(**{k: v for k, v in _ayar.items() if k in _kabul})

    veri_toplayici = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        padding=True,
        label_pad_token_id=-100,
        pad_to_multiple_of=8,
        return_tensors="pt",
    )
    egitici = Trainer(
        model=model,
        args=egitim_ayari,
        train_dataset=tokenli_veri["train"],
        eval_dataset=None if DENEME_MODU else tokenli_veri["validation"],
        data_collator=veri_toplayici,
        callbacks=[DosyaLogCallback(EGITIM_LOGU)],
    )
    son_checkpoint = get_last_checkpoint(str(DENETIM_DIZINI))
    if son_checkpoint:
        _durum_yolu = Path(son_checkpoint) / "trainer_state.json"
        if _durum_yolu.is_file():
            with _durum_yolu.open(encoding="utf-8") as _dosya:
                baslangic_adimi = int(json.load(_dosya).get("global_step", 0))
        else:
            baslangic_adimi = 0
    else:
        baslangic_adimi = 0
    print(f"Devam checkpoint'i: {son_checkpoint or 'yok; sıfırdan başlanacak'}")
    print(f"Dışarıdan izlenebilir log: {EGITIM_LOGU}")

    egitim_sonucu = egitici.train(resume_from_checkpoint=son_checkpoint)
    if not DENEME_MODU:
        egitici.evaluate()

    _train_runtime = float(egitim_sonucu.metrics.get("train_runtime", 0.0))
    _calisan_adim = max(egitici.state.global_step - baslangic_adimi, 0)
    _saniye_adim = _train_runtime / _calisan_adim if _calisan_adim else float("nan")
    _it_s = _calisan_adim / _train_runtime if _train_runtime else float("nan")
    print(f"train_runtime/adım: {_saniye_adim:.4f} s")
    print(f"it/s: {_it_s:.4f}")

    return (
        DENETIM_DIZINI,
        DosyaLogCallback,
        EGITIM_LOGU,
        baslangic_adimi,
        egitici,
        egitim_ayari,
        egitim_sonucu,
        son_checkpoint,
        veri_toplayici,
    )


@app.cell
def _(
    DENEME_MODU,
    KOK,
    Path,
    egitici,
    egitim_sonucu,
    mo,
    model_kisa,
    shutil,
    tokenizer,
):
    _ = egitim_sonucu
    ADAPTOR_DIZINI = KOK / f"adaptor-{model_kisa}"
    if DENEME_MODU:
        adaptor_zip_yolu = None
        adaptor_indirme = mo.md(
            "Deneme modunda adaptör kaydı ve zip oluşturma atlandı."
        )
        print("Deneme modu: adaptör kaydı atlandı.")
    else:
        egitici.save_model(str(ADAPTOR_DIZINI))
        tokenizer.save_pretrained(str(ADAPTOR_DIZINI))
        adaptor_zip_yolu = KOK / f"{ADAPTOR_DIZINI.name}.zip"
        _olusan_zip = shutil.make_archive(
            str(adaptor_zip_yolu.with_suffix("")),
            "zip",
            root_dir=ADAPTOR_DIZINI.parent,
            base_dir=ADAPTOR_DIZINI.name,
        )
        adaptor_zip_yolu = Path(_olusan_zip)
        print(f"Adaptör: {ADAPTOR_DIZINI}")
        print(
            f"İndirilebilir arşiv: {adaptor_zip_yolu} "
            f"({adaptor_zip_yolu.stat().st_size / 1024**2:.0f} MB)"
        )
        adaptor_indirme = mo.download(
            data=lambda: adaptor_zip_yolu.read_bytes(),
            filename=adaptor_zip_yolu.name,
            label="Adaptör zip'ini indir",
        )
    adaptor_indirme
    return ADAPTOR_DIZINI, adaptor_indirme, adaptor_zip_yolu


@app.cell
def _(
    DENEME_MODU,
    KOK,
    MAX_UZUNLUK,
    TEST_TAVAN,
    TOHUM,
    VERI_DIZINI,
    adaptor_zip_yolu,
    gc,
    json,
    mo,
    model,
    model_kisa,
    random,
    re,
    tokenizer,
    torch,
    tqdm,
):
    _ = adaptor_zip_yolu

    def kelimeler(ad: str) -> list[str]:
        _ad = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", ad)
        return [_k for _k in re.split(r"[_\W]+", _ad.lower()) if _k]


    def f1(tahmin: str, gercek: str) -> float:
        _t, _g = kelimeler(tahmin), kelimeler(gercek)
        _ortak = len(set(_t) & set(_g))
        if not _ortak:
            return 0.0
        _p, _r = _ortak / len(set(_t)), _ortak / len(set(_g))
        return 2 * _p * _r / (_p + _r)


    def oku_ve_ornekle(yol, tavan: int) -> list[dict]:
        with yol.open(encoding="utf-8") as _dosya:
            _satirlar = [json.loads(_satir) for _satir in _dosya if _satir.strip()]
        if tavan and len(_satirlar) > tavan:
            _satirlar = random.Random(TOHUM).sample(_satirlar, tavan)
        return _satirlar


    def olc(dosya: str, etiket: str, tavan: int):
        _satirlar = oku_ve_ornekle(VERI_DIZINI / dosya, tavan)
        _sonuclar = []
        for _kayit in tqdm(_satirlar, desc=f"Greedy {etiket} üretimi"):
            _mesajlar = _kayit["messages"][:2]
            _girdi = tokenizer.apply_chat_template(
                _mesajlar,
                tokenize=True,
                add_generation_prompt=True,
                return_tensors="pt",
                return_dict=False,
            ).to(model.device)
            if _girdi.shape[1] > MAX_UZUNLUK:
                raise ValueError(
                    f"Girdi {MAX_UZUNLUK} tokenı aşıyor: {_kayit.get('id')}"
                )
            with torch.inference_mode():
                _uretilen = model.generate(
                    input_ids=_girdi,
                    attention_mask=torch.ones_like(_girdi),
                    max_new_tokens=48,
                    do_sample=False,
                    use_cache=True,
                    pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                )
            _yeni_tokenlar = _uretilen[0, _girdi.shape[1] :]
            _metin = tokenizer.decode(_yeni_tokenlar, skip_special_tokens=True)
            _eslesmeler = re.findall(r"\{[^{}]*\}", _metin)
            try:
                _cevap = (
                    json.loads(_eslesmeler[-1])
                    if _eslesmeler
                    else {"ad": _metin.strip()[:60]}
                )
            except json.JSONDecodeError:
                _cevap = {}
            _tahmin = str(_cevap.get("ad", ""))
            _gercek = str(json.loads(_kayit["messages"][2]["content"])["ad"])
            _skor = f1(_tahmin, _gercek)
            _sonuclar.append(
                {
                    "id": _kayit.get("id", ""),
                    "gercek": _gercek,
                    "tahmin": _tahmin,
                    "aciklama": "",
                    "ogretmen": "",
                    "f1": round(_skor, 3),
                    "opt": _kayit.get("opt", ""),
                    "proje": _kayit.get("proje", ""),
                    "token": int(_girdi.shape[1] + _yeni_tokenlar.shape[0]),
                }
            )

        _sonuc_yolu = KOK / f"sonuc-{etiket}-{model_kisa}-lora.jsonl"
        with _sonuc_yolu.open("w", encoding="utf-8") as _dosya:
            for _sonuc in _sonuclar:
                _dosya.write(json.dumps(_sonuc, ensure_ascii=False) + "\n")
        _ortalama = sum(_r["f1"] for _r in _sonuclar) / len(_sonuclar)
        _tam = sum(_r["f1"] == 1 for _r in _sonuclar)
        print(
            f"{etiket}: ortalama F1 {_ortalama:.3f} "
            f"(n={len(_sonuclar)}, tam isabet {_tam})"
        )
        for _opt in ("-O0", "-O1", "-O2", "-O3", "-Os"):
            _alt = [_r["f1"] for _r in _sonuclar if _r["opt"] == _opt]
            if _alt:
                print(f"  {_opt}: {sum(_alt) / len(_alt):.3f} (n={len(_alt)})")
        print(f"ayrıntı → {_sonuc_yolu}")
        return _sonuc_yolu


    if DENEME_MODU:
        sonuc_yollari = []
        sonuc_indirmeleri = mo.md(
            "Deneme modunda `test` ve `eval115` değerlendirmesi atlandı."
        )
        print("Deneme modu: test/eval115 değerlendirmesi atlandı.")
    else:
        gc.collect()
        torch.cuda.empty_cache()
        model.config.use_cache = True
        model.eval()
        sonuc_yollari = [
            olc("test.jsonl", "test", TEST_TAVAN),
            olc("eval115.jsonl", "eval115", 0),
        ]
        sonuc_indirmeleri = mo.vstack(
            [
                mo.download(
                    data=lambda _yol=_yol: _yol.read_bytes(),
                    filename=_yol.name,
                    label=f"{_yol.name} indir",
                )
                for _yol in sonuc_yollari
            ]
        )
    sonuc_indirmeleri
    return f1, kelimeler, oku_ve_ornekle, olc, sonuc_indirmeleri, sonuc_yollari


if __name__ == "__main__":
    app.run()
