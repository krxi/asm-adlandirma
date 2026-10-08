# Veri hattı v4 — gerçek link ve strip

8 Ekim 2026'da sistem Python 3.9.6 ve Apple clang 21.0.0 (`clang-2100.3.34.2`) ile yerelde çalıştırıldı.
Hedef `x86_64-apple-macos12`; kaynak ve derleyici bayrakları `projeler.json` üzerinden alındı.
Kaynak dizinlerine yazılmadı. Ağ, Evren, model çağrısı veya git commit/push kullanılmadı.

```bash
python3 cikar_bin.py --projeler projeler.json zlib lua tomlc17 --v3-karsilastir
python3 -m unittest -v test_cikar_bin
```

`cikar.py` değişmedi. v4; `derle`, `HEDEF`, `OPTS`, `csym`, string yordamları, `ic_cagrilar`,
`fonksiyon_ozeti` ve `sizar_mi` işlevlerini v3'ten kullanıyor. Her optimizasyon için nesneler tek
dylib'e linkleniyor; `-Wl,-no_deduplicate`, farklı doğru adların aynı kod adresine katlanmasını
engelliyor. Normal link yalnız çözülmemiş semboller nedeniyle başarısız olursa
`-Wl,-undefined,dynamic_lookup` ile yeniden deneniyor. Üç gerçek projede bu ek bayrak gerekmedi;
testte çözümlenmemiş bir import ile bu yol da doğrulandı. Binary'ler geçici dizinde tutuluyor.

`strip -x` çıktısı hem sınır bulma hem disassembly için kullanılıyor. `yerel`, kalan export
adlarını koruyor. `tam`, aynı stripped binary'deki export adlarını da çıktı görünümünde gizliyor;
dyld export trie'sini değiştiren veya yeniden yüklenebilir anonim bir dylib üreten bir işlem değil.

## Sayı karşılaştırması

v3 aynı makinede, aynı kaynak seçimi ve bayraklarla yeniden üretildi. Filtre iki hatta da
6–300 komut; noktalı derleyici parçaları hedef satırı olarak alınmıyor. v4 sütunu **tek kip** için;
`yerel` ve `tam` aynı fonksiyonları içeriyor. Varsayılan JSONL iki kipi birlikte içerir.

| Proje | Optimizasyon | v3 satır | v4 / kip | Fark | Stripped başlangıç / ad eşleşmesi | Atlanan veri bölgesi / bayt |
|---|---|---:|---:|---:|---:|---:|
| zlib | -O0 | 141 | 142 | +1 | 159 / 159 | 3 / 516 |
| zlib | -O2 | 114 | 115 | +1 | 133 / 133 | 5 / 712 |
| lua | -O0 | 1.114 | 1.116 | +2 | 1.124 / 1.124 | 44 / 5.376 |
| lua | -O2 | 643 | 648 | +5 | 716 / 716 | 45 / 6.796 |
| tomlc17 | -O0 | 85 | 85 | 0 | 91 / 91 | 4 / 584 |
| tomlc17 | -O2 | 33 | 33 | 0 | 79 / 79 | 6 / 908 |
| **Toplam** | | **2.130** | **2.139** | **+9** | **2.302 / 2.302** | **107 / 14.892** |

Çıktılar: `veri/bin/zlib.jsonl` (514 satır), `lua.jsonl` (3.528), `tomlc17.jsonl` (236).
Yanlarındaki `*.rapor.json` dosyaları makinece okunabilir denetimleri ve v3/v4 assembly örneklerini içerir.
`veri/bin/v3/` yeniden üretilen karşılaştırma verisidir; önceki veri dosyaları korunmuştur.

2.302 başlangıcın tamamı `LC_FUNCTION_STARTS` içinde bulundu. Unwind kayıtları `-O0` için proje
başına 1, `-O2` için zlib'de 92, lua'da 482, tomlc17'de 22 başlangıcı ayrıca doğruladı;
bu koşuda fazladan unwind başlangıcı çıkmadı. Adsız başlangıç, sınırı bulunamayan kaynak
sembolü ve birden fazla gerçek ad taşıyan adres sayıları tüm projelerde **0**.
Link map yalnız `dosya` metaverisini adres ve adla eşlemek için kullanıldı; boyları sınır üretmedi.

## Örnek farkları

Atlama tablosu baytlarının komut sayılmaması komut sayılarını düşürüyor. Daha önce 300 komut
üstünde kaldığı için elenen şu fonksiyonlar artık veri setinde. Buradaki v3 sayıları, ilgili
`.o` fonksiyonları boy filtresi uygulanmadan yeniden okunarak doğrulandı.

| Fonksiyon | Optimizasyon | v3 komut | v4 komut |
|---|---|---:|---:|
| zlib / gz_open | -O0 | 448 | 289 |
| zlib / gz_open | -O2 | 442 | 223 |
| lua / getoption | -O0 | 335 | 170 |
| lua / match | -O0 | 320 | 285 |
| lua / luaK_exp2K | -O2 | 305 | 293 |
| lua / luaK_prefix | -O2 | 320 | 288 |
| lua / luaO_pushvfstring | -O2 | 417 | 256 |
| lua / subexpr | -O2 | 555 | 228 |
| lua / getoption | -O2 | 353 | 244 |

Her iki hatta da bulunan örnekler: lua `luaV_finishOp` (-O0) 285 → 177,
lua `funcnamefromcall` (-O2) 194 → 78, tomlc17 `parse_val` (-O0) 178 → 143,
tomlc17 `datum_equiv` (-O2) 250 → 228, zlib `gz_decomp` (-O2) 126 → 112.
v3'te bulunan hiçbir `(dosya, ad, opt)` bu koşuda v4'ten kaybolmadı.

Stripped objdump çıktısı iç adreslere bazen ilgisiz `_vsnprintf+...` gibi adlar yakıştırıyor.
v4 bu etiketleri kullanmıyor: sayısal hedefi fonksiyon başlangıcı, stub/indirect-symbol,
GOT/bind ve `__cstring` tablolarıyla çözüyor. Örneğin tomlc17 `toml_free` (-O0, tam) içindeki
çağrılar `sub_001b` ve `sub_0057`; ikinci çağrının bağlamı `__assert_rtn`, `free` ve
`"pool_destroy"` string ipucunu koruyor. RIP ofseti `[rip]`, yerel dal hedefi `loc_N` oluyor.
`sub_`/`dat_` numaraları ad sırasından veya ham adres değerinden türetilmiyor; adres kümeleri
sabit tohumla karıştırılıyor. Optimizasyonların ad uzayları ayrı, iki kipin kimlikleri ortak.

## Sızıntı kontrolü

`sizinti`, v3'ün kendi gerçek adını asm veya bağlamda arayan işareti; string içindeki doğal
ipucunu silmez. Bundan ayrı yapısal denetim, tırnaklı stringler dışında kaynak fonksiyon/veri
adlarını tarar. `yerel` kipte görülebilen exportlar ve iki kipte gerçek importlar izinlidir.
Adres sütunu, sayısal doğrudan dal hedefi, RIP ofseti ve objdump sembol/yorum kalıntıları da aranır.
Denetim başarısızsa rapor yazılır, mevcut sağlam JSONL değiştirilmez.

| Proje / optimizasyon | v3 `sizinti` | v4 yerel `sizinti` | v4 tam `sizinti` | Beklenmeyen sembol / adres kalıntısı |
|---|---:|---:|---:|---:|
| zlib -O0 | 1 | 0 | 1 | 0 / 0 |
| zlib -O2 | 1 | 0 | 1 | 0 / 0 |
| lua -O0 | 2 | 5 | 2 | 0 / 0 |
| lua -O2 | 1 | 4 | 1 | 0 / 0 |
| tomlc17 -O0 | 21 | 21 | 21 | 0 / 0 |
| tomlc17 -O2 | 0 | 5 | 5 | 0 / 0 |

tomlc17 -O2'de ek işaretlenen `pool_destroy`, `pool_alloc`, `tab_emplace`, `arr_emplace`,
`tab_find`, artık ayrı başlangıçlarıyla görülen `.cold` yardımcılarına çağrı yapıyor.
Bu yardımcıların özetlerindeki assert stringleri gerçek adı içeriyor; bunlar normal
binary ipuçları ve `sizinti: true` olarak korunuyor. Stringler dışındaki gizli adlar açığa çıkmıyor.
`yerel` kipte export çağrıları adıyla kaldığından, v3'ün yalnız `sub_` çağrıları için özet
üreten bağlam yordamı bu çağrılara özet eklemiyor; kipler arasındaki bazı işaret farkları bundan.

## Kontroller ve sınırlar

9 `unittest` geçti: gerçek derleme/link/strip; aynı adlı iki static fonksiyonun adres ve dosyayla
ayrılması; iki kipte export/import davranışı; LC_DATA_IN_CODE ile komut aralıklarının kesişmemesi;
sembol tablosundan bağımsız başlangıç bulma; ULEB ve veri aralığı ayrımı; regular/compressed
unwind, sentinel ve `UNWIND_IS_NOT_FUNCTION_START`; DWARF FDE okuma; string/adres normalleştirmesi;
hatalı derleme ve sızıntı denetiminde sağlam çıktının korunması. Üç projenin altı gerçek
derlemesinde tüm eşleşme ve çıktı denetimleri geçti.

- macOS araçları ve thin x86-64 Mach-O dylib'in tek `__text` bölümü desteklenir; ELF/PE, arm64,
  universal binary ve ayrı kod bölümleri bu sürümün kapsamı dışındadır.
- `LC_FUNCTION_STARTS` yoksa unwind yardımcı olur ama tüm fonksiyonları geri getiremez:
  linker aynı unwind kodlamasına sahip komşuları tek kayıtta birleştirebilir. Kaynak sembolleri
  eksik sınırları doldurmak için kullanılmaz; eşleşmeyenler raporlanır. Sınır bulunmaması hatadır.
- Sonraki başlangıç/`__text` sonu üst sınırdır. NOP hizalaması komut sayısına dahildir;
  sınır sonundaki sıfır dolgu atılır ve raporlanır. İşaretlenmemiş kod içi veriyi sezgisel
  olarak keşfetmez; dolaylı atlama tablolarının tüm CFG kenarlarını yeniden kurmaz.
- Birden çok adı aynı adreste kalan fonksiyonlar raporlanıp hedeflerden elenir. Aynı adlı
  farklı adresler korunur. `.cold` parçalar hedef olmaz, çağrı bağlamında görünebilir.
- Gerçek adresler model girdisinden kaldırılır; sayısal algoritma sabitleri korunur.
  Eşleşme sorunu olursa denetim raporundaki adresler teşhis içindir, model girdisi değildir.
- `sizinti` v3 uyumluluğu nedeniyle üç veya daha kısa hedef adlarını işaretlemez. Doğal
  string ipuçları ve `yerel` kipte export adları kasıtlı görünür. Adı zaten bilinen hedefleri
  değerlendirmeden ayırmak için `export: false`, kendi adını içeren girdileri ayırmak için
  `sizinti: false` seçilebilir. JSONL'de iki kip aynı kodu temsil eder; eğitim/ölçüm için
  tek kip seçilmeli, `ad` gibi hedef metaverisi model girdisine verilmemelidir.
- `--projeler` yalnız mevcut yerel kaynakları ve yapılandırılmış bayrakları okur; otomatik
  clone/checkout/hazırlık çalıştırmaz. `surum` yapılandırmanın değeridir, çalışma ağacının
  içeriğini kriptografik olarak doğrulamaz. Derleyici/SDK değişirse sayılar da değişebilir.
