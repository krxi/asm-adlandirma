#!/usr/bin/env python3
"""Taban ölçüm: hazır bir Evren modeli stripped fonksiyona ne kadar doğru isim veriyor?

  python3 taban.py veri/zlib.jsonl -n 60 -m deepseek-v4.1-flash

Skor: tahmin ve gerçek adı kelimelere böl (snake/camel), kelime örtüşmesinin F1'i.
Tam doğruluk nadir olur; F1 "yakın mı" sorusunu ölçer (crc32_update ~ update_crc).
"""
import argparse, json, os, random, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = os.environ.get("EVREN_BASE_URL", "https://evren-llmapi.ssyz.org.tr/v1")
SISTEM = ("Sen deneyimli bir tersine mühendissin. Sana sembolleri silinmiş bir x86-64 fonksiyonu "
          "(Intel sözdizimi) verilecek. Projenin iç fonksiyonları sub_XXXX diye gizlendi; dış "
          "kütüphane çağrıları görünür. Fonksiyonun asıl kaynak koddaki adını tahmin et. "
          'Yalnız JSON dön: {"ad": "snake_case_tahmin", "aciklama": "tek cümle Türkçe"}')


def anahtar() -> str:
    if k := os.environ.get("EVREN_LLM_API_KEY"):
        return k
    for satir in Path(os.environ.get("EVREN_ENV", "~/Desktop/evren.env")).expanduser().read_text().splitlines():
        ad, _, deger = satir.partition("=")
        if ad.strip() == "EVREN_LLM_API_KEY":
            return deger.strip().strip('"')
    sys.exit("anahtar yok")


def sor(model: str, asm: str, dusunme: bool = False) -> dict:
    # Düşünme açıkken bazı modeller 16K token'lık döngüye girip dakikalarca bekletiyor:
    # varsayılan kapalı, açıkken tavan 4096.
    govde = {"model": model, "temperature": 0,
             "messages": [{"role": "system", "content": SISTEM}, {"role": "user", "content": asm}]}
    if dusunme:
        govde["max_tokens"] = 4096
    else:
        govde["chat_template_kwargs"] = {"enable_thinking": False}
    for deneme in range(4):
        try:
            istek = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(govde).encode(),
                                           headers={"X-API-Key": anahtar(), "Content-Type": "application/json"})
            yanit = json.load(urllib.request.urlopen(istek, timeout=180))
            metin = yanit["choices"][0]["message"].get("content") or ""
            token = yanit.get("usage", {}).get("total_tokens", 0)
            m = re.findall(r"\{[^{}]*\}", metin)
            cevap = json.loads(m[-1]) if m else {"ad": metin.strip()[:60], "aciklama": ""}
            return {**cevap, "token": token}
        except Exception as hata:
            son = hata
            time.sleep(2 ** deneme)
    return {"ad": "", "aciklama": f"HATA: {son}", "token": 0}


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("veri", type=Path)
    ap.add_argument("-n", type=int, default=60)
    ap.add_argument("-m", "--model", default="deepseek-v4.1-flash")
    ap.add_argument("-j", type=int, default=6)
    ap.add_argument("--tohum", type=int, default=7)
    ap.add_argument("--dusunme", action="store_true", help="modelin düşünmesini aç (yavaş, pahalı)")
    a = ap.parse_args()

    satirlar = [json.loads(l) for l in a.veri.open()]
    random.Random(a.tohum).shuffle(satirlar)
    ornek = satirlar[: a.n]
    with ThreadPoolExecutor(a.j) as havuz:
        cevaplar = list(havuz.map(lambda r: sor(a.model, r["asm"], a.dusunme), ornek))

    sonuc = Path("sonuc") / f"{a.veri.stem}-{a.model}{'-dusunme' if a.dusunme else ''}.jsonl"
    sonuc.parent.mkdir(exist_ok=True)
    skorlar = {"-O0": [], "-O2": []}
    with sonuc.open("w") as f:
        for r, c in zip(ornek, cevaplar):
            s = f1(str(c.get("ad", "")), r["ad"])
            skorlar[r["opt"]].append(s)
            f.write(json.dumps({"id": r["id"], "gercek": r["ad"], "tahmin": c.get("ad"),
                                "aciklama": c.get("aciklama"), "f1": round(s, 3), "opt": r["opt"],
                                "token": c.get("token", 0)}, ensure_ascii=False) + "\n")
            print(f"{s:.2f}  {r['opt']}  {r['ad']:<28} ← {c.get('ad')}")
    for opt, l in skorlar.items():
        if l:
            print(f"{opt}: ortalama F1 {sum(l) / len(l):.2f}  (n={len(l)}, tam isabet {sum(x == 1 for x in l)})")
    print(f"toplam token: {sum(c.get('token', 0) for c in cevaplar)}")
    print(f"ayrıntı → {sonuc}")


if __name__ == "__main__":
    main()
