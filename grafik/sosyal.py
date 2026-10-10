#!/usr/bin/env python3
"""X/Twitter için deney sonuçlarını 1600×900 PNG grafiklere dönüştürür."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))
sys.dont_write_bytecode = True

from analiz import SIRA, turler  # noqa: E402
from ozet import f1_oneksiz  # noqa: E402


ARKA = "#090D18"
PANEL = "#12192A"
YAZI = "#F4F7FB"
SOLUK = "#9AA6BA"
IZGARA = "#263149"
MAVI = "#58A6FF"
TURKUAZ = "#3DD6C6"
SARI = "#FFC857"
PEMBE = "#FF6B9A"
MOR = "#A78BFA"
IMZA = "github.com/krxi/asmsense"
CIKTI = KOK / "grafik"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "text.color": YAZI,
    "axes.labelcolor": SOLUK,
    "xtick.color": SOLUK,
    "ytick.color": SOLUK,
    "axes.edgecolor": IZGARA,
})


def jsonl(yol: Path) -> list[dict]:
    with yol.open(encoding="utf-8") as f:
        return [json.loads(satir) for satir in f]


def tuval(baslik: str, alt_baslik: str):
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=ARKA)
    fig.text(0.055, 0.925, baslik, fontsize=33, weight="bold", color=YAZI, va="top")
    fig.text(0.057, 0.858, alt_baslik, fontsize=15, color=SOLUK, va="top")
    fig.text(0.955, 0.035, IMZA, fontsize=12, color=SOLUK, ha="right", va="bottom")
    return fig


def kaydet(fig, ad: str) -> None:
    fig.savefig(CIKTI / ad, dpi=100, facecolor=ARKA, bbox_inches=None, pad_inches=0)
    plt.close(fig)


def baglam_grafigi() -> None:
    modeller = [
        ("mimo-v2.6-pro", "mimo v2.6 pro"),
        ("deepseek-v4.1-flash", "deepseek v4.1"),
        ("qwen3.8-flash-next", "qwen 3.8"),
        ("gemma-4-31b", "gemma 4 31b"),
        ("glm-5.3", "glm 5.3"),
    ]
    kipler = [("", "Bağlamsız"), ("-baglam", "Özet bağlam"), ("-baglam2", "Derin bağlam")]
    degerler = np.zeros((len(modeller), len(kipler)))
    for i, (dosya_adi, _) in enumerate(modeller):
        for j, (ek, _) in enumerate(kipler):
            satirlar = jsonl(KOK / "sonuc" / f"test-{dosya_adi}{ek}.jsonl")
            assert len(satirlar) == 115
            degerler[i, j] = sum(f1_oneksiz(r) for r in satirlar) / len(satirlar)

    fig = tuval(
        "Çağrı bağlamı modele ne kazandırır?",
        "Az bilinen 115 fonksiyon · öneksiz F1 · düşünmesiz koşular",
    )
    ax = fig.add_axes([0.075, 0.15, 0.87, 0.62], facecolor=ARKA)
    x = np.arange(len(modeller))
    genislik = 0.23
    renkler = [MAVI, TURKUAZ, SARI]
    for j, (_, etiket) in enumerate(kipler):
        cubuklar = ax.bar(x + (j - 1) * genislik, degerler[:, j], genislik,
                         label=etiket, color=renkler[j], zorder=3)
        for cubuk, deger in zip(cubuklar, degerler[:, j]):
            ax.text(cubuk.get_x() + cubuk.get_width() / 2, deger + 0.007, f"{deger:.2f}",
                    ha="center", va="bottom", fontsize=13, weight="bold", color=YAZI)
    ax.set_xticks(x, [etiket for _, etiket in modeller], fontsize=13)
    ax.set_ylim(0, 0.30)
    ax.set_yticks(np.arange(0, 0.31, 0.05))
    ax.set_ylabel("Öneksiz F1", fontsize=13)
    ax.grid(axis="y", color=IZGARA, linewidth=1, alpha=0.8, zorder=0)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(loc="upper right", frameon=False, ncols=3, fontsize=13, bbox_to_anchor=(1, 1.12))
    kaydet(fig, "x-baglam.png")


def ezber_grafigi() -> None:
    kosullar = [
        ("zlib-v3-mimo-v2.6-pro.jsonl", "zlib-v3-mimo-v2.6-pro-dusunme.jsonl", "zlib\n(çok ünlü)"),
        ("test-mimo-v2.6-pro.jsonl", "test-mimo-v2.6-pro-dusunme.jsonl", "Az bilinen\n5 proje"),
    ]
    degerler = []
    f1ler = []
    for normal, dusunmeli, _ in kosullar:
        ikili, ikili_f1 = [], []
        for dosya in (normal, dusunmeli):
            satirlar = jsonl(KOK / "sonuc" / dosya)
            assert len(satirlar) == 115
            ikili.append(sum(r["f1"] == 1 for r in satirlar))
            ikili_f1.append(sum(f1_oneksiz(r) for r in satirlar) / len(satirlar))
        degerler.append(ikili)
        f1ler.append(ikili_f1)
    degerler = np.array(degerler)

    fig = tuval(
        "Düşünmek ünlü kodda işe yarıyor: ezber",
        "mimo-v2.6-pro · aynı veri hattı · her grupta 115 fonksiyon",
    )
    ax = fig.add_axes([0.12, 0.16, 0.76, 0.61], facecolor=ARKA)
    x = np.arange(2)
    genislik = 0.28
    for j, (etiket, renk) in enumerate((("Düşünmesiz", MAVI), ("Düşünmeli", PEMBE))):
        cubuklar = ax.bar(x + (j - 0.5) * genislik, degerler[:, j], genislik,
                         label=etiket, color=renk, zorder=3)
        for i, cubuk in enumerate(cubuklar):
            deger = int(degerler[i, j])
            ax.text(cubuk.get_x() + cubuk.get_width() / 2, deger + 0.8, str(deger),
                    ha="center", fontsize=26, weight="bold", color=YAZI)
            ax.text(cubuk.get_x() + cubuk.get_width() / 2, deger / 2,
                    f"F1 {f1ler[i][j]:.2f}", ha="center", va="center", fontsize=12,
                    color=ARKA, weight="bold")
    ax.text(x[0], 31.5, "9 → 28", ha="center", fontsize=17, color=PEMBE, weight="bold")
    ax.text(x[1], 6.5, "4 → 3", ha="center", fontsize=17, color=SOLUK, weight="bold")
    ax.set_xticks(x, [k[2] for k in kosullar], fontsize=17)
    ax.set_ylim(0, 35)
    ax.set_yticks(range(0, 36, 5))
    ax.set_ylabel("Tam isabet", fontsize=14)
    ax.grid(axis="y", color=IZGARA, linewidth=1, zorder=0)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(loc="upper right", frameon=False, fontsize=14)
    kaydet(fig, "x-ezber.png")


def veri_grafigi() -> None:
    # v1: 14 eğitim + 5 test projesi; 16.804 + 777 fonksiyon.
    # v4: README ayrımları toplamı; 290 + 23 + 28 proje ve 196.117 + 19.770 + 12.290 satır.
    v1 = (16_804 + 777, 14 + 5, 2)
    v4 = (196_117 + 19_770 + 12_290, 290 + 23 + 28, 5)
    assert v1 == (17_581, 19, 2)
    assert v4 == (228_177, 341, 5)

    fig = tuval(
        "Veri seti 13× büyüdü",
        "v1’den v4’e: daha çok proje, daha çok derleyici görünümü, daha güçlü ayrım",
    )
    ax = fig.add_axes([0.055, 0.14, 0.89, 0.63])
    ax.set_axis_off()
    kartlar = [
        ("FONKSİYON", v1[0], v4[0], MAVI),
        ("PROJE", v1[1], v4[1], TURKUAZ),
        ("OPTİMİZASYON SEVİYESİ", v1[2], v4[2], SARI),
    ]
    for i, (etiket, eski, yeni, renk) in enumerate(kartlar):
        x = i / 3 + 0.012
        w = 0.31
        kart = plt.Rectangle((x, 0.08), w, 0.82, transform=ax.transAxes,
                             facecolor=PANEL, edgecolor=IZGARA, linewidth=1.5)
        ax.add_patch(kart)
        ax.text(x + 0.025, 0.82, etiket, transform=ax.transAxes, fontsize=12,
                color=renk, weight="bold", va="top")
        ax.text(x + w / 2, 0.58, f"{eski:,}".replace(",", "."), transform=ax.transAxes,
                ha="center", fontsize=25, color=SOLUK, weight="bold")
        ax.text(x + w / 2, 0.46, "↓", transform=ax.transAxes,
                ha="center", fontsize=27, color=renk, weight="bold")
        ax.text(x + w / 2, 0.28, f"{yeni:,}".replace(",", "."), transform=ax.transAxes,
                ha="center", fontsize=40, color=YAZI, weight="bold")
        ax.text(x + w / 2, 0.13, "v1  →  v4", transform=ax.transAxes,
                ha="center", fontsize=12, color=SOLUK)
    kaydet(fig, "x-veri.png")


def tur_grafigi() -> None:
    veri = {r["id"]: r for r in jsonl(KOK / "veri" / "test.jsonl")}
    kosullar = [
        ("Bağlamsız", "test-mimo-v2.6-pro.jsonl", MAVI),
        ("Derin bağlam", "test-mimo-v2.6-pro-baglam2.jsonl", SARI),
    ]
    seriler = []
    adetler = []
    for _, dosya, _ in kosullar:
        satirlar = [r for r in jsonl(KOK / "sonuc" / dosya)
                    if not str(r.get("aciklama", "")).startswith("HATA") and r["id"] in veri]
        seriler.append([
            sum(xs) / len(xs) if (xs := [r["f1"] for r in satirlar if kategori in turler(veri[r["id"]])]) else 0
            for kategori in SIRA
        ])
        if not adetler:
            adetler = [sum(kategori in turler(veri[r["id"]]) for r in satirlar) for kategori in SIRA]

    etiketler = [
        f"{kategori}   · n={n}" for kategori, n in zip(SIRA, adetler)
    ]
    fig = tuval(
        "Derin bağlam hangi fonksiyonlarda işe yarıyor?",
        "En iyi model: mimo-v2.6-pro · fonksiyon türüne göre ortalama ad F1",
    )
    ax = fig.add_axes([0.27, 0.12, 0.67, 0.68], facecolor=ARKA)
    y = np.arange(len(SIRA))
    h = 0.34
    for j, (etiket, _, renk) in enumerate(kosullar):
        cubuklar = ax.barh(y + (j - 0.5) * h, seriler[j], h, label=etiket, color=renk, zorder=3)
        for cubuk, deger in zip(cubuklar, seriler[j]):
            ax.text(deger + 0.006, cubuk.get_y() + cubuk.get_height() / 2, f"{deger:.2f}",
                    va="center", fontsize=11, color=YAZI, weight="bold")
    ax.set_yticks(y, etiketler, fontsize=11)
    ax.invert_yaxis()
    ax.set_xlim(0, 0.46)
    ax.set_xticks(np.arange(0, 0.46, 0.1))
    ax.set_xlabel("F1", fontsize=13)
    ax.grid(axis="x", color=IZGARA, linewidth=1, zorder=0)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(loc="lower right", frameon=False, fontsize=13)
    kaydet(fig, "x-tur.png")


def main() -> None:
    CIKTI.mkdir(parents=True, exist_ok=True)
    baglam_grafigi()
    ezber_grafigi()
    veri_grafigi()
    tur_grafigi()


if __name__ == "__main__":
    main()
