#!/usr/bin/env python3
"""Taban ölçüm: hazır bir Evren modeli stripped fonksiyona ne kadar doğru isim veriyor?

  python3 taban.py veri/zlib.jsonl -n 60 -m deepseek-v4.1-flash

Skor: tahmin ve gerçek adı kelimelere böl (snake/camel), kelime örtüşmesinin F1'i.
Tam doğruluk nadir olur; F1 "yakın mı" sorusunu ölçer (crc32_update ~ update_crc).
"""
import argparse, json, os, random, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = os.environ.get("EVREN_BASE_URL", "https://evren-llmapi.ssyz.org.tr/v1")
SISTEM = ("Sen deneyimli bir tersine mühendissin. Sana sembolleri silinmiş bir x86-64 fonksiyonu "
          "(Intel sözdizimi) verilecek. Projenin iç fonksiyonları sub_XXXX diye gizlendi; dış "
          "kütüphane çağrıları görünür. Fonksiyonun asıl kaynak koddaki adını tahmin et. "
          'Yalnız JSON dön: {"ad": "snake_case_tahmin", "aciklama": "tek cümle Türkçe"}')
SISTEM_BAGLAM = SISTEM + " Çağrılan iç fonksiyonların özetleri asm'nin altında verildi."


def anahtar() -> str:
    if k := os.environ.get("EVREN_LLM_API_KEY"):
        return k
    for satir in Path(os.environ.get("EVREN_ENV", "~/Desktop/evren.env")).expanduser().read_text().splitlines():
        ad, _, deger = satir.partition("=")
        if ad.strip() == "EVREN_LLM_API_KEY":
            return deger.strip().strip('"')
    sys.exit("anahtar yok")


def sor(model: str, asm: str, dusunme: bool = False, tavan: int = 4096, baglam: bool = False) -> dict:
    # Düşünme açıkken bazı modeller 16K token'lık döngüye girip dakikalarca bekletiyor:
    # varsayılan kapalı, açıkken max_tokens tavanı var. Tavana çarpan cevap "kesik" sayılır.
    govde = {"model": model, "temperature": 0,
             "messages": [{"role": "system", "content": SISTEM_BAGLAM if baglam else SISTEM},
                          {"role": "user", "content": asm}]}
    if dusunme:
        govde["max_tokens"] = tavan
    else:
        # glm-5.3 düşünme kapalıyken de cevaptan önce uzun gerekçe yazabiliyor: tavansız istek
        # dakikalarca sürüp zaman aşımına düşüyor.
        govde["chat_template_kwargs"] = {"enable_thinking": False}
        govde["max_tokens"] = 2048
    for deneme in range(6):
        try:
            istek = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(govde).encode(),
                                           headers={"X-API-Key": anahtar(), "Content-Type": "application/json"})
            yanit = json.load(urllib.request.urlopen(istek, timeout=900))
            secim = yanit["choices"][0]
            metin = secim["message"].get("content") or ""
            token = yanit.get("usage", {}).get("total_tokens", 0)
            m = re.findall(r"\{[^{}]*\}", metin)
            try:
                cevap = json.loads(m[-1]) if m else {"ad": metin.strip()[:60], "aciklama": ""}
            except json.JSONDecodeError:
                cevap = {"ad": "", "aciklama": metin.strip()[:200]}
            return {**cevap, "token": token, "bitis": secim.get("finish_reason")}
        except Exception as hata:
            son = hata
            time.sleep(2 ** deneme + random.random())
    return {"ad": "", "aciklama": f"HATA: {son}", "token": 0}


def kelimeler(ad: str) -> list[str]:
    ad = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", ad)
    return [k for k in re.split(r"[_\W]+", ad.lower()) if k]


# --esanlam: aynı işi anlatan sözcükler tek temsilciye indirilir (get_size ~ fetch_length). Gruplar ve
# gerekçeleri esanlam.json'da; f1() bunu kullanmaz, yalnız --kismi/--esanlam raporundaki ek sütunları etkiler.
ESANLAM_GRUPLARI = tuple(tuple(g["sozcukler"]) for g in
                         json.loads((Path(__file__).resolve().parent / "esanlam.json").read_text())["gruplar"])
ESANLAM = {k: grup[0] for grup in ESANLAM_GRUPLARI for k in grup}


def kelime_pr(tahmin: str, gercek: str, esanlam: bool = False) -> tuple:
    """Sözcük kümesi precision ve recall'u. f1() ile aynı bölme; esanlam=True ise ESANLAM'a indirger.

    precision düşük, recall yüksek: tahmin doğru sözcükleri içeriyor ama fazlasını da ekliyor.
    precision yüksek, recall düşük: tahmin doğru ama eksik (ör. yalnız "update").
    """
    t, g = set(kelimeler(tahmin)), set(kelimeler(gercek))
    if esanlam:
        t, g = {ESANLAM.get(k, k) for k in t}, {ESANLAM.get(k, k) for k in g}
    ortak = len(t & g)
    if not ortak:
        return 0.0, 0.0
    return ortak / len(t), ortak / len(g)


def harmonik(p: float, r: float) -> float:
    return 2 * p * r / (p + r) if p + r else 0.0


def f1(tahmin: str, gercek: str) -> float:
    t, g = kelimeler(tahmin), kelimeler(gercek)
    ortak = len(set(t) & set(g))
    if not ortak:
        return 0.0
    p, r = ortak / len(set(t)), ortak / len(set(g))
    return 2 * p * r / (p + r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("veri", type=Path)
    ap.add_argument("-n", type=int, default=60)
    ap.add_argument("-m", "--model", default="deepseek-v4.1-flash")
    ap.add_argument("-j", type=int, default=6)
    ap.add_argument("--tohum", type=int, default=7)
    ap.add_argument("--dusunme", action="store_true", help="modelin düşünmesini aç (yavaş, pahalı)")
    ap.add_argument("--tavan", type=int, default=4096, help="düşünmede max_tokens")
    baglam_grubu = ap.add_mutually_exclusive_group()
    baglam_grubu.add_argument("--baglam", action="store_true",
                              help="çağrılan iç fonksiyonların özetlerini asm'ye ekle")
    baglam_grubu.add_argument("--baglam-derin", action="store_true",
                              help="çağrılan iç fonksiyonların derin bağlamını asm'ye ekle")
    ap.add_argument("--devam", action="store_true",
                    help="var olan sonuç dosyasındaki sağlam satırları koru, yalnız eksik/HATA olanları sor")
    ap.add_argument("--kesik-de", action="store_true", help="--devam ile: tavana çarpıp boş kalanları da yeniden sor")
    ap.add_argument("--kismi", action="store_true",
                    help="satırlara sözcük düzeyinde precision (p) ve recall (r) ekle, ortalamalarını raporla")
    ap.add_argument("--esanlam", action="store_true",
                    help="--kismi ile: get/fetch/read gibi eş anlamlıları birleştirerek p_es, r_es, f1_es de yaz")
    ap.add_argument("--oneksiz", action="store_true",
                    help="gerçek ad F1'inin yanına öneksiz F1'i de (ozet.py tanımı) yaz ve raporla")
    a = ap.parse_args()
    if a.oneksiz:
        from ozet import f1_oneksiz  # ozet taban'ı içe aktarır; döngü olmasın diye burada

    satirlar = [json.loads(l) for l in a.veri.open()]
    random.Random(a.tohum).shuffle(satirlar)
    ornek = satirlar[: a.n]

    baglam_eki = "-baglam2" if a.baglam_derin else "-baglam" if a.baglam else ""
    sonuc = Path("sonuc") / f"{a.veri.stem}-{a.model}{'-dusunme' if a.dusunme else ''}{baglam_eki}.jsonl"
    sonuc.parent.mkdir(exist_ok=True)
    eski = {}
    if a.devam and sonuc.exists():
        for l in sonuc.open():
            r = json.loads(l)
            hatali = str(r.get("aciklama", "")).startswith("HATA")
            kesik = not r.get("tahmin") and (r.get("bitis") == "length" or r.get("bitis") is None)
            if not hatali and not (a.kesik_de and kesik):
                eski[r["id"]] = r
    sorulacak = [r for r in ornek if r["id"] not in eski]
    print(f"{len(eski)} satır korundu, {len(sorulacak)} soruluyor", file=sys.stderr)

    def satir(r, c):
        s = f1(str(c.get("ad", "")), r["ad"])
        return {"id": r["id"], "gercek": r["ad"], "tahmin": c.get("ad"), "aciklama": c.get("aciklama"),
                "f1": round(s, 3), "opt": r["opt"], "token": c.get("token", 0), "bitis": c.get("bitis")}

    def iki_f1(r):
        r = {**r, "f1_oneksiz": round(f1_oneksiz(r), 3)} if a.oneksiz else r
        if a.kismi or a.esanlam:
            tahmin = str(r.get("tahmin") or "")
            p, rc = kelime_pr(tahmin, r["gercek"])
            r = {**r, "p": round(p, 3), "r": round(rc, 3)}
            if a.esanlam:
                p, rc = kelime_pr(tahmin, r["gercek"], esanlam=True)
                r = {**r, "p_es": round(p, 3), "r_es": round(rc, 3), "f1_es": round(harmonik(p, rc), 3)}
        return r

    # Satırlar geldikçe ara dosyaya yazılır; koşu yarıda kesilse de --devam kaldığı yerden alır.
    ara = sonuc.with_suffix(".ara")
    yeni = {}
    if ara.exists():
        yeni = {r["id"]: r for r in map(json.loads, ara.open()) if not str(r.get("aciklama", "")).startswith("HATA")}
        sorulacak = [r for r in sorulacak if r["id"] not in yeni]
    with ThreadPoolExecutor(a.j) as havuz, ara.open("a") as f:
        def girdi(r):
            alan = "baglam_derin" if a.baglam_derin else "baglam"
            if not (a.baglam or a.baglam_derin) or not r.get(alan):
                return r["asm"]
            return r["asm"] + "\n\n; --- çağrılan fonksiyonlar ---\n" + r[alan]

        baglamli = a.baglam or a.baglam_derin
        isler = {havuz.submit(sor, a.model, girdi(r), a.dusunme, a.tavan, baglamli): r for r in sorulacak}
        for gelen in as_completed(isler):
            r = isler[gelen]
            yeni[r["id"]] = satir(r, gelen.result())
            f.write(json.dumps(yeni[r["id"]], ensure_ascii=False) + "\n")
            f.flush()

    hepsi = [iki_f1(eski.get(r["id"]) or yeni[r["id"]]) for r in ornek]
    with sonuc.open("w") as f:
        for r in hepsi:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    ara.unlink(missing_ok=True)
    skorlar, oneksiz = {}, {}
    for r in hepsi:
        skorlar.setdefault(r["opt"], []).append(r["f1"])
        oneksiz.setdefault(r["opt"], []).append(r.get("f1_oneksiz", 0.0))
        print(f"{r['f1']:.2f}  {r['opt']}  {r['gercek']:<28} ← {r['tahmin']}")
    for opt, l in sorted(skorlar.items()):
        print(f"{opt}: ortalama F1 {sum(l) / len(l):.2f}  (n={len(l)}, tam isabet {sum(x == 1 for x in l)})")
        if a.oneksiz:
            o = oneksiz[opt]
            print(f"{opt}: öneksiz F1 {sum(o) / len(o):.2f}  (tam isabet {sum(x == 1 for x in o)})")
        grup = [r for r in hepsi if r["opt"] == opt]
        ort = lambda alan: sum(r[alan] for r in grup) / len(grup)
        if a.kismi or a.esanlam:
            print(f"{opt}: precision {ort('p'):.2f}  recall {ort('r'):.2f}")
        if a.esanlam:
            print(f"{opt}: eş anlamlı  precision {ort('p_es'):.2f}  recall {ort('r_es'):.2f}  F1 {ort('f1_es'):.2f}")
    print(f"yeni token: {sum(r.get('token', 0) for r in yeni.values())}")
    print(f"ayrıntı → {sonuc}")


if __name__ == "__main__":
    main()
