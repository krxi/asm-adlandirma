#!/usr/bin/env python3
"""v4: C kaynaklarını gerçek dylib'e linkle, strip edilmiş koddan veri çıkar.

  python3 cikar_bin.py --projeler projeler.json zlib lua tomlc17 --v3-karsilastir
  python3 cikar_bin.py kaynak/zlib -b=-DZ_HAVE_UNISTD_H --kip tam

Yalnız yerel kaynaklar kullanılır; indirme ve projeler.json/hazirlik çalıştırılmaz.
İki kip de strip -x çıktısını okur. 'tam', bu çıktıda kalan export adlarını da
model girdisinde gizler; dylib'in dyld export tablosunu yeniden yazmaz.
"""
import argparse, bisect, json, random, re, struct, subprocess, tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from cikar import (EV, HEDEF, OPTS, cikar as cikar_v3, csym, derle, fonksiyon_ozeti,
                   ic_cagrilar, sizar_mi, string_bul, string_goster)


def calistir(komut):
    r = subprocess.run([str(x) for x in komut], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"{komut[0]} başarısız:\n{r.stderr.strip()}")
    return r.stdout


def uleb(bayt, i):
    deger = kaydir = 0
    while i < len(bayt) and kaydir < 64:
        b = bayt[i]
        i += 1
        deger |= (b & 127) << kaydir
        if not b & 128:
            return deger, i
        kaydir += 7
    raise ValueError("Eksik/taşan ULEB128")


@dataclass
class Bolum:
    ad: str
    segment: str
    adres: int
    boy: int
    ofset: int
    bayrak: int
    indis: int
    dolayli: int
    adim: int

    def icerir(self, adres):
        return self.adres <= adres < self.adres + self.boy


class MachO:
    """Little-endian x86-64 dylib metaverisi; kaynak sembolleri sınır sayılmaz."""
    def __init__(self, yol):
        self.yol, self.bayt = Path(yol), Path(yol).read_bytes()
        h = self.oku("8I", 0)
        if h[:4] != (0xfeedfacf, 0x1000007, 3, 6):
            raise ValueError("Yalnız thin x86-64 (ALL) Mach-O dylib destekleniyor")
        self.bolumler, self.komutlar, self.taban = [], {}, None
        i = 32
        for _ in range(h[4]):
            tur, boy = self.oku("2I", i)
            if boy < 8 or i + boy > 32 + h[5]:
                raise ValueError("Bozuk Mach-O yük komutu")
            self.komutlar[tur] = i
            if tur == 0x19:                           # LC_SEGMENT_64
                seg = self.oku("II16s4Q4I", i)
                if seg[2].rstrip(b"\0") == b"__TEXT":
                    self.taban = seg[3]
                for j in range(seg[9]):
                    s = self.oku("16s16sQQ8I", i + 72 + 80 * j)
                    self.bolumler.append(Bolum(s[0].rstrip(b"\0").decode(),
                        s[1].rstrip(b"\0").decode(), s[2], s[3], s[4], s[8],
                        len(self.bolumler) + 1, s[9], s[10]))
            i += boy
        if self.taban is None:
            raise ValueError("__TEXT segmenti yok")
        self.kod = [s for s in self.bolumler if s.ad == "__text"]
        if len(self.kod) != 1:
            raise ValueError("Tek __text bölümü bekleniyor")
        self.semboller = []
        if 2 in self.komutlar:                         # LC_SYMTAB
            _, _, off, n, strs, strboy = self.oku("6I", self.komutlar[2])
            for j in range(n):
                ix, tur, bolum, _, adres = self.oku("IBBHQ", off + j * 16)
                son = self.bayt.find(b"\0", strs + ix, strs + strboy)
                if ix >= strboy or son < 0:
                    raise ValueError("Bozuk sembol string tablosu")
                ad = csym(self.bayt[strs + ix:son].decode("utf-8", "replace"))
                self.semboller.append((adres, ad, tur, bolum))

    def oku(self, bicim, i):
        return struct.unpack_from("<" + bicim, self.bayt, i)

    def veri(self, tur):
        if tur not in self.komutlar:
            return b""
        _, _, off, boy = self.oku("4I", self.komutlar[tur])
        if off + boy > len(self.bayt):
            raise ValueError("LINKEDIT kaydı dosya dışında")
        return self.bayt[off:off + boy]

    def kodda(self, adres):
        return any(s.icerir(adres) for s in self.kod)

    def tanimli(self):
        return [(a, ad, t, b) for a, ad, t, b in self.semboller
                if not t & 0xe0 and t & 0x0e == 0x0e]  # N_SECT, STAB değil

    def baslangiclar(self):
        sonuc, adres, i = set(), self.taban, 0
        b = self.veri(0x26)                            # LC_FUNCTION_STARTS
        while i < len(b):
            fark, i = uleb(b, i)
            if fark == 0:
                break
            adres += fark
            if self.kodda(adres):
                sonuc.add(adres)
        return sonuc

    def unwind(self):
        """Compact unwind regular/compressed sayfaları; sentinel ve ara aralıklar hariç."""
        sonuc = set()
        for s in self.bolumler:
            if s.ad != "__unwind_info":
                continue
            b = self.bayt[s.ofset:s.ofset + s.boy]
            def oku(bicim, i):
                return struct.unpack_from("<" + bicim, b, i)
            v, ortak, n, _, _, indeks, adet = oku("7I", 0)
            if v != 1:
                raise ValueError("Bilinmeyen compact unwind sürümü")
            ortaklar = list(oku(f"{n}I", ortak))
            for j in range(adet - 1):                 # son indeks yalnız sentinel
                taban, sayfa, _ = oku("3I", indeks + j * 12)
                if not sayfa:
                    continue
                tur, off, sayi = oku("IHH", sayfa)
                if tur == 2:
                    girdiler = [oku("2I", sayfa + off + k * 8) for k in range(sayi)]
                elif tur == 3:
                    enc, encn = oku("2H", sayfa + 8)
                    kodlamalar = ortaklar + list(oku(f"{encn}I", sayfa + enc))
                    girdiler = []
                    for k in range(sayi):
                        x, = oku("I", sayfa + off + k * 4)
                        girdiler.append((taban + (x & 0xffffff), kodlamalar[x >> 24]))
                else:
                    raise ValueError(f"Bilinmeyen unwind sayfası: {tur}")
                for off, enc in girdiler:
                    if enc and not enc & 0x80000000 and self.kodda(self.taban + off):
                        sonuc.add(self.taban + off)
        # Compact kaydı olmayan DWARF FDE'leri de stripped kopyadan okunur.
        if any(s.ad == "__eh_frame" and s.boy for s in self.bolumler):
            dump = calistir(["objdump", "--dwarf=frames", self.yol])
            for a in re.findall(r"\bFDE\b[^\n]*\bpc=([0-9a-fA-F]+)\.\.\.?", dump):
                if self.kodda(int(a, 16)):
                    sonuc.add(int(a, 16))
        return sonuc

    def kod_verisi(self):
        sonuc, b = [], self.veri(0x29)                  # LC_DATA_IN_CODE
        if len(b) % 8:
            raise ValueError("Eksik LC_DATA_IN_CODE girdisi")
        for i in range(0, len(b), 8):
            off, boy, tur = struct.unpack_from("<IHH", b, i)
            for s in self.kod:
                if s.ofset <= off < s.ofset + s.boy:
                    if off + boy > s.ofset + s.boy:
                        raise ValueError("Kod içi veri bölüm sınırını aşıyor")
                    a = s.adres + off - s.ofset
                    sonuc.append((a, a + boy, tur))
                    break
            else:
                raise ValueError("LC_DATA_IN_CODE desteklenen __text dışında")
        return sorted(sonuc)

    def stringler(self):
        sonuc = {}
        for s in self.bolumler:
            if s.ad != "__cstring":
                continue
            b, i = self.bayt[s.ofset:s.ofset + s.boy], 0
            while i < len(b):
                j = b.find(b"\0", i)
                j = len(b) if j < 0 else j
                sonuc[s.adres + i] = b[i:j].decode("utf-8", "replace")
                i = j + 1
        return sonuc

    def ithaller(self):
        """Stub/GOT adresleri ve dyld bind kayıtları; objdump'ın <ad+ofset> tahmini kullanılmaz."""
        sonuc = {}
        if 0xb in self.komutlar:                       # LC_DYSYMTAB
            cmd = self.oku("20I", self.komutlar[0xb])
            off, n = cmd[14:16]
            dolayli = self.oku(f"{n}I", off)
            for s in self.bolumler:
                tur = s.bayrak & 255
                if tur not in (6, 7, 8, 0x10):        # non-lazy/lazy pointers, stubs, lazy dylib
                    continue
                adim = s.adim if tur == 8 else 8
                if not adim:
                    raise ValueError("Sıfır boylu stub")
                for j in range(s.boy // adim):
                    ix = dolayli[s.dolayli + j]
                    if ix & 0xc0000000:               # INDIRECT_SYMBOL_LOCAL/ABS
                        continue
                    _, ad, t, _ = self.semboller[ix]
                    if t & 0x0e == 0:
                        sonuc[s.adres + j * adim] = ad
        dump = calistir(["objdump", "--macho", "--bind", "--lazy-bind", self.yol])
        for satir in dump.splitlines():
            m = re.match(r"^__\S+\s+__\S+\s+0x([0-9a-fA-F]+)\s+.+\s+(_\S+)\s*$", satir)
            if m:
                sonuc[int(m[1], 16)] = csym(m[2])
        return sonuc


def kod_araliklari(bas, son, veriler):
    for a, b, _ in veriler:
        if b <= bas or a >= son:
            continue
        if bas < a:
            yield bas, a
        bas = max(bas, b)
    if bas < son:
        yield bas, son


@dataclass
class Komut:
    adres: int
    boy: int
    metin: str


def ayristir(m, baslar, veriler):
    """Veri aralıklarını objdump'a vermeden çöz; sembol başlıklarını tamamen yok say."""
    s = m.kod[0]
    sinirlar = sorted(baslar) + [s.adres + s.boy]
    araliklar = [aralik for bas, son in zip(sinirlar, sinirlar[1:])
                for aralik in kod_araliklari(bas, son, veriler)]
    def coz(aralik):
        bas, son = aralik
        sonuc = []
        dump = calistir(["objdump", "-d", "--section=__text", "--disassemble-zeroes",
                        "--x86-asm-syntax=intel", f"--start-address={bas}",
                        f"--stop-address={son}", m.yol])
        beklenen = bas
        for satir in dump.splitlines():
            es = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s+)+)\s*(\S.*)$", satir)
            if not es:
                continue
            a, boy, metin = int(es[1], 16), len(es[2].split()), es[3]
            # Linker nesneler arasına tek sayıda sıfır doldurabilir. Sonraki
            # fonksiyonun ilk baytını bu dolguya ekleyip sahte 'add' üretme.
            off = s.ofset + a - s.adres
            if a == beklenen and m.bayt[off] == 0 and not any(m.bayt[off:s.ofset + son - s.adres]):
                beklenen = son
                break
            if a != beklenen or a + boy > son or "<unknown>" in metin or metin.startswith(".byte"):
                raise ValueError(f"Çözülemeyen/kod dışına taşan komut: {satir.strip()}")
            sonuc.append(Komut(a, boy, metin))
            beklenen = a + boy
        if beklenen != son:
            raise ValueError(f"Eksik disassembly: {beklenen:#x}..{son:#x}")
        return sonuc
    with ThreadPoolExecutor(8) as havuz:
        sonuc = [k for grup in havuz.map(coz, araliklar) for k in grup]
    adresler = {k.adres for k in sonuc}
    if set(baslar) - adresler:
        raise ValueError("Fonksiyon başlangıcı komut sınırında değil veya veri içinde")
    return sonuc


DAL = re.compile(r"^((?:(?:bnd|notrack)\s+)?(?:call\w*|j\w+|loop\w*)\s+)0x([0-9a-f]+)\b")
RIP = re.compile(r"\[rip(?:\s*([+-])\s*(0x[0-9a-f]+|\d+))?\]")


class Gorunum:
    def __init__(self, m, baslar, ithaller, proje, opt, kip, tohum):
        self.m, self.baslar, self.ithaller = m, sorted(baslar), ithaller
        rnd = random.Random(f"{proje}-{opt}-{tohum}-bin")
        karisik = self.baslar[:]
        rnd.shuffle(karisik)
        self.kimlik = {a: f"sub_{i:04x}" for i, a in enumerate(karisik)}
        self.exportlar = {a: ad for a, ad, t, _ in m.tanimli() if t & 1 and not t & 0x10}
        self.adlar = {a: self.exportlar.get(a, ad) if kip == "yerel" else ad
                      for a, ad in self.kimlik.items()}
        self.strs, self.veriler, self.kip = m.stringler(), {}, kip

    def veri_adlari(self, adresler, proje, opt, tohum):
        a = sorted(set(adresler))
        random.Random(f"{proje}-{opt}-{tohum}-veri").shuffle(a)
        self.veriler = {adres: f"dat_{i:04x}" for i, adres in enumerate(a)}

    def hedef(self, a):
        if a in self.ithaller:
            return self.ithaller[a]
        if a in self.adlar:
            return self.adlar[a]
        if (s := string_bul(self.strs, a)) is not None:
            return string_goster(s)
        if self.kip == "yerel" and a in self.exportlar:
            return self.exportlar[a]
        # Başka fonksiyonun içindeki hedef de adres/ofset taşımadan anonim kalır.
        if self.m.kodda(a):
            i = bisect.bisect_right(self.baslar, a) - 1
            if i >= 0:
                return self.adlar[self.baslar[i]]
        return self.veriler.get(a, "veri")

    def anonimlestir(self, komutlar):
        adresler = {k.adres for k in komutlar}
        etiketler, sonuc = {}, []
        for k in komutlar:
            # Semboller objdump tarafından en yakın export'a göre yakıştırılabilir.
            s = re.sub(r"\s*##.*$", "", k.metin)
            s = re.sub(r"\s*<[^>]*>", "", s).strip()
            yorum = None
            if (d := DAL.match(s)):
                a = int(d[2], 16)
                if a in adresler and not (s.lstrip().startswith("call") and a == komutlar[0].adres):
                    hedef = etiketler.setdefault(a, f"loc_{len(etiketler) + 1}")
                else:
                    hedef = self.hedef(a)
                    yorum = hedef                       # v3 bağlam/import özeti için
                s = DAL.sub(lambda _: d[1] + hedef, s, count=1)
            if (r := RIP.search(s)):
                fark = int(r[2], 0) if r[2] else 0
                a = k.adres + k.boy + (-fark if r[1] == "-" else fark)
                yorum = self.hedef(a)
                s = RIP.sub("[rip]", s)
            # PIC dışı mutlak bellek operandları da adres sütunu gibi anonimdir.
            def mutlak(m):
                return "[" + self.hedef(int(m[1], 16)) + "]"
            s = re.sub(r"\[0x([0-9a-f]+)\]", mutlak, s)
            if yorum:
                s += f"    ; -> {yorum}"
            sonuc.append((k.adres, s))
        satirlar = []
        for a, s in sonuc:
            if a in etiketler:
                satirlar.append(etiketler[a] + ":")
            satirlar.append(s)
        return "\n".join(satirlar).replace(EV, "~")


def kaynak_esle(harita, nesneler):
    """Link map yalnız dosya etiketi için; boy/sınır alanları kullanılmaz."""
    dosyalar, sonuc = {}, {}
    # Linker string sabitlerini de haritaya ham baytlarla yazabilir (örn. Lua \x93).
    for s in harita.read_text(errors="replace").splitlines():
        if (m := re.match(r"^\[\s*(\d+)\]\s+(.+)$", s)):
            dosyalar[int(m[1])] = nesneler.get(str(Path(m[2]).resolve()))
        elif (m := re.match(r"^(0x[0-9a-fA-F]+)\s+0x[0-9a-fA-F]+\s+\[\s*(\d+)\]\s+(.+)$", s)):
            sonuc[(int(m[1], 16), csym(m[3]))] = dosyalar.get(int(m[2]))
    return sonuc


def sizinti_kontrolu(satirlar, gercekler, exportlar, ithaller):
    """String ipuçları ile beklenmeyen sembol sızıntısını ayır; kısa adları da denetle."""
    adlar = {ad for ad in gercekler if len(ad) > 1}
    ihlal, yapisal = [], []
    for r in satirlar:
        metin = r["asm"] + "\n" + r["baglam"]
        kod = re.sub(r'"(?:\\.|[^"\\])*"', '""', metin)
        izinli = set(ithaller) | (set(exportlar) if r["kip"] == "yerel" else set())
        sozcukler = set(re.findall(r"[A-Za-z_][\w.$]*", kod))
        # Adlar yalnız operand/yorum konumunda aranır; 'push' gibi C adları mnemonic olabilir.
        operandlar = "\n".join(s.partition("\t")[2] if "\t" in s else s
                               for s in kod.splitlines() if not re.match(r"^loc_\d+:$", s))
        bulunan = sorted((sozcukler & adlar) - izinli)
        bulunan = [ad for ad in bulunan if re.search(rf"(?<![\w.$]){re.escape(ad)}(?![\w.$])", operandlar)]
        if bulunan:
            ihlal.append({"id": r["id"], "adlar": bulunan})
        if re.search(r"(?m)^\s*[0-9a-f]+:\s|\b(?:call|j\w+|loop\w*)\s+0x|\[rip\s*[+-]|##|<[^>]+>", kod):
            yapisal.append(r["id"])
    return {"beklenmeyen_semboller": ihlal, "adres_bicim_ihlalleri": yapisal}


def cikar(kok, cikti, dosyalar=("*.c",), haric=(), bayraklar=(), proje=None, surum=None,
          en_az=6, en_cok=300, tohum=7, kipler=("yerel", "tam"), v3=False):
    proje = proje or kok.name
    kaynaklar = sorted({c for d in dosyalar for c in kok.glob(d)} - {c for h in haric for c in kok.glob(h)})
    if not kaynaklar:
        raise ValueError(f"Yerel C kaynağı bulunamadı: {kok}")
    hepsi, rapor = [], {"proje": proje, "surum": surum, "hedef": HEDEF,
        "clang": calistir(["clang", "--version"]).splitlines()[0],
        "bayraklar": list(bayraklar), "min": en_az, "max": en_cok, "tohum": tohum,
        "optimizasyonlar": {}}
    with tempfile.TemporaryDirectory(prefix="asm-bin-") as t:
        for opt in OPTS:
            dizin = Path(t) / opt[1:]
            dizin.mkdir()
            nesneler = {str((dizin / f"{i}.o").resolve()): c.relative_to(kok).as_posix()
                        for i, c in enumerate(kaynaklar)}
            def derle_tek(is_):
                c, o = is_
                return derle(c, opt, Path(o), list(bayraklar), kok)
            with ThreadPoolExecutor(8) as havuz:
                durum = list(havuz.map(derle_tek, zip(kaynaklar, nesneler)))
            hatali = [c.relative_to(kok).as_posix() for c, iyi in zip(kaynaklar, durum) if not iyi]
            if hatali:
                raise RuntimeError(f"{proje} {opt}: derlenemeyenler: {', '.join(hatali)}; eksik dylib üretilmedi")
            asil, stripped, harita = dizin / "asil.dylib", dizin / "stripped.dylib", dizin / "link.map"
            link = ["clang", "-target", HEDEF, "-dynamiclib", *nesneler,
                    "-Wl,-no_deduplicate", f"-Wl,-map,{harita}", "-o", asil]
            # Aynı gövdeli farklı fonksiyonların etiketlerini tek adreste birleştirme.
            r = subprocess.run([str(x) for x in link], capture_output=True, text=True)
            dinamik = False
            if r.returncode:
                if "Undefined symbols" not in r.stderr:
                    raise RuntimeError(r.stderr.strip())
                calistir(link + ["-Wl,-undefined,dynamic_lookup"])
                dinamik = True
            calistir(["strip", "-x", "-o", stripped, asil])
            m, dogru = MachO(stripped), MachO(asil)
            lc, uw, veriler = m.baslangiclar(), m.unwind(), m.kod_verisi()
            baslar = sorted(lc | uw)
            if not baslar:
                raise ValueError(f"{proje} {opt}: stripped binary'de başlangıç/unwind yok")
            isimler = {}
            for a, ad, _, b in dogru.tanimli():
                if any(s.indis == b for s in dogru.kod):
                    isimler.setdefault(a, []).append(ad)
            dosya_adlari = kaynak_esle(harita, nesneler)
            komutlar = ayristir(m, baslar, veriler)
            gruplar = {a: [] for a in baslar}
            for k in komutlar:
                gruplar[baslar[bisect.bisect_right(baslar, k.adres) - 1]].append(k)
            ithaller = m.ithaller()
            refler = []
            for k in komutlar:
                if (r := RIP.search(k.metin)):
                    fark = int(r[2], 0) if r[2] else 0
                    refler.append(k.adres + k.boy + (-fark if r[1] == "-" else fark))
                refler.extend(int(a, 16) for a in re.findall(r"\[0x([0-9a-f]+)\]", k.metin))
            bilgi = {"lc_function_starts": len(lc), "unwind": len(uw), "unwind_ek": len(uw - lc),
                     "sinir": len(baslar), "eslesen": len(set(baslar) & isimler.keys()),
                     "adsiz_baslangiclar": [hex(a) for a in baslar if a not in isimler],
                     "sinirsiz_semboller": [{"adres": hex(a), "adlar": ads} for a, ads in sorted(isimler.items()) if a not in gruplar],
                     "cok_adli_adresler": [{"adres": hex(a), "adlar": ads} for a, ads in sorted(isimler.items()) if len(ads) > 1],
                     "data_in_code": len(veriler), "atlanan_veri_bayti": sum(b - a for a, b, _ in veriler),
                     "cozulen_komut": len(komutlar),
                     "sifir_dolgu_bayti": m.kod[0].adres + m.kod[0].boy - baslar[0]
                         - sum(k.boy for k in komutlar) - sum(b - a for a, b, _ in veriler),
                     "dynamic_lookup": dinamik, "kipler": {}}
            for kip in kipler:
                gor = Gorunum(m, baslar, ithaller, proje, opt, kip, tohum)
                gor.veri_adlari(refler, proje, opt, tohum)
                asmler = {a: gor.anonimlestir(ks) for a, ks in gruplar.items()}
                ozetler = {gor.kimlik[a]: fonksiyon_ozeti(gor.kimlik[a], len(gruplar[a]), asm)
                           for a, asm in asmler.items()}
                satirlar, elenen = [], Counter()
                for a, asm in asmler.items():
                    ads = sorted(isimler.get(a, []))
                    if not ads:
                        elenen["adsiz"] += 1
                        continue
                    if len(ads) > 1:
                        elenen["cok_adli"] += 1           # belirsiz doğru cevap üretme
                        continue
                    ad, n = ads[0], len(gruplar[a])
                    if "." in ad:
                        elenen["derleyici_parcasi"] += 1
                        continue
                    if not en_az <= n <= en_cok:
                        elenen["kisa" if n < en_az else "uzun"] += 1
                        continue
                    dosya = dosya_adlari.get((a, ad)) or "?"
                    baglam = "\n".join(ozetler[h] for h in ic_cagrilar(asm) if h in ozetler)
                    satirlar.append({"id": f"{proje}/{dosya}:{opt}:{kip}:{gor.kimlik[a]}:{ad}",
                        "proje": proje, "surum": surum, "dosya": dosya, "opt": opt, "kip": kip,
                        "ad": ad, "kimlik": gor.kimlik[a], "export": a in gor.exportlar,
                        "komut_sayisi": n, "sizinti": sizar_mi(ad, asm) or sizar_mi(ad, baglam),
                        "asm": asm, "baglam": baglam})
                kontrol = sizinti_kontrolu(satirlar, [ad for _, ad, _, _ in dogru.tanimli()],
                                          gor.exportlar.values(), ithaller.values())
                bilgi["kipler"][kip] = {"satir": len(satirlar), "sizinti": sum(r["sizinti"] for r in satirlar),
                    "export": sum(r["export"] for r in satirlar), "elenen": dict(elenen), **kontrol}
                hepsi.extend(satirlar)
            rapor["optimizasyonlar"][opt] = bilgi
            print(f"{proje} {opt}: {len(baslar)} sınır, {bilgi['eslesen']} ad eşleşti; "
                  f"{len(veriler)} veri bölgesi/{bilgi['atlanan_veri_bayti']} bayt atlandı", flush=True)
    cikti.parent.mkdir(parents=True, exist_ok=True)
    if v3:
        v3_yolu = cikti.parent / "v3" / cikti.name
        cikar_v3(kok, v3_yolu, dosyalar, haric, bayraklar, proje, surum, en_az, en_cok, tohum)
        eski = [json.loads(s) for s in v3_yolu.read_text().splitlines()]
        rapor["v3_karsilastirma"] = karsilastir(eski, hepsi)
    rapor_yolu = cikti.with_suffix(".rapor.json")
    rapor_yolu.write_text(json.dumps(rapor, ensure_ascii=False, indent=2) + "\n")
    if any(k["beklenmeyen_semboller"] or k["adres_bicim_ihlalleri"]
           for o in rapor["optimizasyonlar"].values() for k in o["kipler"].values()):
        raise ValueError(f"Sızıntı/biçim denetimi başarısız; ayrıntı: {rapor_yolu}")
    # Denetim başarısızsa mevcut sağlam veri dosyasına dokunma.
    with tempfile.NamedTemporaryFile(mode="w", dir=cikti.parent, delete=False, encoding="utf-8") as f:
        ara = Path(f.name)
        try:
            for r in hepsi:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.close()
            ara.replace(cikti)
        finally:
            ara.unlink(missing_ok=True)
    print(f"{proje}: {len(hepsi)} satır → {cikti}; denetim → {rapor_yolu}")
    return len(hepsi)


def karsilastir(eski, yeni):
    sonuc = {}
    for opt in OPTS:
        once = [r for r in eski if r["opt"] == opt]
        sonra = [r for r in yeni if r["opt"] == opt and r["kip"] == "tam"]
        if not sonra:
            sonra = [r for r in yeni if r["opt"] == opt]
        a = {(r["dosya"], r["ad"]): r for r in once}
        b = {(r["dosya"], r["ad"]): r for r in sonra}
        ortak = sorted(a.keys() & b.keys())
        farklar = sorted(ortak, key=lambda k: -abs(b[k]["komut_sayisi"] - a[k]["komut_sayisi"]))
        sonuc[opt] = {"v3": len(once), "v4_tek_kip": len(sonra), "ortak": len(ortak),
            "v3_sizinti": sum(r["sizinti"] for r in once),
            "v4_sizinti": sum(r["sizinti"] for r in sonra),
            "yalniz_v3": [list(k) for k in sorted(a.keys() - b.keys())],
            "yalniz_v4": [list(k) for k in sorted(b.keys() - a.keys())],
            "ornekler": [{"dosya": k[0], "ad": k[1], "v3_komut": a[k]["komut_sayisi"],
                          "v4_komut": b[k]["komut_sayisi"], "v3_asm": a[k]["asm"],
                          "v4_asm": b[k]["asm"]} for k in farklar[:3]]}
    return sonuc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kaynak", nargs="*", help="yerel kaynak dizini veya --projeler ile adlar")
    ap.add_argument("--projeler", type=Path)
    ap.add_argument("-o", "--cikti", type=Path)
    ap.add_argument("--veri", type=Path, default=Path("veri/bin"))
    ap.add_argument("-b", "--bayrak", action="append", default=[])
    ap.add_argument("--kip", choices=("yerel", "tam", "ikisi"), default="ikisi")
    ap.add_argument("--min", type=int, default=6)
    ap.add_argument("--max", type=int, default=300)
    ap.add_argument("--tohum", type=int, default=7)
    ap.add_argument("--v3-karsilastir", action="store_true", help="aynı kaynak/bayraklarla v3'ü yerelde yeniden üret")
    a = ap.parse_args()
    if a.min < 1 or a.max < a.min:
        ap.error("1 <= min <= max olmalı")
    if a.projeler:
        projeler = json.loads(a.projeler.read_text())
        eksik = set(a.kaynak) - {p["ad"] for p in projeler}
        if eksik:
            ap.error(f"Bilinmeyen projeler: {', '.join(sorted(eksik))}")
        projeler = [p for p in projeler if not a.kaynak or p["ad"] in a.kaynak]
    else:
        if len(a.kaynak) != 1:
            ap.error("Bir yerel kaynak dizini veya --projeler gerekli")
        projeler = [{"ad": Path(a.kaynak[0]).name, "kok": a.kaynak[0]}]
    if a.cikti and len(projeler) != 1:
        ap.error("-o yalnız tek projeyle kullanılabilir")
    for p in projeler:
        kok = Path(p.get("kok", str(Path("kaynak") / p["ad"])))
        if not kok.is_dir():
            ap.error(f"Yerel kaynak yok: {kok}; ağdan indirme yapılmaz")
        cikar(kok, a.cikti or a.veri / f"{p['ad']}.jsonl", p.get("dosyalar", ["*.c"]),
              p.get("haric", []), p.get("bayraklar", []) + a.bayrak, p["ad"], p.get("surum"),
              a.min, a.max, a.tohum, ("yerel", "tam") if a.kip == "ikisi" else (a.kip,), a.v3_karsilastir)


if __name__ == "__main__":
    main()
