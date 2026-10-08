"""Öğretmen açıklamalarını (veri/aciklama/*.jsonl) Hugging Face veri setine yükler.

Varsayılan kip kuru çalışmadır: birleşik dosyayı hazırlar, sayıları doğrular, hiçbir şey yüklemez.
Gerçek yükleme için `--yukle` verilir (HF girişi: `huggingface-cli login`).

    python3 hf_yukle.py                # kuru: doğrula + aciklama/aciklama.jsonl hazırla
    python3 hf_yukle.py --yukle        # HF'ye yükle (yalnız onaydan sonra)
"""
import argparse
import json
import sys
from pathlib import Path

REPO = "krxi123/asm-adlandirma"
BEKLENEN = 17581  # eğitim 16.804 + test 777


def oku(klasor):
    satirlar, gorulen = [], set()
    for dosya in sorted(klasor.glob("*.jsonl")):
        for no, ham in enumerate(dosya.read_text(encoding="utf-8").splitlines(), 1):
            if not ham.strip():
                continue
            s = json.loads(ham)
            for alan in ("id", "aciklama", "model"):
                if not s.get(alan):
                    sys.exit(f"{dosya.name}:{no}: '{alan}' boş")
            if s["id"] in gorulen:
                sys.exit(f"{dosya.name}:{no}: yinelenen id {s['id']}")
            gorulen.add(s["id"])
            s["proje"] = dosya.stem
            satirlar.append(s)
    return satirlar


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--girdi", default="veri/aciklama")
    p.add_argument("--cikti", default="veri/yayin/aciklama/aciklama.jsonl")
    p.add_argument("--yukle", action="store_true")
    a = p.parse_args()

    satirlar = oku(Path(a.girdi))
    print(f"{len(satirlar)} açıklama, {len({s['proje'] for s in satirlar})} proje")
    if len(satirlar) != BEKLENEN:
        sys.exit(f"beklenen {BEKLENEN}, bulunan {len(satirlar)}: yüklenmedi")

    cikti = Path(a.cikti)
    cikti.parent.mkdir(parents=True, exist_ok=True)
    with cikti.open("w", encoding="utf-8") as f:
        for s in satirlar:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"hazır: {cikti}")

    if not a.yukle:
        print("kuru kip: yükleme yapılmadı (--yukle ile yüklenir)")
        return
    from huggingface_hub import HfApi
    HfApi().upload_file(
        path_or_fileobj=str(cikti),
        path_in_repo="aciklama/aciklama.jsonl",
        repo_id=REPO,
        repo_type="dataset",
        commit_message="Öğretmen açıklamaları: 17.581 fonksiyon için tek cümlelik Türkçe açıklama",
    )
    print(f"yüklendi: https://huggingface.co/datasets/{REPO}/tree/main/aciklama")


if __name__ == "__main__":
    main()
