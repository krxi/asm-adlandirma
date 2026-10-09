#!/usr/bin/env python3
"""Gradio demo: assembly yapıştır ya da nesne dosyası yükle → ad + açıklama.

  pip install -r demo/requirements.txt
  python3 demo/app.py                                    # sahte model, http://127.0.0.1:7860
  ADLANDIR_URL=http://localhost:8000/v1 ADLANDIR_MODEL=qwen3-8b-asm python3 demo/app.py
  ADLANDIR_TABAN=Qwen/Qwen3-8B ADLANDIR_ADAPTOR=adaptor-Qwen3-8B python3 demo/app.py

Modeli ve istemi adlandir.py ile paylaşır; bu dosya yalnız arayüzdür. Yayınlamaz (share=False).
"""

import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import adlandir  # noqa: E402

ORNEK = """push\trbp
mov\trbp, rsp
mov\tqword ptr [rbp - 0x8], rdi
mov\trdi, qword ptr [rbp - 0x8]
call\tloc_1    ; -> strlen
loc_1:
add\trax, 0x1
mov\trdi, rax
call\tloc_2    ; -> malloc
loc_2:
mov\trdi, rax
mov\trsi, qword ptr [rbp - 0x8]
call\tloc_3    ; -> strcpy
loc_3:
pop\trbp
ret"""


def model_kur():
    """Ortam değişkenine göre arka uç: ADLANDIR_TABAN → hf, ADLANDIR_URL → uç nokta, yoksa sahte."""
    if os.environ.get("ADLANDIR_TABAN"):
        return adlandir.HF(os.environ["ADLANDIR_TABAN"], os.environ.get("ADLANDIR_ADAPTOR", "")), "hf"
    if os.environ.get("ADLANDIR_URL"):
        anahtar = os.environ.get("ADLANDIR_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        uc = adlandir.UcNokta(
            os.environ["ADLANDIR_URL"],
            os.environ.get("ADLANDIR_MODEL", ""),
            anahtar,
            os.environ.get("ADLANDIR_ANAHTAR_BASLIGI", "Authorization"),
        )
        return uc, "uç nokta"
    return adlandir.Sahte(), "sahte (model yok)"


def asm_adlandir(model, asm: str, baglam: str = "") -> tuple:
    """Yapıştırılan tek fonksiyon → (ad, açıklama, modele giden istem)."""
    if not asm.strip():
        return "", "Assembly yapıştırın.", ""
    kayit = adlandir.tek_fonksiyon(asm, baglam)
    sonuc = adlandir.adlandir(kayit, model, "ozet" if baglam.strip() else "yok")
    return sonuc["tahmin"], sonuc["aciklama"], adlandir.mesajlar(kayit, "ozet")[1]["content"]


def dosya_adlandir(model, yol: str) -> list:
    """Nesne dosyası → [kimlik, gerçek ad, tahmin, F1, açıklama] satırları."""
    if not yol:
        return []
    satirlar = []
    for kayit in adlandir.girdiden_kayitlar(Path(yol)):
        s = adlandir.adlandir(kayit, model)
        satirlar.append([kayit["id"], kayit["ad"], s["tahmin"], s.get("f1", ""), s["aciklama"]])
    return satirlar


def arayuz(model=None, tur: str = ""):
    import gradio as gr

    if model is None:
        model, tur = model_kur()
    with gr.Blocks(title="asm-adlandirma") as demo:
        gr.Markdown(
            f"# Sembolsüz x86-64 fonksiyon adlandırma\nArka uç: **{tur}**. Girdi modele anonim gider; "
            "nesne dosyasındaki gerçek adlar yalnız puan için gösterilir."
        )
        with gr.Tab("Assembly yapıştır"):
            asm = gr.Code(value=ORNEK, label="Fonksiyon (Intel sözdizimi, veri setindeki biçim)", lines=18)
            baglam = gr.Textbox(label="Çağrılan iç fonksiyonların özeti (isteğe bağlı)", lines=3)
            dugme = gr.Button("Adlandır", variant="primary")
            ad = gr.Textbox(label="Ad")
            aciklama = gr.Textbox(label="Açıklama")
            with gr.Accordion("Modele giden istem", open=False):
                istem = gr.Code(label="istem")
            dugme.click(lambda a, b: asm_adlandir(model, a, b), [asm, baglam], [ad, aciklama, istem])
        with gr.Tab("Nesne dosyası"):
            dosya = gr.File(label="ELF ya da Mach-O x86-64 .o (sembollü)", type="filepath")
            tablo = gr.Dataframe(headers=["kimlik", "gerçek ad", "tahmin", "F1", "açıklama"], wrap=True)
            dosya.upload(lambda y: dosya_adlandir(model, y), dosya, tablo)
    return demo


if __name__ == "__main__":
    arayuz().launch(server_name=os.environ.get("ADLANDIR_HOST", "127.0.0.1"), share=False)
