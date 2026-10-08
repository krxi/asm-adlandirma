#!/usr/bin/env python3
"""LoRA'lı (ya da --adaptor-yok ile taban) modeli lora/veri/test.jsonl üstünde ölç.

  .venv/bin/python lora/olc.py -n 10
  .venv/bin/python lora/olc.py --adaptor-yok --cikti /tmp/taban.jsonl

Satır biçimi taban.py ile aynı (id, gercek, tahmin, aciklama, f1, opt, token); ozet.py okuyabilsin.
"""
import argparse, json, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from taban import f1  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="mlx-community/Qwen2.5-Coder-0.5B-Instruct-4bit")
    ap.add_argument("--adaptor", default="lora/adaptor")
    ap.add_argument("--adaptor-yok", action="store_true", help="eğitimsiz taban")
    ap.add_argument("--test", type=Path, default=Path("lora/veri/test.jsonl"))
    ap.add_argument("--ad", default=None, help="sonuç adındaki test etiketi (vars. test projesi için 'test')")
    ap.add_argument("-n", type=int, default=0, help="0 = hepsi")
    ap.add_argument("--maks-token", type=int, default=48)
    ap.add_argument("--cikti", type=Path, default=None)
    a = ap.parse_args()

    from mlx_lm import generate, load
    model, tok = load(a.model, adapter_path=None if a.adaptor_yok else a.adaptor)

    satirlar = [json.loads(l) for l in a.test.open() if l.strip()]
    if a.n:
        satirlar = satirlar[: a.n]
    kisa = a.model.split("/")[-1]
    cikti = a.cikti or Path("sonuc") / f"{a.ad or 'test'}-{kisa}-{'taban' if a.adaptor_yok else 'lora'}.jsonl"
    cikti.parent.mkdir(exist_ok=True)

    t0, hepsi = time.time(), []
    for r in satirlar:
        mesajlar = r["messages"][:2]
        istem = tok.apply_chat_template(mesajlar, add_generation_prompt=True, tokenize=False)
        n_giris = len(tok.encode(istem))
        metin = generate(model, tok, prompt=istem, max_tokens=a.maks_token, verbose=False)
        m = re.findall(r"\{[^{}]*\}", metin)
        try:
            tahmin = str(json.loads(m[-1]).get("ad", "")) if m else metin.strip()[:60]
        except json.JSONDecodeError:
            tahmin = ""
        gercek = json.loads(r["messages"][2]["content"])["ad"]
        s = f1(tahmin, gercek)
        hepsi.append({"id": r["id"], "gercek": gercek, "tahmin": tahmin, "aciklama": "",
                      "f1": round(s, 3), "opt": r.get("opt", ""), "token": n_giris + len(tok.encode(metin))})
        print(f"{s:.2f}  {hepsi[-1]['opt']}  {gercek:<28} ← {tahmin}", flush=True)

    with cikti.open("w") as f:
        for r in hepsi:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    ort = sum(r["f1"] for r in hepsi) / max(1, len(hepsi))
    tam = sum(r["f1"] == 1 for r in hepsi)
    print(f"ortalama F1 {ort:.3f}  (n={len(hepsi)}, tam isabet {tam})  süre {time.time() - t0:.0f}s\nayrıntı → {cikti}")


if __name__ == "__main__":
    main()
