#!/usr/bin/env python3
"""Saklanan stripped Mach-O ikililerindeki eşlenmiş fonksiyonları Ghidra ile decompile et.

Örnek:
  ~/araclar/ghidra-venv/bin/python decompile_ghidra.py veri/ikili/test2000 \
    --idler lora/test_sabit_idler.txt -o veri/decompile/test2000.jsonl --devam
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import warnings
from collections import defaultdict
from pathlib import Path

from cikar_bin import MachO

warnings.filterwarnings("ignore", message=r"open_program\(\) is deprecated", category=DeprecationWarning)


OTOMATIK_AD = re.compile(r"^(?:FUN|DAT|LAB|PTR|UNK|OFF|switchD|jumptable)_[0-9a-fA-F_]+$")
TIRNAK = re.compile(r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')', re.DOTALL)


def java_yineleyici(yineleyici):
    while yineleyici.hasNext():
        yield yineleyici.next()


def id_adi(kimlik):
    return kimlik.rsplit(":", 1)[-1]


def ad_geciyor(metin, ad):
    """Gerçek ad, C tanımlayıcısı sınırlarında ham decompile içinde geçiyor mu?"""
    if not ad:
        return False
    desen = rf"(?<![A-Za-z0-9_])_?{re.escape(ad)}(?![A-Za-z0-9_])"
    return re.search(desen, metin, re.IGNORECASE) is not None


def _adlari_degistir(metin, ad_haritasi):
    """String/karakter sabitlerine dokunmadan proje-içi tanımlayıcıları değiştir."""
    ad_haritasi = {ad: yeni for ad, yeni in ad_haritasi.items()
                   if ad and yeni and ad != yeni}
    if not ad_haritasi:
        return metin
    # Uzun adı önce işlemek, önek taşıyan adlarda gereksiz ikinci eşleşmeyi önler.
    desen = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(
        re.escape(ad) for ad in sorted(ad_haritasi, key=len, reverse=True)) + r")(?![A-Za-z0-9_])")
    parcalar = TIRNAK.split(metin)
    for i in range(0, len(parcalar), 2):
        parcalar[i] = desen.sub(lambda m: ad_haritasi[m.group(1)], parcalar[i])
    return "".join(parcalar)


def anonimlestir_decompile(metin, gercek_ad, ad_haritasi, anonim_ad):
    """Decompile metnini anonimleştir ve hedef adın ham metindeki sızıntısını bildir."""
    sizinti = ad_geciyor(metin, gercek_ad)
    harita = dict(ad_haritasi)
    harita[gercek_ad] = anonim_ad
    harita["_" + gercek_ad] = anonim_ad
    return _adlari_degistir(metin, harita), sizinti


def eslemeleri_oku(dizin, idler=None):
    """Eşlemeleri ikiliye göre grupla; ikili yolu JSONL dosyasına göre çözülür."""
    istenen = set(idler) if idler is not None else None
    gruplar, gorulen = defaultdict(list), set()
    for yol in sorted(Path(dizin).glob("**/*.jsonl")):
        for no, satir in enumerate(yol.open(), 1):
            if not satir.strip():
                continue
            r = json.loads(satir)
            if not {"id", "adres", "boyut", "ikili"} <= r.keys():
                raise SystemExit(f"{yol}:{no}: id/adres/boyut/ikili alanı eksik")
            if istenen is not None and r["id"] not in istenen:
                continue
            if r["id"] in gorulen:
                raise SystemExit(f"eşlemelerde yinelenen id: {r['id']}")
            gorulen.add(r["id"])
            ikili = Path(r["ikili"])
            if not ikili.is_absolute():
                ikili = yol.parent / ikili
            gruplar[ikili.resolve()].append(r)
    if istenen is not None:
        eksik = [x for x in idler if x not in gorulen]
        if eksik:
            print(f"eşlemesi bulunmayan id: {len(eksik)}", file=sys.stderr)
    return gruplar


def dis_fonksiyon(fonksiyon):
    if fonksiyon is None or fonksiyon.isExternal():
        return True
    try:
        return bool(fonksiyon.isThunk() and fonksiyon.getThunkedFunction(True) is not None and
                    fonksiyon.getThunkedFunction(True).isExternal())
    except Exception:
        return False


def sembol_haritasi(program, satirlar, izinli=()):
    """Dış importlar hariç Ghidra'nın gördüğü proje sembollerini anonim ada bağla."""
    izinli = set(izinli)
    kimlikler = {int(r["adres"]): r.get("kimlik") or r["id"].rsplit(":", 2)[-2]
                 for r in satirlar}
    harita = {}
    for fonksiyon in java_yineleyici(program.getFunctionManager().getFunctions(True)):
        if dis_fonksiyon(fonksiyon):
            continue
        ad = str(fonksiyon.getName())
        adres = fonksiyon.getEntryPoint().getOffset()
        if ad not in izinli and not OTOMATIK_AD.match(ad):
            harita[ad] = kimlikler.get(adres, f"FUN_{adres:x}")

    # Export edilmiş proje verileri de sözde kodda anlamlı ad taşımamalı.
    for sembol in java_yineleyici(program.getSymbolTable().getAllSymbols(True)):
        try:
            adres = sembol.getAddress()
            if sembol.isExternal() or adres is None or not adres.isMemoryAddress():
                continue
            tur = str(sembol.getSymbolType()).upper()
            if "LABEL" not in tur and "FUNCTION" not in tur:
                continue
            ad = str(sembol.getName())
            if ad not in izinli and ad not in harita and not OTOMATIK_AD.match(ad):
                harita[ad] = f"DAT_{adres.getOffset():x}"
        except Exception:
            continue

    # Filtrelenmiş satırlardaki gerçek adlar, sembol yineleyicisinden düşmüş olsa da gizlensin.
    ad_adresleri = defaultdict(set)
    for r in satirlar:
        ad_adresleri[id_adi(r["id"])].add(int(r["adres"]))
    for ad, adresler in ad_adresleri.items():
        if len(adresler) == 1:
            adres = next(iter(adresler))
            harita.setdefault(ad, kimlikler[adres])
            harita.setdefault("_" + ad, kimlikler[adres])
    return harita


def ithal_haritasi(ikili):
    """Mach-O stub/GOT adreslerini Ghidra'nın FUN_/DAT_ yazımlarından import adına bağla."""
    sonuc = {}
    for adres, ad in MachO(ikili).ithaller().items():
        for on_ek in ("FUN", "DAT", "PTR"):
            for genislik in (0, 8, 16):
                sayi = f"{adres:x}" if not genislik else f"{adres:0{genislik}x}"
                sonuc[f"{on_ek}_{sayi}"] = ad
                sonuc[f"{on_ek}_{sayi.upper()}"] = ad
    return sonuc


def fonksiyon_bul_veya_olustur(flat_api, adres, boyut):
    program = flat_api.getCurrentProgram()
    hedef = flat_api.toAddr(adres)
    fonksiyon = program.getFunctionManager().getFunctionAt(hedef)
    if fonksiyon is not None:
        return fonksiyon
    # Mach-O loader nadiren LC_FUNCTION_STARTS girdisini fonksiyona çevirmeyebilir.
    # Yanlış bir kapsayan fonksiyonu kullanmak yerine kayıtlı aralıkla yenisini oluştur.
    try:
        from ghidra.program.model.address import AddressSet
        from ghidra.program.model.symbol import SourceType
        flat_api.disassemble(hedef)
        govde = AddressSet(hedef, hedef.add(max(0, boyut - 1)))
        return program.getFunctionManager().createFunction(
            f"FUN_{adres:x}", hedef, govde, SourceType.ANALYSIS)
    except Exception:
        return None


def ikiliyi_decompile_et(ikili, satirlar, zaman_asimi, ithaller=None):
    import pyghidra
    from ghidra.app.decompiler import DecompInterface, DecompileOptions
    from ghidra.util.task import ConsoleTaskMonitor

    sonuc, sayac = {}, defaultdict(int)
    with tempfile.TemporaryDirectory(prefix="ghidra-decompile-") as proje_dizini:
        with pyghidra.open_program(ikili, project_location=proje_dizini,
                                  project_name="decompile", analyze=True) as flat_api:
            program = flat_api.getCurrentProgram()
            ithaller = ithaller if ithaller is not None else ithal_haritasi(ikili)
            ithal_adlari = set(ithaller.values())
            harita = sembol_haritasi(
                program, satirlar, ithal_adlari | {"_" + ad for ad in ithal_adlari})
            harita.update(ithaller)
            harita.update({"_" + ad: ad for ad in ithal_adlari})
            arayuz = DecompInterface()
            secenekler = DecompileOptions()
            secenekler.grabFromProgram(program)
            arayuz.setOptions(secenekler)
            arayuz.toggleCCode(True)
            arayuz.toggleSyntaxTree(True)
            arayuz.setSimplificationStyle("decompile")
            if not arayuz.openProgram(program):
                raise RuntimeError("Ghidra decompiler programı açamadı: " + str(arayuz.getLastMessage()))
            monitor = ConsoleTaskMonitor()
            try:
                for r in satirlar:
                    fonksiyon = fonksiyon_bul_veya_olustur(
                        flat_api, int(r["adres"]), int(r["boyut"]))
                    if fonksiyon is None:
                        sayac["fonksiyon_yok"] += 1
                        continue
                    d = arayuz.decompileFunction(fonksiyon, zaman_asimi, monitor)
                    if d.isTimedOut():
                        sayac["zaman_asimi"] += 1
                        continue
                    if not d.decompileCompleted() or d.getDecompiledFunction() is None:
                        sayac["basarisiz"] += 1
                        continue
                    ham = str(d.getDecompiledFunction().getC()).strip()
                    kimlik = r.get("kimlik") or r["id"].rsplit(":", 2)[-2]
                    metin, sizinti = anonimlestir_decompile(
                        ham, id_adi(r["id"]), harita, kimlik)
                    sonuc[r["id"]] = {"id": r["id"], "decompile": metin,
                                       "sizinti": sizinti}
                    sayac["basarili"] += 1
            finally:
                arayuz.dispose()
    return sonuc, sayac


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ikili_dizini", type=Path, help="cikar_bin.py --ikili-sakla çıktısı")
    ap.add_argument("-o", "--cikti", type=Path, required=True)
    ap.add_argument("--idler", type=Path, help="yalnız bu id'leri ve bu sırayı kullan")
    ap.add_argument("--ghidra", type=Path,
                    default=Path("~/araclar/ghidra_12.1.4_PUBLIC").expanduser())
    ap.add_argument("--java-home", type=Path,
                    help="JDK kökü (macOS'ta varsayılan /usr/libexec/java_home çıktısı)")
    ap.add_argument("--decompiler", type=Path,
                    help="Ghidra paketinde platform ikilisi yoksa decompile yürütülebilirinin yolu")
    ap.add_argument("--zaman-asimi", type=int, default=60, help="fonksiyon başına saniye")
    ap.add_argument("--devam", action="store_true", help="mevcut/ara başarılı satırları yeniden üretme")
    a = ap.parse_args()
    if a.zaman_asimi < 1:
        ap.error("--zaman-asimi en az 1 olmalı")
    idler = ([x.strip() for x in a.idler.read_text().splitlines() if x.strip()]
             if a.idler else None)
    gruplar = eslemeleri_oku(a.ikili_dizini, idler)
    if not gruplar:
        raise SystemExit("decompile edilecek eşleme yok")
    eksik_ikili = [str(yol) for yol in gruplar if not yol.is_file()]
    if eksik_ikili:
        raise SystemExit(f"ikili yok: {eksik_ikili[0]}")
    # JVM başlatılmadan önce macOS objdump ile çöz; PyGhidra çalışma zamanı
    # subprocess ortamını değiştirse bile dış sembol adları kaybolmasın.
    ithaller = {ikili: ithal_haritasi(ikili) for ikili in gruplar}

    try:
        import pyghidra
    except ImportError:
        raise SystemExit("PyGhidra yok; betiği ~/araclar/ghidra-venv/bin/python ile çalıştırın")
    from pyghidra import HeadlessPyGhidraLauncher
    launcher = HeadlessPyGhidraLauncher(install_dir=a.ghidra)
    java_home = a.java_home
    if java_home is None and Path("/usr/libexec/java_home").is_file():
        java_home = Path(subprocess.check_output(
            ["/usr/libexec/java_home"], text=True).strip())
    if java_home is not None:
        launcher.java_home = java_home
    # Yönetilen/salt-okunur ev dizinlerinde Ghidra tercih dosyalarını /tmp'de tut.
    ayar_dizini = tempfile.mkdtemp(prefix="ghidra-user-")
    os.environ.setdefault("XDG_CONFIG_HOME", ayar_dizini)
    launcher.add_vmargs(f"-Duser.home={ayar_dizini}")
    launcher.start()
    if a.decompiler is not None:
        if not a.decompiler.is_file():
            raise SystemExit(f"--decompiler bulunamadı: {a.decompiler}")
        from ghidra.app.decompiler import DecompileProcessFactory
        alan = DecompileProcessFactory.class_.getDeclaredField("exepath")
        alan.setAccessible(True)
        alan.set(None, str(a.decompiler.resolve()))

    a.cikti.parent.mkdir(parents=True, exist_ok=True)
    ara = a.cikti.with_suffix(".ara")
    tamam = {}
    if a.devam:
        for yol in (a.cikti, ara):
            if yol.exists():
                tamam.update((r["id"], r) for r in map(json.loads, yol.open())
                              if r.get("decompile"))
    sayac = defaultdict(int)
    with ara.open("a" if a.devam else "w") as f:
        for no, (ikili, satirlar) in enumerate(gruplar.items(), 1):
            kalan = [r for r in satirlar if r["id"] not in tamam]
            if not kalan:
                continue
            try:
                yeni, durum = ikiliyi_decompile_et(
                    ikili, kalan, a.zaman_asimi, ithaller[ikili])
            except Exception as hata:
                sayac["basarisiz"] += len(kalan)
                print(f"[{no}/{len(gruplar)}] {ikili.name}: HATA {type(hata).__name__}: {hata}",
                      file=sys.stderr, flush=True)
                continue
            tamam.update(yeni)
            sayac.update(durum)
            for r in yeni.values():
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{no}/{len(gruplar)}] {ikili.parent.name}/{ikili.name}: "
                  f"{durum['basarili']} başarılı, {durum['zaman_asimi']} zaman aşımı, "
                  f"{durum['basarisiz'] + durum['fonksiyon_yok']} başarısız",
                  file=sys.stderr, flush=True)

    sira = idler if idler is not None else [r["id"] for rs in gruplar.values() for r in rs]
    with a.cikti.open("w") as f:
        for kimlik in sira:
            if kimlik in tamam:
                f.write(json.dumps(tamam[kimlik], ensure_ascii=False) + "\n")
    ara.unlink(missing_ok=True)
    print(f"toplam={len(sira)} basarili={sum(x in tamam for x in sira)} "
          f"sizinti={sum(bool(tamam[x].get('sizinti')) for x in sira if x in tamam)} "
          f"zaman_asimi={sayac['zaman_asimi']} "
          f"basarisiz={sayac['basarisiz'] + sayac['fonksiyon_yok']} → {a.cikti}")


if __name__ == "__main__":
    main()
