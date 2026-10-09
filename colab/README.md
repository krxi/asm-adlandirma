# Colab eğitimi

`egit.ipynb`, veri kümesini QLoRA ile eğitir ve `lora/olc.py` ile aynı ad F1 ölçümünü yapar. A100 40 GB için 7B, L4 24 GB için 3B model otomatik seçilir.

1. Repo kökünde `sh colab/zip_hazirla.sh` çalıştır; oluşan `veri.zip` dosyasını Colab dosya paneline yükle veya Drive'a koy.
2. `egit.ipynb` dosyasını Colab'da aç, GPU çalışma zamanı seç ve ayar hücresindeki `VERI_KAYNAGI` ile yolları denetle.
3. Hücreleri sırayla çalıştır. Adaptör Drive'daki `MyDrive/asm-adlandirma/adaptor-<model>` dizinine de yazılır.
4. Kaydetme ve ölçüm hücrelerinden adaptör zip'ini ve sonuç JSONL dosyasını indir.

Yaklaşık kaynak kullanımı: A100 + 7B için 22–32 GB ve 2–5 saat; L4 + 3B için 15–22 GB ve 4–9 saat. Süreler Colab kotası, dizi uzunlukları ve o anki GPU'ya göre değişir. Eğitim yalnız NVIDIA CUDA/bf16 ortamında çalışır; oturum kesilirse yerel denetim noktaları kaybolur, Drive'a son adaptör ancak kaydetme hücresinde yazılır.

## Sonraki deney (bağlam + ad/açıklama)

`sh colab/zip_sonraki.sh` ile `veri-sonraki.zip` oluşturup `egit_sonraki.ipynb` dosyasını Colab'da açın. Bu deney, assembly girdisine çağrılan fonksiyon bağlamını ekler ve modelden fonksiyon adıyla birlikte kısa bir açıklama üretmesini ister.

Veri, ana checkout'taki `veri/bin/olcek/` ve `veri/aciklama-v4/codex.jsonl` dosyalarından üretilir:

```bash
.venv/bin/python lora/hazirla_sonraki.py --cikti lora/veri-sonraki
```

Varsayılanlar: proje başına en çok 1.500 eğitim satırı, asm+bağlam için 2.500 token tavanı (notebook `MAX_UZUNLUK=3072`). 9 Ekim 2026 üretimi: train 131.588, valid 19.770, test 12.290 satır; test girdilerinin 7.211'inde bağlam var. Ana metrik `f1`, `taban.py` ile aynı puanlamayla önekli gerçek ada göre hesaplanır; `f1_oneksiz` hedefteki öneksiz ada göredir. `TEST_N=2000` varsayılanıyla test tohumlu bir alt kümede yapılır; tüm test için `None` verin.
