# Yol haritası

Tarih: 11 Ekim 2026 · main `cb26709` sonrası. Bu belge sıradaki işleri, her işin çıkış ölçütünü ve
karar kurallarını sabitler. Olasılıklar ya repodaki verilerden hesaplandı (yöntemi yanında) ya da
öznel önseldir (öyle işaretli). Yeni bir sonuç geldiğinde ilgili satır güncellenir; geçmiş satırlar silinmez.

## Bugünkü durum

| Alan | Durum |
|---|---|
| Küçük model | Qwen3-8B + LoRA v5: test2000 ad F1 0,124 (snkv dışı 0,132), eval115 0,155 |
| Büyük model | mimo + çağrı bağlamı 0,167 (snkv dışı 0,190); + decompile 0,192 (0,214) |
| Fark | v5 − mimo+bağlam −0,044 [−0,076; −0,021]; snkv dışı −0,058 [−0,082; −0,033] |
| Veri bütünlüğü | Bölümler ayrık; snkv ⊃ sqlite istisnası açıklandı ([V6_VERI_DENETIMI.md](arastirma/V6_VERI_DENETIMI.md)) |
| v6 | Veri yayımlandı ve denetlendi; eğitim koşulmadı (≈13 saat GPU) |
| Altyapı | CI yeşil; doğrudan push'ta yeni dosyalar da lint'leniyor; release künyesi ve atıf dosyaları hazır |

## Fazlar

| Faz | İş | Çıkış ölçütü | Durum |
|---|---|---|---|
| F0 | Altyapı ve bütünlük | CI yeşil, v6 verisi denetlendi, README'de istisna açıklandı | tamam |
| F1 | v6 tam eğitimi (`molab/egit.py`, `VERI_SURUM=v6`) | `olcum_v6.py rapor` çıktısı; valid_300 farkı gömülü-ad satırları hariç ayrıca raporlandı | sırada |
| F2 | MSR 2027 Data & Tool Showcase (özet 5 Kasım, makale 10 Kasım AoE) | Taslak [`makale/msr2027`](../makale/msr2027) gönderildi; Zenodo DOI alındı | taslak hazır |
| F3 | Mühürlü v7 testi | ≥15 proje, Qwen3 çıkışından (Nisan 2025) sonra açılmış, ≤200 yıldız; liste hash'i ölçümden önce commit'lendi; nihai modeller bir kez ölçüldü | açılmadı |
| F4 | Yöntem makalesi (koşullu) | Yalnız BAR 2027 çağrısı 15 Aralık'a kadar çıkarsa; yoksa DIMVA veya ICSE çalıştayları | koşula bağlı |
| F5 | Bakım | README son durum, release'ler DOI'li, açık PR yok | sonda |

`lora/v6_dogrulama.py` (eşit bütçeli asm/combined pilotu) F1'in yerine geçmez. Tam v6 − v5 koşusu aynı
soruyu satır satır hizalı veride yanıtlar; pilot ancak iki ikili kanıt hash'i sabitlendikten sonra çalışır.

## Karar kuralları

| Koşul | Karar |
|---|---|
| v6 valid_300 (gömülü-ad satırları hariç) ≥ v5 + 0,010 | Decompile v7'de kalır |
| Aynı fark < +0,005 | Decompile bırakılır; hedef ve açıklama kalitesine dönülür |
| 1 Kasım'da MSR taslağı gönderilebilir durumda değil | MSR bırakılır; arXiv + F4 |
| v6 test2000 ≥ 0,14 | Sonuç başlıkta; değilse v6 nötr ablasyon olarak raporlanır |
| 15 Aralık'ta BAR 2027 çağrısı yok | F4 yedek venue'ya kayar |
| Yeni araç/protokol fikri, F1 sonucu gelmeden | Bekletilir; önce ölçüm |

## Olasılıklar

| Olay | Olasılık | Dayanak |
|---|---|---|
| v6 − v5 eşli fark proje-kümeli %95 GA'da sıfırı dışlar | 0,62–0,76 | Ölçülen: v5 − v1 eşli farkının proje-kümeli SE'si 0,0054 (test2000, 4.000 çekim), anlamlılık eşiği ≈ +0,011. Önsel kazanç: büyük modelde decompile göreli +%15; küçük modele %11 (alt sınır) ile %15 (üst sınır) aktarıldı, belirsizlik ±0,010 |
| v6 test2000 ≥ 0,14 | 0,42–0,60 | Aynı önsel |
| 6 ay içinde küçük model ≥ 0,167 (mimo + bağlam) | 0,09–0,15 | Öznel kalem kazanımları (decompile, tüm veri/2 epoch, 9B taban, alttan-yukarı adlar; RL eklenirse üst sınır), azalan getiri katsayısı 0,7 |
| Mart 2027'ye kadar ≥1 hakemli kabul (MSR, sonra koşullu BAR) | ≈0,46 | Öznel: MSR kabul 0,40 (oran yayımlanmıyor; yılda 22–32 kabul), BAR çağrısı 0,70, BAR kabul 0,38 (yılda 8–10 kabul) |

Sonuç: "küçük model büyük modeli yakalar" iddiası önümüzdeki 6 ayda düşük olasılıklı. Yayınlar
ezbere dayanıklı benchmark, denetlenmiş veri ve dürüst küçük-model taban çizgisi üzerine kurulur.

## Yeniden üretim açıkları

- v4'ün 473 projelik aday listesi (url, commit, rol) git'te yok (`.notlar/aday-projeler.json`); F2 öncesi
  commit'lenmeli. HF'deki kaynak tablosunda url ve rol eksik.
- Mühürlü test (F3) olmadan bütün sonuçlar "geliştirmede kullanılmış ölçüt" etiketi taşır.
