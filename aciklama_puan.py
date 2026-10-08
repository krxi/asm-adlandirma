#!/usr/bin/env python3
"""Model açıklamalarını kaynak koda göre puanla (hakem model, 0-2).

  python3 aciklama_puan.py sonuc/test-qwen2.5-coder-1.5b-lora-v4.jsonl --kuru -n 2
  python3 aciklama_puan.py sonuc/test-mimo-v2.6-pro-baglam.jsonl -m mimo-v2.6-pro -j 6

Hakem fonksiyonun C kaynağını ve öğretmen açıklamasını görür; öğrencinin açıklamasına
2 (doğru), 1 (kısmen), 0 (yanlış/boş) verir. Sonuç <girdi>-puan.jsonl; özet stdout'a.
"""
import argparse, json, random, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from taban import BASE, anahtar

SISTEM = ("Sen C kodunu iyi bilen titiz bir hakemsin. Bir fonksiyonun kaynak kodu, referans açıklaması ve "
          "bir öğrencinin yalnız assembly'ye bakarak yazdığı açıklama verilecek. Öğrencinin açıklamasını "
          "fonksiyonun gerçekte ne yaptığına göre puanla: 2 = ana işlevi doğru, 1 = kısmen doğru ya da çok genel, "
          "0 = yanlış, boş veya anlamsız. Üslubu ve uzunluğu puanlama. "
          'Yalnız JSON dön: {"puan": 0|1|2, "gerekce": "kısa"}')


def kaynaklar() -> dict:
    out = {}
    for p in Path("veri/kaynak").glob("*.jsonl"):
        for l in p.open():
            r = json.loads(l)
            out[r["id"]] = r["kaynak"]
    return out


def ogretmen() -> dict:
    out = {}
    for p in Path("veri/aciklama").glob("*.jsonl"):
        for l in p.open():
            r = json.loads(l)
            out[r["id"]] = r["aciklama"]
    return out


def istem(r: dict, kaynak: str, ref: str, model: str) -> dict:
    kullanici = (f"C kaynak kodu:\n```c\n{kaynak}\n```\n\nReferans açıklama: {ref}\n\n"
                 f"Öğrencinin açıklaması: {r.get('aciklama') or '(boş)'}")
    return {"model": model, "temperature": 0, "max_tokens": 200,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "system", "content": SISTEM}, {"role": "user", "content": kullanici}]}


def sor(govde: dict) -> dict:
    son = None
    for d in range(6):
        try:
            istek = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(govde).encode(),
                                           headers={"X-API-Key": anahtar(), "Content-Type": "application/json"})
            metin = json.load(urllib.request.urlopen(istek, timeout=600))["choices"][0]["message"].get("content") or ""
            m = re.findall(r"\{[^{}]*\}", metin)
            c = json.loads(m[-1])
            if int(c["puan"]) not in (0, 1, 2):
                raise ValueError(f"geçersiz puan: {c}")
            return {"puan": int(c["puan"]), "gerekce": str(c.get("gerekce", ""))}
        except Exception as e:
            son = e
            time.sleep(2 ** d + random.random())
    return {"puan": None, "gerekce": f"HATA: {son}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sonuc", type=Path)
    ap.add_argument("-m", "--model", default="mimo-v2.6-pro")
    ap.add_argument("-j", type=int, default=6)
    ap.add_argument("-n", type=int, default=0)
    ap.add_argument("--kuru", action="store_true", help="istek atma; istemleri yazdır")
    a = ap.parse_args()

    satirlar = [json.loads(l) for l in a.sonuc.open() if l.strip()]
    if a.n:
        satirlar = satirlar[: a.n]
    kay, ogr = kaynaklar(), ogretmen()
    eksik = [r["id"] for r in satirlar if r["id"] not in kay]
    if eksik:
        sys.exit(f"kaynağı olmayan {len(eksik)} satır, ör. {eksik[0]}")
    istemler = [istem(r, kay[r["id"]], r.get("ogretmen") or ogr.get(r["id"], ""), a.model) for r in satirlar]
    if a.kuru:
        for g in istemler:
            print(json.dumps(g, ensure_ascii=False))
        return

    with ThreadPoolExecutor(a.j) as h:
        puanlar = list(h.map(sor, istemler))
    cikti = a.sonuc.with_name(a.sonuc.stem + "-puan.jsonl")
    with cikti.open("w") as f:
        for r, p in zip(satirlar, puanlar):
            f.write(json.dumps({"id": r["id"], "aciklama": r.get("aciklama", ""), **p}, ensure_ascii=False) + "\n")
    gecerli = [p["puan"] for p in puanlar if p["puan"] is not None]
    hata = len(puanlar) - len(gecerli)
    print(f"{a.sonuc.stem}: ortalama {sum(gecerli) / max(1, len(gecerli)):.2f} / 2  "
          f"(2: {gecerli.count(2)}, 1: {gecerli.count(1)}, 0: {gecerli.count(0)}, hata: {hata})  → {cikti}")


if __name__ == "__main__":
    main()
