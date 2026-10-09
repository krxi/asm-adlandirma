#!/usr/bin/env python3
"""LoRA sonuç dosyasını test verisiyle eşleyip kırılım raporu yaz.

  python3 analiz_molab.py sonuc/test2000-molab-qwen3-8b.jsonl -o rapor/MOLAB_KIRILIM.md

Kırılımlar: string var/yok, komut sayısı, opt, bağlam, export, proje; tahminin eğitimdeki bir adın
birebir kopyası olup olmadığı (ezber işareti), en sık tahminler. F1 dosyadaki `f1` alanıdır.
"""
import argparse, json, statistics as st
from collections import Counter, defaultdict
from pathlib import Path


def ad_oku(satir: str) -> str:
    i = satir.find('"ad": "') + 7
    return satir[i:satir.find('"', i)]


def tablo(baslik, gruplar):
    out = [f"### {baslik}", "", "| grup | n | F1 | F1=0 payı | tam isabet |", "|---|---:|---:|---:|---:|"]
    for k, rs in gruplar:
        f = [r["f1"] for r in rs]
        out.append(f"| {k} | {len(rs)} | {st.mean(f):.3f} | {sum(x == 0 for x in f) / len(f):.0%} "
                   f"| {sum(r['f1'] >= 1 for r in rs)} |")
    return out + [""]


def grupla(R, anahtar, sira=None):
    g = defaultdict(list)
    for r in R:
        g[anahtar(r)].append(r)
    return [(k, g[k]) for k in (sira or sorted(g, key=str)) if k in g]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sonuc", type=Path)
    ap.add_argument("--veri", type=Path, default=Path("veri/bin/olcek"))
    ap.add_argument("-o", "--cikti", type=Path, default=Path("/dev/stdout"))
    a = ap.parse_args()

    R = [json.loads(l) for l in a.sonuc.open() if l.strip()]
    ids = {r["id"] for r in R}
    T = {}
    for p in (a.veri / "test.jsonl", a.veri / "dogrulama.jsonl", Path("veri/test.jsonl")):
        for l in p.open():
            d = json.loads(l)
            if d["id"] in ids:
                T.setdefault(d["id"], d)
    eksik = ids - T.keys()
    if eksik:
        raise SystemExit(f"{len(eksik)} id veride yok: {sorted(eksik)[:3]}")
    egitim_adlari = Counter(ad_oku(l) for l in (a.veri / "egitim.jsonl").open())
    for r in R:
        t = T[r["id"]]
        r["_string"] = '"' in t["asm"]
        r["_komut"] = t["komut_sayisi"]
        r["_baglam"] = bool(t.get("baglam"))
        r["_export"] = bool(t.get("export"))
        r["_kopya"] = r["tahmin"] in egitim_adlari
        r["_gercek_egitimde"] = r["gercek"] in egitim_adlari

    f = [r["f1"] for r in R]
    C = Counter(r["tahmin"] for r in R)
    kopya = [r for r in R if r["_kopya"]]
    out = [f"# Kırılım: {a.sonuc.name}", "",
           f"`python3 analiz_molab.py {a.sonuc}` çıktısı. n={len(R)}, ortalama ad F1 **{st.mean(f):.3f}**, "
           f"tam isabet (F1=1) {sum(r['f1'] >= 1 for r in R)}.", "",
           f"- Benzersiz tahmin: {len(C)} / {len(R)} (%{100 * len(C) / len(R):.0f})",
           f"- Tahmin eğitimdeki bir adın birebir kopyası: {len(kopya)} (%{100 * len(kopya) / len(R):.0f}); "
           f"bunlarda F1 {st.mean(r['f1'] for r in kopya):.3f}, diğerlerinde "
           f"{st.mean(r['f1'] for r in R if not r['_kopya']):.3f}",
           f"- Gerçek ad eğitimde de geçiyor (vendored/ortak ad): {sum(r['_gercek_egitimde'] for r in R)} satır",
           "- En sık 10 tahmin: " + ", ".join(f"`{k}` ×{v}" for k, v in C.most_common(10)), ""]
    out += tablo("String sabiti", grupla(R, lambda r: "var" if r["_string"] else "yok", ["var", "yok"]))
    kova = lambda n: "<20" if n < 20 else "20-59" if n < 60 else "60-199" if n < 200 else "200+"
    out += tablo("Komut sayısı", grupla(R, lambda r: kova(r["_komut"]), ["<20", "20-59", "60-199", "200+"]))
    out += tablo("Opt", grupla(R, lambda r: r["opt"]))
    out += tablo("Çağrı bağlamı", grupla(R, lambda r: "var" if r["_baglam"] else "yok", ["var", "yok"]))
    out += tablo("Export", grupla(R, lambda r: "evet" if r["_export"] else "hayır", ["evet", "hayır"]))
    out += tablo("Tahmin eğitim adı kopyası", grupla(R, lambda r: "evet" if r["_kopya"] else "hayır", ["evet", "hayır"]))
    projeler = grupla(R, lambda r: r["proje"])
    out += tablo("Proje", sorted(projeler, key=lambda x: -len(x[1])))
    a.cikti.parent.mkdir(parents=True, exist_ok=True)
    a.cikti.write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
