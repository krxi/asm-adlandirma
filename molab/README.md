# molab — v6 eğitim

Emin için: RTX PRO 6000 96 GB üzerinde `egit.py` marimo notebook'unu aç.
Varsayılan Qwen3-8B, bf16 LoRA (niceleme yok), r16/alpha32/all-linear/dropout .05;
lr 1e-4, cosine, %3 warmup, etkin batch 16, 1 epoch, 3072 token ve tohum 7.
Mikro batch 2, gradient checkpointing kapalı; model belleğe göre değiştirilmez.
Varsayılan `VERI_SURUM=v6`dır. Eski koşuyu aynı düzenle yeniden üretmek için
başlamadan önce `VERI_SURUM=v5` ayarla; veri URL'si, HF repo varsayılanı ve yerel
çalışma dizini buna göre birlikte v5'e döner.

1. Hugging Face'te **private model repository** oluştur (`v6` varsayılanı
   `krxi123/asmsense-lora-v6`). Bu repoya yazabilen fine-grained write tokenı
   yalnız notebook formundaki parola alanına gir. Tokenı koda, dosyaya,
   README'ye veya ekran çıktısına yazma. Gerekirse `HF_REPO` ile repo kimliğini değiştir.
2. Önce `MAX_ADIM=20`, `DEVAM=0` ile notebook'u çalıştır. Model/veri yüklenir,
   20 optimizer adımı koşar; valid_300'ün ilk 10 satırında loss ve greedy üretim
   ölçülür. Token varsa bir checkpoint yüklemesi yapılır. Logdaki **HF yedeği
   doğrulandı** kaydını ve repodaki `duman/<zaman>/` dosyalarını kontrol et.
3. Tam eğitim için `MAX_ADIM=0`, `DEVAM=0` yap. `HF_TOKEN` olmadan tam eğitim
   başlamaz. Repo private değilse veya erişim doğrulanamazsa da başlamaz.
   Duman koşusu tam koşunun kayıtlarını ezmez. Farklı modeller için farklı repo kullan.
4. Oturum kesilince aynı `MODEL`, `HF_REPO`, veri, paket sürümleri ve mikro batch
   ayarlarıyla yeni molab oturumu aç; formda **devam** kipini seç. `son/` adaptörü
   ve `durum/son/` içindeki optimizer, scheduler, RNG ve Trainer adımı birlikte
   geri yüklenir. `kosu.json` veri karması ile tüm ayarları doğrular; eksik durum
   veya farklı veri/ayar sessizce yeni koşuya çevrilmez. Yeni oturumda benzersiz
   `ASM_KOK` normaldir; devam kaynağı private HF reposudur.
5. Sonda adaptör zip'ini, sonuç JSONL'larını ve logu notebook indirme düğmelerinden al.

`VERI_URL` v6 varsayılanı
`https://github.com/krxi/asmsense-data/releases/download/v6/veri-v6.zip`.
Arşivde train, valid, valid_300, test, test_sabit, eval115 JSONL'ları ve ozet.json
birlikte bulunmalı; v6 değerlendirmesi aynı arşivdeki decompile'lı test_sabit ve
eval115 girdilerini kullanır. `ASM_KOK` yerel çalışma dizinini belirler. Aynı dizinde eski
koşu varsa devam et veya yeni dizin kullan. Train satırı sessizce atılmaz:
3072 tokenı aşan örnek, veri/tokenizer uyumunu düzeltmek için açık hata verir.
Notebook aynı tam koşu sürerken **Başlat hücresini yeniden çalıştırma**; benzersiz
bir `ASM_KOK` ve ikinci bir eğitim süreci oluşturabilir.

Her 500 adımda ve son adımda valid_300 loss, `taban.f1` tanımlı ham ad F1 ve
geçerli JSON oranı `olcum.jsonl`'a yazılır. En yüksek valid F1 seçilir
(eşitlikte önceki korunur); yalnız bu adaptörle test_sabit (2000) ve eval115
birer kez ölçülür. Başarıyla tamamlanıp HF'ye yazılmış test yeniden çalıştırılmaz.
Üretim greedy, `enable_thinking=False`, `max_new_tokens=160`; `token` girdi+yeni token sayısıdır.

HF düzeni: `adim-00500/`, `adim-01000/`, … ve `son/` yalnız
`adapter_model.safetensors` + `adapter_config.json` içerir. Tokenizer ve temel
model yüklenmez. `durum/son/` yalnız son devam durumudur; optimizer geçmişi için
ayrı klasörler biriktirilmez (HF commit geçmişi eski nesneleri yine tutabilir).
Adaptör/durum/ölçümler tek atomik `upload_folder` commit'iyle güncellenir.
Yükleme üç kez denenir; başarısız paket silinmez, sonraki checkpoint'te ve sonda
tekrar denenir. Son uyarı kalırsa oturumu kapatmadan `hf-kuyruk/` klasörünü indir;
ağ kesintisi boyunca henüz uzak yedeği olmayan adımlar risk altındadır.

Paketleme kararı: **group_by_length**. Standart SDPA'da yalnız position_ids
sıfırlamak örnekler arası attention izolasyonu için yeterli kabul edilmedi;
Qwen3.5'in lineer attention durumunun da sınırda sıfırlanması gerekir. Bu nedenle
DataCollatorWithFlattening kullanılmaz. Ortak ham metin uzunluğu ile tohumlu
800 satırlık pencereler gruplanır; Trainer bunları sırayla tüketir. Böylece iki
model tokenizer/mikro batch farkına rağmen her adımda aynı 16 örneği görür.
Donanım ve dropout nedeniyle sayısal birebirlik beklenmez.

95.000 satırda **5.938 optimizer adımı** (son batch kısmi), 11 ara + 1 son ölçüm.
v5 koşusu 3–4,5 sn/adım ve toplam yaklaşık 9,5 saat sürdü. Güncel %6,78 train
decompile kapsamı tam sohbet ortalamasını 1.036,7'den 1.091,9 tokene
(**1,053×**), p99'u 2.755'ten 2.988'e çıkardı. Decompile başına gözlenen artışı
tam kapsama doğrusal yayma tahmini ortalama **1.438,9 token (1,388×)** ve
p99 **yaklaşık 3.071–3.072** verir. Aynı oranla toplam süre yaklaşık **13,2 saat**;
4,2–6,2 sn/adım aralığı beklenir. Bu 12 saat sınırını aştığı için tam koşuyu iki
oturum planla ve ikinci oturumda yukarıdaki **devam** kipini kullan. Attention,
padding ve ölçüm süreleri doğrusal olmadığından duman koşusu en güvenilir son kontroldür.
