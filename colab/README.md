# Colab — v6 eğitim (molab yedeği)

`egit_sonraki.ipynb` molab arızalanırsa koşu liderinin seçtiği **yedek** akıştır;
molab çalışırken ikinci tam eğitimi aynı HF reposuna başlatma. Notebook'u Colab'da
açıp **A100** çalışma zamanı seç. Varsayılan **Qwen/Qwen3-8B**, bf16 LoRA,
mikro batch 2 ve gradient checkpointing kapalı: molab v6 ile aynı ayarlar.
Belleğe göre otomatik model seçimi veya 4-bit niceleme yok.

1. Varsayılan HF model reposu `krxi123/asmsense-lora-v6`dır; repo private olmalı.
   Colab'ın anahtar simgesinden bu repoya yazabilen `HF_TOKEN` secret'ını ekle;
   notebook erişimini aç. Tokenı hücreye yazma. Ayrı koşu/model için `HF_REPO` değiştir.
2. Ayar hücresini çalıştırıp Drive'ı bağla. İlk koşu `MAX_ADIM=20`, `DEVAM=0`.
   20 adım + valid'den 10 üretim/ayrıştırma + token varsa tek HF checkpoint yüklemesi
   yapılır. Logdaki **HF yedeği doğrulandı** mesajını kontrol et.
3. Tam koşu için `MAX_ADIM=0`. HF token yoksa veya private repo doğrulanamazsa tam
   eğitim başlamaz. Model değiştirirken **HF_REPO**, **ASM_KOK** ve **DRIVE_KOK**
   değerlerini de ayrı koşuya yönelt. Notebook hücrelerini değiştirdiğinde mevcut
   ortam değişkenlerini de güncelle (`setdefault` daha önceki değeri değiştirmez).
4. Kesilmeden sonra aynı veri sürümü/model/paketler/mikro batch/gradient checkpointing
   ile `DEVAM=1` ve `MAX_ADIM=0`: HF `son/` + `durum/son/` indirilir;
   optimizer/scheduler/RNG ve adım sürdürülür. Molab'dan Colab'a geçişte de aynı
   private HF reposunu kullan; `kosu.json` uyumsuz veri/ayar/paketleri açık hatayla
   reddeder. Tamamlanmış test dosyaları geri alınır ve yeniden ölçülmez.
5. Adaptör zip'i, JSONL sonuçları ve log son hücredeki düğmelerden indirilebilir.
   Drive'a **her checkpoint'te**, ayrıca final sonuçlarında yazılır;
   varsayılan yol `MyDrive/asm-adlandirma-v6/Qwen3-8B/`.

Molab ve Colab eğitim motoru aynı çevrimdışı kopyadır; AST eşitliğini testler korur:
r16, alpha32, all-linear, dropout .05; lr 1e-4 cosine, %3 warmup, etkin batch 16,
1 epoch, tüm train, 3072 token, tohum 7, yalnız assistant JSON kaybı.
`VERI_SURUM=v6`; `VERI_URL` varsayılanı
`https://github.com/krxi/asmsense-data/releases/download/v6/veri-v6.zip`.
Decompile'lı test_sabit ve eval115 de aynı arşivden alınır; sürüm ve decompile
metadata'sı doğrulanır. v5'i yeniden üretmek için yeni ortamda `VERI_SURUM=v5`
ayarla; HF repo ve yerel/Drive yolları sürümden türetilir. Mevcut ortamda önceden
ayarlanmış değişkenleri de değiştir (`setdefault` eski değeri korur).
Ayrıntılı dosya düzeni, kayıt/yeniden deneme kuralları ve ölçümler
[molab açıklamasında](../molab/README.md).

Alternatif `MODEL=Qwen/Qwen3.5-9B` için ayrı HF repo ve çalışma/Drive yolları kullan.
Bu model değişikliği mevcut Qwen3-8B koşusunu devam ettiremez.

Qwen3.5-9B'nin [resmi config'i](https://huggingface.co/Qwen/Qwen3.5-9B/blob/main/config.json)
9 Ekim 2026'da ağdan doğrulandı: `Qwen3_5ForConditionalGeneration`,
`qwen3_5_text`, 32 katman, 3:1 lineer/full attention.
[Transformers metin modeli](https://huggingface.co/docs/transformers/model_doc/qwen3_5)
`Qwen3_5ForCausalLM` ile yüklenir; görsel gövde eğitilmez. Notebook
`model.named_modules()` üzerinden lineer modül türlerini yazdırır;
`all-linear` ile bütün metin lineer katmanlarının LoRA aldığını ve eksik model
ağırlığı olmadığını doğrular. Kurulum Transformers 5.3.0 / PEFT 0.18.1 kullanır;
paketler önceden import edildiyse kurulumdan sonra çalışma zamanını yeniden başlat.

**Paketleme: group_by_length.** Hibrit katmanlarda örnek sınırında durum sıfırlaması
kanıtlanmadığından flattening kullanılmaz. Molab ile aynı ham metin uzunluğu,
tohum ve sıralama kullanılır: aynı optimizer adımı aynı 16 satırı görür.
3072 token taşması sessiz veri kaybına yol açmaz, açık hata verir.

95k satır/1 epoch: **5.938 adım**. v6 daha uzun decompile girdileri içerir;
A100 süre/bellek gereksinimi burada henüz ölçülmedi. Yeni koşuda 20 adımlık
duman denemesiyle ölç. OOM durumunda farklı mikro batch veya `GRAD_CKPT=1`
yalnız ayrı yeni koşu olarak kullanılabilir; mevcut molab kaydının ayarları
değiştirilerek devam edilemez. Qwen3.5 alternatifinde hızlı lineer attention
kernel'leri bulunmazsa PyTorch yolu çok yavaş olabilir.
160 token üretim tavanında JSON kesilebilir; geçerli JSON oranı bunu görünür kılar.
Oturum kapanması ve ağ/Drive hataları nedeniyle henüz yüklenmemiş adımlar kaybolabilir.

Eski `egit.ipynb` ve zip betikleri v6 akışının parçası değildir.
