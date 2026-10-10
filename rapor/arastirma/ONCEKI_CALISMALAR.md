# Stripped binary fonksiyon adı ve açıklaması: kaynak haritası

Kod referansı: [main `15e3b28f1be387d0e8655edd838e1c32f9d348d5`](https://github.com/krxi/asmsense/tree/15e3b28f1be387d0e8655edd838e1c32f9d348d5),
tree `6f8d4781522bc7be45839071dc7231e12d0164e5`.
Bu belge yeni model sonucu üretmez. Literatür değerleri yazar bildirimidir;
bağımsız yeniden eğitim/değerlendirme **not run**, doğrulanamayan alanlar
**unverified**. Kod lisansı veri veya ağırlık lisansı yerine geçmez.

## Mevcut durum: karşılanmış gereksinimler ve kalan boşluklar

**İlk iş mevcut v6 hattını değerlendir; yeni bir veri hattı kurma.**
Aşağıdakiler artık önerilecek eksik özellikler değil, ana depoda bulunan
bileşenlerdir. Kanıt, her satırdaki sabit kod bağlantısıdır.

| Main'de karşılanan gereksinim | Halka açık kod ve kalan sınır |
|---|---|
| V6 eğitim girdisi hazırlama | [`lora/hazirla_sonraki.py --surum v6`](https://github.com/krxi/asmsense/blob/15e3b28f1be387d0e8655edd838e1c32f9d348d5/lora/hazirla_sonraki.py): decompile ekleme, proje-içi ad anonimleştirme ve ham/öneksiz hedef sızıntısı denetimi. Aynı işi pilot içinde ikinci kez uygulama. |
| Eğitim veri sürümü seçimi | [`molab/egit.py`, `VERI_SURUM`](https://github.com/krxi/asmsense/blob/15e3b28f1be387d0e8655edd838e1c32f9d348d5/molab/egit.py): v6 veri seçimi mevcut. Tam eğitim yolunun sonundaki test değerlendirmesi nedeniyle kontrolsüz validation pilotu yerine kullanılmamalı. |
| Ghidra çıkarımı | [`decompile_ghidra.py`](https://github.com/krxi/asmsense/blob/15e3b28f1be387d0e8655edd838e1c32f9d348d5/decompile_ghidra.py): mevcut çıktı ve anonimleştirme sözleşmesi kullanılmalı. İnsan tarafından doğrulanmış semantik doğruluk bundan otomatik çıkmaz. |
| İkili/assembly kimlik eşlemesi | [`dogrula_v6.py`](https://github.com/krxi/asmsense/blob/15e3b28f1be387d0e8655edd838e1c32f9d348d5/dogrula_v6.py): hazır kimlikler ve proje bazlı kapsam raporu mevcut. Başarı çıkış kodu, bütün hedeflerin eşleştiğini tek başına kanıtlamaz; eşleşen ID listesi ve sayaçlar incelenmeli. |
| Derleme/ölçekleme orkestrasyonu | [`olcekle.py`](https://github.com/krxi/asmsense/blob/15e3b28f1be387d0e8655edd838e1c32f9d348d5/olcekle.py), [v4 protokolü](https://github.com/krxi/asmsense/blob/15e3b28f1be387d0e8655edd838e1c32f9d348d5/VERI_HATTI_V4.md): mevcut proje/bölme ve lisans sınırları korunmalı; araştırma için benchmark yeniden üretilmemeli. |

**Kalan boşluklar:** mevcut ana-hat çıktılarının beklenen hash ve eşleme
kanıtlarıyla sabitlenmesi; eşit bütçeli küçük-model assembly/combined
validation karşılaştırması; açıklama değerlendirmesinin insanlarla
kalibrasyonu; Ghidra'nın model servisi ve GUI ile uçtan uca doğrulanması.
Açık [#4](https://github.com/krxi/asmsense/pull/4),
[#5](https://github.com/krxi/asmsense/pull/5),
[#6](https://github.com/krxi/asmsense/pull/6),
[#7](https://github.com/krxi/asmsense/pull/7),
[#8](https://github.com/krxi/asmsense/pull/8) ve
[#9](https://github.com/krxi/asmsense/pull/9) bu boşlukların bir kısmına araç
sağlar; açık PR, main'de birleşmiş veya gerçek GPU'da ölçülmüş sonuç değildir.
#6 taslaktır; hazır olmayan kanıtlar **not run / unverified** kalır.

### Test2000: geliştirmede kullanılmış ölçüt

Mevcut sabit 2.000 satırlık testin sonuçları deney yönünü seçerken zaten
kullanılmıştır. `molab/egit.py` tam koşuların sonunda testi ölçer; önceki
araştırma planı ve [depo sonuçları](https://github.com/krxi/asmsense/blob/15e3b28f1be387d0e8655edd838e1c32f9d348d5/README.md)
da bu sonuçlardan hareket eder. Bu nedenle test2000 **geliştirmede kullanılmış
ölçüt** olarak adlandırılmalı, el değmemiş nihai holdout gibi sunulmamalıdır.
Proje-ayrıklığı bu adaptif kullanım veya temel modelin ön eğitim bulaşması
sorununu tek başına çözmez.

“Test yalnız bir kez, yalnız finalde” gerçekleşmiş bir özellik değildir.
**Geleceğe yönelik öneri:** aday/istem/checkpoint kararlarını validation'da
önceden tanımlı protokolle ver; dondurulmuş final yapılandırmayı mevcut
benchmark'ta ayrıca raporla, fakat bu raporu bağımsız temiz-test kanıtı diye
sunma. Gerçekten el değmemiş dış değerlendirme ancak ayrıca onaylanmış bir
çalışmayla mümkün olur; bu PR mevcut testin dosyalarını, kimliklerini veya
bölmelerini değiştirmez. Burada yeni test tahmini ya da test-altgrup analizi yoktur.

## Önceki çalışmalar: görev, veri, sonuç, erişim

Fonksiyon adı, değişken adı, açıklama benzerliği ve yeniden çalıştırılabilir
kaynak ayrı görevlerdir. Aşağıdaki F1 değerleri, açıkça belirtilmedikçe
`taban.f1` ile aynı ölçüt değildir. Proje-ayrık test de ön eğitimde
hiç görülmemişlik garantisi değildir. Tüm sonuçlar bağlantılı kaynaklara aittir.

| Çalışma / birincil kaynak | Görev, temsil, veri ve split | Bildirilen sonuç / karşılaştırma sınırı | Kod, ağırlık ve lisans |
|---|---|---|---|
| **DIRE**, [ASE 2019, arXiv:1909.09029](https://arxiv.org/pdf/1909.09029), §III/V, Table I | Değişken adı; Hex-Rays tokenları + AST/GGNN. 1.259.935 işlev; binary 80:10:10, proje ayrık değil. | Ad exact-match %74,3; eğitimde gövdesi olmayan altkümede %35,3. Fonksiyon adı sonucu değildir. | [Kod MIT](https://github.com/CMUSTRUDEL/DIRE/blob/master/LICENSE); [veri/model kaydı](https://zenodo.org/records/3403078), [model bağlantıları](https://github.com/pcyin/dire). Ayrı veri/ağırlık lisansı ve indirme bütünlüğü **unverified**. |
| **DIRTY**, [USENIX 2022](https://www.usenix.org/system/files/sec22-chen-qibin.pdf), §3.1, Tables 4/8 | Değişken adı/türü; decompile tokenları + veri yerleşimi. DIRT 75.656 binary; binary split, proje ayrıklığı **unverified**. | Tek-görev ad doğruluğu %66,4; unseen-body %36,9. Ortak model %65,1 ad / %74,9 tür; ayrı modellerin başlık sayıları birleştirilmez. | [Kod MIT ve model/veri bağlantıları](https://github.com/CMUSTRUDEL/DIRTY); [ham veri DOI](https://doi.org/10.1184/R1/20732656.v1). Ayrı veri/ağırlık lisansları **unverified**. |
| **NERO**, [OOPSLA 2020](https://yanivmd.github.io/files/Nero-Paper.pdf), §6, Table 2 | Fonksiyon subtokenu; çağrı argümanı değerleri + CFG. GNU/Linux x64, 67.246 örnek; proje/paket ayrımı ve aynı paketin sürümlerinin ayrılması beyan edilir. Near-clone bağımsızlığı **unverified**. | Stripped F1 %45,53; API adları da gizlenince %38,83. Sıra/tekrar/case-duyarsız subtokenu F1. | [Kod GPL-3.0](https://github.com/tech-srl/Nero/blob/main/LICENSE), [veri/model](https://zenodo.org/records/4099685). Ayrı veri/ağırlık lisansları **unverified**; MIT çekirdeğe kod kopyalanmaz. |
| **SymLM**, [CCS 2022](https://xinjin95.github.io/assets/pdf/SymLM_ccs2022_paper.pdf), §4–5, Table 4 | Fonksiyon adı; Ghidra ICFG, Trex, caller/callee. 16.027 binary / 1.431.169 işlev; binary 80:10:10, proje ayrık değil. | Ağırlıklı F1 0,655; CodeWordNet semantik eşleme içerir. Katı ad-token eşleşmesiyle doğrudan karşılaştırılamaz. | [Kod MIT](https://github.com/OSUSecLab/SymLM), [veri](https://zenodo.org/records/8306055). Trex/CodeWordNet bağlantısı son SymLM checkpoint'inin yayımlandığını kanıtlamaz; final ağırlık ve ayrı lisanslar **unverified**. |
| **XFL**, [S&P 2023, arXiv:2107.13404](https://arxiv.org/pdf/2107.13404), Table III | Fonksiyon adı etiketi; DEXTER + çağrı/binary bağlamı. Debian 10.047 binary / 741.724 işlev; binary 90:5:5, proje ayrıklığı yok. | 1.024 etiket uzayında micro F1 0,6809; precision 0,8345. Hedef sık eğitim etiketi uzayına projekte edilir; açık sözlüklü ad F1 değildir. | [Kod GPL-3.0](https://github.com/lmu-plai/xfl/blob/main/COPYING), [model kaydı](https://zenodo.org/records/10733597). Ayrı model/veri lisansı ve makale-artefakt sürüm eşdeğerliği **unverified**. |
| **VarBERT**, [S&P 2024](https://sefcom.asu.edu/publications/varbert-oakland24.pdf), Table 2 | Değişken adı/kökeni; kaynak ön eğitimi + IDA/Ghidra decompile. VarCorpus O2; function/binary 80:20, proje ayrık değil. | Ghidra top-1 ad: function-split %54,49, binary-split %40,49. Exact dedup, yakın kopyaları tamamen dışlamaz. | [Kod ve veri/ağırlık bağlantıları](https://github.com/sefcom/VarBERT); kod/veri/ağırlık lisansları **unverified**. |
| **ReSym**, [CCS 2024](https://www.cs.purdue.edu/homes/lintan/publications/resym-ccs24.pdf), Tables 2/5 | Değişken/yapı sembolleri; IDA, StarCoder3B, Prolog. Ana deney proje 95:5; ortak gövdeler tamamen atılmaz. | VarDecoder %56,4 ad / %64,6 tür; unseen-body %37,5 / %49,9. Yapı düzeni F1 %41,4 ayrı hedeftir. | [Kod BSD-3-Clause](https://github.com/lt-asset/resym/blob/main/LICENSE), [veri/checkpoint](https://zenodo.org/records/15161423). Ayrı veri/model lisansı ve StarCoder koşulları ayrıca incelenmeli; **unverified**. |
| **HexT5**, [ASE 2023 kaydı](https://conf.researchr.org/details/ase-2023/ase-2023-papers/96/HexT5-Unified-Pre-training-for-Stripped-Binary-Code-Information-Inference), [DOI](https://doi.org/10.1109/ASE56229.2023.00099) | Stripped pseudo-code üzerinde ad/özet/değişken/benzerlik görevleri. Özgün tam metin, n ve split doğrulaması **unverified**. | Başlık başarı sayısı ve özgün tablolar **unverified**; sonraki çalışmanın proje-split nitelemesi orijinal manifest kanıtı değildir. | [Inference kodu](https://github.com/USTC-TTCN/hext5), [ağırlık bağlantısı](https://zenodo.org/records/11393904). Eğitim/veri erişimi ve tüm ayrı lisanslar **unverified**. |
| **AsmDepictor**, [AsiaCCS 2023 DOI](https://doi.org/10.1145/3579856.3582823), [yazar README](https://github.com/agwaBom/AsmDepictor) | Assembly→fonksiyon adı, encoder–decoder. DS_N/DS_A; orijinal n/proje ayrımı **unverified**. | README'nin yayın sonrası güncellemesi F1 %80,85, Jaccard %81,63; özgün makale skoru, split ve n ile eşdeğerliği **unverified**. | Eğitim/inference kodu ve [veri/parametreler](https://zenodo.org/records/7978756) listelenmiş. Kod/veri/ağırlık lisansları **unverified**. |
| **BinT5 / CAPYBARA**, [SANER 2023, arXiv:2301.01701](https://arxiv.org/pdf/2301.01701), Tables I/II | CodeT5 özetleme; kaynak/sembollü/gerçek stripped/yapay anonim koşullar. 79.673 kaynak/decompile, 7.826 gerçek stripped örnek; proje 80:10:10. Test n **unverified**. | Gerçek stripped BLEU-4 11,26; sembollü decompile BLEU 58,82 stripped başarı diye taşınamaz. | Makaledeki artefakt bağlantıları esas alınmalı; bu kısaltılmış kayıtta kod/ağırlık/veri lisansları **unverified**. |
| **CP-BCS**, [EMNLP 2023](https://aclanthology.org/2023.emnlp-main.911.pdf), Tables 1/2/12 | Assembly + iki yönlü CFG + pseudo-code özetleme. 51 proje; x64-O2 train/val/test 11.949/1.494/1.493; split biriminin proje olması **unverified**. | x64-O2 BLEU: assembly 21,52, pseudo 22,37, tam 25,50. Bu gerçek çoklu-temsil ablasyonu, asmsense F1 kazancı değildir. | [Kod MIT ve veri klasörleri](https://github.com/tongye98/BinaryCodeSummary); hazır ağırlık ve verinin ayrı lisansı **unverified**. |
| **BinSum**, [arXiv:2312.09601](https://arxiv.org/pdf/2312.09601), §3–4 | Binary özetleme; bytes/assembly/IR/pseudo-code. 44 GNU proje, 557.664 çift; 1.000 örneklik istem seçiminin final ölçümle ayrıklığı **unverified**. | Embedding cosine: stripped decompile 0,202, assembly 0,188, IR 0,185. Ad F1 veya insan semantik doğruluğu değildir. | [Yazar repo](https://github.com/xinjin95/BinSum); code/data release ve lisanslar **unverified**; yeni görev ağırlığı doğrulanmadı. |
| **LLM4Decompile**, [EMNLP 2024](https://aclanthology.org/2024.emnlp-main.203/), [arXiv:2403.05286](https://arxiv.org/pdf/2403.05286), Tables 1/3 | Assembly→C ve Ghidra pseudo-code→iyileştirilmiş C. ExeBench eğitim; C HumanEval 164 problem ve ExeBench 5.000 test. Proje/ön eğitim bağımsızlığı **unverified**. | HumanEval re-executability End6.7B %45,37, Ref6.7B %52,74, Ref22B %64,18. Bu isim veya özet puanı değildir. | [Kod MIT](https://github.com/albertan017/LLM4Decompile/blob/main/LICENSE), [ayrı model lisansı](https://github.com/albertan017/LLM4Decompile/blob/main/LICENSE-MODEL); veri lisansı **unverified**. Hazır ağırlık bağlantıları repo içinde. |
| **ProRec**, [NeurIPS 2024, arXiv:2405.19581](https://arxiv.org/html/2405.19581), Table 1 | Assembly/bağımlılık grafiğinden sembollü bağlam; ayrı LLM ad/özet. 270k çift, 260k train/10k test; maliyet için 1k test. Proje ayrımı **unverified**. | Aynı 1k üzerinde SymLM-token F1 23,5 vs 17,2; asmsense katı protokolü sayılmaz. GPT4 functionality ayrı hakem ölçütüdür. | [Kod ve otomatik model/veri bağlantıları](https://github.com/ziansu/prorec); tüm ayrı lisanslar ve indirme bütünlüğü **unverified**. |
| **MiSum**, [FSE 2025](https://shangwenwang.github.io/files/FSE-25.pdf), Tables 3/6 | Niyetli özet; CFG + AST + heterojen grafik. Rastgele 8:1:1 örnek split; proje ayrık değil. x64 train/val/test 762.561/53.426/56.875. | ARM-O1 altı niyet BLEU-4 10,05; grafiksiz 4,98. Başka tablodaki toplam n, bu hücrenin n'si değildir. | [Makalenin bağladığı repo](https://github.com/Kobe-Zed/MiSum) kendini bağımsız reproduction diye tanımlıyor; özgün artefakt, weights ve lisanslar **unverified**. |
| **Decompile-Bench**, [2025, arXiv:2505.12668](https://arxiv.org/pdf/2505.12668), §3–5 | C/C++→binary eşleme; Clang19, DWARF/tree-sitter, MinHash. 3.961 repo / 2M çift; ayrıca yeni GitHub projeleri değerlendirmesi. Ön eğitim sonrasılık modele göre ayrıca incelenmeli. | 6.7B HumanEval re-executability %39,48; yeni GitHub bölümündeki readability/edit similarity farklı hedeftir. | [LLM4Decompile artefaktları](https://github.com/albertan017/LLM4Decompile); MIT kod, ayrı model koşulları. Her sürümün veri/model lisansı **unverified**. |
| **SemFlow**, [Cybersecurity 2026](https://link.springer.com/article/10.1186/s42400-026-00602-6), Tables 2/3 | Çağrı grafiğinde aşağıdan yukarı ad/özet; pseudo-code. SymGen 33 proje/9.842 binary; binary 8:1:1, proje ayrık değil. | Semantik F1 x64 0,420 vs 0,380; kontrollü 8B-O3 orta katman 0,357 vs 0,268. Doğrudan wrapper-kümesi veya katı F1 değildir. | Veri makul istek üzerine; açık kod/ağırlık ve lisanslar **unverified**. |
| **Hieronym**, [Eylül 2026 preprint, arXiv:2609.12457](https://arxiv.org/html/2609.12457), §5.6 | CodeLlama34B LoRA; Ghidra + domain/caller/callee. 9.842 binary/2.237.915 işlev; ana split kaynak-dosyası gruplu. Ek proje-ayrık değerlendirme mevcut, n **unverified**. | Ek cross-project ağırlıklı macro F1 0,4661 vs 0,3377; morfoloji/embedding eşanlam içerir. Katı `taban.f1` değildir. | [Kod ve adapter bağlantıları](https://github.com/NASP-THU/Hieronym); kod/veri/adapter lisansları **unverified**, temel CodeLlama lisansı ayrıca geçerli. |
| **REBench**, [Nisan 2026 preprint, arXiv:2604.27319](https://arxiv.org/html/2604.27319v1) | Ad/tür; normalize IDA/Ghidra. 96 proje, dört mimari/opt; 160k train/40k test; rastgele fonksiyon seçimi, proje ayrık değil. | Belirli model headline hücresi **unverified**; protokol kaynağı, asmsense SOTA iddiası değil. | [Kod](https://github.com/OSUSecLab/REBench), [veri](https://zenodo.org/records/19899116); ayrı lisanslar/ağırlık **unverified**. |
| **REFORGE**, [Temmuz 2026 preprint, arXiv:2607.07738](https://arxiv.org/abs/2607.07738) | Kontrollü C/ELF, DWARF/tree-sitter/Ghidra hizalama. Özgün n/proje split/ad F1 **unverified**. | Bildirilen hizalama verimi, ad F1 değildir; doğrulanmamış isim headline'ı taşınmıyor. | [Kod MIT ve release](https://github.com/NicolasKol/reforge); türev veri lisansları/ağırlık **unverified**. |
| **BinJudge**, [Ağustos 2026 preprint, arXiv:2608.07038](https://arxiv.org/abs/2608.07038) | Reference-free ad/özet/decompile hakemi ve insan kalibrasyonu. Tam n/split/korelasyon tanımı **unverified**. | Abstract sayıları özgün tablo/protokolle doğrulanmadığı için burada nicel kazanç aktarılmıyor. | Resmî kod/veri/weights ve lisanslar **unverified**. |

Grafik öncülleri ayrıca [Debin, CCS 2018](https://files.sri.inf.ethz.ch/website/papers/ccs18-debin.pdf)
([Apache-2.0 kod](https://github.com/eth-sri/debin)) ve
[Punstrip, ACSAC 2020](https://kclpure.kcl.ac.uk/ws/portalfiles/portal/138401574/desyl.pdf)
([kod aynası](https://github.com/punstrip/punstrip)) içindedir. Debug bilgisi
ve tam ad/semantik ölçütler fonksiyon token-F1'ı ile karıştırılmamalı; ayrı
veri/model lisansları **unverified**.

## Directly applicable to asmsense

Bu sıra fayda/hesap maliyeti için **mühendislik önceliğidir**, ölçülmüş veya
sayısal olarak tahmin edilmiş F1 kazancı değildir. Mevcut küçük modelin v6
kazancı henüz gösterilmedi; aşağıdaki beş aday bir doğrulama ailesi sayılır.

| Sıra | Deney ve hedef | Dayanak ve en ucuz sınanabilir adım |
|---|---|---|
| 1 | **Mevcut v6 hattını değerlendir.** String'siz/optimize işlev ve açıklama semantiği. | CP-BCS çoklu temsil ablasyonu; ana v6 hazırlayıcı ve eşleme doğrulayıcısının mevcut çıktıları. Önce kanıt/hash/uzunluk kapsamı, sonra eşit bütçeli iki kollu LoRA. Ana hattı baypas eden yeni anonimleştirici yok. |
| 2 | Dondurulmuş tahmini callee adı/özeti bağlamı. | NERO/SemFlow fonksiyonlar arası bağlam. Önce mevcut validation tahminlerinde doğrudan aktarım kontrolü; sonra en fazla bir ek context çıkarım turu. Kapsam/eksikcallee oranı ayrı. Test etiketli onarım tavanı karar gerekçesi değil. |
| 3 | Train-only öğretmen alanlarından kısa davranış hedefleri. | Hieronym/MiSum; işlem, girdi/çıktı, dönüş, yan etki. Mevcut etiketleri kullan; yeni büyük öğretmen çağrısı ve uzun chain-of-thought hedefi zorunlu değil. Aynı çıktı şeması korunur; insan rubriği ayrıca doğrulanır. |
| 4 | Dar argüman/veri-akışı özeti; sabit/maske ve bellek erişim örüntüsü. | NERO/ProRec. Önce CPU çıkarımı ve aynı checkpoint üzerinde validation ablasyonu. Çözülemeyen köken `unknown`; offset'ten gerçek yapı alanı adı uydurulmaz. Ağır GNN/LLVM bağımlılığı çekirdeğe eklenmez. |
| 5 | Train içindeki optimizasyon varyantlarının semantik hedef tutarlılığı. | Decompile-Bench/REFORGE eşleme kaygısı. Önce kaynak-gruplu envanter, sonra mevcut token/adım bütçesinde küçük pilot. Test veya validation kopyaları eğitime taşınmaz. |

Bütçe kaydı gerçek eğitim tokenı/adımı, saniye/adım, tepe bellek, çıkarım
sayısı ve decompile CPU süresidir. Ölçüm olmadan GPU-saat veya para tasarrufu
verilmez. Ana Molab yolu final test çalıştırdığından, sırf validation taraması
için kontrolsüz tam koşular başlatılmaz. #6 mevcut hazırlanmış ana-hat
çıktılarını kullanarak bu ayrımı dener; taslak ve GPU **not run** durumundadır.

## Küme bootstrap ve beş aday için kabul kuralı — önerilen protokol

Önce aynı validation kimlikleri, baseline, beş aday, bütçe, birincil kanonik
F1 ve asgari anlamlı fark dondurulur. Nokta tahmini yine aynı satırların
ortalama kanonik F1 farkıdır; scorer değiştirilmez.

**Birincil yeniden örnekleme birimi proje** olmalıdır. Her çekimde seçilen
projenin bütün kaynak işlevleri, onların bütün optimizasyon kopyaları ve
baseline/aday tahminleri **birlikte** taşınır. Beş adayda aynı çekimler
kullanılır. Satırları veya aynı kaynağın optimizasyonlarını bağımsız yeniden
örneklemek yasaktır. Kaynak-fonksiyon anahtarı `(proje, dosya, kaynak işlev)`
ile yapılan eşli küme bootstrap yalnız ikincil duyarlılık analizidir;
proje-içi ortaklık sürdüğü için proje sonucunun yerine geçmez. Dar opt
altkümeleri ve açıklama puanları önceden belirlenen ikincil tanılardır.

**Çoklu karşılaştırma düzeltmesi:** beş baseline–aday karşılaştırması için
Bonferroni ailesi önerilir: toplam alfa 0,05 / 5 = **0,01**. Her aday için
iki taraflı **%99** küme-bootstrap aralığı, 0,005 ve 0,995 kuantilleriyle
raporlanır; normal %95 aralıklar yalnız tanısal ek olabilir. Önceden sabit
20.000 eşli proje çekimi ve tohum 7 kullanılabilir. Düzeltme yalnız raporlanan
kazananlara değil, denenen beş adaya uygulanır. Kabul için düzeltilmiş alt
sınır sıfırın üstünde, nokta farkı önceden belirlenmiş pratik eşikten büyük
ve çıktı/karar kapsamı azalmamış olmalıdır. Açıklama değerlendirmesinde
`uydurma=var` ve bilinmeyen dahil risk artmamalıdır.

Bonferroni birlik sınırı geçerli tekil hata oranlarını varsayar; bootstrap
aralıkları yaklaşık olduğundan az proje, bağımlılık veya adaptif yeni aday
seçimi altında kesin sonlu-örneklem aile-hatası garantisi verilmez. Daha fazla
aday/tekrar denendiğinde aile baştan genişletilmeli veya ayrı bir onaylı
protokol kurulmalıdır; aynı validation sonuçlarına bakarak tekrar tekrar
%95 kapı açmak kabul edilmez. Bu öneri **çalıştırılmış bir kabul testi veya
gerçekleşmiş başarı değildir**.

## Açıklama ve metrik sınırları

Kısa gözlenebilir davranış hedefi, assembly'den çıkarılamayan “why” gerekçesi
uydurmaktan farklıdır. İnsanlar ana işlem, girdi/çıktı, yan etki ve uydurma
alanlarını kör değerlendirmelidir. Kaynakta olup optimizasyonda silinen
özellikler ayrıca işaretlenmeli; öğretmen kendi çıktısının bağımsız hakemi
sayılmamalıdır. Embedding cosine veya akıcılık semantik doğruluk değildir.

`taban.f1`, öneksiz F1 ve mevcut geniş `f1_es` korunur. Dar alias metriği (#5)
ek tanıdır; aynı tahmine esnek eşleme uygulamak model kazanımı değildir.
Önek temizleme semantik eşleme değildir. Alan/sözlük veya çıktı şeması
müdahalesi ayrı açık etki açıklaması gerektirir.

## Yeniden üretim ve sınırlar

```sh
python3 -m pytest -q
ruff check tests/test_arastirma_belgesi.py
ruff format --check tests/test_arastirma_belgesi.py
```

Belge regresyonları mevcut main dosyalarına yapılan atıfları, v6 önceliğini,
geliştirmede kullanılmış test tanımını ve küme/çoklu-karşılaştırma protokolünü
korur. **Tam pytest gerçek arşiv tahminlerini rapor regresyonu için de yeniden
puanlar**; yalnız sentetik diye sunulmaz. Yeni GPU eğitimi, model çıkarımı,
test-altgrup analizi veya insan puanlaması bu belge değişikliğinde **not run**.
Güncel halka açık commit/tree ve CI PR #2'de kayıtlıdır. Eski makineye özgü
çalışma günlüğü ve yerel commit kayıtları çıkarılmıştır. Yeni kod/özet özgün
MIT ekidir; lisansı doğrulanmamış dış kod/veri/ağırlık içe aktarılmaz.
