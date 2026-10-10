#!/usr/bin/env python3
"""Sonraki deney verisi: girdi = asm + çağrı bağlamı, hedef = ad + kısa açıklama.

  .venv/bin/python lora/hazirla_sonraki.py --cikti lora/veri-sonraki

Kaynak: veri/bin/olcek/{egitim,dogrulama,test}.jsonl (hazirla_olcek.py ile aynı proje bazlı ayrım)
ve veri/aciklama-v4/codex.jsonl ("proje/dosya:ad" anahtarlı öğretmen açıklamaları).
Açıklaması olmayan satır train/valid'den atılır; testte kalır (hedefte yalnız ad), puan ada bakar.
Ek alanlar: proje, baglam_var, gercek_ad (önekli ham ad; taban.py ile aynı puan buna göre),
oneksiz_onek (ozet.ONEK'teki proje öneki; notebook öneksiz F1'i iki_f1.py ile aynı hesaplasın diye).

v2 (önerilen): --onek-kurali proje --test-ham-ad. ozet.ONEK veri/egitim ve veri/test'ten okunur:
betiği o dizinlerin bulunduğu repo kökünden çalıştırın.

v5: --surum v5 --cikti lora/veri-v5. Üç alanlı hedef, açıklamasızlarda yalnız ad,
proje öneki, ham test adları, jenerik ad filtresi, fonksiyon kapsamı ve opt dengesi.
1.500'den fazla fonksiyonlu projelerde varsayılan kapsam önceliklidir; kesin
tavan için --kapsam-onceligi tavan. Her iki durumda istisnalar özete yazılır.
Qwen3 tokenizer tercih edilir, indirilemezse önbellekteki Qwen2.5 kullanılır.

v6: --surum v6 --decompile veri/decompile-v6 --cikti lora/veri-v6. v5'in
satırlarına, sığdığı ölçüde anonim Ghidra decompile metni eklenir. Birden
fazla --decompile verilebilir; sonraki dizin aynı id için öncekini geçersiz kılar.
"""
import argparse, json, math, random, re, sys
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(Path(__file__).resolve().parent.parent))
import hazirla as h
from hazirla_olcek import onekler


def acikla_oku(yol: Path) -> dict[str, str]:
    return {r["anahtar"]: r["aciklama"] for r in map(json.loads, yol.open()) if r.get("aciklama")}


def satir(r: dict, aciklama, a, ham: bool = False) -> dict:
    hedef = {"ad": r["ad"] if ham else h.oneksiz(r)}
    if aciklama:
        hedef["aciklama"] = aciklama
    return {"messages": [{"role": "system", "content": h.SISTEM_ACIKLAMA},
                         {"role": "user", "content": h.girdi(r, "ozet", a.satir_tavan, a.token_tavan)},
                         {"role": "assistant", "content": json.dumps(hedef, ensure_ascii=False)}],
            "id": r["id"], "proje": r["proje"], "opt": r["opt"],
            "baglam_var": bool(r.get("baglam")), "gercek_ad": r["ad"],
            "oneksiz_onek": sorted(OZET_ONEK.get(r["proje"], ()))}


OZET_ONEK: dict[str, set[str]] = {}


JENERIK = re.compile(r"^(main|init|foo|bar|baz|helper|test|f[0-9]+|test_.*|sub_.*)$", re.I)
OPT_AGIRLIK = {"-O0": .15, "-O1": .20, "-O2": .25, "-O3": .20, "-Os": .20}
YEDEK_TOKENIZER = "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"
DECOMPILE_KIRPMA = "/* ... kırpıldı */"
TANIMLAYICI = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
ITHAL_YORUM = re.compile(r";\s*->\s*([A-Za-z_][A-Za-z0-9_]*)")
# Projede aynı adla bir sarmalayıcı olsa bile bunlar decompiler/import gürültüsü
# sayılır. Diğer adlar zaten ancak projenin gerçek ad listesinde ise ölçülür.
LIBC_ADLARI = {
    "abort", "abs", "calloc", "close", "exit", "fclose", "fflush", "fopen", "fprintf",
    "free", "fread", "fwrite", "malloc", "memcmp", "memcpy", "memmove", "memset", "open",
    "printf", "puts", "qsort", "read", "realloc", "snprintf", "sprintf", "strcat", "strchr",
    "strcmp", "strcpy", "strdup", "strlen", "strncmp", "strncpy", "strrchr", "strstr", "write",
}
GHIDRA_YEREL_ADI = re.compile(
    r"(?:param_[0-9]+|local_[0-9a-f]+|[A-Za-z]+Var[0-9]+|[A-Za-z]+Stack_[0-9a-f]+|"
    r"extraout_[A-Za-z0-9_]+|in_[A-Za-z0-9_]+|unaff_[A-Za-z0-9_]+|register0x[0-9a-f]+)",
    re.IGNORECASE,
)


def anahtar(r):
    return f"{r['proje']}/{r['dosya']}:{r['ad']}"


def jsonl_oku(yol):
    with yol.open(encoding="utf-8") as f:
        for l in f:
            if l.strip():
                yield json.loads(l)


def aciklama_yollarini_tamamla(a):
    """Worktree'de yalnız veri/bin bağlıysa açıklamaları onun veri kökünde bul."""
    kok = a.veri.resolve().parents[1]
    varsayilanlar = (("aciklama", Path("veri/aciklama-v4/codex.jsonl"),
                      kok / "aciklama-v4/codex.jsonl"),
                     ("aciklama_detay", Path("veri/aciklama-v4/codex-detay.jsonl"),
                      kok / "aciklama-v4/codex-detay.jsonl"))
    for alan, varsayilan, aday in varsayilanlar:
        if getattr(a, alan) == varsayilan and not varsayilan.exists() and aday.exists():
            setattr(a, alan, aday)


def satir_v5(r, tr, en, a, ham=False):
    # Kısmi öğretmen hedefleri kullanılmaz: ya üç alan ya yalnız ad.
    tam = bool(tr and en)
    hedef = {}
    if tam:
        hedef["aciklama_en"] = en
    hedef["ad"] = r["ad"] if ham else h.oneksiz(r)
    if tam:
        hedef["aciklama"] = tr
    girdi = h.girdi(r, "ozet", a.satir_tavan, a.token_tavan)
    # Eski girdi() çok uzun tek asm satırını kesmez; v5'te tavan yine geçerli.
    if a.token_tavan and len(h.TOK.encode(girdi)) > a.token_tavan:
        girdi = h.TOK.decode(h.TOK.encode(girdi)[:a.token_tavan])
        while len(h.TOK.encode(girdi)) > a.token_tavan:
            girdi = girdi[:-1]
    return {"messages": [{"role": "system", "content": h.SISTEM_V5},
                         {"role": "user", "content": girdi},
                         {"role": "assistant", "content": json.dumps(hedef, ensure_ascii=False)}],
            "id": r["id"], "proje": r["proje"], "opt": r["opt"],
            "baglam_var": bool(r.get("baglam")), "gercek_ad": r["ad"],
            "oneksiz_onek": sorted(OZET_ONEK.get(r["proje"], ())),
            "hedef_tur": "tam" if tam else "ad"}


def _toplam_token(satir):
    return len(h.TOK.apply_chat_template(satir["messages"], tokenize=True,
                                         add_generation_prompt=False, enable_thinking=False,
                                         return_dict=False))


def _sabit_maskesi(metin):
    """C string/char sabitlerindeki karakterleri işaretle; kaçışları koru."""
    maske = bytearray(len(metin))
    durum = "kod"
    i = 0
    while i < len(metin):
        c = metin[i]
        sonraki = metin[i + 1] if i + 1 < len(metin) else ""
        if durum == "kod":
            if c in "\"'":
                durum = "string" if c == '"' else "char"
                maske[i] = 1
            elif c == "/" and sonraki == "/":
                durum = "satir_yorum"
                i += 1
            elif c == "/" and sonraki == "*":
                durum = "blok_yorum"
                i += 1
        elif durum == "satir_yorum":
            if c == "\n":
                durum = "kod"
        elif durum == "blok_yorum":
            if c == "*" and sonraki == "/":
                durum = "kod"
                i += 1
        else:
            maske[i] = 1
            if c == "\\" and i + 1 < len(metin):
                i += 1
                maske[i] = 1
            elif (durum == "string" and c == '"') or (durum == "char" and c == "'"):
                durum = "kod"
        i += 1
    return maske


def _ad_aliaslari(adlar):
    """Gerçek ada ek olarak Mach-O baştaki alt çizgi biçimini kabul et."""
    if isinstance(adlar, dict):
        return adlar
    gercek = sorted({ad for ad in adlar if TANIMLAYICI.fullmatch(ad)})
    alias = {ad: ad for ad in gercek}
    for ad in gercek:
        alias.setdefault("_" + ad, ad)
    return alias


def _istisna_mi(token, gercek_ad, istisnalar):
    yalniz = token[1:] if token.startswith("_") else token
    gercek_yalniz = gercek_ad[1:] if gercek_ad.startswith("_") else gercek_ad
    return (token in istisnalar or yalniz in istisnalar or gercek_ad in istisnalar or
            gercek_yalniz in istisnalar or GHIDRA_YEREL_ADI.fullmatch(token) is not None)


def _islev_konumu(metin, bas, son):
    """Doğrudan çağrı/bildirim veya açık `&ad` adres konumunu tanı."""
    once = bas - 1
    while once >= 0 and metin[once].isspace():
        once -= 1
    sonra = son
    while sonra < len(metin) and metin[sonra].isspace():
        sonra += 1
    alan = once >= 0 and (metin[once] == "." or
                           (metin[once] == ">" and once and metin[once - 1] == "-"))
    return (sonra < len(metin) and metin[sonra] == "(" and not alan) or (once >= 0 and metin[once] == "&")


def proje_ad_eslesmeleri(metin, adlar, istisnalar=()):
    """String/char dışındaki gerçek proje adlarını konumlarıyla döndür."""
    alias = _ad_aliaslari(adlar)
    istisnalar = set(istisnalar) | LIBC_ADLARI
    istisnalar.update(ad[1:] for ad in list(istisnalar) if ad.startswith("_") and len(ad) > 1)
    maske = _sabit_maskesi(metin)
    sonuc = []
    for es in TANIMLAYICI.finditer(metin):
        token = es.group()
        gercek_ad = alias.get(token)
        if gercek_ad is None or maske[es.start()] or _istisna_mi(token, gercek_ad, istisnalar):
            continue
        sonuc.append((es, gercek_ad, "islev" if _islev_konumu(metin, *es.span()) else "diger"))
    return sonuc


def proje_adlarini_anonimlestir(metin, adlar, istisnalar=()):
    """Yalnız güvenli işlev/adres konumlarını FUN_xN biçimine çevir."""
    aliaslar = _ad_aliaslari(adlar)
    eslesmeler = proje_ad_eslesmeleri(metin, aliaslar, istisnalar)
    mevcut = set(TANIMLAYICI.findall(metin)) | set(aliaslar)
    ad_haritasi = {}
    sira = 1
    parcalar, konum = [], 0
    degisen_satirlar = set()
    for es, gercek_ad, tur in eslesmeler:
        if tur != "islev":
            continue
        if gercek_ad not in ad_haritasi:
            while f"FUN_x{sira}" in mevcut:
                sira += 1
            ad_haritasi[gercek_ad] = f"FUN_x{sira}"
            mevcut.add(ad_haritasi[gercek_ad])
            sira += 1
        parcalar.extend((metin[konum:es.start()], ad_haritasi[gercek_ad]))
        konum = es.end()
        degisen_satirlar.add(metin.count("\n", 0, es.start()) + 1)
    parcalar.append(metin[konum:])
    islev = sum(tur == "islev" for _, _, tur in eslesmeler)
    diger = len(eslesmeler) - islev
    return "".join(parcalar), {
        "islev_adres_eslesmesi": islev,
        "diger_konum_eslesmesi": diger,
        "degisim": islev,
        "degisen_satir": len(degisen_satirlar),
    }


def ad_sizintisi(metin, adlar):
    """Adları string/char dışında tam C tanımlayıcısı olarak ara."""
    aranan = {x.casefold() for ad in adlar if ad for x in (ad, "_" + ad)}
    maske = _sabit_maskesi(metin)
    for es in TANIMLAYICI.finditer(metin):
        if not maske[es.start()] and es.group().casefold() in aranan:
            return es.group()
    return None


def decompile_kirp(satir, decompile, max_uzunluk, alt_sinir):
    """Decompile'ı satır bazında sığdır; (metin, kırpıldı) veya (None, False)."""
    taban = satir["messages"][1]["content"]

    def dene(metin):
        satir["messages"][1]["content"] = taban + h.DECOMPILE_BASLIK + metin
        return _toplam_token(satir) <= max_uzunluk

    try:
        if dene(decompile):
            return decompile, False
        satirlar = decompile.splitlines()
        # En uzun sığan satır önekini bul. Son denetim tokenizer'ın nadir
        # monoton olmayan parçalanmalarına karşı aşağı doğru tarar.
        alt, ust, iyi = 0, len(satirlar), 0
        while alt <= ust:
            orta = (alt + ust) // 2
            aday = "\n".join(satirlar[:orta] + [DECOMPILE_KIRPMA])
            if dene(aday):
                iyi, alt = orta, orta + 1
            else:
                ust = orta - 1
        while iyi and not dene("\n".join(satirlar[:iyi] + [DECOMPILE_KIRPMA])):
            iyi -= 1
        govde = "\n".join(satirlar[:iyi])
        if iyi == 0 or len(h.TOK.encode(govde)) < alt_sinir:
            return None, False
        return govde + "\n" + DECOMPILE_KIRPMA, True
    finally:
        satir["messages"][1]["content"] = taban


def satir_v6(r, tr, en, a, decompile_kaydi=None, ham=False, esleme="id", taban_satir=None,
             proje_adlari=()):
    """v5 satırını ve asm/bağlamını koruyup güvenli decompile ekle."""
    s = (satir_v5(r, tr, en, a, ham) if taban_satir is None else
         {**taban_satir, "messages": [dict(m) for m in taban_satir["messages"]]})
    s["messages"][0]["content"] = h.SISTEM_V6
    s.update({"decompile_var": False, "decompile_kirpildi": False,
              "decompile_sizinti": False, "decompile_ham_sizinti": False,
              "decompile_ad_anonim_degisim": 0, "decompile_ad_anonim_satir": 0,
              "decompile_esleme": esleme if decompile_kaydi else "yok",
              "decompile_yok_neden": "eksik" if not decompile_kaydi else None})
    if not decompile_kaydi or not decompile_kaydi.get("decompile"):
        return s
    metin = decompile_kaydi["decompile"]
    s["decompile_ham_sizinti"] = bool(decompile_kaydi.get("sizinti"))
    metin, ad_anonim = proje_adlarini_anonimlestir(
        metin, proje_adlari, ITHAL_YORUM.findall(r.get("asm", "")),
    )
    s["decompile_ad_anonim_degisim"] = ad_anonim["degisim"]
    s["decompile_ad_anonim_satir"] = ad_anonim["degisen_satir"]
    sizan = ad_sizintisi(metin, (r["ad"], h.oneksiz(r)))
    if sizan:
        s["decompile_sizinti"] = True
        s["decompile_yok_neden"] = "hedef_ad_sizintisi"
        return s
    metin, kirpildi = decompile_kirp(s, metin, a.max_uzunluk, a.decompile_alt_token)
    if metin is None:
        s["decompile_yok_neden"] = "butce_alt_sinir"
        return s
    s["messages"][1]["content"] += h.DECOMPILE_BASLIK + metin
    s["decompile_var"] = True
    s["decompile_kirpildi"] = kirpildi
    s["decompile_yok_neden"] = None
    return s


def decompile_dizinlerini_oku(dizinler):
    """Yalnız tamamlanmış *.jsonl projelerini oku; *.ara dosyalarına dokunma."""
    sonuc, projeler, yinelenen = {}, set(), 0
    for dizin in dizinler:
        if not dizin.is_dir():
            raise FileNotFoundError(f"decompile dizini bulunamadı: {dizin}")
        for yol in sorted(dizin.glob("*.jsonl")):
            projeler.add(yol.stem)
            for no, r in enumerate(jsonl_oku(yol), 1):
                if not {"id", "decompile", "sizinti"} <= r.keys():
                    raise ValueError(f"{yol}:{no}: id/decompile/sizinti alanı eksik")
                yinelenen += r["id"] in sonuc
                sonuc[r["id"]] = {**r, "_kaynak_dizin": str(dizin)}
    return sonuc, projeler, yinelenen


def eval_esleme_indeksi(yollar, eval_satirlari):
    """Eski eval115 id'lerini v6 ölçek id'lerine bağlamak için küçük indeks."""
    indeks = defaultdict(list)
    istenen = {(r["proje"], r["dosya"], r["ad"], r["opt"]) for r in eval_satirlari}
    for yol in yollar:
        for r in jsonl_oku(yol):
            key = (r["proje"], r["dosya"], r["ad"], r["opt"])
            if key in istenen:
                indeks[key].append((r["id"], r["asm"]))
    return indeks


def decompile_kaydi_bul(r, decompile, eval_indeksi=None):
    if r["id"] in decompile:
        return decompile[r["id"]], "id"
    if eval_indeksi is None:
        return None, "yok"
    adaylar = eval_indeksi.get((r["proje"], r["dosya"], r["ad"], r["opt"]), ())
    # Derleyici/hattı aynıysa asm eşitliği en güçlü kanıt; eski v3 asm'si
    # değişmişse benzersiz proje+dosya+ad+opt eşlemesi kullanılabilir.
    asm = [kimlik for kimlik, metin in adaylar if metin == r["asm"] and kimlik in decompile]
    if len(asm) == 1:
        return decompile[asm[0]], "asm"
    uygun = [kimlik for kimlik, _ in adaylar if kimlik in decompile]
    if len(uygun) == 1:
        return decompile[uygun[0]], "proje+dosya+ad+opt"
    return None, "yok"


def tamligi_denetle(gerekli_projeler, tamam_projeler, tam_zorunlu=False):
    eksik = sorted(set(gerekli_projeler) - set(tamam_projeler))
    if tam_zorunlu and eksik:
        raise ValueError(f"--tam-zorunlu: {len(eksik)} proje henüz tamamlanmamış: {eksik[:10]}")
    return eksik


def egitim_sec_v5(rs, hedef=95000, proje_tavan=1500, tohum=7, kapsam_onceligi=True):
    """İlk varyantlar önce; sonra farklı opt'lu en çok bir ek varyant.

    rs, kaynak anahtarı ve hazırlanmış satır içeren kayıtlardır. Ağırlık satır
    sayısına değil opt'a uygulanır. Girdi sırasından bağımsız, tohumlu seçim.
    Kapsam ve tavan çelişirse varsayılan olarak kapsam korunur.
    """
    gruplar = defaultdict(list)
    for r in rs:
        gruplar[r["kaynak"]].append(r)
    rng = random.Random(tohum)
    ilkler, ikinciler = [], []
    for key in sorted(gruplar):
        opts = defaultdict(list)
        for r in sorted(gruplar[key], key=lambda x: x["satir"]["id"]):
            opts[r["satir"]["opt"]].append(r)
        secimler = []
        for _ in range(min(2, len(opts))):
            adlar = sorted(opts)
            opt = rng.choices(adlar, weights=[OPT_AGIRLIK.get(o, .2) for o in adlar])[0]
            secimler.append(rng.choice(opts.pop(opt)))
        ilkler.append(secimler[0])
        if len(secimler) > 1:
            ikinciler.append(secimler[1])
    rng.shuffle(ilkler)
    rng.shuffle(ikinciler)
    sonuc, say = [], Counter()
    for r in ilkler:
        p = r["satir"]["proje"]
        if kapsam_onceligi or not proje_tavan or say[p] < proje_tavan:
            sonuc.append(r)
            say[p] += 1
    ilk_sayi = len(sonuc)
    for r in ikinciler:
        p = r["satir"]["proje"]
        if len(sonuc) >= hedef:
            break
        if not proje_tavan or say[p] < proje_tavan:
            sonuc.append(r)
            say[p] += 1
    rng.shuffle(sonuc)
    return sonuc, {"uygun_fonksiyon": len(gruplar), "secilen_fonksiyon": ilk_sayi,
                   "tavandan_atilan_fonksiyon": len(gruplar) - ilk_sayi,
                   "ikinci_varyant": len(sonuc) - ilk_sayi,
                   "hedef_satir": hedef, "hedefe_eksik": max(0, hedef - len(sonuc)),
                   "tavan_asan_projeler": dict(sorted((p, n) for p, n in say.items()
                                                       if proje_tavan and n > proje_tavan))}


def dengeli_sec_v5(rs, n=300, tohum=7):
    rng = random.Random(tohum)
    projeler = defaultdict(list)
    for r in sorted(rs, key=lambda x: x["satir"]["id"]):
        projeler[r["satir"]["proje"]].append(r)
    for p in sorted(projeler):
        rng.shuffle(projeler[p])
    sonuc = []
    while len(sonuc) < n and any(projeler.values()):
        for p in sorted(projeler):
            if projeler[p] and len(sonuc) < n:
                sonuc.append(projeler[p].pop())
    return sonuc


def yuzdelikler(ns):
    ns = sorted(ns)
    if not ns:
        return dict.fromkeys(("p50", "p90", "p99", "maks"), 0)
    return {**{f"p{p}": ns[max(0, math.ceil(len(ns) * p / 100) - 1)] for p in (50, 90, 99)},
            "maks": ns[-1]}


def puan_onekleri(veri):
    """ozet.onekler ölçütü; cwd yerine kaynak veri kökünü kullanır."""
    from taban import kelimeler
    sonuc = {}
    for p in sorted([*veri.glob("egitim/*.jsonl"), *veri.glob("test/*.jsonl")]):
        adlar = [kelimeler(r["ad"]) for r in jsonl_oku(p)]
        say = Counter(k[0] for k in adlar if len(k) > 1)
        proje = p.stem.lower().replace("_", "").removeprefix("lib")
        ilgili = lambda k: proje.startswith(k.rstrip("0123456789")) or (len(k) <= 3 and proje.startswith(k[0]))
        sonuc[p.stem] = {k for k, n in say.items() if n >= .1 * len(adlar) and ilgili(k)}
    return sonuc


def tokenizer_v5(a):
    from transformers import AutoTokenizer
    tercih = a.tokenizer or "Qwen/Qwen3-8B"
    try:
        tok = AutoTokenizer.from_pretrained(tercih, cache_dir=str(a.tokenizer_cache) if a.tokenizer_cache else None)
        return tok, {"kullanilan": tercih, "tercih": tercih, "yedek_nedeni": None}
    except (OSError, ValueError) as e:
        if a.tokenizer:
            raise
        tok = AutoTokenizer.from_pretrained(YEDEK_TOKENIZER, local_files_only=True)
        return tok, {"kullanilan": YEDEK_TOKENIZER, "tercih": tercih,
                     "yedek_nedeni": f"{type(e).__name__}: Qwen3 indirilemedi/önbellekte yok"}


def proje_adlarini_oku(veri, ham_yolu=None):
    """Üç ana bölme ve varsa filtresiz v6 ham çıktısından proje ad kümesi kur."""
    yollar = [veri / f"{ad}.jsonl" for ad in ("egitim", "dogrulama", "test")]
    if ham_yolu and ham_yolu.is_dir():
        yollar.extend(sorted(ham_yolu.rglob("*.jsonl")))
    adlar, id_ithalleri = defaultdict(set), defaultdict(set)
    satir_sayisi = 0
    for yol in yollar:
        if not yol.is_file():
            continue
        for r in jsonl_oku(yol):
            if not {"proje", "ad"} <= r.keys():
                continue
            satir_sayisi += 1
            adlar[r["proje"]].add(r["ad"])
            if r.get("id") and r.get("asm"):
                id_ithalleri[r["id"]].update(ITHAL_YORUM.findall(r["asm"]))
    return adlar, id_ithalleri, {
        "dosya": len([yol for yol in yollar if yol.is_file()]),
        "satir": satir_sayisi,
        "proje": len(adlar),
        "benzersiz_ad": sum(map(len, adlar.values())),
        "filtresiz_ham": str(ham_yolu) if ham_yolu and ham_yolu.is_dir() else None,
    }


def baska_ad_olc(decompile, proje_adlari, id_ithalleri=None, ornek_tavan=200):
    """Dönüşümü tüm kayıtlarda, kalan oranı proje başına örneklemde ölç."""
    gruplar = defaultdict(list)
    for kimlik, kayit in decompile.items():
        gruplar[kimlik.split("/", 1)[0]].append((kimlik, kayit["decompile"]))
    toplam = Counter()
    degisen_kayit = 0
    for proje in sorted(gruplar):
        aliaslar = _ad_aliaslari(proje_adlari.get(proje, ()))
        for kimlik, metin in gruplar[proje]:
            _, sayac = proje_adlarini_anonimlestir(
                metin, aliaslar, (id_ithalleri or {}).get(kimlik, ()),
            )
            toplam.update(sayac)
            degisen_kayit += bool(sayac["degisim"])

    denetlenen = once_sizintili = kalan_sizintili = diger_konumlu = 0
    ornekler, diger_ornekler = [], []
    for proje in sorted(gruplar):
        tum_adlar = set(proje_adlari.get(proje, ()))
        for kimlik, metin in sorted(gruplar[proje])[:ornek_tavan]:
            denetlenen += 1
            hedef = kimlik.rsplit(":", 1)[-1]
            adlar = tum_adlar - {hedef}
            istisnalar = (id_ithalleri or {}).get(kimlik, ())
            once = proje_ad_eslesmeleri(metin, adlar, istisnalar)
            anonim, _ = proje_adlarini_anonimlestir(metin, adlar, istisnalar)
            kalan = proje_ad_eslesmeleri(anonim, adlar, istisnalar)
            once_islev = sorted({gercek for _, gercek, tur in once if tur == "islev"})
            kalan_islev = sorted({gercek for _, gercek, tur in kalan if tur == "islev"})
            kalan_diger = sorted({gercek for _, gercek, tur in kalan if tur == "diger"})
            if once_islev:
                once_sizintili += 1
            if kalan_islev:
                kalan_sizintili += 1
                if len(ornekler) < 20:
                    ornekler.append({"id": kimlik, "adlar": kalan_islev[:8]})
            if kalan_diger:
                diger_konumlu += 1
                if len(diger_ornekler) < 20:
                    diger_ornekler.append({"id": kimlik, "adlar": kalan_diger[:8]})
    return {"orneklem": denetlenen, "sizintili": kalan_sizintili,
            "oran": kalan_sizintili / denetlenen if denetlenen else 0,
            "donusum_oncesi_islevsel_sizintili": once_sizintili,
            "donusum_oncesi_islevsel_oran": once_sizintili / denetlenen if denetlenen else 0,
            "diger_konumlu": diger_konumlu,
            "diger_konumlu_oran": diger_konumlu / denetlenen if denetlenen else 0,
            "islev_adres_eslesmesi": toplam["islev_adres_eslesmesi"],
            "diger_konum_eslesmesi": toplam["diger_konum_eslesmesi"],
            "degistirilen_kayit": degisen_kayit,
            "degistirilen_satir": toplam["degisen_satir"],
            "degisim": toplam["degisim"],
            "ornekler": ornekler, "diger_konum_ornekleri": diger_ornekler,
            "proje_basi_tavan": ornek_tavan,
            "not": "String/char sabitleri, satır ASM importları, libc/sistem adları, hedef ad ve Ghidra yerelleri hariç. Yalnız çağrı/bildirim ve açık &ad konumları değiştirilir; diğer konumlar ölçülür ama korunur."}


def decompile_ham_olcumunu_ekle(olcumler, r, taban_satir, kayit, max_uzunluk, satir_tavan=200):
    """Kural uygulanmadan önce asm/bağlam/decompile dağılımını biriktir."""
    asm = h.kes(r["asm"], satir_tavan)
    baglam = h.baglam_metni(r, "ozet")
    d = kayit["decompile"]
    user = taban_satir["messages"][1]["content"] + h.DECOMPILE_BASLIK + d
    aday = {**taban_satir, "messages": [dict(m) for m in taban_satir["messages"]]}
    aday["messages"][0]["content"] = h.SISTEM_V6
    aday["messages"][1]["content"] = user
    kaynak = kayit.get("_kaynak_dizin", "?")
    o = olcumler[kaynak]
    o["asm"].append(len(h.TOK.encode(asm)))
    o["baglam"].append(len(h.TOK.encode(baglam)))
    o["decompile"].append(len(h.TOK.encode(d)))
    o["v5_girdi_tavanina_sigan"].append(len(h.TOK.encode(user)) <= 2500)
    o["tam_3072_sigan"].append(_toplam_token(aday) <= max_uzunluk)


def ham_olcum_ozeti(olcumler):
    sonuc = {}
    for kaynak, o in sorted(olcumler.items()):
        n = len(o["decompile"])
        sonuc[kaynak] = {
            "satir": n,
            "token": {k: yuzdelikler(o[k]) for k in ("asm", "baglam", "decompile")},
            "v5_girdi_tavanina_sigan": sum(o["v5_girdi_tavanina_sigan"]),
            "v5_girdi_tavanina_sigan_oran": (sum(o["v5_girdi_tavanina_sigan"]) / n if n else 0),
            "tam_3072_sigan": sum(o["tam_3072_sigan"]),
            "tam_3072_sigan_oran": (sum(o["tam_3072_sigan"]) / n if n else 0),
        }
    return sonuc


def hazirla_v5(a):
    aciklama_yollarini_tamamla(a)
    if not 0 < a.token_tavan <= 2500:
        raise ValueError("v5 token tavanı 1..2500 olmalı")
    tr = acikla_oku(a.aciklama)
    en = {r["anahtar"]: r["aciklama_en"] for r in jsonl_oku(a.aciklama_detay) if r.get("aciklama_en")}
    yollar = {ad: a.veri / f"{dosya}.jsonl" for ad, dosya in
              (("train", "egitim"), ("valid", "dogrulama"), ("test", "test"))}
    yollar["eval115"] = a.eval115
    # İlk taramada asm'yi bellekte tutma; önekler yalnız proje/ad ile hesaplanır.
    h.ONEK = onekler((r for ad in ("train", "valid", "test") for r in jsonl_oku(yollar[ad])),
                    "proje", belirlenimci=True)
    OZET_ONEK.clear()
    OZET_ONEK.update(puan_onekleri(a.veri.resolve().parents[1]))
    idler = [s.strip() for s in a.test_idler.read_text().splitlines() if s.strip()]
    test_idler = Counter(r["id"] for r in jsonl_oku(yollar["test"]))
    eksik = [i for i in idler if not test_idler[i]]
    if eksik:
        raise ValueError(f"test_sabit eksik id ({len(eksik)}): {eksik[:5]}")
    if len(set(idler)) != len(idler) or any(test_idler[i] != 1 for i in idler):
        raise ValueError("test_sabit id'leri benzersiz olmalı")
    h.TOK, tok_ozet = tokenizer_v5(a)
    # girdi() kesme sırasında aynı metinleri, opt varyantları aynı hedefi tekrar sayar.
    h.TOK.encode = lru_cache(maxsize=4096)(h.TOK.encode)
    ozet = {"surum": "v5", "tohum": a.tohum, "valid_300_tohum": 7,
            "onek_kurali": "proje", "onek_atilan_proje": len(h.ONEK), "test_hedefi": "gercek",
            "tokenizer": tok_ozet, "token_tavan": a.token_tavan, "max_uzunluk": a.max_uzunluk,
            "sistem_token": len(h.TOK.encode(h.SISTEM_V5)),
            "toplam_token_olcumu": "chat_template, enable_thinking=False, add_generation_prompt=False",
            "proje_tavan": a.proje_tavan, "kapsam_onceligi": a.kapsam_onceligi == "kapsam",
            "opt_agirlik": OPT_AGIRLIK, "filtreler": {}}
    bolumler = {}
    for ad, yol in yollar.items():
        rs, kaynaklar, uygun_kaynaklar = [], set(), set()
        filtre = dict.fromkeys(("girdi", "jenerik", "aciklamasiz", "kismi_aciklama", "uzunluk_asan",
                               "uzunluktan_atilan"), 0)
        for r in jsonl_oku(yol):
            filtre["girdi"] += 1
            key = anahtar(r)
            if ad == "train" and JENERIK.fullmatch(r["ad"]):
                filtre["jenerik"] += 1
                continue
            kaynaklar.add(key)
            if not (tr.get(key) and en.get(key)):
                filtre["aciklamasiz"] += 1
                filtre["kismi_aciklama"] += bool(tr.get(key) or en.get(key))
            s = satir_v5(r, tr.get(key), en.get(key), a, ham=ad in ("test", "eval115"))
            m = s["messages"]
            token = {"girdi": len(h.TOK.encode(m[1]["content"])),
                     "hedef": len(h.TOK.encode(m[2]["content"])),
                     "toplam": len(h.TOK.apply_chat_template(m, tokenize=True, add_generation_prompt=False,
                                                            enable_thinking=False, return_dict=False))}
            if token["toplam"] > a.max_uzunluk:
                filtre["uzunluk_asan"] += 1
                if ad == "train":
                    filtre["uzunluktan_atilan"] += 1
                    continue
            uygun_kaynaklar.add(key)
            rs.append({"kaynak": key, "satir": s, "token": token})
            if filtre["girdi"] % 10000 == 0:
                print(f"{ad}: {filtre['girdi']} satır işlendi", file=sys.stderr, flush=True)
        filtre["uzunluktan_kaybolan_fonksiyon"] = len(kaynaklar - uygun_kaynaklar)
        if ad == "train":
            once = len(rs)
            rs, ozet["secim"] = egitim_sec_v5(rs, a.hedef_satir, a.proje_tavan, a.tohum,
                                             a.kapsam_onceligi == "kapsam")
            filtre["varyant_seciminde_atilan"] = once - len(rs)
        ozet["filtreler"][ad] = filtre
        bolumler[ad] = rs
    bolumler["valid_300"] = dengeli_sec_v5(bolumler["valid"], tohum=7)
    test = {r["satir"]["id"]: r for r in bolumler["test"]}
    bolumler["test_sabit"] = [test[i] for i in idler]
    a.cikti.mkdir(parents=True, exist_ok=True)
    for ad, rs in bolumler.items():
        with (a.cikti / f"{ad}.jsonl").open("w", encoding="utf-8") as f:
            for r in rs:
                f.write(json.dumps(r["satir"], ensure_ascii=False) + "\n")
        ss = [r["satir"] for r in rs]
        ozet[ad] = {"satir": len(rs), "proje": len({r["proje"] for r in ss}),
                    "fonksiyon": len({r["kaynak"] for r in rs}),
                    "baglam_var": sum(r["baglam_var"] for r in ss),
                    "opt": dict(sorted(Counter(r["opt"] for r in ss).items())),
                    "hedef_tur": dict(sorted(Counter(r["hedef_tur"] for r in ss).items())),
                    "token": {k: yuzdelikler([r["token"][k] for r in rs]) for k in ("girdi", "hedef", "toplam")},
                    "uzunluk_asan": sum(r["token"]["toplam"] > a.max_uzunluk for r in rs)}
    (a.cikti / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(ozet, ensure_ascii=False))


def hazirla_v6(a):
    """v5'in filtre/seçim kararlarını aynen kullanıp sonradan decompile ekle."""
    aciklama_yollarini_tamamla(a)
    if not 0 < a.token_tavan <= 2500:
        raise ValueError("v6 taban token tavanı 1..2500 olmalı")
    if a.decompile_alt_token < 1:
        raise ValueError("--decompile-alt-token en az 1 olmalı")
    tr = acikla_oku(a.aciklama)
    en = {r["anahtar"]: r["aciklama_en"] for r in jsonl_oku(a.aciklama_detay) if r.get("aciklama_en")}
    yollar = {ad: a.veri / f"{dosya}.jsonl" for ad, dosya in
              (("train", "egitim"), ("valid", "dogrulama"), ("test", "test"))}
    yollar["eval115"] = a.eval115
    h.ONEK = onekler((r for ad in ("train", "valid", "test") for r in jsonl_oku(yollar[ad])),
                    "proje", belirlenimci=True)
    OZET_ONEK.clear()
    OZET_ONEK.update(puan_onekleri(a.veri.resolve().parents[1]))
    idler = [s.strip() for s in a.test_idler.read_text().splitlines() if s.strip()]
    test_idler = Counter(r["id"] for r in jsonl_oku(yollar["test"]))
    eksik = [i for i in idler if not test_idler[i]]
    if eksik:
        raise ValueError(f"test_sabit eksik id ({len(eksik)}): {eksik[:5]}")
    if len(set(idler)) != len(idler) or any(test_idler[i] != 1 for i in idler):
        raise ValueError("test_sabit id'leri benzersiz olmalı")
    h.TOK, tok_ozet = tokenizer_v5(a)
    h.TOK.encode = lru_cache(maxsize=4096)(h.TOK.encode)
    sistem_token_farki = len(h.TOK.encode(h.SISTEM_V6)) - len(h.TOK.encode(h.SISTEM_V5))

    decompile, tamam_projeler, yinelenen = decompile_dizinlerini_oku(a.decompile)
    ham_adlar = getattr(a, "ham_adlar", Path("veri/olcek-v6/ham"))
    proje_adlari, id_ithalleri, ad_kaynagi = proje_adlarini_oku(a.veri, ham_adlar)
    proje_aliaslari = {proje: _ad_aliaslari(adlar) for proje, adlar in proje_adlari.items()}
    asm_uyusmaz = ({r["id"] for r in jsonl_oku(a.asm_uyusmaz)} if a.asm_uyusmaz.exists() else set())
    eval_satirlari = list(jsonl_oku(a.eval115))
    eval_indeksi = eval_esleme_indeksi((yollar[x] for x in ("train", "valid", "test")), eval_satirlari)
    ozet = {"surum": "v6", "taban_surum": "v5", "tohum": a.tohum, "valid_300_tohum": 7,
            "onek_kurali": "proje", "onek_atilan_proje": len(h.ONEK), "test_hedefi": "gercek",
            "tokenizer": tok_ozet, "token_tavan": a.token_tavan, "max_uzunluk": a.max_uzunluk,
            "decompile_alt_token": a.decompile_alt_token,
            "sistem_token": len(h.TOK.encode(h.SISTEM_V6)),
            "toplam_token_olcumu": "chat_template, enable_thinking=False, add_generation_prompt=False",
            "proje_tavan": a.proje_tavan, "kapsam_onceligi": a.kapsam_onceligi == "kapsam",
            "opt_agirlik": OPT_AGIRLIK, "filtreler": {},
            "decompile": {"dizinler": [str(x) for x in a.decompile], "kayit": len(decompile),
                          "tamam_proje": len(tamam_projeler), "yinelenen_id": yinelenen,
                          "proje_ad_kaynagi": ad_kaynagi}}
    bolumler, gerekli_projeler = {}, set()
    ham_olcum = defaultdict(lambda: defaultdict(list))
    olculen_decompile = set()
    for ad, yol in yollar.items():
        rs, kaynaklar, uygun_kaynaklar = [], set(), set()
        filtre = dict.fromkeys(("girdi", "jenerik", "aciklamasiz", "kismi_aciklama", "uzunluk_asan",
                               "uzunluktan_atilan"), 0)
        kaynak_satirlar = eval_satirlari if ad == "eval115" else jsonl_oku(yol)
        for r in kaynak_satirlar:
            filtre["girdi"] += 1
            if ad != "eval115":
                gerekli_projeler.add(r["proje"])
            key = anahtar(r)
            if ad == "train" and JENERIK.fullmatch(r["ad"]):
                filtre["jenerik"] += 1
                continue
            kaynaklar.add(key)
            if not (tr.get(key) and en.get(key)):
                filtre["aciklamasiz"] += 1
                filtre["kismi_aciklama"] += bool(tr.get(key) or en.get(key))
            ham = ad in ("test", "eval115")
            taban = satir_v5(r, tr.get(key), en.get(key), a, ham=ham)
            tm = taban["messages"]
            taban_token = {"girdi": len(h.TOK.encode(tm[1]["content"])),
                           "hedef": len(h.TOK.encode(tm[2]["content"])),
                           "toplam": _toplam_token(taban)}
            # Bu karar tam olarak v5'in kararıdır; v6 decompile yüzünden satır atmaz.
            if taban_token["toplam"] > a.max_uzunluk:
                filtre["uzunluk_asan"] += 1
                if ad == "train":
                    filtre["uzunluktan_atilan"] += 1
                    continue
            uygun_kaynaklar.add(key)
            kayit, esleme = decompile_kaydi_bul(r, decompile, eval_indeksi if ad == "eval115" else None)
            if kayit and kayit["id"] not in olculen_decompile:
                decompile_ham_olcumunu_ekle(ham_olcum, r, taban, kayit, a.max_uzunluk,
                                            a.satir_tavan)
                olculen_decompile.add(kayit["id"])
            s = satir_v6(r, tr.get(key), en.get(key), a, kayit, ham=ham, esleme=esleme,
                         taban_satir=taban, proje_adlari=proje_aliaslari.get(r["proje"], {}))
            if not kayit:
                if ad == "eval115":
                    s["decompile_yok_neden"] = "eval_eslesmedi"
                elif r["id"] in asm_uyusmaz:
                    s["decompile_yok_neden"] = "asm_uyusmaz"
                elif r["proje"] not in tamam_projeler:
                    s["decompile_yok_neden"] = "eksik_proje"
                else:
                    s["decompile_yok_neden"] = "uretilemedi"
            m = s["messages"]
            token = {"girdi": len(h.TOK.encode(m[1]["content"])),
                     "hedef": len(h.TOK.encode(m[2]["content"])),
                     # Decompile yoksa user/assistant ve sohbet sınırları aynıdır;
                     # yalnız sistem içeriğinin sabit token farkı eklenir.
                     "toplam": (_toplam_token(s) if s["decompile_var"] else
                                taban_token["toplam"] + sistem_token_farki)}
            if token["toplam"] > a.max_uzunluk and ad == "train":
                raise ValueError(f"{r['id']}: decompile'sız v6 satırı {token['toplam']} > {a.max_uzunluk}; "
                                 "asm/bağlamı değiştirmeden v5 satırı korunamıyor")
            s["token"] = token
            rs.append({"kaynak": key, "satir": s, "token": token, "taban_token": taban_token})
            if filtre["girdi"] % 10000 == 0:
                print(f"{ad}: {filtre['girdi']} satır işlendi", file=sys.stderr, flush=True)
        filtre["uzunluktan_kaybolan_fonksiyon"] = len(kaynaklar - uygun_kaynaklar)
        if ad == "train":
            once = len(rs)
            rs, ozet["secim"] = egitim_sec_v5(rs, a.hedef_satir, a.proje_tavan, a.tohum,
                                             a.kapsam_onceligi == "kapsam")
            filtre["varyant_seciminde_atilan"] = once - len(rs)
        ozet["filtreler"][ad] = filtre
        bolumler[ad] = rs
    bolumler["valid_300"] = dengeli_sec_v5(bolumler["valid"], tohum=7)
    test = {r["satir"]["id"]: r for r in bolumler["test"]}
    bolumler["test_sabit"] = [test[i] for i in idler]

    eksik_projeler = tamligi_denetle(gerekli_projeler, tamam_projeler, a.tam_zorunlu)
    ozet["decompile"].update({"gerekli_proje": len(gerekli_projeler),
                              "eksik_proje": len(eksik_projeler),
                              "eksik_proje_ornek": eksik_projeler[:20],
                              "ham_token_olcumu": ham_olcum_ozeti(ham_olcum),
                              "baska_ad_sizintisi": baska_ad_olc(decompile, proje_adlari,
                                                                 id_ithalleri)})
    print(f"decompile tamam proje: {len(tamam_projeler)}; eksik proje: {len(eksik_projeler)}",
          file=sys.stderr)
    a.cikti.mkdir(parents=True, exist_ok=True)
    for ad, rs in bolumler.items():
        with (a.cikti / f"{ad}.jsonl").open("w", encoding="utf-8") as f:
            for r in rs:
                f.write(json.dumps(r["satir"], ensure_ascii=False) + "\n")
        ss = [r["satir"] for r in rs]
        neden = Counter(s.get("decompile_yok_neden") or "var" for s in ss)
        ozet[ad] = {"satir": len(rs), "proje": len({r["proje"] for r in ss}),
                    "fonksiyon": len({r["kaynak"] for r in rs}),
                    "baglam_var": sum(r["baglam_var"] for r in ss),
                    "opt": dict(sorted(Counter(r["opt"] for r in ss).items())),
                    "hedef_tur": dict(sorted(Counter(r["hedef_tur"] for r in ss).items())),
                    "token": {k: yuzdelikler([r["token"][k] for r in rs])
                              for k in ("girdi", "hedef", "toplam")},
                    "token_ortalama": {k: (sum(r["token"][k] for r in rs) / len(rs) if rs else 0)
                                       for k in ("girdi", "hedef", "toplam")},
                    "taban_token": {k: yuzdelikler([r["taban_token"][k] for r in rs])
                                    for k in ("girdi", "hedef", "toplam")},
                    "taban_token_ortalama": {
                        k: (sum(r["taban_token"][k] for r in rs) / len(rs) if rs else 0)
                        for k in ("girdi", "hedef", "toplam")},
                    "uzunluk_asan": sum(r["token"]["toplam"] > a.max_uzunluk for r in rs),
                    "v5_satir_kaybi": 0,
                    "decompile_var": sum(s["decompile_var"] for s in ss),
                    "decompile_var_oran": sum(s["decompile_var"] for s in ss) / len(ss) if ss else 0,
                    "decompile_kirpildi": sum(s["decompile_kirpildi"] for s in ss),
                    "decompile_kirpildi_oran": sum(s["decompile_kirpildi"] for s in ss) / len(ss) if ss else 0,
                    "decompile_sizinti": sum(s["decompile_sizinti"] for s in ss),
                    "decompile_sizinti_oran": sum(s["decompile_sizinti"] for s in ss) / len(ss) if ss else 0,
                    "decompile_ad_anonim_degisim": sum(s["decompile_ad_anonim_degisim"] for s in ss),
                    "decompile_ad_anonim_satir": sum(s["decompile_ad_anonim_satir"] for s in ss),
                    "decompile_esleme": dict(sorted(Counter(s["decompile_esleme"] for s in ss).items())),
                    "decompile_yok": len(ss) - sum(s["decompile_var"] for s in ss),
                    "decompile_yok_neden": dict(sorted(neden.items()))}
    (a.cikti / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(ozet, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--veri", type=Path, default=Path("veri/bin/olcek"))
    ap.add_argument("--aciklama", type=Path, default=Path("veri/aciklama-v4/codex.jsonl"))
    ap.add_argument("--cikti", type=Path, default=Path("lora/veri-sonraki"))
    ap.add_argument("--proje-tavan", type=int, default=1500,
                    help="proje başına satır (0=sınırsız); v5 kapsam önceliğinde ilk varyantlar korunur")
    ap.add_argument("--satir-tavan", type=int, default=200)
    ap.add_argument("--token-tavan", type=int, default=2500,
                    help="asm+bağlam token tavanı; notebook MAX_UZUNLUK=3072, sistem+cevaba ~500 pay")
    ap.add_argument("--tokenizer", default=None,
                    help="varsayılan eski akışta Qwen2.5; v5'te Qwen3-8B, indirilemezse Qwen2.5")
    ap.add_argument("--onek-kurali", choices=("siklik", "proje"), default="siklik",
                    help="hazirla_olcek.py ile aynı; proje: yalnız proje adıyla ilişkili önek (v2)")
    ap.add_argument("--test-ham-ad", action="store_true", help="test hedefinde gerçek adı koru (v2)")
    ap.add_argument("--tohum", type=int, default=7)
    ap.add_argument("--surum", choices=("v5", "v6"), default=None)
    ap.add_argument("--decompile", type=Path, action="append",
                    help="v6 decompile proje JSONL dizini; birden fazla kez verilebilir")
    ap.add_argument("--decompile-alt-token", type=int, default=200,
                    help="kırpılmış decompile gövdesi için alt token sınırı")
    ap.add_argument("--tam-zorunlu", action="store_true",
                    help="v6'da herhangi bir kaynak projenin tamamlanmış JSONL'i yoksa hata ver")
    ap.add_argument("--asm-uyusmaz", type=Path, default=Path("veri/olcek-v6/asm-uyusmaz.jsonl"),
                    help="v6 ikilisiyle asm'si uyuşmayan ve decompile beklenmeyen id'ler")
    ap.add_argument("--ham-adlar", type=Path, default=Path("veri/olcek-v6/ham"),
                    help="varsa proje ad kümesine eklenecek filtresiz v6 ham JSONL kökü")
    ap.add_argument("--aciklama-detay", type=Path, default=Path("veri/aciklama-v4/codex-detay.jsonl"))
    ap.add_argument("--eval115", type=Path, default=Path("veri/test.jsonl"))
    ap.add_argument("--test-idler", type=Path, default=Path(__file__).with_name("test_sabit_idler.txt"))
    ap.add_argument("--tokenizer-cache", type=Path)
    ap.add_argument("--max-uzunluk", type=int, default=3072)
    ap.add_argument("--hedef-satir", type=int, default=95000)
    ap.add_argument("--kapsam-onceligi", choices=("kapsam", "tavan"), default="kapsam")
    a = ap.parse_args()
    if a.surum == "v5":
        hazirla_v5(a)
        return
    if a.surum == "v6":
        if not a.decompile:
            ap.error("--surum v6 için --decompile DIZIN gerekli")
        hazirla_v6(a)
        return
    a.tokenizer = a.tokenizer or YEDEK_TOKENIZER
    if a.token_tavan:
        from transformers import AutoTokenizer
        h.TOK = AutoTokenizer.from_pretrained(a.tokenizer)
    aciklamalar = acikla_oku(a.aciklama)
    ayrim = {ad: [json.loads(l) for l in (a.veri / f"{dosya}.jsonl").open()]
             for ad, dosya in (("train", "egitim"), ("valid", "dogrulama"), ("test", "test"))}
    h.ONEK = onekler([r for v in ayrim.values() for r in v], a.onek_kurali)
    import ozet as ozet_modulu  # import anında cwd'deki veri/egitim ve veri/test'ten önek çıkarır
    OZET_ONEK.update(ozet_modulu.ONEK)
    anahtar = lambda r: f"{r['proje']}/{r['dosya']}:{r['ad']}"
    ozet = {"onek_atilan_proje": len(h.ONEK), "onek_kurali": a.onek_kurali,
            "test_hedefi": "gercek" if a.test_ham_ad else "oneksiz", "token_tavan": a.token_tavan}
    for ad in ("train", "valid"):
        once = len(ayrim[ad])
        ayrim[ad] = [r for r in h.tekil(ayrim[ad]) if anahtar(r) in aciklamalar]
        ozet[f"{ad}_atilan(kopya+aciklamasiz)"] = once - len(ayrim[ad])
    if a.proje_tavan:
        gruplar = defaultdict(list)
        for r in ayrim["train"]:
            gruplar[r["proje"]].append(r)
        ayrim["train"] = [r for p, rs in sorted(gruplar.items())
                          for r in (random.Random(f"{p}{a.tohum}").sample(rs, a.proje_tavan)
                                    if len(rs) > a.proje_tavan else rs)]
    random.Random(a.tohum).shuffle(ayrim["train"])
    a.cikti.mkdir(parents=True, exist_ok=True)
    for ad, rs in ayrim.items():
        with (a.cikti / f"{ad}.jsonl").open("w") as f:
            for r in rs:
                ham = ad == "test" and a.test_ham_ad
                f.write(json.dumps(satir(r, aciklamalar.get(anahtar(r)), a, ham), ensure_ascii=False) + "\n")
        ozet[ad] = {"satir": len(rs), "proje": len({r["proje"] for r in rs}),
                    "baglam_var": sum(bool(r.get("baglam")) for r in rs),
                    "aciklamali": sum(anahtar(r) in aciklamalar for r in rs),
                    "opt": dict(sorted(Counter(r["opt"] for r in rs).items()))}
    (a.cikti / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(ozet, ensure_ascii=False))


if __name__ == "__main__":
    main()
