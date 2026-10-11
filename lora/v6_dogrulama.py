#!/usr/bin/env python3
"""Yerel modelle, sabit valid300 üzerinde iki kollu v6 pilotu. Ayrıntılar: V6_DOGRULAMA.md."""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.metadata
import json
import math
import os
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "lora"))

from cikti import ad_ayikla  # noqa: E402
import hazirla_sonraki as hs  # noqa: E402
from hazirla import SISTEM_V5, SISTEM_V6  # noqa: E402
from taban import f1  # noqa: E402

VALID_CACHE = KOK / "sonuc/valid300-molab-qwen3-8b-v5.jsonl"
VALID_SHA256 = "88f7bfb32ed87f5c43a43d670c5ca5e80bfd00c3592d59dc24b9ee52e14e4faf"
PROJECT_GUARD = KOK / "lora/v6_ayrilmis_projeler.json"
PROJECT_GUARD_SHA256 = "905295d0e9e2cb16a59ed050747375a896994e32950b4c0da20b71bcc18e2259"
GIRDI_MANIFESTI = KOK / "lora/v6_girdi_manifest.json"
EK = hs.h.DECOMPILE_BASLIK
V6_ALANLAR = {
    "decompile_var",
    "decompile_kirpildi",
    "decompile_sizinti",
    "decompile_ham_sizinti",
    "decompile_ad_anonim_degisim",
    "decompile_ad_anonim_satir",
    "decompile_esleme",
    "decompile_yok_neden",
    "token",
}
ALANLAR = {"messages", "id", "proje", "opt", "baglam_var", "gercek_ad", "oneksiz_onek", "hedef_tur"}
ETKIN_BATCH = 16
TOHUM = 7


def sha256(veri):
    return hashlib.sha256(veri).hexdigest()


def ozet(veri):
    return sha256(json.dumps(veri, ensure_ascii=False, sort_keys=True).encode())


def tek_anahtar(ciftler):
    sonuc = {}
    for ad, deger in ciftler:
        if ad in sonuc:
            raise ValueError("Yinelenen JSON anahtarı.")
        sonuc[ad] = deger
    return sonuc


def json_oku(metin):
    return json.loads(metin, object_pairs_hook=tek_anahtar)


def jsonl_oku(yol):
    veri = Path(yol).read_bytes()
    try:
        satirlar = [json_oku(s) for s in veri.splitlines() if s.strip()]
    except (ValueError, UnicodeError):
        raise ValueError("Geçersiz JSONL; satır içeriği günlüğe yazılmadı.") from None
    if not satirlar or any(not isinstance(r, dict) for r in satirlar):
        raise ValueError("JSONL boş olamaz; her satır nesne olmalı.")
    return satirlar, sha256(veri)


def valid_capasi():
    satirlar, kimlik = jsonl_oku(VALID_CACHE)
    if kimlik != VALID_SHA256 or len(satirlar) != 300:
        raise ValueError("Commit'teki sabit valid300 cache değişmiş; pilot başlamaz.")
    return [{k: r[k] for k in ("id", "proje", "opt", "gercek")} for r in satirlar]


def proje_capasi():
    veri = PROJECT_GUARD.read_bytes()
    if sha256(veri) != PROJECT_GUARD_SHA256:
        raise ValueError("Sabit ayrılmış proje manifest'i değişmiş; pilot başlamaz.")
    hashes = json_oku(veri).get("ayrilmis_proje_sha256")
    if (
        not isinstance(hashes, list)
        or not hashes
        or any(not isinstance(h, str) or re.fullmatch(r"[0-9a-f]{64}", h) is None for h in hashes)
    ):
        raise ValueError("Ayrılmış proje manifest şeması bozuk.")
    if len(set(hashes)) != len(hashes):
        raise ValueError("Ayrılmış proje manifest'inde yinelenen hash.")
    return set(hashes)


def ad_geciyor(metin, adlar):
    """Ana v6 hazırlayıcısının aynı tanımlayıcı/sabit maskesini kullan."""
    return hs.ad_sizintisi(metin, adlar) is not None


def _kok(ad):
    return ad.casefold().lstrip("_")


def ithaller(user):
    """Stripped binary'de de görünen import adları: asm `; -> ad` yorumları ve bağlamdaki `çağırır` listeleri."""
    asm, _, baglam = user.partition(EK)[0].partition(hs.h.BAGLAM_BASLIK)
    adlar = set(hs.ITHAL_YORUM.findall(asm))
    for satir in baglam.splitlines():
        _, ayrac, cagri = satir.partition("çağırır ")
        if ayrac:
            adlar.update(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", cagri.split(";", 1)[0]))
    return {ad for ad in adlar if not ad.startswith(("sub_", "dat_"))}


def sizinti_adlari(r, hedef_ad, ith):
    """Ham ad her zaman aranır. Öneksiz hedef yalnız satırın kendi import'u olarak görünüyorsa
    (janet_asin -> `call asin ; -> asin`) muaftır; bu gerçek stripped binary'de de görünen sinyaldir."""
    adlar = [r["gercek_ad"]]
    if hedef_ad != r["gercek_ad"] and _kok(hedef_ad) not in {_kok(a) for a in ith}:
        adlar.append(hedef_ad)
    return tuple(adlar)


def sizinti_bolumleri(user, ham_ad, ith):
    """asm, bağlam ve decompile ayrı aranır: C sabit maskesi karışık asm+C metninde tırnak eşini kaybetmesin.
    Komut adları (`push`, `add`) ve bağlam biçim etiketleri (`komut`, `string`) program tanımlayıcısı değildir.
    asm/bağlamdaki import (`; -> ad`, `çağırır ad`) tanımsız dış semboldür; bu dylib'de tanımlı fonksiyonun
    kendisi olamaz (`Abort` ~ `abort`, `mi_is_redirected` ~ `_mi_is_redirected`). Decompile'da fonksiyon
    başlığı sızıntısı aynı biçimde görüneceği için orada istisna yoktur."""
    govde, _, decompile = user.partition(EK)
    asm, _, baglam = govde.partition(hs.h.BAGLAM_BASLIK)
    satirlar = []
    for s in asm.splitlines():
        parca = s.split(None, 1)
        satirlar.append(s if s.rstrip().endswith(":") else parca[1] if len(parca) == 2 else "")
    asm = "\n".join(satirlar)
    baglam = re.sub(r"\(\d+ komut\)|(?<=[:;] )string(?= )", " ", baglam)
    for ad in ith:
        if _kok(ad) == _kok(ham_ad):
            desen = r"(?<![A-Za-z0-9_])" + re.escape(ad) + r"(?![A-Za-z0-9_])"
            asm, baglam = re.sub(desen, "ext_", asm), re.sub(desen, "ext_", baglam)
    return [b for b in (asm, baglam, decompile) if b.strip()]


def sema_dogrula(r, surum="v5"):
    gerekli = ALANLAR if surum == "v5" else ALANLAR | V6_ALANLAR
    if set(r) != gerekli or any(not isinstance(r[k], str) or not r[k] for k in ("id", "proje", "opt", "gercek_ad")):
        raise ValueError("Ana hazırlayıcının v5/v6 satır şeması bekleniyordu.")
    m = r["messages"]
    if (
        not isinstance(m, list)
        or len(m) != 3
        or any(
            not isinstance(x, dict)
            or set(x) != {"role", "content"}
            or not isinstance(x["content"], str)
            or not x["content"]
            for x in m
        )
    ):
        raise ValueError("Üç metin mesajı gerekli.")
    sistem = SISTEM_V5 if surum == "v5" else SISTEM_V6
    if [x["role"] for x in m] != ["system", "user", "assistant"] or m[0]["content"] != sistem:
        raise ValueError("Ana v5/v6 sistem/mesaj sözleşmesi değişmiş.")
    try:
        hedef = json_oku(m[2]["content"])
    except ValueError:
        raise ValueError("Assistant hedefi geçerli JSON olmalı.") from None
    alanlar = ["ad"] if r["hedef_tur"] == "ad" else ["aciklama_en", "ad", "aciklama"]
    if r["hedef_tur"] not in ("ad", "tam") or not isinstance(hedef, dict) or list(hedef) != alanlar:
        raise ValueError("Ana hedef alanları/sırası değişmiş.")
    if any(not isinstance(v, str) or not v for v in hedef.values()):
        raise ValueError("Hedef alanları boş olmayan metin olmalı.")
    if (
        type(r["baglam_var"]) is not bool
        or not isinstance(r["oneksiz_onek"], list)
        or any(not isinstance(x, str) or not x for x in r["oneksiz_onek"])
    ):
        raise ValueError("Bağlam/önek metaverisi bozuk.")
    if surum == "v5" and EK in m[1]["content"]:
        raise ValueError("v5 kontrol girdisine önceden decompile eklenmiş.")
    # Assistant adı, ana hazırlayıcıdaki h.oneksiz(r) sonucunun gerçek eğitim hedefidir.
    user = m[1]["content"]
    ith = ithaller(user)
    adlar = sizinti_adlari(r, hedef["ad"], ith)
    if r["id"] in user or any(ad_geciyor(b, adlar) for b in sizinti_bolumleri(user, r["gercek_ad"], ith)):
        raise ValueError("Girdide ham veya öneksiz hedef adı/kimlik sızıntısı var.")
    if surum == "v6":
        bayraklar = ("decompile_var", "decompile_kirpildi", "decompile_sizinti", "decompile_ham_sizinti")
        # Ana hat sızıntı bulduğunda decompile'ı girdiden çıkarır; bayrak ancak decompile hâlâ varsa kirli.
        if any(type(r[k]) is not bool for k in bayraklar) or (r["decompile_sizinti"] and r["decompile_var"]):
            raise ValueError("Ana v6 sızıntı bayrakları geçerli ve temiz olmalı.")
        if any(type(r[k]) is not int or r[k] < 0 for k in ("decompile_ad_anonim_degisim", "decompile_ad_anonim_satir")):
            raise ValueError("Ana v6 anonimleştirme sayacı bozuk.")
        if not isinstance(r["token"], dict) or set(r["token"]) != {"girdi", "hedef", "toplam"}:
            raise ValueError("Ana v6 token metaverisi eksik.")
        if r["decompile_var"]:
            if r["decompile_esleme"] != "id" or r["decompile_yok_neden"] is not None:
                raise ValueError("Pilot yalnız ana hattın doğrudan kimlik eşlemesini kabul eder.")
            if m[1]["content"].count(EK) != 1 or not m[1]["content"].split(EK)[1].strip():
                raise ValueError("Ana v6 decompile bölümü eksik veya yinelenmiş.")
        elif EK in m[1]["content"] or not isinstance(r["decompile_yok_neden"], str):
            raise ValueError("Decompile olmayan satırın ana hat metaverisi tutarsız.")


def dosya_sha(yol):
    return sha256(Path(yol).read_bytes())


def git_blob(yol):
    veri = Path(yol).read_bytes()
    return hashlib.sha1(f"blob {len(veri)}\0".encode() + veri).hexdigest()


def id_dizini_oku(kok):
    yollar = sorted(Path(kok).glob("*.txt"))
    if not yollar:
        raise ValueError("Ana dogrula_v6 kimlik çıktıları eksik.")
    iz, idler = {}, {}
    for yol in yollar:
        b = yol.read_bytes()
        iz[yol.name] = sha256(b)
        kimlikler = b.decode("utf-8").splitlines()
        if len(kimlikler) != len(set(kimlikler)):
            raise ValueError("Doğrulanmış proje kimliklerinde yineleme var.")
        idler[yol.stem] = set(kimlikler)
    return idler, ozet(iz)


def beklenen_girdiler(a):
    """Hash'ler önceden gözden geçirilen tracked manifestten gelir; otomatik mühürleme yok."""
    m = json_oku(GIRDI_MANIFESTI.read_bytes())
    roller = ("train", "valid", "train_v6", "valid_v6", "dogrulama_raporu", "dogrulanmis_idler")
    beklenen = m.get("beklenen_sha256", {})
    if set(beklenen) != set(roller) or any(
        not isinstance(beklenen[k], str) or re.fullmatch(r"[0-9a-f]{64}", beklenen[k]) is None for k in roller
    ):
        raise ValueError("Beklenen veri SHA-256 değerleri manifestte önceden sabitlenmeli; pilot başlamaz.")
    if not isinstance(m.get("train_sira_sha256"), str) or re.fullmatch(r"[0-9a-f]{64}", m["train_sira_sha256"]) is None:
        raise ValueError("Beklenen v5 eğitim sırası manifestte önceden sabitlenmeli.")
    for yol, beklenen_blob in m.get("ana_hat_bloblari", {}).items():
        if yol not in ("lora/hazirla_sonraki.py", "dogrula_v6.py") or git_blob(KOK / yol) != beklenen_blob:
            raise ValueError("Ana v6 hazırlayıcı/doğrulayıcı kodu manifestle aynı değil.")
    if set(m.get("ana_hat_bloblari", {})) != {"lora/hazirla_sonraki.py", "dogrula_v6.py"}:
        raise ValueError("Ana hat kod kimlikleri manifestte eksik.")
    iz = {k: dosya_sha(getattr(a, k)) for k in roller[:-1]}
    idler, iz["dogrulanmis_idler"] = id_dizini_oku(a.dogrulanmis_idler)
    if iz != beklenen:
        raise ValueError("Girdi SHA-256 manifestle uyuşmuyor; eğitimden önce duruldu.")
    return m, iz, idler


def yasak_idler():
    ids = set((KOK / "lora/test_sabit_idler.txt").read_text(encoding="utf-8").splitlines())
    rs, _ = jsonl_oku(KOK / "veri/test.jsonl")
    return ids | {r["id"] for r in rs}


def girdileri_oku(a, capa, ayrilmis_projeler):
    # Harici cache eklemek yerine ana hazırlayıcının ürettiği iki sürümü oku.
    yollar = [a.train, a.valid, a.train_v6, a.valid_v6]
    stat = [Path(p).stat() for p in yollar]
    if len({(s.st_dev, s.st_ino) for s in stat}) != 4:
        raise ValueError("Dört hazırlanmış girdi ayrı dosya olmalı.")
    manifest, parmak_izleri, dogrulanmis = beklenen_girdiler(a)
    rapor = json_oku(a.dogrulama_raporu.read_bytes())
    yasak = yasak_idler()
    veriler = {}
    for rol in ("train", "valid"):
        rs, h5 = jsonl_oku(getattr(a, rol))
        v6_rs, h6 = jsonl_oku(getattr(a, rol + "_v6"))
        if (h5, h6) != (parmak_izleri[rol], parmak_izleri[rol + "_v6"]):
            raise ValueError("Okuma sırasında hazırlanmış girdi değişti.")
        if len(rs) != len(v6_rs):
            raise ValueError("v5/v6 satır kapsamı aynı değil; satır düşürülmedi.")
        ids = [r.get("id") for r in rs]
        if len(ids) != len(set(ids)) or set(ids) & yasak:
            raise ValueError("Yinelenen veya test_sabit/eval115 kimliği; pilot durdu.")
        kol6 = {}
        for r, s in zip(rs, v6_rs):
            sema_dogrula(r)
            sema_dogrula(s, "v6")
            if any(r[k] != s[k] for k in ALANLAR - {"messages"}) or r["messages"][2] != s["messages"][2]:
                raise ValueError("v5/v6 sıra, kimlik, metaveri veya hedef baytları farklı.")
            user5, user6 = r["messages"][1]["content"], s["messages"][1]["content"]
            taban6 = user6.split(EK)[0] if s["decompile_var"] else user6
            if taban6 != user5:
                raise ValueError("Ana v6 çıktısının assembly/bağlamı v5 ile aynı değil.")
            proje = r["proje"]
            if rol == "train" and sha256(proje.encode()) in ayrilmis_projeler:
                raise ValueError("Train satırı sabit test/validation proje manifest'inde; eğitim yasak.")
            bilgi = rapor.get("proje", {}).get(proje, {})
            uygun = dogrulanmis.get(proje, set())
            if r["id"] not in uygun or bilgi.get("rol") != ("egitim" if rol == "train" else "dogrulama"):
                raise ValueError("Ana dogrula_v6 ikili/assembly kimlik kanıtı veya bölüm rolü eksik.")
            if bilgi.get("decompile_hazir") != len(uygun):
                raise ValueError("Ana dogrula_v6 raporu ile doğrulanmış kimlik sayısı uyuşmuyor.")
            kol6[r["id"]] = s
        veriler[rol] = (rs, kol6)
    train, valid = veriler["train"][0], veriler["valid"][0]
    beklenen = [{"id": r["id"], "proje": r["proje"], "opt": r["opt"], "gercek": r["gercek_ad"]} for r in valid]
    if beklenen != capa:
        raise ValueError("Valid sıra/id/proje/opt/gerçek ad sabit commit cache ile aynı değil.")
    if {r["id"] for r in train} & {r["id"] for r in capa} or {r["proje"] for r in train} & {r["proje"] for r in capa}:
        raise ValueError("Train ile sabit valid kimlik/proje örtüşmesi.")

    def govde(r):
        return sha256(" ".join(r["messages"][1]["content"].split()).encode())

    if {govde(r) for r in train} & {govde(r) for r in valid}:
        raise ValueError("Train/valid normalize girdi metni birebir örtüşüyor.")
    if ozet([train[i]["id"] for i in veri_sirasi(train)]) != manifest["train_sira_sha256"]:
        raise ValueError("Eğitim sırası beklenen v5 sıra SHA-256 ile uyuşmuyor.")
    _, son_iz, _ = beklenen_girdiler(a)
    if parmak_izleri != son_iz:
        raise ValueError("Çalışma sırasında ana hat kanıtı/girdiler değişti.")
    return veriler, parmak_izleri


def veri_sirasi(rs):
    sira = list(range(len(rs)))
    random.Random(TOHUM).shuffle(sira)
    return [
        i
        for bas in range(0, len(sira), 800)
        for i in sorted(
            sira[bas : bas + 800], key=lambda i: sum(len(m["content"]) for m in rs[i]["messages"]), reverse=True
        )
    ]


def mesajlar(r, hazirlanmis_v6, kol):
    if kol not in ("asm", "combined"):
        raise ValueError("Bilinmeyen deney kolu.")
    # Aynı ana v6 sistemi ve hedef; combined doğrudan ana v6 çıktısıdır.
    m = [dict(x) for x in hazirlanmis_v6[r["id"]]["messages"]]
    if kol == "asm":
        m[1]["content"] = r["messages"][1]["content"]
    return m


def planla(a, veriler, parmak_izleri):
    if not 1 <= a.steps <= 2000 or a.micro_batch not in (1, 2, 4, 8, 16):
        raise ValueError("Adım 1..2000; mikro batch 16'nın pozitif böleni olmalı.")
    if not 256 <= a.max_length <= 8192 or a.max_length % 8 or not 1 <= a.max_new_tokens <= 512:
        raise ValueError("Uzunluk 256..8192 ve 8'in katı; üretim tavanı 1..512 olmalı.")
    if a.max_new_tokens >= a.max_length:
        raise ValueError("Üretim tavanı bağlamdan küçük olmalı.")
    train, valid = veriler["train"][0], veriler["valid"][0]
    n = a.steps * ETKIN_BATCH
    if n > len(train):
        raise ValueError("Sabit adım bütçesi train'i birden fazla tüketir; adımı azaltın.")
    sira = veri_sirasi(train)[:n]
    token_ust = n * a.max_length
    if token_ust > a.max_train_tokens:
        raise ValueError("Kol başına padded eğitim token üst sınırı bütçeyi aşıyor.")
    plan = {
        "schema": "asmsense-v6-validation-pilot-2",
        "valid_anchor_sha256": VALID_SHA256,
        "heldout_project_guard_sha256": PROJECT_GUARD_SHA256,
        "input_sha256": parmak_izleri,
        "system_sha256": sha256(SISTEM_V6.encode()),
        "input_manifest_sha256": dosya_sha(GIRDI_MANIFESTI),
        "upstream": "hazirla_sonraki --surum v6; pinned dogrula_v6 report and identity outputs",
        "decompile_coverage": {
            rol: sum(r["decompile_var"] for r in veriler[rol][1].values()) / len(veriler[rol][0])
            for rol in ("train", "valid")
        },
        "runner_sha256": sha256(Path(__file__).read_bytes()),
        "seed": TOHUM,
        "steps_per_arm": a.steps,
        "effective_batch": ETKIN_BATCH,
        "micro_batch": a.micro_batch,
        "max_length": a.max_length,
        "max_new_tokens": a.max_new_tokens,
        "train_rows_available": len(train),
        "train_rows_per_arm": n,
        "valid_rows": len(valid),
        "train_order_sha256": ozet([train[i]["id"] for i in sira]),
        "arms": ["asm", "combined"],
        "api_calls": 0,
        "optimizer_steps_total": 2 * a.steps,
        "generation_calls_total": 2 * len(valid),
        "train_padded_tokens_upper_total": 2 * token_ust,
        "bounds_per_arm": {
            "train_padded_tokens": token_ust,
            "valid_loss_calls": len(valid),
            "valid_generate_calls": len(valid),
            "valid_loss_tokens": len(valid) * a.max_length,
            "valid_prompt_tokens": len(valid) * (a.max_length - a.max_new_tokens),
            "valid_new_tokens": len(valid) * a.max_new_tokens,
        },
        "gpu_seconds": None,
        "gpu_cost_status": "unmeasured; GPU execution not run by CPU planner",
        "token_status": "upper bounds only; actual chat-template lengths checked before GPU model loading",
        "selection": "fixed final step; canonical taban.f1 only; no checkpoint selection",
        "prefix_f1": "not computed; unchanged existing scorer requires independently verified prefix map",
        "criterion": {
            "canonical_f1_delta_min": 0.01,
            "paired_project_bootstrap_95_low_gt": 0.0,
            "valid_json_rate_must_not_drop": True,
            "bootstrap_repeats": 2000,
            "bootstrap_seed": 7,
        },
    }
    return plan, [train[i] for i in sira]


def sablon_ids(tok, m, uret):
    try:
        ids = tok.apply_chat_template(
            m, tokenize=True, add_generation_prompt=uret, enable_thinking=False, return_dict=False
        )
        return list(ids["input_ids"] if hasattr(ids, "keys") else ids)
    except Exception:
        raise ValueError("Tokenizer şablonu uygulanamadı; örnek içeriği günlüğe yazılmadı.") from None


def kodla(r, cache, kol, tok, a):
    m = mesajlar(r, cache, kol)
    istem = sablon_ids(tok, m[:2], True)
    tum = sablon_ids(tok, m, False)
    if tum[: len(istem)] != istem or len(tum) <= len(istem):
        raise ValueError("Assistant token sınırı doğrulanamadı.")
    if len(tum) > a.max_length or len(istem) + a.max_new_tokens > a.max_length:
        raise ValueError("Chat-template token tavanı aşıldı; satır/girdi/hedef kesilmedi.")
    return {"input_ids": tum, "attention_mask": [1] * len(tum), "labels": [-100] * len(istem) + tum[len(istem) :]}


def json_yaz(yol, veri):
    with Path(yol).open("x", encoding="utf-8") as f:
        f.write(json.dumps(veri, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")


def yeni_cikti(yol):
    yol = Path(yol).resolve()
    if yol == KOK or KOK in yol.parents:
        raise ValueError("Deney çıktısı repo dışında yeni bir dizin olmalı.")
    yol.mkdir(parents=True, exist_ok=False)
    return yol


def puanla(rs, capa):
    if len(rs) != len(capa):
        raise ValueError("Sonuç eksik/fazla; paired karşılaştırma başlamaz.")
    puanlar = []
    for r, c in zip(rs, capa):
        if any(r.get(k) != c[k] for k in ("id", "proje", "opt", "gercek")) or not isinstance(r.get("tahmin"), str):
            raise ValueError("Sonuç kimliği/hedefi valid cache ile aynı değil.")
        if type(r.get("gecerli_json")) is not bool:
            raise ValueError("Sonuç JSON geçerlilik alanı boolean olmalı.")
        skor = f1(r["tahmin"], c["gercek"])
        if not isinstance(r.get("f1"), (int, float)) or not math.isfinite(r["f1"]) or abs(r["f1"] - skor) > 1e-12:
            raise ValueError("Sonuçtaki F1 kanonik skorla aynı değil.")
        puanlar.append(skor)
    return {
        "f1": sum(puanlar) / len(rs),
        "gecerli_json_orani": sum(r["gecerli_json"] for r in rs) / len(rs),
        "n": len(rs),
    }, puanlar


def karsilastir(kontrol, birlesik, capa):
    a, x = puanla(kontrol, capa)
    b, y = puanla(birlesik, capa)
    grup = defaultdict(list)
    for r, s, t in zip(capa, x, y):
        grup[r["proje"]].append(t - s)
    gruplar, rng, dagilim = list(grup.values()), random.Random(7), []
    for _ in range(2000):
        cekim = [rng.choice(gruplar) for _ in gruplar]
        dagilim.append(sum(sum(g) for g in cekim) / sum(len(g) for g in cekim))
    dagilim.sort()
    aralik = [dagilim[49], dagilim[1949]]
    delta = b["f1"] - a["f1"]
    return {
        "asm": a,
        "combined": b,
        "canonical_f1_delta": delta,
        "paired_project_bootstrap_95": aralik,
        "bootstrap_repeats": 2000,
        "bootstrap_seed": 7,
        "pilot_pass": delta >= 0.01 and aralik[0] > 0 and b["gecerli_json_orani"] >= a["gecerli_json_orani"],
        "interpretation": "validation screening only; no final-test or cross-seed claim",
        "prefix_f1": "not computed",
    }


def gpu_calistir(a, veriler, secili, plan, kok, capa):
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
    from transformers import DataCollatorForSeq2Seq, Trainer, TrainingArguments, set_seed

    if (
        not torch.cuda.is_available()
        or not torch.cuda.is_bf16_supported()
        or torch.cuda.device_count() != 1
        or int(os.environ.get("WORLD_SIZE", "1")) != 1
    ):
        raise ValueError("Tek CUDA GPU ve bf16 gerekli.")
    model_yolu = a.model.resolve(strict=True)
    if not model_yolu.is_dir():
        raise ValueError("Model, önceden hazırlanmış yerel bir dizin olmalı.")
    ortak = {"local_files_only": True, "trust_remote_code": False, "token": False}
    config = AutoConfig.from_pretrained(str(model_yolu), **ortak)
    if (
        config.model_type != "qwen3"
        or getattr(config, "quantization_config", None)
        or config.max_position_embeddings < a.max_length
    ):
        raise ValueError("Bu pilot yalnız yeterli bağlamlı, kuantize edilmemiş dense Qwen3 destekler.")
    tok = AutoTokenizer.from_pretrained(str(model_yolu), **ortak)
    tok.padding_side = "right"
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    kod = {}
    for kol in ("asm", "combined"):
        kod[kol] = {
            rol: [kodla(r, veriler[rol][1], kol, tok, a) for r in rs]
            for rol, rs in (("train", secili), ("valid", veriler["valid"][0]))
        }
    model_hash = {}
    for p in sorted(model_yolu.iterdir()):
        if p.is_file() and (p.suffix in (".json", ".safetensors", ".jinja", ".txt") or p.name == "tokenizer.model"):
            h = hashlib.sha256()
            with p.open("rb") as f:
                for parca in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(parca)
            model_hash[p.name] = h.hexdigest()
    runtime = {
        "model_files_sha256": model_hash,
        "packages": {p: importlib.metadata.version(p) for p in ("torch", "transformers", "peft", "accelerate")},
        "gpu": torch.cuda.get_device_name(0),
        "plan": plan,
    }
    sonuclar = {}
    for kol in ("asm", "combined"):
        set_seed(TOHUM)
        yol = kok / kol
        yol.mkdir()
        json_yaz(yol / "runtime.json", runtime)
        model, bilgi = AutoModelForCausalLM.from_pretrained(
            str(model_yolu),
            dtype=torch.bfloat16,
            attn_implementation="sdpa",
            use_safetensors=True,
            output_loading_info=True,
            **ortak,
        )
        if any(bilgi.get(k) for k in ("missing_keys", "mismatched_keys", "unexpected_keys", "error_msgs")):
            raise ValueError("Model ağırlıkları eksik veya uyumsuz.")
        model.config.use_cache = False
        model = get_peft_model(
            model,
            LoraConfig(
                r=16, lora_alpha=32, lora_dropout=0.05, target_modules="all-linear", bias="none", task_type="CAUSAL_LM"
            ),
        )
        args = TrainingArguments(
            output_dir=str(yol / "trainer"),
            max_steps=a.steps,
            num_train_epochs=1,
            per_device_train_batch_size=a.micro_batch,
            gradient_accumulation_steps=ETKIN_BATCH // a.micro_batch,
            per_device_eval_batch_size=1,
            learning_rate=1e-4,
            lr_scheduler_type="cosine",
            warmup_steps=math.ceil(a.steps * 0.03),
            optim="adamw_torch",
            weight_decay=0.0,
            max_grad_norm=0.3,
            bf16=True,
            gradient_checkpointing=True,
            gradient_checkpointing_kwargs={"use_reentrant": False},
            eval_strategy="no",
            save_strategy="no",
            logging_steps=10,
            report_to="none",
            push_to_hub=False,
            seed=TOHUM,
            data_seed=TOHUM,
            train_sampling_strategy="sequential",
            remove_unused_columns=False,
            prediction_loss_only=True,
            dataloader_num_workers=0,
            disable_tqdm=True,
        )
        trainer = Trainer(
            model=model,
            args=args,
            train_dataset=kod[kol]["train"],
            eval_dataset=kod[kol]["valid"],
            data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100, pad_to_multiple_of=8),
        )
        torch.cuda.reset_peak_memory_stats()
        bas = time.monotonic()
        trainer.train()
        egitim_sn = time.monotonic() - bas
        if trainer.state.global_step != a.steps:
            raise ValueError("Gerçek optimizer adımı bütçeyle aynı değil.")
        loss = trainer.evaluate()["eval_loss"]
        if not math.isfinite(loss):
            raise ValueError("Doğrulama kaybı sonlu değil.")
        model.eval()
        rs, bas = [], time.monotonic()
        with (yol / "valid-sonuc.jsonl").open("x", encoding="utf-8") as f, torch.inference_mode():
            for r in veriler["valid"][0]:
                ids = sablon_ids(tok, mesajlar(r, veriler["valid"][1], kol)[:2], True)
                girdi = torch.tensor([ids], device=model.device)
                sonuc = model.generate(
                    input_ids=girdi,
                    attention_mask=torch.ones_like(girdi),
                    do_sample=False,
                    num_beams=1,
                    max_new_tokens=a.max_new_tokens,
                    use_cache=True,
                    pad_token_id=tok.pad_token_id,
                )
                yeni = sonuc[0, len(ids) :]
                ad, en, tr, gecerli = ad_ayikla(tok.decode(yeni, skip_special_tokens=True))
                satir = {
                    "id": r["id"],
                    "gercek": r["gercek_ad"],
                    "tahmin": ad,
                    "aciklama_en": en,
                    "aciklama": tr,
                    "gecerli_json": gecerli,
                    "f1": f1(ad, r["gercek_ad"]),
                    "opt": r["opt"],
                    "proje": r["proje"],
                    "token": len(ids) + len(yeni),
                }
                f.write(json.dumps(satir, ensure_ascii=False) + "\n")
                rs.append(satir)
        uretim_sn = time.monotonic() - bas
        model.save_pretrained(yol / "adaptor", safe_serialization=True, save_embedding_layers=False)
        tok.save_pretrained(yol / "adaptor")
        metric, _ = puanla(rs, capa)
        json_yaz(
            yol / "tamam.json",
            {
                **metric,
                "eval_loss": loss,
                "steps": trainer.state.global_step,
                "train_seconds": egitim_sn,
                "generation_seconds": uretim_sn,
                "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                "actual_train_tokens": sum(len(x["input_ids"]) for x in kod[kol]["train"]),
            },
        )
        sonuclar[kol] = rs
        del trainer, model
        gc.collect()
        torch.cuda.empty_cache()
    json_yaz(kok / "karsilastirma.json", karsilastir(sonuclar["asm"], sonuclar["combined"], capa))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=("plan", "run"))
    for ad in ("train", "valid", "train-v6", "valid-v6", "dogrulama-raporu", "dogrulanmis-idler", "output"):
        ap.add_argument("--" + ad, type=Path, required=True)
    ap.add_argument("--model", type=Path, help="run için hazırlanmış yerel dense Qwen3 dizini; ağdan indirilmez")
    ap.add_argument("--steps", type=int, default=100)
    ap.add_argument("--micro-batch", type=int, default=1)
    ap.add_argument("--max-length", type=int, default=4096)
    ap.add_argument("--max-new-tokens", type=int, default=160)
    ap.add_argument("--max-train-tokens", type=int, default=8_000_000, help="kol başına padded token bütçesi")
    a = ap.parse_args(argv)
    if a.mode == "run" and a.model is None:
        ap.error("run için --model gerekli")
    try:
        capa = valid_capasi()
        veriler, izler = girdileri_oku(a, capa, proje_capasi())
        plan, secili = planla(a, veriler, izler)
        kok = yeni_cikti(a.output)
        json_yaz(kok / "plan.json", plan)
        if a.mode == "run":
            gpu_calistir(a, veriler, secili, plan, kok, capa)
        print(json.dumps(plan if a.mode == "plan" else {"status": "completed", "output": kok.name}, ensure_ascii=False))
    except ImportError:
        ap.exit(2, "İsteğe bağlı GPU bağımlılıkları eksik; lora/requirements-v6.txt dosyasına bakın.\n")
    except (ValueError, OSError) as hata:
        mesaj = str(hata) if isinstance(hata, ValueError) else "girdi/çıktı dosyası kullanılamadı"
        ap.exit(2, f"Pilot durdu: {mesaj}\n")


if __name__ == "__main__":
    main()
