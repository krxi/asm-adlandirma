#!/usr/bin/env python3
"""sonuc/*.jsonl ölçümlerini iki F1 tanımıyla yeniden puanla → markdown rapor.

  python3 iki_f1.py                                  # sonuc/*.jsonl → rapor/F1_IKI_TANIM.md
  python3 iki_f1.py sonuc/test-*.jsonl -o /dev/stdout
  python3 iki_f1.py ~/indirilen/test-qwen3-8b-lora.jsonl -o /tmp/r.md   # Colab/molab çıktısı

Tanımlar:
  gerçek ad F1  taban.f1(tahmin, gerçek ad)          README tablolarındaki -O0/-O2 sütunları
  öneksiz F1    ozet.f1_oneksiz: projenin ortak öneki iki taraftan atılır (ozet.onekler)

"Hedef" sütunu, sonuç dosyasındaki `gercek` alanının veri/ altındaki gerçek adla aynı olup olmadığını
gösterir. lora/hazirla_olcek.py varsayılanda test hedefinden öneki atar; o hedefle puanlanmış bir
koşunun "f1" alanı gerçek ad F1'i değildir. Gerçek adı bulunan satırlar burada gerçek adla yeniden puanlanır.
"""

import argparse, json, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lora"))
from taban import f1  # noqa: E402
import ozet  # noqa: E402


def gercek_adlar(veri: Path) -> dict[str, str]:
    adlar = {}
    for p in [
        *veri.glob("test/*.jsonl"),
        *veri.glob("egitim/*.jsonl"),
        *veri.glob("*.jsonl"),
        *veri.glob("bin/olcek/*.jsonl"),
    ]:
        for l in p.open():
            if l.strip():
                r = json.loads(l)
                adlar.setdefault(r["id"], r["ad"])
    return adlar


def puanla(satirlar: list[dict], adlar: dict[str, str]) -> dict:
    gr, ok, hedef_farkli, bilinmeyen = defaultdict(list), defaultdict(list), 0, 0
    kayitli_uyumsuz = 0
    for r in satirlar:
        tahmin = str(r.get("tahmin") or "")
        asil = adlar.get(r["id"])
        if asil is None:
            bilinmeyen += 1
            asil = r["gercek"]
        elif asil != r["gercek"]:
            hedef_farkli += 1
        if "f1" in r and abs(round(r["f1"], 3) - round(f1(tahmin, r["gercek"]), 3)) > 1e-9:
            kayitli_uyumsuz += 1
        duz = {**r, "gercek": asil, "tahmin": tahmin}
        for opt in (r.get("opt", ""), "hepsi"):
            gr[opt].append(f1(tahmin, asil))
            ok[opt].append(ozet.f1_oneksiz(duz))
    ort = lambda l: sum(l) / len(l) if l else float("nan")
    return {
        "n": len(satirlar),
        "hedef_farkli": hedef_farkli,
        "bilinmeyen": bilinmeyen,
        "kayitli_uyumsuz": kayitli_uyumsuz,
        "gercek": {k: ort(v) for k, v in gr.items()},
        "oneksiz": {k: ort(v) for k, v in ok.items()},
        "isabet_gercek": sum(x == 1 for x in gr["hepsi"]),
        "isabet_oneksiz": sum(x == 1 for x in ok["hepsi"]),
        "kayitli_f1": ort([r["f1"] for r in satirlar if "f1" in r]),
    }


def tablo(sonuclar: dict[str, dict]) -> list[str]:
    s = lambda x: "-" if x != x else f"{x:.3f}"
    satir = [
        "| koşu | n | gerçek ad F1 (-O0 / -O2 / hepsi) | öneksiz F1 (-O0 / -O2 / hepsi) | fark | "
        "tam isabet gerçek / öneksiz | dosyadaki f1 | hedef |",
        "|---|---:|---|---|---:|---|---:|---|",
    ]
    for ad, p in sorted(sonuclar.items(), key=lambda x: -x[1]["oneksiz"]["hepsi"]):
        g, o = p["gercek"], p["oneksiz"]
        hedef = "gerçek ad" if not p["hedef_farkli"] else f"**{p['hedef_farkli']} satırda öneksiz**"
        if p["bilinmeyen"]:
            hedef += f", {p['bilinmeyen']} id veri/'de yok"
        satir.append(
            f"| {ad} | {p['n']} | {s(g.get('-O0', float('nan')))} / {s(g.get('-O2', float('nan')))} / "
            f"{s(g['hepsi'])} | {s(o.get('-O0', float('nan')))} / {s(o.get('-O2', float('nan')))} / "
            f"{s(o['hepsi'])} | {o['hepsi'] - g['hepsi']:+.3f} | {p['isabet_gercek']} / "
            f"{p['isabet_oneksiz']} | {s(p['kayitli_f1'])} | {hedef} |"
        )
    return satir


def onek_tablosu(veri: Path) -> list[str]:
    import hazirla_olcek as ho

    satirlar = [json.loads(l) for p in sorted(veri.glob("test/*.jsonl")) for l in p.open() if l.strip()]
    if not satirlar:
        return []
    siklik, proje = ho.onekler(satirlar, "siklik"), ho.onekler(satirlar, "proje")
    out = [
        "| test projesi | ozet.py (öneksiz F1) | hazirla_olcek.py siklik (varsayılan) | hazirla_olcek.py proje |",
        "|---|---|---|---|",
    ]
    for p in sorted({r["proje"] for r in satirlar}):
        g = lambda d: ", ".join(sorted(d.get(p, ()))) or "-"
        out.append(f"| {p} | {g(ozet.ONEK)} | {g(siklik)} | {g(proje)} |")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dosyalar", nargs="*", type=Path)
    ap.add_argument("--veri", type=Path, default=Path("veri"))
    ap.add_argument("-o", "--cikti", type=Path, default=Path("rapor/F1_IKI_TANIM.md"))
    a = ap.parse_args()
    dosyalar = a.dosyalar or sorted(Path("sonuc").glob("*.jsonl"))
    adlar = gercek_adlar(a.veri)
    sonuclar = {}
    for p in dosyalar:
        satirlar = [json.loads(l) for l in p.open() if l.strip()]
        if satirlar and "gercek" in satirlar[0]:
            sonuclar[p.stem] = puanla(satirlar, adlar)

    md = [
        "# Ad F1: gerçek ad ve öneksiz ad",
        "",
        f"`python3 iki_f1.py` çıktısı, {len(sonuclar)} sonuç dosyası. Elle düzenlemeyin; betiği yeniden çalıştırın.",
        "",
        "- **gerçek ad F1**: `taban.f1(tahmin, gerçek ad)`. Ad snake/camel sözcüklere bölünür, sözcük kümelerinin F1'i.",
        "- **öneksiz F1**: `ozet.f1_oneksiz`. Projenin ortak öneki (aşağıdaki tablo, ilk sütun) iki taraftan atılır;",
        "  model öneki assembly'den bilemez.",
        "- **dosyadaki f1**: sonuç dosyasına koşu sırasında yazılan değer. Hedef öneksizse gerçek ad F1'inden farklıdır.",
        "- **hedef**: dosyadaki `gercek` alanı veri/'deki gerçek adla aynı mı.",
        "",
    ]
    md += tablo(sonuclar)
    uyumsuz = {k: v["kayitli_uyumsuz"] for k, v in sonuclar.items() if v["kayitli_uyumsuz"]}
    md += [
        "",
        f"Dosyadaki `f1` alanı, aynı dosyadaki `gercek` ile yeniden hesaplanan değerle "
        f"{'her satırda tutuyor' if not uyumsuz else 'şu dosyalarda tutmuyor: ' + json.dumps(uyumsuz)}.",
        "",
    ]
    onek = onek_tablosu(a.veri)
    if onek:
        md += [
            "## Önek tanımları test projelerinde",
            "",
            "İki kod yolu farklı önek buluyor. `hazirla_olcek.py` varsayılanı proje adından bağımsız en sık "
            "`xxx_` başını alıyor; bu, bazı projelerde anlamlı fiilleri (sajs `eat_`, picomatch `emit_`) "
            "eğitim ve test hedefinden siliyor.",
            "",
        ] + onek
    a.cikti.parent.mkdir(parents=True, exist_ok=True)
    a.cikti.write_text("\n".join(md) + "\n")
    print(f"{len(sonuclar)} dosya → {a.cikti}")


if __name__ == "__main__":
    main()
