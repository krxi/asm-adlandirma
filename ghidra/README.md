# Ghidra entegrasyonu

`ad_ver.py`, seçili fonksiyonları; seçim yoksa adı `FUN_` ile başlayan en çok
`EN_COK` fonksiyonu OpenAI uyumlu bir modele yollar. Tahmini geçerli bir ada
çevirir, açıklamayı plate comment olarak ekler. Varsayılan kip kurudur: modeli
çağırır ama Ghidra veritabanını değiştirmez.

## Kurulum ve kullanım

1. `ad_ver.py` ile `bicim.py` dosyalarını aynı Ghidra script dizinine koyun ve
   Script Manager'da dizini ekleyin. PyGhidra/Python 3 önerilir; kod eski
   Jython 2.7 ile de uyumlu tutulmuştur.
2. `ad_ver.py` başındaki `SUNUCU` ve `MODEL` ayarlarını değiştirin. Varsayılan
   sunucu `http://127.0.0.1:8080/v1` adresindeki `mlx_lm.server`'dır. Sunucu
   anahtar istiyorsa yalnız ortamda `OPENAI_API_KEY` tanımlayın; betik dosya
   veya `.env` okumaz.
3. Binary'yi analiz ettikten sonra isteğe bağlı bir adres aralığı seçip betiği
   çalıştırın. Seçim yoksa yalnız `FUN_...` fonksiyonları ele alınır.
4. Sonucu gördükten sonra `KURU_CALIS = False` yaparak yeniden çalıştırın.

Başta düzenlenebilen `EN_COK` ve `BAGLAM` seçeneklerine ek olarak headless
çalıştırmada şu argümanlar kullanılabilir:

```text
--kuru | --uygula
--en-cok 10
--baglam | --baglamsiz
```

`--baglam`, çağrılan iç fonksiyonların `cikar.py` biçimindeki kısa özetlerini
assembly'nin sonuna ekler. Yalnız x86-64 desteklenir. Dolaylı çağrılarda hedef
Ghidra analizi tarafından çözülememişse import/iç fonksiyon adı da çözülemez.

Ghidra gerektirmeyen testler depo kökünden çalışır:

```bash
python3 -m unittest discover -s ghidra -p 'test_*.py'
```

## Ghidra 12 (PyGhidra) ile deneme

Ghidra 12'de Jython yok; betik PyGhidra ile çalışır. Ghidra'nın kendi wheel'lerinden ayrı bir venv:

```bash
python3.12 -m venv ~/ghidra-venv
~/ghidra-venv/bin/pip install --no-index --find-links <ghidra>/Ghidra/Features/PyGhidra/pypkg/dist pyghidra
source ~/ghidra-venv/bin/activate
.venv/bin/python -m mlx_lm server --model mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit --adapter-path lora/adaptor-15b-v3 &
<ghidra>/support/pyghidraRun --headless /tmp proje -import libtomlc17.dylib -deleteProject \
  -scriptPath ghidra -postScript ad_ver.py --kuru --baglam --istem=lora-ad \
  --model=mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit --en-cok 100
```

`--istem=lora` (ad + açıklama, v4) ve `--istem=lora-ad` (yalnız ad, v3) LoRA'nın eğitildiği istemi birebir kullanır;
varsayılan `taban` büyük modeller içindir. `--model=` sunucuya hangi modelin sorulacağını seçer.

İlk deneme (tomlc17, eğitimde görülmemiş test projesi, `-O2`, `strip -x`, 1.5B LoRA v3'ün 750. adım kaydı):
67 `FUN_` parçası; `pool_destroy`, `pool_alloc`, `tab_find` tam isabet. Parçaların çoğu `-O2`'nin ayırdığı
`.cold` dallarıdır (assert kolları); model bunlara ana fonksiyonun ya da `assert_rtn` adını veriyor.
22 parçada ad yerine girdideki `sub_XXXX` yer tutucusunu kopyaladı (erken kayıt).
