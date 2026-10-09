# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "transformers==5.3.0",
#     "peft==0.18.1",
#     "accelerate>=1.12,<2",
#     "datasets>=3,<5",
#     "huggingface_hub>=1.0,<2",
#     "torch>=2.6",
#     "marimo>=0.15.2",
# ]
# ///

import marimo

__generated_with = "0.15.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md(
        r"""
        # Fonksiyon adlandırma — v5 bf16 LoRA

        Tüm train, 1 epoch, etkin batch 16, tohum 7. Kayıp yalnız assistant JSON cevabında.
        Her 500 adımda valid_300: loss + greedy ad F1 + geçerli JSON oranı.
        HF private repo zorunlu; `MAX_ADIM=20` yalnız duman denemesidir (valid'den 10 satır).
        `DEVAM=1` son adaptörle birlikte optimizer/scheduler/RNG/adımı geri yükler.
        Tam eğitim sonunda yalnız valid F1 ile seçilen adaptör test_sabit ve eval115'te ölçülür.

        Paketleme: `group_by_length`. SDPA ve Qwen3.5 hibrit attention için dolgusuz
        örnek sınırları doğrulanmadığından DataCollatorWithFlattening kullanılmaz.
        Sıra ortak ham metin uzunluğuyla önceden hazırlanır; tokenizer ve mikro batch'ten bağımsızdır.
        """
    )
    return


@app.cell
def _():
    import hashlib
    import inspect
    import json
    import logging
    import math
    import os
    import random
    import re
    import shutil
    import sys
    import time
    import urllib.request
    import zipfile
    from pathlib import Path


    # lora/cikti.py ile aynı tutulmalı. Tek dosya notebook için çevrimdışı kopya.
    def ad_ayikla(metin: str) -> tuple[str, str, str, bool]:
        """JSON, kesik JSON ve düz metin için (ad, İngilizce, Türkçe, geçerli JSON)."""
        metin = metin.strip()
        # Kod çiti veya ön açıklama içindeki tamamlanmış JSON da kabul edilir.
        decoder = json.JSONDecoder()
        for bas in (m.start() for m in re.finditer(r"\{", metin)):
            try:
                veri, _ = decoder.raw_decode(metin[bas:])
            except ValueError:
                continue
            if isinstance(veri, dict) and isinstance(veri.get("ad"), str):
                return (veri["ad"], veri.get("aciklama_en") or "", veri.get("aciklama") or "", True)

        def alan(ad):
            es = re.search(r'"' + ad + r'"\s*:\s*("(?:\\.|[^"\\])*")', metin)
            if es:
                try:
                    return json.loads(es[1])
                except ValueError:
                    pass
            return ""

        ad = alan("ad")
        if ad:
            return ad, alan("aciklama_en"), alan("aciklama"), False
        es = re.search(r"[A-Za-z_][A-Za-z0-9_]*", metin)
        return (es[0] if es else ""), "", "", False

    def kelimeler(ad: str) -> list[str]:
        ad = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", ad)
        return [k for k in re.split(r"[_\W]+", ad.lower()) if k]


    def f1(tahmin: str, gercek: str) -> float:
        t, g = kelimeler(tahmin), kelimeler(gercek)
        ortak = len(set(t) & set(g))
        if not ortak:
            return 0.0
        p, r = ortak / len(set(t)), ortak / len(set(g))
        return 2 * p * r / (p + r)


    def hf_klasoru(adim):
        if isinstance(adim, bool) or not isinstance(adim, int) or adim < 0:
            raise ValueError("Adım negatif olmayan tamsayı olmalı.")
        return f"adim-{adim:05d}"


    def jsonl_oku(yol):
        with Path(yol).open(encoding="utf-8") as dosya:
            return [json.loads(satir) for satir in dosya if satir.strip()]


    def json_yaz(yol, veri):
        Path(yol).write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")


    def veri_sirasi(satirlar, tohum=7):
        # group_by_length: ortak ham metin uzunluğu; tokenizer/mikro batch bağımsız.
        # 16*50'lik karışık pencereler içinde uzunluğa göre grupla, sonra sabit sırayla tüket.
        indisler = list(range(len(satirlar)))
        random.Random(tohum).shuffle(indisler)
        uzunluk = lambda i: sum(len(m["content"]) for m in satirlar[i]["messages"])
        return [i for bas in range(0, len(indisler), 800)
                for i in sorted(indisler[bas:bas + 800], key=uzunluk, reverse=True)]


    def sablon_ids(tokenizer, mesajlar, uret):
        # transformers 5: tokenize=True varsayılan olarak BatchEncoding döndürür; list() anahtarları verir.
        cikti = tokenizer.apply_chat_template(
            mesajlar, tokenize=True, add_generation_prompt=uret, enable_thinking=False, return_dict=False,
        )
        if hasattr(cikti, "keys"):
            cikti = cikti["input_ids"]
        return list(cikti)


    def kodla(satir, tokenizer, max_uzunluk=3072):
        mesajlar = satir["messages"]
        if [m["role"] for m in mesajlar] != ["system", "user", "assistant"]:
            raise ValueError("Mesaj sırası system/user/assistant olmalı.")
        hedef = json.loads(mesajlar[-1]["content"])
        if not isinstance(hedef, dict) or not isinstance(hedef.get("ad"), str):
            raise ValueError("Assistant hedefi ad alanlı JSON olmalı.")
        istem = sablon_ids(tokenizer, mesajlar[:2], True)
        tumu = sablon_ids(tokenizer, mesajlar, False)
        if tumu[:len(istem)] != istem or len(tumu) <= len(istem):
            raise ValueError("Assistant sınırı doğrulanamadı; tokenizer şablonunu denetleyin.")
        # Tüm train kullanılır; taşma sessiz filtrelenmez/kesilmez, veri yeniden hazırlanır.
        if len(tumu) > max_uzunluk:
            raise ValueError(f"{satir['id']}: {len(tumu)} token > {max_uzunluk}; veriyi bu tokenizer ile kısaltın.")
        return {"input_ids": tumu, "attention_mask": [1] * len(tumu),
                "labels": [-100] * len(istem) + tumu[len(istem):]}



    def hf_paketle(kaynak, paket, adim):
        """Adaptör alanlarına yalnız iki dosya; devam durumu tek ayrı dizine."""
        kaynak, paket = Path(kaynak), Path(paket)
        paket.mkdir(parents=True, exist_ok=True)
        for hedef in (paket / hf_klasoru(adim), paket / "son"):
            hedef.mkdir(exist_ok=True)
            for ad in ("adapter_model.safetensors", "adapter_config.json"):
                shutil.copy2(kaynak / ad, hedef / ad)
        durum = paket / "durum/son"
        durum.mkdir(parents=True, exist_ok=True)
        for ad in ("optimizer.pt", "scheduler.pt", "rng_state.pth", "trainer_state.json", "training_args.bin"):
            shutil.copy2(kaynak / ad, durum / ad)


    def egitim_ayarlari(ortam):
        deneme = int(os.environ.get("MAX_ADIM", "0"))
        mikro = int(os.environ.get("MIKRO_BATCH", "1" if ortam == "colab" else "4"))
        if deneme < 0 or mikro <= 0 or 16 % mikro:
            raise ValueError("MAX_ADIM >= 0; MIKRO_BATCH pozitif ve 16'nın böleni olmalı.")
        token = os.environ.get("HF_TOKEN", "").strip()
        if not token and not deneme:
            raise RuntimeError("HF_TOKEN eksik: tam eğitim başlamaz. Secret olarak write token tanımlayın.")
        if not token:
            print("!!! HF_TOKEN YOK: yalnız duman modu; HF yedeği alınamayacak !!!")
        if deneme and os.environ.get("DEVAM", "0") == "1":
            raise ValueError("Duman modu DEVAM=1 ile kullanılamaz; tam koşu durumunu değiştirmeyin.")
        return {
            "ortam": ortam,
            "model": os.environ.get("MODEL", "Qwen/Qwen3.5-9B" if ortam == "colab" else "Qwen/Qwen3-8B"),
            "veri_url": os.environ.get(
                "VERI_URL", "https://github.com/krxi/asm-adlandirma-veri/releases/download/v5/veri-v5.zip",
            ),
            "repo": os.environ.get("HF_REPO", "krxi123/asm-adlandirma-lora-v5"),
            "kok": Path(os.environ.get("ASM_KOK", "asm-calisma-v5")).expanduser().resolve(),
            "drive": Path(os.environ["DRIVE_KOK"]) if os.environ.get("DRIVE_KOK") else None,
            "max_adim": deneme, "mikro": mikro,
            "grad_ckpt": os.environ.get("GRAD_CKPT", "1") == "1",
            "devam": os.environ.get("DEVAM", "0") == "1",
        }


    def egit(ayar):
        import torch
        import transformers
        from datasets import Dataset
        from huggingface_hub import HfApi, snapshot_download
        from peft import LoraConfig, get_peft_model, set_peft_model_state_dict
        from peft.utils.save_and_load import load_peft_weights
        from torch.utils.data import SequentialSampler
        from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
        from transformers import DataCollatorForSeq2Seq, Trainer, TrainerCallback, TrainingArguments, set_seed

        # Repo içindeyken asıl ayrıştırıcı; tek dosya çalışmada yukarıdaki kopya.
        for aday in (Path.cwd() / "lora", Path.cwd().parent / "lora"):
            if (aday / "cikti.py").is_file():
                sys.path.insert(0, str(aday))
                break
        try:
            from cikti import ad_ayikla as ayikla
        except ModuleNotFoundError as hata:
            if hata.name != "cikti":
                raise
            ayikla = ad_ayikla

        kok = ayar["kok"]
        deneme = ayar["max_adim"] > 0
        if deneme:
            kok = kok / "duman" / time.strftime("%Y%m%d-%H%M%S")
        elif (kok / "kosu.json").exists() and not ayar["devam"]:
            raise FileExistsError("Yerel koşu var: DEVAM=1 veya yeni ASM_KOK seçin.")
        kok.mkdir(parents=True, exist_ok=True)
        token = os.environ.get("HF_TOKEN", "").strip() or None
        logger = logging.getLogger("asm-v5")
        for eski in list(logger.handlers):
            eski.close()
            logger.removeHandler(eski)
        logger.setLevel(logging.INFO)
        logger.propagate = False

        class Gizle(logging.Filter):
            def filter(self, record):
                metin = record.getMessage()
                if token:
                    metin = metin.replace(token, "[GİZLİ]")
                record.msg, record.args = metin, ()
                return True

        for handler in (logging.FileHandler(kok / "egitim.log", encoding="utf-8"), logging.StreamHandler()):
            handler.addFilter(Gizle())
            handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            logger.addHandler(handler)

        def tekrar(islem, etiket):
            for deneme_no in range(3):
                try:
                    islem()
                    return True
                except Exception as hata:
                    # HTTP hata metni/token/headers hiçbir zaman çıktıya taşınmaz.
                    logger.error("!!! HF YEDEK BAŞARISIZ: %s (%s), deneme %s/3 !!!",
                                 etiket, type(hata).__name__, deneme_no + 1)
                    if deneme_no < 2:
                        time.sleep(2 ** (deneme_no + 1))
            return False

        api = HfApi(token=token) if token else None
        if api:
            def repo_hazirla():
                api.create_repo(repo_id=ayar["repo"], repo_type="model", private=True, exist_ok=True)
                if not api.repo_info(ayar["repo"]).private:
                    raise ValueError("HF_REPO private olmalı; mevcut public repo kabul edilmez.")
            if not tekrar(repo_hazirla, "private repo denetimi"):
                raise RuntimeError("Private HF repo doğrulanamadı; repo erişimini ve write token yetkisini denetleyin.")

        # Duman çıktısı tam koşunun son/ ve durum/ klasörlerini asla ezmez.
        hf_onek = f"duman/{time.strftime('%Y%m%d-%H%M%S')}/" if deneme else ""
        uzak = None
        if api and not deneme:
            try:
                var = api.file_exists(ayar["repo"], "son/adapter_config.json")
                if var and not ayar["devam"]:
                    raise FileExistsError("HF_REPO'da son/ var: DEVAM=1 veya yeni HF_REPO seçin.")
                if var:
                    uzak = Path(snapshot_download(
                        ayar["repo"], token=token,
                        allow_patterns=["son/*", "durum/son/*", "kosu.json", "en_iyi.json", "olcum.jsonl",
                                        "*-sonuc.jsonl", "*-tamam.json", "egitim.log"],
                    ))
                elif ayar["devam"]:
                    raise FileNotFoundError("DEVAM=1 fakat HF_REPO/son bulunamadı.")
            except (FileExistsError, FileNotFoundError):
                raise
            except Exception:
                raise RuntimeError("HF devam durumu okunamadı; bağlantıyı ve repo yetkisini denetleyin.") from None

        arsiv = kok / "veri-v5.zip"
        if not arsiv.exists():
            gecici = arsiv.with_suffix(".part")
            with urllib.request.urlopen(ayar["veri_url"]) as yanit, gecici.open("wb") as dosya:
                shutil.copyfileobj(yanit, dosya)
            gecici.replace(arsiv)
        acilmis = kok / "veri-v5"
        gerekli = (
            "train.jsonl", "valid.jsonl", "valid_300.jsonl", "test.jsonl",
            "test_sabit.jsonl", "eval115.jsonl", "ozet.json",
        )
        with zipfile.ZipFile(arsiv) as z:
            for bilgi in z.infolist():
                hedef = (acilmis / bilgi.filename).resolve()
                if acilmis.resolve() not in hedef.parents:
                    raise ValueError("Arşiv yolu çalışma dizini dışına taşıyor.")
            z.extractall(acilmis)
        adaylar = [acilmis] + sorted({p.parent for p in acilmis.rglob("train.jsonl")})
        veri = next((p for p in adaylar if all((p / ad).is_file() for ad in gerekli)), None)
        if veri is None:
            raise FileNotFoundError(f"v5 dosyaları eksik: {gerekli}")
        train = jsonl_oku(veri / "train.jsonl")
        valid = jsonl_oku(veri / "valid_300.jsonl")
        if not train or len(valid) != 300:
            raise ValueError("Train boş olamaz; valid_300 tam 300 satır olmalı.")
        if deneme:
            valid = valid[:10]
        sira = veri_sirasi(train)
        train = [train[i] for i in sira]
        # Dataset fingerprint + kimlik sırası, model/hiperparametre değişimini devamda reddeder.
        ozet = hashlib.sha256()
        for ad in gerekli:
            ozet.update(ad.encode())
            with (veri / ad).open("rb") as dosya:
                for parca in iter(lambda: dosya.read(1024 * 1024), b""):
                    ozet.update(parca)
        kosu = {"model": ayar["model"], "veri_sha256": ozet.hexdigest(), "tohum": 7,
                "max_uzunluk": 3072, "etkin_batch": 16, "epoch": 1,
                "lr": 1e-4, "scheduler": "cosine", "warmup_ratio": 0.03,
                "r": 16, "alpha": 32, "dropout": 0.05, "target_modules": "all-linear",
                "max_adim": ayar["max_adim"], "mikro": ayar["mikro"], "grad_ckpt": ayar["grad_ckpt"],
                "transformers": transformers.__version__, "torch": torch.__version__,
                "sira_sha256": hashlib.sha256(json.dumps([r["id"] for r in train]).encode()).hexdigest()}
        if uzak and json.loads((uzak / "kosu.json").read_text()) != kosu:
            raise ValueError("Devam ayarları/veri/paket sürümü değişmiş; aynı koşu ayarlarını kullanın.")
        json_yaz(kok / "kosu.json", kosu)
        olcum_yolu = kok / "olcum.jsonl"
        if uzak:
            if (uzak / "egitim.log").exists():
                for handler in logger.handlers:
                    handler.flush()
                yeni_log = (kok / "egitim.log").read_text()
                (kok / "egitim.log").write_text((uzak / "egitim.log").read_text() + yeni_log)
            shutil.copy2(uzak / "olcum.jsonl", olcum_yolu)
            for dosya in list(uzak.glob("*-sonuc.jsonl")) + list(uzak.glob("*-tamam.json")):
                shutil.copy2(dosya, kok / dosya.name)
        else:
            olcum_yolu.write_text("", encoding="utf-8")
        if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
            raise RuntimeError("CUDA ve bf16 destekli GPU gerekli.")
        if int(os.environ.get("WORLD_SIZE", "1")) != 1:
            raise ValueError("Karşılaştırılabilir sıra için tek GPU kullanın.")
        set_seed(7)
        tokenizer = AutoTokenizer.from_pretrained(ayar["model"])
        tokenizer.padding_side = "right"
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token = tokenizer.eos_token
        config = AutoConfig.from_pretrained(ayar["model"])
        metin_config = config.get_text_config()
        hibrit = "linear_attention" in getattr(metin_config, "layer_types", [])
        logger.info("Mimari=%s; text_model_type=%s; katmanlar=%s", config.architectures,
                    metin_config.model_type, getattr(metin_config, "layer_types", []))
        sinif = AutoModelForCausalLM
        if config.model_type == "qwen3_5":
            from transformers import Qwen3_5ForCausalLM
            sinif = Qwen3_5ForCausalLM
        model, yukleme = sinif.from_pretrained(
            ayar["model"], config=metin_config, dtype=torch.bfloat16,
            device_map={"": 0}, attn_implementation="sdpa", output_loading_info=True,
        )
        if yukleme.get("missing_keys") or yukleme.get("mismatched_keys"):
            raise RuntimeError("Model ağırlıkları eksik/uyumsuz yüklendi; eğitimi başlatmıyorum.")
        lineer = {ad for ad, katman in model.named_modules()
                  if isinstance(katman, torch.nn.Linear) and katman is not model.get_output_embeddings()}
        if not lineer or (hibrit and not any("linear_attn" in ad for ad in lineer)):
            raise RuntimeError("Beklenen lineer attention LoRA hedefleri bulunamadı.")
        logger.info("LoRA all-linear: %s modül; türler=%s",
                    len(lineer), sorted({ad.rsplit(".", 1)[-1] for ad in lineer}))
        model.config.use_cache = False
        model = get_peft_model(model, LoraConfig(
            r=16, lora_alpha=32, lora_dropout=0.05, target_modules="all-linear", bias="none", task_type="CAUSAL_LM",
        ))
        eksik = [ad for ad in lineer if not any(n.endswith(ad) and hasattr(m, "lora_A")
                                               for n, m in model.named_modules())]
        if eksik:
            raise RuntimeError(f"LoRA kapsamı eksik: {eksik[:5]}")
        model.print_trainable_parameters()
        logger.info("Paketleme: group_by_length. SDPA/hibrit durum sınırları için dolgusuz birleştirme kapalı.")
        train_ds = Dataset.from_list([kodla(r, tokenizer) for r in train])
        valid_ds = Dataset.from_list([kodla(r, tokenizer) for r in valid])
        logger.info("Tüm train=%s; etkin batch=16; beklenen adım=%s", len(train), math.ceil(len(train) / 16))

        def uret(satirlar, yol):
            once_egitim = model.training
            model.eval()
            sonuclar = []
            try:
                with Path(yol).open("w", encoding="utf-8") as dosya, torch.inference_mode():
                    for r in satirlar:
                        ids = sablon_ids(tokenizer, r["messages"][:2], True)
                        if len(ids) > 3072:
                            raise ValueError(f"{r['id']}: üretim girdisi 3072 tokenı aşıyor.")
                        girdi = torch.tensor([ids], device=model.device)
                        sonuc = model.generate(input_ids=girdi, attention_mask=torch.ones_like(girdi),
                                               do_sample=False, max_new_tokens=160, use_cache=True,
                                               pad_token_id=tokenizer.pad_token_id)
                        yeni = sonuc[0, len(ids):]
                        ad, en, tr, gecerli = ayikla(tokenizer.decode(yeni, skip_special_tokens=True))
                        satir = {"id": r["id"], "gercek": r["gercek_ad"], "tahmin": ad,
                                 "aciklama_en": en, "aciklama": tr, "gecerli_json": gecerli,
                                 "f1": f1(ad, r["gercek_ad"]), "opt": r["opt"], "proje": r["proje"],
                                 "token": len(ids) + len(yeni)}
                        dosya.write(json.dumps(satir, ensure_ascii=False) + "\n")
                        dosya.flush()
                        sonuclar.append(satir)
            finally:
                model.train(once_egitim)
            return {"f1": sum(r["f1"] for r in sonuclar) / len(sonuclar),
                    "gecerli_json_orani": sum(r["gecerli_json"] for r in sonuclar) / len(sonuclar), "n": len(sonuclar)}

        devam_yolu = None
        en_iyi = {"adim": 0, "f1": -1.0}
        en_iyi_yol = kok / "en-iyi-adaptor"
        if uzak:
            en_iyi = json.loads((uzak / "en_iyi.json").read_text())
            try:
                en_iyi_uzak = Path(snapshot_download(ayar["repo"], token=token,
                                                    allow_patterns=[f"{hf_klasoru(en_iyi['adim'])}/*"]))
            except Exception:
                raise RuntimeError("En iyi adaptör indirilemedi.") from None
            shutil.copytree(en_iyi_uzak / hf_klasoru(en_iyi["adim"]), en_iyi_yol, dirs_exist_ok=True)
            json_yaz(kok / "en_iyi.json", en_iyi)
            devam_yolu = kok / "devam-checkpoint"
            if devam_yolu.exists():
                shutil.rmtree(devam_yolu)
            shutil.copytree(uzak / "durum/son", devam_yolu)
            shutil.copytree(uzak / "son", devam_yolu, dirs_exist_ok=True)
            for ad in ("optimizer.pt", "scheduler.pt", "rng_state.pth", "trainer_state.json"):
                if not (devam_yolu / ad).is_file():
                    raise ValueError(f"Devam durumu eksik: {ad}; ağırlıkla sıfırdan devam edilmeyecek.")

        kuyruk = []

        def kuyrugu_it():
            if not api:
                return
            while kuyruk:
                paket = kuyruk[0]
                for handler in logger.handlers:
                    handler.flush()
                shutil.copy2(kok / "egitim.log", paket / "egitim.log")
                basarili = tekrar(lambda: api.upload_folder(
                    repo_id=ayar["repo"], repo_type="model", folder_path=str(paket), path_in_repo=hf_onek or None,
                    commit_message=f"v5 {paket.name}",
                    # Aynı atomik commit: son adaptörü + optimizer/trainer/RNG + ölçümler.
                ), paket.name)
                if not basarili:
                    logger.error("!!! YEDEK YEREL KUYRUKTA; sonraki checkpoint/sonda yeniden denenecek !!!")
                    break
                logger.info("HF yedeği doğrulandı: %s", paket.name)
                kuyruk.pop(0)
                shutil.rmtree(paket)

        def drive_yedekle(paket):
            if ayar["drive"]:
                try:
                    shutil.copytree(paket, ayar["drive"] / hf_onek, dirs_exist_ok=True)
                except Exception as hata:
                    logger.error("!!! DRIVE YEDEK BAŞARISIZ (%s); HF yüklemesine devam ediliyor !!!",
                                 type(hata).__name__)

        class SabitSiraliTrainer(Trainer):
            def _get_train_sampler(self, train_dataset=None):
                # Uzunluk gruplaması önceden yapıldı; iki model aynı 16 satırı aynı adımda görür.
                return SequentialSampler(train_dataset if train_dataset is not None else self.train_dataset)

        adim_sureleri = []

        class KaydetOlc(TrainerCallback):
            def on_step_begin(self, args, state, control, **kwargs):
                self.adim_baslangici = time.monotonic()

            def on_log(self, args, state, control, logs=None, **kwargs):
                logger.info("adim=%s %s", state.global_step, json.dumps(logs or {}, ensure_ascii=False))

            def on_step_end(self, args, state, control, **kwargs):
                adim_sureleri.append(time.monotonic() - self.adim_baslangici)
                # Son adım 500'ün katı olmasa da ölçülür ve TAM trainer checkpoint'i kaydedilir.
                if state.global_step == state.max_steps:
                    control.should_evaluate = True
                    control.should_save = True
                return control

            def on_evaluate(self, args, state, control, metrics=None, **kwargs):
                nonlocal en_iyi
                olcum = uret(valid, kok / "valid-sonuc.jsonl")
                olcum.update({"adim": state.global_step, "eval_loss": metrics["eval_loss"], "model": ayar["model"]})
                with olcum_yolu.open("a", encoding="utf-8") as dosya:
                    dosya.write(json.dumps(olcum, ensure_ascii=False) + "\n")
                logger.info("VALID %s", json.dumps(olcum, ensure_ascii=False))
                if olcum["f1"] > en_iyi["f1"]:
                    en_iyi = {"adim": state.global_step, "f1": olcum["f1"]}
                    model.save_pretrained(en_iyi_yol, safe_serialization=True, save_embedding_layers=False)
                json_yaz(kok / "en_iyi.json", en_iyi)

            def on_save(self, args, state, control, **kwargs):
                kaynak = Path(args.output_dir) / f"checkpoint-{state.global_step}"
                paket = kok / "hf-kuyruk" / hf_klasoru(state.global_step)
                hf_paketle(kaynak, paket, state.global_step)
                for ad in ("kosu.json", "en_iyi.json", "olcum.jsonl", "valid-sonuc.jsonl", "egitim.log"):
                    shutil.copy2(kok / ad, paket / ad)
                drive_yedekle(paket)
                if api:
                    kuyruk.append(paket)
                    kuyrugu_it()
                else:
                    logger.warning("!!! HF_TOKEN yok: checkpoint yalnız yerelde/Drive'da !!!")

        toplam_adim = ayar["max_adim"] if deneme else math.ceil(len(train) / 16)
        argumanlar = dict(
            output_dir=str(kok / "checkpoints"), num_train_epochs=1,
            max_steps=ayar["max_adim"] if deneme else -1,
            per_device_train_batch_size=ayar["mikro"], gradient_accumulation_steps=16 // ayar["mikro"],
            per_device_eval_batch_size=1, learning_rate=1e-4, lr_scheduler_type="cosine",
            warmup_steps=math.ceil(toplam_adim * 0.03), optim="adamw_torch", weight_decay=0.0,
            bf16=True, tf32=True, gradient_checkpointing=ayar["grad_ckpt"],
            gradient_checkpointing_kwargs={"use_reentrant": False}, max_grad_norm=0.3,
            eval_strategy="steps", eval_steps=500, save_strategy="steps", save_steps=500,
            save_total_limit=2, save_only_model=False, logging_steps=1 if deneme else 10,
            report_to="none", seed=7, data_seed=7, remove_unused_columns=False,
            prediction_loss_only=True, dataloader_num_workers=0, disable_tqdm=True,
        )
        # Transformers 5.3 yeni ad; 4.x/5.2 için eski ad.
        alanlar = inspect.signature(TrainingArguments).parameters
        argumanlar.update({"train_sampling_strategy": "group_by_length"} if "train_sampling_strategy" in alanlar
                         else {"group_by_length": True})
        trainer = SabitSiraliTrainer(
            model=model, args=TrainingArguments(**argumanlar), train_dataset=train_ds, eval_dataset=valid_ds,
            data_collator=DataCollatorForSeq2Seq(
                tokenizer, padding=True, label_pad_token_id=-100, pad_to_multiple_of=8,
            ),
            callbacks=[KaydetOlc()],
        )
        # PEFT modeli doğru kuruldu; Trainer adaptör + optimizer/scheduler/RNG/adımı birlikte yükler.
        baslangic = time.monotonic()
        tamam_adim = json.loads((devam_yolu / "trainer_state.json").read_text())["global_step"] if devam_yolu else 0
        if tamam_adim < toplam_adim:
            trainer.train(resume_from_checkpoint=str(devam_yolu) if devam_yolu else None)
        else:
            logger.info("Eğitim zaten tamamlanmış; yalnız eksik final çıktıları hazırlanıyor.")
        logger.info("Eğitim süresi %.1f sn; en iyi=%s", time.monotonic() - baslangic, en_iyi)
        if adim_sureleri:
            saniye = sum(adim_sureleri) / len(adim_sureleri)
            logger.info("Ölçüm/yükleme hariç %.2f sn/adım; 5938 adım için %.2f saat", saniye, saniye * 5938 / 3600)
        kuyrugu_it()
        dosyalar = [kok / "egitim.log", olcum_yolu, kok / "valid-sonuc.jsonl"]
        if not deneme:
            # Yalnız valid F1 seçimi; test kümeleri eğitim/erken seçim sırasında açılmaz.
            agirliklar = load_peft_weights(str(en_iyi_yol), device="cpu")
            set_peft_model_state_dict(model, agirliklar)
            for bolum, beklenen in (("test_sabit", 2000), ("eval115", 115)):
                satirlar = jsonl_oku(veri / f"{bolum}.jsonl")
                if len(satirlar) != beklenen:
                    raise ValueError(f"{bolum}: {beklenen} satır bekleniyordu, {len(satirlar)} bulundu.")
                sonuc_yolu = kok / f"{bolum}-sonuc.jsonl"
                # Tamamlanmış testi DEVAM=1 tekrar ölçmez; yarım dosya tamamlanmış sayılmaz.
                damga = kok / f"{bolum}-tamam.json"
                test_kimligi = {"en_iyi": en_iyi, "kosu": kosu}
                if not (damga.exists() and sonuc_yolu.exists() and json.loads(damga.read_text()) == test_kimligi):
                    olcum = uret(satirlar, sonuc_yolu)
                    logger.info("TEST %s en_iyi=%s %s", bolum, en_iyi, olcum)
                    json_yaz(damga, test_kimligi)
                    # Uzun ikinci test sırasında oturum kaybolursa biten ilk test tekrar edilmesin.
                    test_paketi = kok / "hf-kuyruk" / f"sonuc-{bolum}"
                    test_paketi.mkdir(parents=True, exist_ok=True)
                    for tamam in (sonuc_yolu, damga):
                        shutil.copy2(tamam, test_paketi / tamam.name)
                    drive_yedekle(test_paketi)
                    if api:
                        kuyruk.append(test_paketi)
                        kuyrugu_it()
                dosyalar.extend([sonuc_yolu, damga])
        zip_yolu = Path(shutil.make_archive(str(kok / "adaptor-en-iyi"), "zip", en_iyi_yol))
        dosyalar.append(zip_yolu)
        sonuc_paketi = kok / "hf-sonuclar"
        sonuc_paketi.mkdir(exist_ok=True)
        for dosya in dosyalar:
            shutil.copy2(dosya, sonuc_paketi / dosya.name)
        drive_yedekle(sonuc_paketi)
        # Duman modunda checkpoint upload'u tek HF itişidir; bu dosyalar zaten onun içindedir.
        if api and not deneme:
            kuyruk.append(sonuc_paketi)
            kuyrugu_it()
        if kuyruk:
            logger.error("!!! %s PAKET HF'YE GİTMEDİ; oturumu kapatmadan hf-kuyruk dizinini kurtarın !!!", len(kuyruk))
        return dosyalar

    return egit, egitim_ayarlari


@app.cell
def _(mo):
    # Ortam değişkeni yoksa token ve kip buradan girilir; token ekrana/loga yazılmaz.
    form = mo.ui.dictionary({
        "token": mo.ui.text(kind="password", label="HF write token (molab Secrets'ta HF_TOKEN varsa boş bırak)",
                            full_width=True),
        "kip": mo.ui.dropdown(["duman (20 adım)", "tam eğitim", "devam (kesilen tam eğitimi sürdür)"],
                              value="duman (20 adım)", label="Kip"),
    }).form(submit_button_label="Başlat")
    form
    return (form,)


@app.cell
def _(egitim_ayarlari, form, mo):
    import os as _os

    mo.stop(form.value is None, mo.md("Token'ı gir, kipi seç, **Başlat**'a bas."))
    if form.value["token"].strip():
        _os.environ["HF_TOKEN"] = form.value["token"].strip()
    _kip = form.value["kip"]
    _os.environ["MAX_ADIM"] = "20" if _kip.startswith("duman") else "0"
    _os.environ["DEVAM"] = "1" if _kip.startswith("devam") else "0"
    if _kip.startswith("duman"):
        _os.environ.setdefault("ASM_KOK", "asm-calisma-v5-duman")
    ayar = egitim_ayarlari("molab")
    return (ayar,)


@app.cell
def _(ayar, egit):
    indirilecekler = egit(ayar)
    return (indirilecekler,)


@app.cell
def _(indirilecekler, mo):
    mo.vstack([
        mo.download(data=_yol.read_bytes(), filename=_yol.name, label=f"İndir: {_yol.name}")
        for _yol in indirilecekler if _yol.exists()
    ])
    return


if __name__ == "__main__":
    app.run()
