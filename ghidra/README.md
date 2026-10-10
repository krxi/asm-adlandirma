# Ghidra entegrasyonu

`ad_ver.py`, seçili x86-64 fonksiyonlarını; seçim yoksa `FUN_` adlı en çok
`EN_COK` fonksiyonu OpenAI uyumlu sunucuya sorar. Varsayılan **kuru kip** model
çağrısı yapar, veritabanına yazmaz.

## Kullanım

`ad_ver.py`, `bicim.py` ve `uygulama.py` aynı Script Manager dizininde olmalı.
Betikteki `SUNUCU` ve `MODEL` değerlerini yerel sunucuya göre ayarlayın.
Kimlik bilgilerini betiğe yazmayın. Önce atılabilir bir projede kuru çalıştırın:

```text
--kuru --en-cok 2 --baglam --istem=sonraki
```

Sonuçları kontrol ettikten sonra `--uygula` kullanın. `YORUM_HEDEFI`:
`ikisi`, `plate` veya `fonksiyon`. Eski LoRA kipleri `lora` ve `lora-ad`;
`taban` genel model istemidir. Bu betik mevcut v6 eğitim hattının yerine geçmez.
`GIRDI_KARAKTER_TAVANI` yaklaşık karakter sınırıdır; token garantisi değildir.

## Yazma ve geri alma

Ad ve yorum aynı transaction içinde yazılır. Aynı sonuç yeniden yazılmaz.
Yalnız `DuplicateNameException` tam 64 bit adres sonekiyle yeniden denenir.
Her model yorum satırı `[asmsense] ` taşır; analist metni ve satır sonları korunur.
Boş model açıklaması mevcut yorumu silmez. Yazma hatası veya iptal işleminde
rollback yapılır ve betik durur. İç içe Ghidra transaction'ları bağımsız
olmadığından **fonksiyon başına ayrı Undo adımı garanti edilmez**.
Betik otomatik kaydetmez ve Undo geçmişini temizlemez.

Dayanaklar: [adlandırma API'si](https://ghidra.re/ghidra_docs/api/ghidra/program/model/listing/Function.html#setName(java.lang.String,ghidra.program.model.symbol.SourceType)),
[transaction sözleşmesi](https://ghidra.re/ghidra_docs/api/ghidra/framework/model/DomainObject.html#endTransaction(int,boolean)).

## Otomatik testler

```sh
python3 -m pytest -q
python3 -m unittest discover -s ghidra -p 'test_*.py'
```

Normal CI Ghidra yüklemez. Birim testleri sahte program nesnelerini kullanır;
CI'daki macOS link/strip testi de gerçek Ghidra duman testi değildir.

## Elle koşulan isteğe bağlı gerçek Ghidra duman testi

**Bu test CI'da koşmaz; elle koşulan isteğe bağlı bir testtir.**
Linux x86-64, gcc/binutils, JDK 21 ve Ghidra 12.0/PyGhidra 3 ayrı ortamda gerekir.
Ghidra kurulum yolunu `GHIDRA_INSTALL_DIR`, JDK yolunu `JAVA_HOME` ile belirtin.
Ayrı ortamda Ghidra dağıtımındaki PyGhidra wheel'lerini kurduktan sonra:

```sh
python3 ghidra/duman_uygulama.py \
  --ghidra-kurulum "$GHIDRA_INSTALL_DIR" --cikti ghidra-duman-sonuc.json
```

Betik kendi sentetik C kaynağını derler, strip uygular ve geçici ProgramDB açar.
Mevcut proje/benchmark girdisi kabul etmez. Yazma, tekrar çalıştırma, Undo/Redo,
hata ve iptal rollback'i denetlenir; geçici proje otomatik temizlenir.
Model sunucusu ve GUI akışı bu testin kapsamı dışındadır.
Bu belge düzeltmesinde gerçek duman testi yeniden çalıştırılmadı (`not run`).
Kaynak kimlikleri ve kapsam [GHIDRA_KANIT.json](../rapor/arastirma/GHIDRA_KANIT.json) içindedir.
