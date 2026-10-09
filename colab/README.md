# Colab — v5 eğitim

Emin için: `egit_sonraki.ipynb` dosyasını Colab'da aç, **A100** çalışma zamanı seç.
Varsayılan **Qwen/Qwen3.5-9B**, bf16 LoRA; mikro batch 1 ve gradient checkpointing
A100 belleği için açık. `MODEL` değişkenini `Qwen/Qwen3-8B` yaparak model değiştir.
Belleğe göre otomatik seçim veya 4-bit niceleme yok.

1. Hugging Face'te private model reposu ve bu repoya yazabilen write token oluştur.
   Colab'ın anahtar simgesinden `HF_TOKEN` secret'ını ekle; notebook erişimini aç.
   Tokenı hücreye yazma. `HF_REPO` ortam değişkenini kendi repo kimliğine ayarla.
2. Ayar hücresini çalıştırıp Drive'ı bağla. İlk koşu `MAX_ADIM=20`, `DEVAM=0`.
   20 adım + valid'den 10 üretim/ayrıştırma + token varsa tek HF checkpoint yüklemesi
   yapılır. Logdaki **HF yedeği doğrulandı** mesajını kontrol et.
3. Tam koşu için `MAX_ADIM=0`. HF token yoksa veya private repo doğrulanamazsa tam
   eğitim başlamaz. Model değiştirirken **HF_REPO**, **ASM_KOK** ve **DRIVE_KOK**
   değerlerini de ayrı koşuya yönelt. Notebook hücrelerini değiştirdiğinde mevcut
   ortam değişkenlerini de güncelle (`setdefault` daha önceki değeri değiştirmez).
4. Kesilmeden sonra aynı veri/model/paketler/mikro batch ile `DEVAM=1` ve
   `MAX_ADIM=0`: HF `son/` + `durum/son/` indirilir; optimizer/scheduler/RNG ve adım
   sürdürülür. Tamamlanmış test dosyaları geri alınır ve yeniden ölçülmez.
5. Adaptör zip'i, JSONL sonuçları ve log son hücredeki düğmelerden indirilebilir.
   Drive'a **her checkpoint'te**, ayrıca final sonuçlarında yazılır;
   varsayılan yol `MyDrive/asm-adlandirma-v5/<model>/`.

İki notebook'un eğitim motoru aynıdır ve testte eşitliği denetlenir:
r16, alpha32, all-linear, dropout .05; lr 1e-4 cosine, %3 warmup, etkin batch 16,
1 epoch, tüm train, 3072 token, tohum 7, yalnız assistant JSON kaybı.
`VERI_URL` varsayılanı
`https://github.com/krxi/asm-adlandirma-veri/releases/download/v5/veri-v5.zip`.
Ayrıntılı dosya düzeni, kayıt/yeniden deneme kuralları ve ölçümler
[molab açıklamasında](../molab/README.md).

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

95k satır/1 epoch: **5.938 adım**. A100/9B için henüz ölçülmemiş kaba planlama
aralığı **12–24 saat**; 20 adımlık denemeyle güncelle. Qwen3.5 lineer attention
hızlı kernel'leri bulunmazsa PyTorch yolu çok yavaş olabilir; A100 40 GB'da
uzun örnekler bellek sınırına yaklaşabilir. Gerekirse daha büyük GPU seç.
160 token üretim tavanında JSON kesilebilir; geçerli JSON oranı bunu görünür kılar.
Oturum kapanması ve ağ/Drive hataları nedeniyle henüz yüklenmemiş adımlar kaybolabilir.

Eski `egit.ipynb` ve zip betikleri v5 akışının parçası değildir.
