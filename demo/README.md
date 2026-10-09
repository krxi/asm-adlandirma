# Demo

Gradio arayüzü: bir fonksiyonun assembly'sini yapıştırın ya da sembollü bir x86-64 nesne dosyası yükleyin;
model her fonksiyon için ad ve tek cümlelik Türkçe açıklama önersin. Arayüz yalnız yerelde açılır
(`share=False`), hiçbir yere yüklenmez.

```bash
pip install -r demo/requirements.txt
python3 demo/app.py            # http://127.0.0.1:7860
```

## Arka uç

`adlandir.py` ile aynı arka uçlar; ortam değişkeniyle seçilir:

| Değişkenler | Arka uç |
|---|---|
| hiçbiri | **sahte**: model yok, ilk dış importtan ad uydurur. Arayüzü ve hattı denemek için. |
| `ADLANDIR_URL`, `ADLANDIR_MODEL` (+ `ADLANDIR_API_KEY`, `ADLANDIR_ANAHTAR_BASLIGI`) | OpenAI uyumlu uç nokta: vLLM, llama.cpp server, Ollama, Evren (`ADLANDIR_ANAHTAR_BASLIGI=X-API-Key`) |
| `ADLANDIR_TABAN` (+ `ADLANDIR_ADAPTOR`) | transformers + peft ile yerel model ve Colab'da eğitilen LoRA adaptörü (`pip install torch transformers peft accelerate`) |

Örnek, Colab adaptörüyle:

```bash
ADLANDIR_TABAN=Qwen/Qwen2.5-Coder-1.5B-Instruct \
ADLANDIR_ADAPTOR=~/Downloads/adaptor-Qwen2.5-Coder-1.5B-Instruct \
python3 demo/app.py
```

## Sekmeler

- **Assembly yapıştır**: veri setindeki biçimde tek fonksiyon (iç çağrılar `sub_XXXX`, stringler `; -> "..."`).
  İsteğe bağlı bağlam kutusu, eğitimdeki "çağrılan fonksiyonlar" özetidir. "Modele giden istem" bölümü
  modelin tam olarak ne gördüğünü gösterir.
- **Nesne dosyası**: ELF ya da Mach-O `.o`. Fonksiyonlar `adlandir.py` ile ayrılır ve anonimleştirilir;
  gerçek adlar modele gitmez, tabloda yalnız F1 puanı için görünür. `llvm-objdump` gerekir.

Sembolleri silinmiş, linklenmiş binary'lerde fonksiyon sınırlarını bulmak için Ghidra betiğini kullanın
([ghidra/](../ghidra/README.md)).

## Komut satırı

Aynı iş arayüzsüz:

```bash
python3 adlandir.py ornek.o --arka-uc uc --url http://localhost:8000/v1 --model <ad> --olc
```
