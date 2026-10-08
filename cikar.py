#!/usr/bin/env python3
"""Açık kaynak C kodunu x86-64'e derle, her fonksiyonu (isim, assembly) çiftine çevir.

Stripped binary'yi taklit eder:
- projenin kendi fonksiyon adları sub_XXXX, global veri adları dat_XXXX olur
  (numaralar karıştırılır; alfabetik sıra ipucu vermesin),
- dış kütüphane çağrıları (memcpy vb.) görünür kalır — gerçek binary'de de import adları görünür,
- string sabitleri Ghidra'daki gibi yorum olarak eklenir: ; "out of memory".
Fonksiyonun gerçek adı kendi asm'sinde (ör. bir hata mesajında) geçiyorsa satır "sizinti" ile işaretlenir.

  python3 cikar.py kaynak/zlib -o veri/zlib.jsonl -b -DZ_HAVE_UNISTD_H
  python3 cikar.py --projeler projeler.json            # hepsi → veri/<rol>/<ad>.jsonl
  python3 cikar.py --projeler projeler.json lua sqlite # yalnız bunlar
"""
import argparse, json, random, re, subprocess, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OPTS = ["-O0", "-O2"]
HEDEF = "x86_64-apple-macos12"
FONK = re.compile(r"^[0-9a-f]+ <(_?[A-Za-z_][\w.$]*)>:$")
ADRES_YORUMU = re.compile(r"##\s*0x([0-9a-f]+)")
RELOK_EKI = re.compile(r"[-+](?:0x[0-9a-f]+|\d+)$")        # Mach-O PC-relative ek: vfsList-1, global_error-4
BOLUM = re.compile(r"^__[a-z][a-z0-9_]*$")                 # bölüm adı: __cstring, __const, __literal16
DAL = re.compile(r"(0x[0-9a-f]+ )?<([\w.$]+?)(\+0x[0-9a-f]+)?>")
EV = str(Path.home())


def csym(ham: str) -> str:
    """Mach-O C sembolündeki tek '_' önekini at (___stack_chk_guard → __stack_chk_guard)."""
    return ham[1:] if ham.startswith("_") else ham


def derle(c: Path, opt: str, cikti: Path, bayraklar: list[str], kok: Path = Path(".")) -> bool:
    # Göreli -I/-D yolları proje kökünden çözülsün diye clang proje dizininde çalışır.
    # Kaynak yolu göreli verilir: __FILE__ string'lerine yerel dizin (kullanıcı adı) girmesin.
    r = subprocess.run(["clang", "-target", HEDEF, opt, "-w", "-c", str(c.resolve().relative_to(kok.resolve())),
                        "-o", str(cikti.resolve()), *bayraklar], capture_output=True, text=True, cwd=kok)
    return r.returncode == 0


def semboller(o: Path) -> tuple[set[str], set[str]]:
    """.o içinde tanımlı (fonksiyon, veri) sembolleri."""
    fonk, veri = set(), set()
    for satir in subprocess.run(["nm", str(o)], capture_output=True, text=True).stdout.splitlines():
        p = satir.split()
        if len(p) == 3 and p[1] != "U":
            ad = csym(p[2])
            (fonk if p[1] in "Tt" else veri).add(ad)
    return fonk, veri


def stringler(o: Path) -> dict[int, str]:
    """__cstring bölümü: adres → string."""
    dump = subprocess.run(["objdump", "-s", "--section=__cstring", str(o)], capture_output=True, text=True).stdout
    bayt, bas = bytearray(), None
    for satir in dump.splitlines():
        m = re.match(r"^ ([0-9a-f]{4,}) ((?:[0-9a-f]{2,8} ?){1,4})", satir)
        if m:
            bas = int(m.group(1), 16) if bas is None else bas
            bayt += bytes.fromhex(m.group(2).replace(" ", ""))
    sonuc, i = {}, 0
    while i < len(bayt):
        j = bayt.find(b"\0", i)
        j = len(bayt) if j < 0 else j
        sonuc[bas + i] = bayt[i:j].decode("utf-8", "replace")
        i = j + 1
    return sonuc


def ayristir(o: Path) -> dict[str, list[str]]:
    dump = subprocess.run(["objdump", "-d", "-r", "--no-show-raw-insn", "--x86-asm-syntax=intel", str(o)],
                          capture_output=True, text=True).stdout
    fonklar, ad = {}, None
    for satir in dump.splitlines():
        m = FONK.match(satir.strip())
        if m:
            ad = csym(m.group(1))
            fonklar[ad] = []
        elif ad and satir.strip() and "\t" in satir:
            fonklar[ad].append(satir.strip())
    return fonklar


def string_bul(strs: dict[int, str], adres) -> "str | None":
    """Adres bir string'in başına ya da ortasına (derleyici kuyruk paylaşımı) düşebilir."""
    if adres is None:
        return None
    if adres in strs:
        return strs[adres]
    for bas, st in strs.items():
        if bas <= adres < bas + len(st.encode()):
            return st.encode()[adres - bas:].decode("utf-8", "replace")
    return None


def string_goster(s: str) -> str:
    s = s.encode("unicode_escape").decode("ascii").replace('"', '\\"')
    return f'"{s[:80]}{"…" if len(s) > 80 else ""}"'


def anonimlestir(satirlar: list[str], adlar: dict[str, str], strs: dict[int, str], kendi: str) -> str:
    """objdump satırları → stripped binary görünümü.

    Fonksiyon içi dal hedefleri sıralı loc_N etiketine çevrilir (.o yerleşimi ve fonksiyonun kendi
    kimliği sızmasın); relokasyonlu RIP ofsetleri [rip] olur; dış importlar adıyla kalır.
    """
    out, adresler, son_adres, etiketler = [], [], None, {}

    def dal(m):
        ad = csym(m.group(2))
        if m.group(3) or ad == kendi:
            anahtar = int(m.group(1), 16) if m.group(1) else m.group(0)
            return etiketler.setdefault(anahtar, f"loc_{len(etiketler) + 1}")
        return adlar.get(ad, "loc")

    for s in satirlar:
        a = re.match(r"^([0-9a-f]+):", s)
        s = re.sub(r"^[0-9a-f]+:\s*", "", s)                  # adres sütunu
        if s.startswith(("X86_64_RELOC", "0000")):          # relokasyon satırı → hedefi yorum olarak ekle
            ham = RELOK_EKI.sub("", s.split()[-1].split("@")[0])
            if ham == "__cstring" and (st := string_bul(strs, son_adres)) is not None:
                hedef = string_goster(st)
            elif BOLUM.match(ham) or not ham.startswith("_"):  # bölüm ya da derleyici etiketi (LCPI, L_.str)
                hedef = "veri"
            elif "." in ham:                                # fonk.static_degisken → veri (ad sızmasın)
                hedef = "veri"
            else:
                hedef = adlar.get(csym(ham), csym(ham))     # iç → sub_/dat_, dış import adıyla kalır
            if out:                                         # .o'da çözülmemiş hedef adresi yanıltıcı, sil
                onceki = re.sub(r"\[rip\s*[+-]\s*0x[0-9a-f]+\]", "[rip]", out[-1])
                out[-1] = re.sub(r"\s*(0x[0-9a-f]+ )?<[^>]*>", "", onceki).rstrip() + f"    ; -> {hedef}"
            continue
        m = ADRES_YORUMU.search(s)
        son_adres = int(m.group(1), 16) if m else None
        s = re.sub(r"\s*##.*$", "", s)                       # objdump'ın rip yorumları
        s = DAL.sub(dal, s)
        if not s or s.startswith("<"):                      # kod içine gömülü veri artığı
            continue
        out.append(s)
        adresler.append(int(a.group(1), 16) if a else None)
    # Dal hedefi olan komutların önüne "loc_N:" etiketi (döngü/dallanma yapısı görünsün)
    son = []
    for adres, s in zip(adresler, out):
        if adres in etiketler:
            son.append(f"{etiketler[adres]}:")
        son.append(s)
    return "\n".join(son).replace(EV, "~")


def sizar_mi(ad: str, asm: str) -> bool:
    """Gerçek ad asm metninde (ör. bir hata mesajında) ayrı bir sözcük olarak geçiyor mu? Kısa adlar (≤3) sayılmaz."""
    if len(ad) <= 3:
        return False
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(ad)}(?![A-Za-z0-9_])", asm, re.I) is not None


def tekil(liste: list[str], deger: str, sinir: int):
    """Sırayı koruyarak benzersiz ve sınırlı ekle."""
    if deger not in liste and len(liste) < sinir:
        liste.append(deger)


def ic_cagrilar(asm: str, sinir: int = 8) -> list[str]:
    """call/jmp ile çağrılan anonim iç fonksiyonlar."""
    sonuc = []
    for satir in asm.splitlines():
        if not re.match(r"^\s*(?:call|jmp)\w*\s", satir):
            continue
        m = re.search(r";\s*->\s*(sub_[0-9a-f]+)\s*$", satir)
        if not m:
            m = re.match(r"^\s*(?:call|jmp)\w*\s+(sub_[0-9a-f]+)\b", satir)
        if m:
            tekil(sonuc, m.group(1), sinir)
    return sonuc


def string_kisalt(hedef: str) -> str:
    """Tırnaklar dahil en çok 60 karakterlik string gösterimi."""
    if len(hedef) <= 60:
        return hedef
    icerik = hedef[1:-1][:57].rstrip("\\")
    return f'"{icerik}…"'


def fonksiyon_ozeti(kimlik: str, komut_sayisi: int, asm: str) -> str:
    """Anonim asm'den tek satırlık çağrı özeti çıkar."""
    ithaller, stringler = [], []
    for satir in asm.splitlines():
        m = re.search(r";\s*->\s*(.+?)\s*$", satir)
        if not m:
            continue
        hedef = m.group(1)
        if hedef.startswith('"'):
            tekil(stringler, string_kisalt(hedef), 4)
        elif hedef != "veri" and not hedef.startswith(("sub_", "dat_")):
            tekil(ithaller, hedef, 6)
    cagrilar = ic_cagrilar(asm)[:4]
    parcalar = []
    if ithaller or cagrilar:
        parcalar.append("çağırır " + ", ".join(ithaller + cagrilar))
    if stringler:
        parcalar.append("string " + ", ".join(stringler))
    bas = f"{kimlik} ({komut_sayisi} komut)"
    return bas + (": " + "; ".join(parcalar) if parcalar else "")


def baglam_derin_uret(dosya: str, opt: str, asm: str, dosya_bilgileri: dict, genel_bilgiler: dict) -> str:
    """Doğrudan çağrılanların asm'sini ya da iki seviyeli özetini üret."""
    satirlar = []

    def bilgi_bul(kaynak_dosya: str, hedef: str):
        return dosya_bilgileri.get((kaynak_dosya, opt, hedef)) or genel_bilgiler[(opt, hedef)]

    for hedef in ic_cagrilar(asm, 6):
        hedef_dosya, komut_sayisi, hedef_asm, ozet = bilgi_bul(dosya, hedef)
        if komut_sayisi <= 40:
            satirlar.append(f"; {hedef} ({komut_sayisi} komut):")
            satirlar.extend(hedef_asm.splitlines())
        else:
            satirlar.append(ozet)
            for alt_hedef in ic_cagrilar(hedef_asm, 4):
                satirlar.append("  " + bilgi_bul(hedef_dosya, alt_hedef)[3])

    if len(satirlar) > 150:
        satirlar = satirlar[:149] + ["; ... kesildi"]
    return "\n".join(satirlar)


def gercek_sembol_deseni(adlar: set[str]):
    """Derin bağlamdaki anonimleştirilmemiş iç sembolleri doğrulamak için desen."""
    uzun = sorted((ad for ad in adlar if len(ad) >= 5), key=lambda ad: (-len(ad), ad))
    if not uzun:
        return None
    return re.compile(r"(?<![A-Za-z0-9_])(?:" + "|".join(map(re.escape, uzun)) + r")(?![A-Za-z0-9_])", re.I)


def cikar(kok: Path, cikti: Path, dosyalar=("*.c",), haric=(), bayraklar=(), proje=None, surum=None,
          en_az=6, en_cok=300, tohum=7) -> int:
    proje = proje or kok.name
    kaynaklar = sorted({c for d in dosyalar for c in kok.glob(d)} - {c for h in haric for c in kok.glob(h)})
    ham, tanimli_fonk, tanimli_veri, basarisiz = [], set(), set(), []
    with tempfile.TemporaryDirectory() as t:
        def is_(ck):
            c, opt = ck
            o = Path(t) / f"{c.relative_to(kok).as_posix().replace('/', '__')}{opt}.o"
            if not derle(c, opt, o, list(bayraklar), kok):
                return c, opt, None
            return c, opt, (semboller(o), stringler(o), ayristir(o))
        with ThreadPoolExecutor(8) as havuz:
            for c, opt, r in havuz.map(is_, [(c, opt) for c in kaynaklar for opt in OPTS]):
                if r is None:
                    basarisiz.append(f"{c.relative_to(kok)}{opt}")
                    continue
                (f, v), strs, fonklar = r
                tanimli_fonk |= f
                tanimli_veri |= v
                ham += [(c.relative_to(kok).as_posix(), opt, ad, s, strs) for ad, s in fonklar.items()]

    # Her kip ayrı bir binary sayılır: -O0 ve -O2 aynı sub_ kimliklerini paylaşmasın.
    adlar = {}
    for opt in OPTS:
        rnd = random.Random(f"{proje}-{opt}-{tohum}")
        fonk_adlari = sorted(tanimli_fonk | {ad for _, o, ad, _, _ in ham if o == opt})
        veri_adlari = sorted(tanimli_veri - set(fonk_adlari))
        rnd.shuffle(fonk_adlari)
        rnd.shuffle(veri_adlari)
        adlar[opt] = {ad: f"sub_{i:04x}" for i, ad in enumerate(fonk_adlari)}
        adlar[opt] |= {ad: f"dat_{i:04x}" for i, ad in enumerate(veri_adlari)}

    # Bağlam özeti kısa/uzun diye elenecek fonksiyonları da görebilsin.
    anonim_ham, dosya_bilgileri, genel_bilgiler = [], {}, {}
    for dosya, opt, ad, s, strs in ham:
        komut = [x for x in s if not x.split(":", 1)[-1].strip().startswith(("X86_64_RELOC",))]
        asm = anonimlestir(s, adlar[opt], strs, ad)
        kimlik = adlar[opt][ad]
        ozet = fonksiyon_ozeti(kimlik, len(komut), asm)
        anonim_ham.append((dosya, opt, ad, komut, asm))
        bilgi = (dosya, len(komut), asm, ozet)
        dosya_bilgileri.setdefault((dosya, opt, kimlik), bilgi)
        genel_bilgiler.setdefault((opt, kimlik), bilgi)

    cikti.parent.mkdir(parents=True, exist_ok=True)
    n = sizan = sembol_sizintili = sembol_eslesmesi = 0
    sembol_deseni = gercek_sembol_deseni(tanimli_fonk | tanimli_veri)
    gorulen = set()
    with cikti.open("w") as f:
        for dosya, opt, ad, komut, asm in anonim_ham:
            if "." in ad:                                   # foo.cold.1: derleyicinin ayırdığı parça, kaynak fonksiyonu değil
                continue
            if not (en_az <= len(komut) <= en_cok):
                continue
            if (opt, ad, asm) in gorulen:                   # aynı static yardımcı birden çok dosyada
                continue
            gorulen.add((opt, ad, asm))
            baglam = "\n".join((dosya_bilgileri.get((dosya, opt, hedef)) or genel_bilgiler[(opt, hedef)])[3]
                                for hedef in ic_cagrilar(asm))
            baglam_derin = baglam_derin_uret(dosya, opt, asm, dosya_bilgileri, genel_bilgiler)
            sizinti = sizar_mi(ad, asm) or sizar_mi(ad, baglam) or sizar_mi(ad, baglam_derin)
            if sembol_deseni:
                eslesmeler = sembol_deseni.findall(baglam_derin)
                sembol_sizintili += bool(eslesmeler)
                sembol_eslesmesi += len(eslesmeler)
            sizan += sizinti
            f.write(json.dumps({"id": f"{proje}/{dosya}:{opt}:{ad}", "proje": proje, "surum": surum,
                                "dosya": dosya, "opt": opt, "ad": ad, "komut_sayisi": len(komut),
                                "sizinti": sizinti, "asm": asm, "baglam": baglam,
                                "baglam_derin": baglam_derin}, ensure_ascii=False) + "\n")
            n += 1
    print(f"{proje}: {n} fonksiyon ({sizan} sızıntılı) → {cikti}"
          f"  [derin bağlam gerçek sembol: {sembol_sizintili} kayıt, {sembol_eslesmesi} eşleşme]"
          + (f"  [derlenemeyen: {len(basarisiz)}: {', '.join(basarisiz[:6])}…]" if basarisiz else ""))
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kaynak", nargs="*", help="kaynak dizini (ya da --projeler ile proje adları)")
    ap.add_argument("-o", "--cikti", type=Path)
    ap.add_argument("-b", "--bayrak", action="append", default=[], help="derleyici bayrağı (-I, -D)")
    ap.add_argument("--projeler", type=Path, help="projeler.json: ad, url, surum, dosyalar, haric, bayraklar")
    ap.add_argument("--veri", type=Path, default=Path("veri"))
    ap.add_argument("--min", type=int, default=6)
    ap.add_argument("--max", type=int, default=300)
    a = ap.parse_args()

    if not a.projeler:
        kok = Path(a.kaynak[0])
        cikar(kok, a.cikti or a.veri / f"{kok.name}.jsonl", bayraklar=a.bayrak, en_az=a.min, en_cok=a.max)
        return
    for p in json.loads(a.projeler.read_text()):
        if a.kaynak and p["ad"] not in a.kaynak:
            continue
        kok = Path("kaynak") / p["ad"]
        if not kok.exists():
            subprocess.run(["git", "clone", "--filter=blob:none", p["url"], str(kok)], check=True)
            subprocess.run(["git", "-C", str(kok), "checkout", "-q", p["surum"]], check=True)
        for komut in p.get("hazirlik", []):
            subprocess.run(komut, shell=True, cwd=kok, check=True)
        cikar(kok, a.veri / p.get("rol", "egitim") / f"{p['ad']}.jsonl", p.get("dosyalar", ["*.c"]), p.get("haric", []),
              p.get("bayraklar", []), p["ad"], p.get("surum"), a.min, a.max)


if __name__ == "__main__":
    main()
