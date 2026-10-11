# MSR 2027 Data and Tool Showcase taslağı

Son tarihler (AoE): özet 5 Kasım 2026, makale 10 Kasım 2026. Sınır: 4 sayfa + 1 sayfa kaynak, IEEE
biçimi, tek-taraflı kör hakemlik. Kabulde en az bir yazar kayıt yaptırıp sunmak zorunda; kamera-hazırda
verinin DOI'si gerekir.

```sh
tectonic main.tex          # veya: pdflatex main && bibtex main && pdflatex main && pdflatex main
```

Bugünkü taslak 3 sayfa (kaynaklar dahil); bir şekil veya v6 satırı için yer var.

## Göndermeden önce

- [ ] Yazar adı, kurum ve e-posta (`main.tex` başı)
- [ ] Zenodo DOI (`asmsense-data` için entegrasyonu aç, yeni release yayımla) ve metindeki `DOI: TODO`
- [x] `refs.bib`: BLens ve SymGen kayıtlarını birincil konferans kaynaklarından doğrula
- [ ] v6 sonucu geldiyse Tablo III'e satır ekle (`olcum_v6.py rapor`)
- [ ] Metni kendi sesinle revize et; sayıları değiştirme, kaynakları aşağıda
- [ ] İsteğe bağlı şekil: `grafik/x-ezber.png` (ezber karşılaştırması) veya `grafik/test-hata.png`

## Sayıların kaynağı

| Metindeki sayı | Kaynak |
|---|---|
| Veri boyutu ve bölmeler | README "Scaled dataset (v4 pipeline)" |
| Ezber tablosu | README bölüm 2 |
| test2000 taban çizgileri ve snkv dışı sütun | `sonuc/test2000-*.jsonl`, `rapor/arastirma/V6_VERI_DENETIMI.md` |
| v5 − v1 aralığı (+0,010 … +0,031) | proje-kümeli bootstrap, `aciklama_degerlendir.bootstrap_farki`, 4.000 çekim, tohum 42 |
| Açıklama kalitesi | README bölüm 6 (`aciklama_puan_v5.py`) |
| Decompile kazancı | README bölüm 7 |
