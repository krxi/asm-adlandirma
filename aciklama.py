#!/usr/bin/env python3
"""C kaynaklarından damıtma için kısa Türkçe fonksiyon açıklamaları üret.

  python3 aciklama.py --kuru -n 3
  python3 aciklama.py zlib -j 6 --model deepseek-v4.1-flash
  python3 aciklama.py --devam

--kuru yalnız istemleri JSONL olarak yazdırır; anahtar okumaz ve istek atmaz.
"""
import argparse, json, random, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from taban import BASE, anahtar

SISTEM = ("Sen C kaynak kodunu açıklayan deneyimli bir yazılım mühendisisin. "
          "Yalnız tek cümlelik Türkçe açıklama yaz. Cümle 'Bu fonksiyon' ile başlasın, "
          "en çok 25 kelime olsun ve verilen fonksiyon adını tekrar etmesin. "
          "Markdown, başlık, JSON veya ek açıklama kullanma.")


def adini_bul(kimlik: str) -> str:
    if ":" not in kimlik:
        raise ValueError(f"geçersiz id: {kimlik}")
    return kimlik.rsplit(":", 1)[1]


def istem(kayit: dict, model: str) -> dict:
    ad = adini_bul(kayit["id"])
    kullanici = f"Fonksiyon adı: {ad}\n\nC kaynak kodu:\n```c\n{kayit['kaynak']}\n```"
    return {"model": model, "temperature": 0, "max_tokens": 128,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "system", "content": SISTEM},
                         {"role": "user", "content": kullanici}]}


def temizle(metin: str, ad: str) -> str:
    """Model cevabını sözleşmenin basit, belirlenimci sınırlarına getir."""
    metin = metin.strip().strip("`").strip()
    try:
        nesne = json.loads(metin)
        if isinstance(nesne, dict):
            metin = str(nesne.get("aciklama", ""))
    except json.JSONDecodeError:
        pass
    metin = " ".join(metin.split()).strip(' "\'')
    bas = metin.find("Bu fonksiyon")
    if bas >= 0:
        metin = metin[bas:]
    elif metin:
        metin = "Bu fonksiyon " + metin[0].lower() + metin[1:]
    else:
        return ""

    # Tam fonksiyon adı cevapta geçerse anlamı bozmadan genel bir ifadeyle değiştir.
    metin = re.sub(re.escape(ad), "ilgili işlemi", metin, flags=re.I)
    bitis = re.search(r"[.!?](?:\s|$)", metin)
    if bitis:
        metin = metin[:bitis.end()].strip()
    kelimeler = metin.split()
    if len(kelimeler) > 25:
        metin = " ".join(kelimeler[:25]).rstrip(",;:") + "."
    elif metin[-1:] not in ".!?":
        metin += "."
    return metin


def sor(model: str, kayit: dict) -> str:
    govde = istem(kayit, model)
    son_hata = None
    for deneme in range(6):
        try:
            istek = urllib.request.Request(BASE + "/chat/completions",
                                           data=json.dumps(govde).encode(),
                                           headers={"X-API-Key": anahtar(),
                                                    "Content-Type": "application/json"})
            yanit = json.load(urllib.request.urlopen(istek, timeout=900))
            metin = yanit["choices"][0]["message"].get("content") or ""
            aciklama = temizle(metin, adini_bul(kayit["id"]))
            if not aciklama:
                raise ValueError("boş model cevabı")
            return aciklama
        except Exception as hata:
            son_hata = hata
            time.sleep(2 ** deneme + random.random())
    return f"HATA: {son_hata}"


def saglam(kayit: dict, model: str) -> bool:
    return kayit.get("model") == model and not str(kayit.get("aciklama", "")).startswith("HATA")


def jsonl_oku(yol: Path) -> list[dict]:
    return [json.loads(satir) for satir in yol.open() if satir.strip()]


def projeyi_isle(proje: str, satirlar: list[dict], veri: Path, model: str, is_sayisi: int, devam: bool):
    cikti = veri / "aciklama" / f"{proje}.jsonl"
    cikti.parent.mkdir(parents=True, exist_ok=True)
    eski = {}
    if devam and cikti.exists():
        eski = {r["id"]: r for r in jsonl_oku(cikti) if saglam(r, model)}

    ara = cikti.with_suffix(".ara")
    yeni = {}
    if ara.exists():
        yeni = {r["id"]: r for r in jsonl_oku(ara) if saglam(r, model)}

    sorulacak = [r for r in satirlar if r["id"] not in eski and r["id"] not in yeni]
    yerel = [r for r in sorulacak if not r.get("bulundu") or not r.get("kaynak")]
    for r in yerel:
        yeni[r["id"]] = {"id": r["id"], "aciklama": "HATA: kaynak bulunamadı", "model": model}
    sorulacak = [r for r in sorulacak if r not in yerel]
    print(f"{proje}: {len(eski)} satır korundu, {len(yeni)} ara/yerel, {len(sorulacak)} soruluyor",
          file=sys.stderr)

    with ThreadPoolExecutor(max_workers=is_sayisi) as havuz, ara.open("a") as f:
        isler = {havuz.submit(sor, model, r): r for r in sorulacak}
        for gelen in as_completed(isler):
            r = isler[gelen]
            sonuc = {"id": r["id"], "aciklama": gelen.result(), "model": model}
            yeni[r["id"]] = sonuc
            f.write(json.dumps(sonuc, ensure_ascii=False) + "\n")
            f.flush()

    with cikti.open("w") as f:
        for r in satirlar:
            sonuc = eski.get(r["id"]) or yeni[r["id"]]
            f.write(json.dumps(sonuc, ensure_ascii=False) + "\n")
    ara.unlink(missing_ok=True)
    print(f"{len(satirlar)} açıklama → {cikti}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("proje", nargs="*", help="yalnız bu proje adlarını işle")
    ap.add_argument("--veri", type=Path, default=Path("veri"))
    ap.add_argument("--model", "-m", default="deepseek-v4.1-flash")
    ap.add_argument("-j", type=int, default=6)
    ap.add_argument("-n", type=int, help="toplam en çok bu kadar satır işle")
    ap.add_argument("--devam", action="store_true",
                    help="var olan sağlam satırları ve kesilmiş koşunun ara dosyasını koru")
    ap.add_argument("--kuru", action="store_true", help="istek atma; istemleri JSONL yazdır")
    a = ap.parse_args()
    if a.j < 1:
        ap.error("-j en az 1 olmalı")
    if a.n is not None and a.n < 0:
        ap.error("-n negatif olamaz")

    yollar = sorted((a.veri / "kaynak").glob("*.jsonl"))
    bilinen = {p.stem for p in yollar}
    bilinmeyen = set(a.proje) - bilinen
    if bilinmeyen:
        ap.error("kaynak verisi olmayan proje: " + ", ".join(sorted(bilinmeyen)))
    if a.proje:
        yollar = [p for p in yollar if p.stem in a.proje]

    kalan = a.n
    secilenler = []
    for yol in yollar:
        satirlar = jsonl_oku(yol)
        if kalan is not None:
            satirlar = satirlar[:kalan]
            kalan -= len(satirlar)
        if satirlar:
            secilenler.append((yol.stem, satirlar))
        if kalan == 0:
            break

    if a.kuru:
        for _, satirlar in secilenler:
            for kayit in satirlar:
                print(json.dumps({"id": kayit["id"], "istek": istem(kayit, a.model)}, ensure_ascii=False))
        return

    for proje, satirlar in secilenler:
        projeyi_isle(proje, satirlar, a.veri, a.model, a.j, a.devam)


if __name__ == "__main__":
    main()
