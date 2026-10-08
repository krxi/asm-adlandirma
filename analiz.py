#!/usr/bin/env python3
"""Hata analizi: modeller hangi fonksiyon türlerinde çöküyor?

Her fonksiyon asm'sinden türlere ayrılır (bir fonksiyon birden çok türde olabilir),
her model × tür için ortalama F1 hesaplanır, tablo basılır ve ısı haritası çizilir.

  python3 analiz.py veri/zlib.jsonl                      # sonuc/zlib-*.jsonl
  python3 analiz.py veri/test.jsonl -o grafik/test-hata.png
"""
import argparse, json, re
from pathlib import Path


def turler(r: dict) -> list[str]:
    asm, n = r["asm"], r["komut_sayisi"]
    satirlar = asm.splitlines()
    cagrilar = [s for s in satirlar if s.startswith("call")]
    ic_cagri = [s for s in cagrilar if "sub_" in s]
    kuyruk = [s for s in satirlar if s.startswith("jmp") and "sub_" in s]
    t = [r["opt"]]
    t.append("kısa (<20)" if n < 20 else "orta (20-80)" if n <= 80 else "uzun (>80)")
    if n <= 25 and len(ic_cagri) + len(kuyruk) == 1 and len(cagrilar) <= 1:
        t.append("sarmalayıcı")
    if not cagrilar and not kuyruk:
        t.append("yaprak (çağrısız)")
    t.append("string'li" if re.search(r'; -> "', asm) else "string'siz")
    if any("; -> sub_" not in s and "; ->" in s for s in cagrilar):
        t.append("dış çağrılı")
    return t


SIRA = ["-O0", "-O2", "kısa (<20)", "orta (20-80)", "uzun (>80)", "sarmalayıcı", "yaprak (çağrısız)",
        "dış çağrılı", "string'li", "string'siz"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("veri", type=Path)
    ap.add_argument("-o", "--cikti", type=Path)
    ap.add_argument("--baslik")
    a = ap.parse_args()

    veri = {r["id"]: r for r in map(json.loads, a.veri.open())}
    modeller, tablo, sayilar = [], {}, {}
    for p in sorted(Path("sonuc").glob(f"{a.veri.stem}-*.jsonl")):
        model = p.stem[len(a.veri.stem) + 1:]
        satirlar = [json.loads(l) for l in p.open()]
        satirlar = [s for s in satirlar if not str(s.get("aciklama", "")).startswith("HATA") and s["id"] in veri]
        if not satirlar:
            continue
        modeller.append(model)
        for s in satirlar:
            for t in turler(veri[s["id"]]):
                tablo.setdefault((model, t), []).append(s["f1"])
        if not sayilar:
            for s in satirlar:
                for t in turler(veri[s["id"]]):
                    sayilar[t] = sayilar.get(t, 0) + 1
    kolonlar = [t for t in SIRA if t in sayilar]
    # En iyi ortalamadan en kötüye
    ort = lambda m: sum(sum(tablo.get((m, k), [0])) for k in ("-O0", "-O2")) / max(1, sum(len(tablo.get((m, k), [])) for k in ("-O0", "-O2")))
    modeller.sort(key=ort, reverse=True)

    print(f"{'model':<30}" + "".join(f"{k[:11]:>12}" for k in kolonlar))
    print(f"{'(n)':<30}" + "".join(f"{sayilar[k]:>12}" for k in kolonlar))
    for m in modeller:
        print(f"{m:<30}" + "".join(f"{sum(v) / len(v):>12.2f}" if (v := tablo.get((m, k))) else f"{'-':>12}" for k in kolonlar))

    if not a.cikti:
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    # Tek ton (mavi) sıralı rampa: açık = düşük F1, koyu = yüksek F1.
    rampa = LinearSegmentedColormap.from_list("mavi", ["#f2f6fc", "#a9c8f0", "#2a78d6", "#0d3a73"])
    M = [[(sum(v) / len(v)) if (v := tablo.get((m, k))) else float("nan") for k in kolonlar] for m in modeller]
    ust = max(0.5, max(x for satir in M for x in satir if x == x))
    fig, ax = plt.subplots(figsize=(1.05 * len(kolonlar) + 3.2, 0.42 * len(modeller) + 1.9), dpi=160)
    fig.patch.set_facecolor("#fcfcfb")
    ax.imshow(M, cmap=rampa, vmin=0, vmax=ust, aspect="auto")
    for i, satir in enumerate(M):
        for j, x in enumerate(satir):
            if x == x:
                ax.text(j, i, f"{x:.2f}", ha="center", va="center", fontsize=8,
                        color="#ffffff" if x > ust * 0.55 else "#0b0b0b")
    ax.set_xticks(range(len(kolonlar)))
    ax.set_xticklabels([f"{k}\nn={sayilar[k]}" for k in kolonlar], fontsize=8, color="#52514e")
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(modeller)))
    ax.set_yticklabels(modeller, fontsize=8.5, color="#0b0b0b")
    ax.set_xticks([x - 0.5 for x in range(1, len(kolonlar))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(modeller))], minor=True)
    ax.grid(which="minor", color="#fcfcfb", linewidth=2)
    ax.tick_params(which="both", length=0)
    for k in ax.spines.values():
        k.set_visible(False)
    fig.suptitle(a.baslik or f"Fonksiyon türüne göre ortalama ad F1 ({a.veri.stem})", x=0.01, ha="left",
                 fontsize=11, color="#0b0b0b", y=0.995)
    fig.text(0.01, 0.005, "Hücre: kelime örtüşmesi F1 ortalaması (1.0 = tam doğru). Türler örtüşebilir. "
             "Sarmalayıcı: ≤25 komut, tek iç çağrı.", fontsize=7, color="#52514e")
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    a.cikti.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.cikti, facecolor=fig.get_facecolor())
    print(f"grafik → {a.cikti}")


if __name__ == "__main__":
    main()
