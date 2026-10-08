#!/usr/bin/env python3
"""Assembly veri satırlarını özgün C fonksiyonlarıyla eşleştir.

Önce çeviri biriminin ham metni ayrıştırılır. Başlıkta tanımlanan inline
fonksiyonlar ve makroyla üretilen adlar için aynı dosya, projeler.json'daki
bayraklarla ön işlemciden geçirilir.

  python3 kaynak_kod.py                         # bütün eğitim ve test projeleri
  python3 kaynak_kod.py zlib cyaml -j 4         # yalnız seçilen projeler
  python3 kaynak_kod.py --veri-dosyalari veri/bin/olcek/{egitim,dogrulama,test}.jsonl
"""
import argparse, json, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HEDEF = "x86_64-apple-macos12"
DUZ_KIMLIK = re.compile(r"(?P<ad>[A-Za-z_]\w*)\s*(?P<par>\()")
SARMAL_KIMLIK = re.compile(r"\(\s*(?P<ad>[A-Za-z_]\w*)\s*\)\s*(?P<par>\()")
KIMLIK = re.compile(r"[A-Za-z_]\w*")
C_TUR_ADLARI = {
    "auto", "char", "const", "double", "enum", "extern", "float", "int",
    "long", "register", "restrict", "short", "signed", "static", "struct",
    "typedef", "union", "unsigned", "void", "volatile", "_Bool", "_Complex",
}


def maskele(metin: str) -> str:
    """Yorum ve dizgeleri, konumları değiştirmeden boşlukla maskele."""
    sonuc = list(metin)
    i, n = 0, len(metin)
    while i < n:
        if metin.startswith("//", i):
            son = metin.find("\n", i)
            son = n if son < 0 else son
            sonuc[i:son] = " " * (son - i)
            i = son
            continue
        if metin.startswith("/*", i):
            son = metin.find("*/", i + 2)
            son = n - 2 if son < 0 else son
            for j in range(i, son + 2):
                if sonuc[j] != "\n":
                    sonuc[j] = " "
            i = son + 2
            continue
        if metin[i] in "\"'":
            tirnak = metin[i]
            sonuc[i] = " "
            i += 1
            while i < n:
                if metin[i] == "\\":
                    sonuc[i] = " "
                    i += 1
                    if i < n and sonuc[i] != "\n":
                        sonuc[i] = " "
                elif metin[i] == tirnak:
                    sonuc[i] = " "
                    i += 1
                    break
                elif sonuc[i] != "\n":
                    sonuc[i] = " "
                i += 1
            continue
        i += 1
    return "".join(sonuc)


def makro_satiri_mi(metin: str, konum: int) -> bool:
    """Konum, devam satırları dahil bir #define yönergesinde mi?"""
    bas = metin.rfind("\n", 0, konum) + 1
    while bas:
        onceki_son = bas - 1
        onceki_bas = metin.rfind("\n", 0, onceki_son) + 1
        if not metin[onceki_bas:onceki_son].rstrip().endswith("\\"):
            break
        bas = onceki_bas
    return metin[bas:konum].lstrip().startswith("#")


def esini_bul(metin: str, konum: int, ac: str, kapa: str) -> int:
    derin = 1
    for i in range(konum + 1, len(metin)):
        if metin[i] == ac:
            derin += 1
        elif metin[i] == kapa:
            derin -= 1
            if derin == 0:
                return i
    return -1


def tanimlari_ayir(metin: str, arananlar: set[str]) -> dict[str, list[str]]:
    """Metinden istenen C fonksiyon tanımlarını çıkar.

    Küresel süslü-parantez derinliğine güvenilmez: koşullu derleme dalları ham
    kaynakta aynı anda bulunduğu için bu yaklaşım büyük amalgamation dosyalarında
    kolayca şaşar. Bunun yerine yalnız aranan adların imzası doğrulanır.
    """
    maske = maskele(metin)
    sonuc: dict[str, list[str]] = {}
    eslesmeler = list(DUZ_KIMLIK.finditer(maske)) + list(SARMAL_KIMLIK.finditer(maske))
    for eslesme in sorted(eslesmeler, key=lambda e: e.start()):
        ad = eslesme.group("ad")
        ad_konumu = eslesme.start("ad")
        if ad not in arananlar or makro_satiri_mi(metin, ad_konumu):
            continue
        parantez = eslesme.start("par")
        imza_sonu = esini_bul(maske, parantez, "(", ")")
        if imza_sonu < 0:
            continue

        # K&R tanımlarında türler imzadan sonra bildirilir:
        # ``f(a, b) int a; char *b; { ... }``. Yalnız parantez içi yalın
        # adlardan oluşuyorsa noktalı virgüllü bu bölgeye izin ver.
        parcalar = [p.strip() for p in maske[parantez + 1:imza_sonu].split(",")]
        knr_adlari = []
        if parcalar and all(KIMLIK.fullmatch(p) and p not in C_TUR_ADLARI for p in parcalar):
            knr_adlari = parcalar

        # İmzadan sonra __attribute__((...)) gibi ekler bulunabilir. Sıfır
        # derinlikteki ';', '=', ',' veya fazladan ')' bunun tanım olmadığını gösterir.
        # Tek istisna, C'nin ``void (*ad(...))(void)`` dönüş bildirimidir.
        onceki = max(maske.rfind(";", 0, ad_konumu), maske.rfind("}", 0, ad_konumu),
                      maske.rfind("{", 0, ad_konumu))
        isaretci_dondurur = re.search(r"\(\s*\*\s*$", maske[onceki + 1:ad_konumu]) is not None
        i, derin, govde, knr_bildirimi = imza_sonu + 1, 0, -1, False
        while i < len(maske) and i - imza_sonu < 8000:
            c = maske[i]
            if c == "(":
                derin += 1
            elif c == ")":
                if derin == 0:
                    if isaretci_dondurur:
                        isaretci_dondurur = False
                    else:
                        break
                else:
                    derin -= 1
            elif derin == 0 and c == "{":
                if knr_bildirimi:
                    bildirimler = maske[imza_sonu + 1:i]
                    if not all(re.search(rf"\b{re.escape(ad)}\b", bildirimler)
                               for ad in knr_adlari):
                        break
                govde = i
                break
            elif derin == 0 and c == ";":
                # Prototipte ')' ile ';' arası boştur; K&R'da ilk tür
                # bildirimi vardır. Böylece sonraki ilgisiz gövdeye taşmayız.
                if knr_adlari and maske[imza_sonu + 1:i].strip():
                    knr_bildirimi = True
                else:
                    break
            elif derin == 0 and c in "=,}":
                break
            i += 1
        if govde < 0:
            continue
        son = esini_bul(maske, govde, "{", "}")
        if son < 0:
            continue

        onceki = max(maske.rfind(";", 0, eslesme.start()),
                      maske.rfind("}", 0, eslesme.start()))
        bas = onceki + 1
        # Dosyanın ilk tanımından önceki uzun lisans/koşullu-derleme önsözü,
        # 200 satırlık kısaltmada imzayı dışarı itmesin.
        yakin = ad_konumu
        for _ in range(20):
            onceki_satir = maske.rfind("\n", 0, yakin)
            if onceki_satir < 0:
                yakin = 0
                break
            yakin = onceki_satir
        bas = max(bas, yakin + (yakin > 0))
        while bas < eslesme.start() and maske[bas].isspace():
            bas += 1
        kaynak = metin[bas:son + 1].strip()
        if kaynak:
            sonuc.setdefault(ad, []).append(kaynak)
    return sonuc


def kisalt(kaynak: str, tavan: int = 200) -> str:
    """Kaynağı başı ve sonu korunacak biçimde en çok tavan satıra indir."""
    satirlar = kaynak.splitlines()
    if len(satirlar) <= tavan:
        return kaynak
    bas = 120
    son = tavan - bas - 1
    atlanan = len(satirlar) - bas - son
    return "\n".join(satirlar[:bas] + [f"/* ... {atlanan} satır kısaltıldı ... */"] + satirlar[-son:])


def on_isle(kok: Path, dosya: str, opt: str, bayraklar: list[str], arananlar: set[str]):
    komut = ["clang", "-target", HEDEF, opt, "-E", "-P", "-w", *bayraklar, dosya]
    calisma = subprocess.run(komut, cwd=kok, capture_output=True, encoding="utf-8", errors="replace")
    if calisma.returncode:
        hata = calisma.stderr.strip().splitlines()
        return {}, hata[-1] if hata else f"clang çıkış kodu {calisma.returncode}"
    return tanimlari_ayir(calisma.stdout, arananlar), ""


def projeyi_isle(p: dict, veri: Path, kaynak_koku: Path, is_sayisi: int) -> tuple[int, int]:
    girdi = veri / p.get("rol", "egitim") / f"{p['ad']}.jsonl"
    if not girdi.exists():
        print(f"{p['ad']}: girdi yok: {girdi}", file=sys.stderr)
        return 0, 0
    satirlar = [json.loads(satir) for satir in girdi.open()]
    kok = kaynak_koku / p["ad"]
    dosyaya_gore: dict[str, list[dict]] = {}
    for kayit in satirlar:
        dosyaya_gore.setdefault(kayit["dosya"], []).append(kayit)

    bulunan: dict[tuple[str, str, str], str] = {}
    belirsiz: dict[tuple[str, str], list[str]] = {}
    hatalar = []

    def ham_is(item):
        dosya, kayitlar = item
        yol = kok / dosya
        if not yol.exists():
            return dosya, {}, f"dosya yok: {yol}"
        adlar = {r["ad"] for r in kayitlar}
        try:
            return dosya, tanimlari_ayir(yol.read_text(errors="replace"), adlar), ""
        except OSError as hata:
            return dosya, {}, str(hata)

    with ThreadPoolExecutor(max_workers=is_sayisi) as havuz:
        for dosya, tanimlar, hata in havuz.map(ham_is, dosyaya_gore.items()):
            if hata:
                hatalar.append(f"{dosya}: {hata}")
            for ad, adaylar in tanimlar.items():
                if len(adaylar) == 1:
                    bulunan[(dosya, "-O0", ad)] = adaylar[0]
                    bulunan[(dosya, "-O2", ad)] = adaylar[0]
                else:
                    belirsiz[(dosya, ad)] = adaylar

    # Ham dosyada olmayan başlık inline'ları ve makro üretimleri, gerçekten
    # derlendiği optimizasyon kipinde ön işlemci çıktısından alınır.
    isler = []
    for dosya, kayitlar in dosyaya_gore.items():
        for opt in ("-O0", "-O2"):
            eksik = {r["ad"] for r in kayitlar
                     if r.get("opt") == opt and (dosya, opt, r["ad"]) not in bulunan}
            if eksik:
                isler.append((dosya, opt, eksik))

    def on_is(args):
        dosya, opt, adlar = args
        tanimlar, hata = on_isle(kok, dosya, opt, list(p.get("bayraklar", [])), adlar)
        return dosya, opt, tanimlar, hata

    with ThreadPoolExecutor(max_workers=is_sayisi) as havuz:
        for dosya, opt, tanimlar, hata in havuz.map(on_is, isler):
            if hata:
                hatalar.append(f"{dosya} {opt}: {hata}")
            for ad, adaylar in tanimlar.items():
                if adaylar:
                    bulunan[(dosya, opt, ad)] = adaylar[0]

    # Ön işlemci başarısız olursa çoklu ham tanımlardan biri hiç yoktan iyidir.
    for kayit in satirlar:
        anahtar = (kayit["dosya"], kayit["opt"], kayit["ad"])
        if anahtar not in bulunan and (kayit["dosya"], kayit["ad"]) in belirsiz:
            bulunan[anahtar] = belirsiz[(kayit["dosya"], kayit["ad"])][0]

    cikti = veri / "kaynak" / f"{p['ad']}.jsonl"
    cikti.parent.mkdir(parents=True, exist_ok=True)
    gecici = cikti.with_suffix(".jsonl.tmp")
    adet = 0
    with gecici.open("w") as f:
        for kayit in satirlar:
            kaynak = bulunan.get((kayit["dosya"], kayit["opt"], kayit["ad"]), "")
            adet += bool(kaynak)
            sonuc = {"id": kayit["id"], "kaynak": kisalt(kaynak) if kaynak else "", "bulundu": bool(kaynak)}
            f.write(json.dumps(sonuc, ensure_ascii=False) + "\n")
    gecici.replace(cikti)

    oran = adet / len(satirlar) if satirlar else 0.0
    print(f"{p['ad']}: {adet}/{len(satirlar)} bulundu ({oran:.2%}) → {cikti}")
    for hata in hatalar[:3]:
        print(f"  {hata}", file=sys.stderr)
    if len(hatalar) > 3:
        print(f"  ... {len(hatalar) - 3} hata daha", file=sys.stderr)
    return adet, len(satirlar)


def v4_projeyi_isle(p: dict, kayitlar: list[dict], kaynak_koku: Path,
                    cikti_dizini: Path, is_sayisi: int) -> tuple[int, int]:
    """Tekil (dosya, ad) çiftlerinin kaynağını v4 biçiminde yaz."""
    kok = Path(p.get("kok") or kaynak_koku / p["ad"])
    dosyaya_gore: dict[str, list[dict]] = {}
    for kayit in kayitlar:
        dosyaya_gore.setdefault(kayit["dosya"], []).append(kayit)

    bulunan: dict[tuple[str, str], str] = {}
    belirsiz: dict[tuple[str, str], list[str]] = {}
    hatalar = []

    def ham_is(item):
        dosya, dosya_kayitlari = item
        yol = kok / dosya
        if not yol.exists():
            return dosya, {}, f"dosya yok: {yol}"
        adlar = {r["ad"] for r in dosya_kayitlari}
        try:
            return dosya, tanimlari_ayir(yol.read_text(errors="replace"), adlar), ""
        except OSError as hata:
            return dosya, {}, str(hata)

    with ThreadPoolExecutor(max_workers=is_sayisi) as havuz:
        for dosya, tanimlar, hata in havuz.map(ham_is, dosyaya_gore.items()):
            if hata:
                hatalar.append(f"{dosya}: {hata}")
            for ad, adaylar in tanimlar.items():
                if len(adaylar) == 1:
                    bulunan[(dosya, ad)] = adaylar[0]
                else:
                    belirsiz[(dosya, ad)] = adaylar

    # Başlık inline'ları ve makroyla üretilen adlar için iki derleme
    # kipini de dene. Sonuç tekil olduğundan -O0 sonucu önceliklidir.
    isler = []
    for dosya, dosya_kayitlari in dosyaya_gore.items():
        eksik = {r["ad"] for r in dosya_kayitlari if (dosya, r["ad"]) not in bulunan}
        for opt in ("-O0", "-O2"):
            if eksik:
                isler.append((dosya, opt, eksik))

    def on_is(args):
        dosya, opt, adlar = args
        tanimlar, hata = on_isle(kok, dosya, opt, list(p.get("bayraklar", [])), adlar)
        return dosya, opt, tanimlar, hata

    on_sonuclar = []
    with ThreadPoolExecutor(max_workers=is_sayisi) as havuz:
        for sonuc in havuz.map(on_is, isler):
            on_sonuclar.append(sonuc)
    for dosya, opt, tanimlar, hata in sorted(on_sonuclar, key=lambda x: x[1]):
        if hata:
            hatalar.append(f"{dosya} {opt}: {hata}")
        for ad, adaylar in tanimlar.items():
            if adaylar:
                bulunan.setdefault((dosya, ad), adaylar[0])

    # Ön işlemci başarısızsa çoklu ham tanımlardan ilki kullanılır.
    for anahtar, adaylar in belirsiz.items():
        if anahtar not in bulunan and adaylar:
            bulunan[anahtar] = adaylar[0]

    cikti = cikti_dizini / f"{p['ad']}.jsonl"
    cikti.parent.mkdir(parents=True, exist_ok=True)
    gecici = cikti.with_suffix(".jsonl.tmp")
    adet = 0
    with gecici.open("w") as f:
        for kayit in kayitlar:
            kaynak = bulunan.get((kayit["dosya"], kayit["ad"]), "")
            adet += bool(kaynak)
            sonuc = {
                "anahtar": f"{p['ad']}/{kayit['dosya']}:{kayit['ad']}",
                "kaynak": kisalt(kaynak) if kaynak else "",
                "bulundu": bool(kaynak),
            }
            f.write(json.dumps(sonuc, ensure_ascii=False) + "\n")
    gecici.replace(cikti)

    oran = adet / len(kayitlar) if kayitlar else 0.0
    print(f"{p['ad']}: {adet}/{len(kayitlar)} bulundu ({oran:.2%}) → {cikti}")
    for hata in hatalar[:3]:
        print(f"  {hata}", file=sys.stderr)
    if len(hatalar) > 3:
        print(f"  ... {len(hatalar) - 3} hata daha", file=sys.stderr)
    return adet, len(kayitlar)


def kataloglari_oku(yollar: list[Path]) -> dict[str, dict]:
    """Sonraki katalog öncekini geçersiz kılacak biçimde projeleri birleştir."""
    sonuc = {}
    for yol in yollar:
        if yol.exists():
            sonuc.update((p["ad"], p) for p in json.loads(yol.read_text()))
    return sonuc


def v4_verisini_oku(yollar: list[Path]) -> dict[str, list[dict]]:
    """Birden çok bölümdeki optimizasyon kopyalarını tekilleştir."""
    tekil = {}
    for yol in yollar:
        with yol.open() as f:
            for satir_no, satir in enumerate(f, 1):
                if not satir.strip():
                    continue
                kayit = json.loads(satir)
                try:
                    anahtar = (kayit["proje"], kayit["dosya"], kayit["ad"])
                except KeyError as hata:
                    raise ValueError(f"{yol}:{satir_no}: eksik alan: {hata.args[0]}") from hata
                tekil.setdefault(anahtar, {"proje": anahtar[0], "dosya": anahtar[1], "ad": anahtar[2]})
    sonuc = {}
    for kayit in tekil.values():
        sonuc.setdefault(kayit["proje"], []).append(kayit)
    for kayitlar in sonuc.values():
        kayitlar.sort(key=lambda r: (r["dosya"], r["ad"]))
    return sonuc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("proje", nargs="*", help="yalnız bu proje adlarını işle")
    ap.add_argument("--projeler", type=Path, default=Path("projeler.json"))
    ap.add_argument("--aday-projeler", type=Path, default=Path(".notlar/aday-projeler.json"))
    ap.add_argument("--veri", type=Path, default=Path("veri"))
    ap.add_argument("--kaynak", type=Path, default=Path("kaynak"))
    ap.add_argument("--veri-dosyalari", nargs="+", type=Path,
                    help="v4 JSONL bölümleri; (proje,dosya,ad) tekilleştirilir")
    ap.add_argument("--cikti-dizini", type=Path, default=Path("veri/kaynak-v4"),
                    help="v4 kaynak JSONL dosyalarının dizini")
    ap.add_argument("-j", type=int, default=6, help="eşzamanlı clang/ayrıştırma işi")
    a = ap.parse_args()
    if a.j < 1:
        ap.error("-j en az 1 olmalı")

    if a.veri_dosyalari:
        try:
            proje_kayitlari = v4_verisini_oku(a.veri_dosyalari)
        except (OSError, ValueError, json.JSONDecodeError) as hata:
            ap.error(str(hata))
        katalog = kataloglari_oku([a.aday_projeler, a.projeler])
        bilinmeyen = set(a.proje) - set(proje_kayitlari)
        if bilinmeyen:
            ap.error("veride olmayan proje: " + ", ".join(sorted(bilinmeyen)))
        for ad in sorted(proje_kayitlari):
            if a.proje and ad not in a.proje:
                continue
            p = katalog.get(ad, {"ad": ad, "bayraklar": []})
            v4_projeyi_isle(p, proje_kayitlari[ad], a.kaynak, a.cikti_dizini, a.j)
        return

    projeler = json.loads(a.projeler.read_text())
    bilinen = {p["ad"] for p in projeler}
    bilinmeyen = set(a.proje) - bilinen
    if bilinmeyen:
        ap.error("bilinmeyen proje: " + ", ".join(sorted(bilinmeyen)))

    basarisiz = []
    for p in projeler:
        if a.proje and p["ad"] not in a.proje:
            continue
        bulunan, toplam = projeyi_isle(p, a.veri, a.kaynak, a.j)
        if toplam and bulunan / toplam < 0.95:
            basarisiz.append(p["ad"])
    if basarisiz:
        raise SystemExit("%95 hedefinin altında: " + ", ".join(basarisiz))


if __name__ == "__main__":
    main()
