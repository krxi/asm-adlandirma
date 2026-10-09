#!/usr/bin/env python3
"""C kaynağına bakarak v4 öğretmen açıklamalarını Evren hakemiyle denetle."""

import argparse
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from taban import evren_istek, token_tahmini


ALANLAR = ("aciklama", "kategori", "girdiler", "donus", "yan_etki", "aciklama_en")
SISTEM = """Sen C kaynak kodu ve işlev açıklaması denetleyen titiz bir hakemsin.
Her öğretmen alanını yalnız verilen C kaynağına göre ayrı ayrı puanla:
2 = doğru ve kaynağa özgü, 1 = kısmen doğru ama eksik/genel, 0 = yanlış veya kaynakla çelişiyor.
Ayrıca Türkçe aciklama ile aciklama_en aynı şeyi söylüyorsa evet, söylemiyorsa hayır yaz.
Kısa, somut bir gerekçe ver. Düşünme metni veya Markdown yazma; yalnız şu biçimde JSON dön:
{"puanlar":{"aciklama":2,"kategori":2,"girdiler":2,"donus":2,"yan_etki":2,"aciklama_en":2},
 "aciklama_uyumu":"evet","gerekce":"kısa gerekçe"}"""


def jsonl_oku(yol: Path) -> list[dict]:
    kayitlar = []
    if not yol.exists():
        return kayitlar
    for no, satir in enumerate(yol.open(), 1):
        if not satir.strip():
            continue
        try:
            kayitlar.append(json.loads(satir))
        except json.JSONDecodeError:
            # Yarım kalmış son yazım --devam koşusunu engellemesin.
            if no != sum(1 for _ in yol.open()):
                raise
    return kayitlar


def etiketleri_yukle(aciklama_yolu: Path, detay_yolu: Path) -> list[dict]:
    turkce = {r["anahtar"]: r for r in jsonl_oku(aciklama_yolu)}
    birlesik = []
    for detay in jsonl_oku(detay_yolu):
        if detay["anahtar"] not in turkce:
            continue
        anahtar = detay["anahtar"]
        birlesik.append({
            "anahtar": anahtar,
            "proje": anahtar.split("/", 1)[0],
            "aciklama": turkce[anahtar].get("aciklama", ""),
            **{alan: detay.get(alan, "") for alan in ALANLAR if alan != "aciklama"},
            "ogretmen_model": detay.get("model") or turkce[anahtar].get("model") or "bilinmiyor",
        })
    return birlesik


def _kategori_katmanli_sec(kayitlar: list[dict], n: int, rng: random.Random) -> list[dict]:
    """Kategori oranlarını en büyük kalan yöntemiyle koruyarak n kayıt seç."""
    kovalar = defaultdict(list)
    for r in kayitlar:
        kovalar[r.get("kategori") or "bilinmiyor"].append(r)
    toplam = len(kayitlar)
    kategoriler = sorted(kovalar, key=lambda _: rng.random())
    kotalar = {kategori: math.floor(n * len(kovalar[kategori]) / toplam) for kategori in kategoriler}
    kalan = n - sum(kotalar.values())
    sirali = sorted(kategoriler, key=lambda k: n * len(kovalar[k]) / toplam - kotalar[k], reverse=True)
    for kategori in sirali[:kalan]:
        kotalar[kategori] += 1
    secilen = []
    for kategori in kategoriler:
        rng.shuffle(kovalar[kategori])
        secilen.extend(kovalar[kategori][:kotalar[kategori]])
    rng.shuffle(secilen)
    return secilen


def ornekle(kayitlar: list[dict], n: int, tohum: int = 42) -> tuple[list[dict], int]:
    """Projeleri tavanla dengeler; proje içinde kategori oranlarını katmanlar."""
    if n <= 0 or not kayitlar:
        return [], 0
    hedef = min(n, len(kayitlar))
    projeler = defaultdict(list)
    for r in kayitlar:
        projeler[r["proje"]].append(r)
    adlar = sorted(projeler)
    rng = random.Random(tohum)
    rng.shuffle(adlar)
    tavan = max(1, math.ceil(hedef / len(adlar)))
    while sum(min(len(projeler[p]), tavan) for p in adlar) < hedef:
        tavan += 1
    kotalar = Counter()
    while sum(kotalar.values()) < hedef:
        ilerledi = False
        for proje in adlar:
            if kotalar[proje] >= min(tavan, len(projeler[proje])):
                continue
            kotalar[proje] += 1
            ilerledi = True
            if sum(kotalar.values()) == hedef:
                break
        if not ilerledi:
            break
    proje_secimleri = {p: _kategori_katmanli_sec(projeler[p], kotalar[p], rng) for p in adlar if kotalar[p]}
    secilen = []
    for sira in range(tavan):
        secilen.extend(proje_secimleri[p][sira] for p in adlar if len(proje_secimleri.get(p, ())) > sira)
    return secilen, tavan


def kaynaklari_yukle(dizin: Path, anahtarlar: set[str]) -> dict[str, str]:
    projeler = {a.split("/", 1)[0] for a in anahtarlar}
    kaynaklar = {}
    for yol in sorted(dizin.glob("*.jsonl")):
        if yol.stem not in projeler:
            continue
        for r in jsonl_oku(yol):
            if r.get("anahtar") in anahtarlar and r.get("kaynak"):
                kaynaklar[r["anahtar"]] = r["kaynak"]
    return kaynaklar


def kaynak_kisalt(kaynak: str, anahtar: str, tavan: int = 6000) -> tuple[str, int, bool]:
    token = token_tahmini(kaynak)
    if token <= tavan:
        return kaynak, token, False
    isaret = "\n\n/* KAYNAK UZUN OLDUĞU İÇİN KESİLDİ */\n\n"
    karakter = max(1, tavan * 4 - len(isaret))
    ad = anahtar.rsplit(":", 1)[-1]
    eslesme = re.search(rf"\b{re.escape(ad)}\b", kaynak)
    if eslesme:
        once = karakter // 3
        bas = max(0, eslesme.start() - once)
        son = min(len(kaynak), bas + karakter)
        bas = max(0, son - karakter)
        parca = kaynak[bas:son]
        on = "/* ... baş taraf kesildi ... */\n" if bas else ""
        arka = "\n/* ... son taraf kesildi ... */" if son < len(kaynak) else ""
        parca = (on + parca + arka)[:karakter]
    else:
        yarim = karakter // 2
        parca = kaynak[:yarim] + isaret + kaynak[-(karakter - yarim):]
        return parca, token, True
    return parca + isaret, token, True


def istem_hazirla(r: dict, kaynak: str) -> str:
    etiketler = {alan: r.get(alan, "") for alan in ALANLAR}
    return (f"ANAHTAR: {r['anahtar']}\n\nC KAYNAĞI:\n```c\n{kaynak}\n```\n\n"
            f"ÖĞRETMEN ETİKETLERİ:\n{json.dumps(etiketler, ensure_ascii=False, indent=2)}")


def hakem_sonucunu_ayristir(metin: str) -> dict:
    temiz = metin.strip()
    if temiz.startswith("```"):
        temiz = re.sub(r"^```(?:json)?\s*|\s*```$", "", temiz, flags=re.I)
    adaylar = [temiz]
    adaylar.extend(temiz[i:] for i, c in enumerate(temiz) if c == "{")
    nesne = None
    for aday in adaylar:
        try:
            nesne, _ = json.JSONDecoder().raw_decode(aday)
            break
        except (json.JSONDecodeError, TypeError):
            continue
    if not isinstance(nesne, dict):
        raise ValueError("hakem JSON nesnesi dönmedi")
    puanlar = nesne.get("puanlar", nesne)
    if not isinstance(puanlar, dict):
        raise ValueError("puanlar nesnesi yok")
    sonuc = {}
    for alan in ALANLAR:
        puan = puanlar.get(alan)
        if isinstance(puan, str) and puan.strip().isdigit():
            puan = int(puan)
        if type(puan) is not int or puan not in (0, 1, 2):
            raise ValueError(f"geçersiz {alan} puanı")
        sonuc[alan] = puan
    uyum = nesne.get("aciklama_uyumu", nesne.get("aciklama_en_uyumu"))
    if isinstance(uyum, bool):
        uyum = "evet" if uyum else "hayır"
    uyum = str(uyum or "").strip().lower().replace("hayir", "hayır")
    if uyum not in ("evet", "hayır"):
        raise ValueError("aciklama_uyumu evet/hayır değil")
    return {"puanlar": sonuc, "aciklama_uyumu": uyum,
            "gerekce": str(nesne.get("gerekce", "")).strip()[:1000]}


def hakeme_sor(model: str, istem: str, deneme_sayisi: int = 3) -> dict:
    token = 0
    son_hata = None
    for _ in range(deneme_sayisi):
        try:
            yanit = evren_istek(model, [{"role": "system", "content": SISTEM},
                                         {"role": "user", "content": istem}], max_tokens=700)
            token += int(yanit.get("usage", {}).get("total_tokens", 0))
            secim = yanit["choices"][0]
            sonuc = hakem_sonucunu_ayristir(secim["message"].get("content") or "")
            return {**sonuc, "token": token, "bitis": secim.get("finish_reason")}
        except (ValueError, KeyError, IndexError, TypeError) as hata:
            son_hata = hata
        except Exception as hata:
            return {"hata": f"HATA: {hata}", "token": token}
    return {"hata": f"HATA: bozuk hakem JSON'u ({son_hata})", "token": token}


def _yuzde(x: int, n: int) -> str:
    return f"%{100 * x / n:.1f}" if n else "—"


def bootstrap_araligi(degerler: list[int], tohum: int = 42, tekrar: int = 1000) -> tuple[float, float]:
    if not degerler:
        return 0.0, 0.0
    if len(degerler) == 1:
        return float(degerler[0]), float(degerler[0])
    rng = random.Random(tohum)
    n = len(degerler)
    ortalamalar = sorted(sum(rng.choice(degerler) for _ in range(n)) / n for _ in range(tekrar))
    return ortalamalar[int(tekrar * .025)], ortalamalar[min(tekrar - 1, int(tekrar * .975))]


def _tum_puanlar(r: dict) -> list[int]:
    return [r["puanlar"][alan] for alan in ALANLAR]


def _kirlim(satirlar: list[dict], alan: str) -> list[str]:
    gruplar = defaultdict(list)
    for r in satirlar:
        gruplar[str(r.get(alan) or "bilinmiyor")].append(r)
    cikti = ["| grup | n | ortalama puan | 0 oranı |", "|---|---:|---:|---:|"]
    for ad, grup in sorted(gruplar.items(), key=lambda x: (-len(x[1]), x[0])):
        puanlar = [p for r in grup for p in _tum_puanlar(r)]
        cikti.append(f"| {md(ad)} | {len(grup)} | {sum(puanlar) / len(puanlar):.3f} | "
                     f"{_yuzde(puanlar.count(0), len(puanlar))} |")
    return cikti


def kaynak_dilimi(r: dict) -> str:
    token = r.get("kaynak_token_tahmini", 0)
    if token <= 1000:
        return "≤1K"
    if token <= 3000:
        return "1K–3K"
    if token <= 6000:
        return "3K–6K"
    return ">6K (kesildi)"


def md(deger) -> str:
    return str(deger).replace("|", "\\|").replace("\n", " ")


def rapor_metni(satirlar: list[dict]) -> str:
    saglam = [r for r in satirlar if isinstance(r.get("puanlar"), dict)
              and all(r["puanlar"].get(a) in (0, 1, 2) for a in ALANLAR)]
    metin = ["# Öğretmen Denetimi", "",
             f"C kaynağına göre puanlanan örnek sayısı: **{len(saglam)}**. "
             "Puanlar: 2 doğru, 1 kısmen doğru/genel, 0 yanlış.", "",
             "## Alan puanları", "",
             "| alan | n | 0 | 1 | 2 | ortalama | %95 bootstrap GA |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for i, alan in enumerate(ALANLAR):
        puanlar = [r["puanlar"][alan] for r in saglam]
        alt, ust = bootstrap_araligi(puanlar, 42 + i)
        n = len(puanlar)
        ort = sum(puanlar) / n if n else 0
        metin.append(f"| {alan} | {n} | {_yuzde(puanlar.count(0), n)} | {_yuzde(puanlar.count(1), n)} | "
                     f"{_yuzde(puanlar.count(2), n)} | {ort:.3f} | [{alt:.3f}, {ust:.3f}] |")
    uyum = Counter(r.get("aciklama_uyumu") for r in saglam)
    metin += ["", "## Türkçe–İngilizce açıklama uyumu", "",
              f"Evet: **{uyum['evet']}** ({_yuzde(uyum['evet'], len(saglam))}); "
              f"hayır: **{uyum['hayır']}** ({_yuzde(uyum['hayır'], len(saglam))})."]
    for baslik, alan in (("Proje kırılımı", "proje"), ("Kategori kırılımı", "kategori"),
                         ("Öğretmen model kırılımı", "ogretmen_model")):
        metin += ["", f"## {baslik}", "", *_kirlim(saglam, alan)]
    uzunluklu = [{**r, "kaynak_dilimi": kaynak_dilimi(r)} for r in saglam]
    metin += ["", "## Kaynak uzunluğu kırılımı", "", *_kirlim(uzunluklu, "kaynak_dilimi")]
    sifirlar = sorted((r for r in saglam if 0 in _tum_puanlar(r)),
                      key=lambda r: (-_tum_puanlar(r).count(0), r["anahtar"]))[:15]
    metin += ["", "## 0 puanlı 15 somut örnek", "",
              "| anahtar | 0 alanlar | öğretmen etiketi | kısa gerekçe |",
              "|---|---|---|---|"]
    for r in sifirlar:
        alanlar = [a for a in ALANLAR if r["puanlar"][a] == 0]
        etiket = "; ".join(f"{a}={str(r.get('etiketler', {}).get(a, ''))[:100]}" for a in alanlar)
        metin.append(f"| {md(r['anahtar'])} | {', '.join(alanlar)} | {md(etiket)} | {md(r.get('gerekce', ''))} |")
    if not sifirlar:
        metin.append("| — | — | 0 puanlı örnek yok | — |")
    return "\n".join(metin) + "\n"


def rapor_yaz(satirlar: list[dict], yol: Path) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(rapor_metni(satirlar))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=3000)
    ap.add_argument("--tohum", type=int, default=42)
    ap.add_argument("-m", "--model", default="mimo-v2.6-pro")
    ap.add_argument("-j", type=int, default=8)
    ap.add_argument("--devam", action="store_true", help="sağlam sonuç satırlarını koruyup eksikleri tamamla")
    ap.add_argument("--kuru", action="store_true", help="istek/dosya yazımı yapmadan girdi token tahmini")
    ap.add_argument("--rapor", action="store_true", help="rapor/OGRETMEN_DENETIM.md dosyasını üret")
    a = ap.parse_args()

    kayitlar = etiketleri_yukle(Path("veri/aciklama-v4/codex.jsonl"),
                                Path("veri/aciklama-v4/codex-detay.jsonl"))
    secilen, tavan = ornekle(kayitlar, a.n, a.tohum)
    kaynaklar = kaynaklari_yukle(Path("veri/kaynak-v4"), {r["anahtar"] for r in secilen})
    eksik = [r["anahtar"] for r in secilen if r["anahtar"] not in kaynaklar]
    if eksik:
        raise SystemExit(f"{len(eksik)} örneğin C kaynağı yok; ilk: {eksik[0]}")
    hazir = []
    for r in secilen:
        kaynak, kaynak_token, kesildi = kaynak_kisalt(kaynaklar[r["anahtar"]], r["anahtar"])
        hazir.append((r, istem_hazirla(r, kaynak), kaynak_token, kesildi))

    guvenli_model = re.sub(r"[^A-Za-z0-9_.-]+", "-", a.model)
    sonuc_yolu = Path("sonuc") / f"ogretmen-denetim-{guvenli_model}.jsonl"
    if a.kuru:
        toplam = sum(token_tahmini(SISTEM) + token_tahmini(istem) for _, istem, _, _ in hazir)
        kesik = sum(k for *_, k in hazir)
        print(f"kuru: {len(hazir)} örnek, proje başına tavan {tavan}, kesilen kaynak {kesik}")
        print(f"tahmini toplam girdi tokenı (model başına): {toplam:,}")
        print(f"çıktı yolu → {sonuc_yolu}")
        return

    sonuc_yolu.parent.mkdir(exist_ok=True)
    eski = {}
    if a.devam and sonuc_yolu.exists():
        for r in jsonl_oku(sonuc_yolu):
            if isinstance(r.get("puanlar"), dict) and all(r["puanlar"].get(x) in (0, 1, 2) for x in ALANLAR):
                eski[r["anahtar"]] = r
    else:
        sonuc_yolu.write_text("")
    sorulacak = [x for x in hazir if x[0]["anahtar"] not in eski]
    print(f"{len(eski)} satır korundu, {len(sorulacak)} soruluyor", file=sys.stderr)
    yeni = {}
    kosu_token = 0
    with ThreadPoolExecutor(a.j) as havuz, sonuc_yolu.open("a") as f:
        isler = {havuz.submit(hakeme_sor, a.model, istem): (r, kaynak_token, kesildi)
                 for r, istem, kaynak_token, kesildi in sorulacak}
        for no, gelen in enumerate(as_completed(isler), 1):
            r, kaynak_token, kesildi = isler[gelen]
            cevap = gelen.result()
            satir = {
                "anahtar": r["anahtar"], "proje": r["proje"], "kategori": r.get("kategori"),
                "ogretmen_model": r.get("ogretmen_model"),
                "etiketler": {alan: r.get(alan, "") for alan in ALANLAR},
                "kaynak_token_tahmini": kaynak_token, "kaynak_kesildi": kesildi,
                **cevap,
            }
            yeni[r["anahtar"]] = satir
            kosu_token += satir.get("token", 0)
            f.write(json.dumps(satir, ensure_ascii=False) + "\n")
            f.flush()
            if no % 200 == 0:
                print(f"token: {kosu_token:,} ({no}/{len(sorulacak)} yeni satır)", file=sys.stderr)

    hepsi = [eski.get(r["anahtar"]) or yeni[r["anahtar"]] for r in secilen]
    with sonuc_yolu.open("w") as f:
        for r in hepsi:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"yeni token: {kosu_token:,}")
    print(f"toplam token: {sum(r.get('token', 0) for r in hepsi):,}")
    print(f"ayrıntı → {sonuc_yolu}")
    if a.rapor:
        rapor = Path("rapor/OGRETMEN_DENETIM.md")
        rapor_yaz(hepsi, rapor)
        print(f"rapor → {rapor}")


if __name__ == "__main__":
    main()
