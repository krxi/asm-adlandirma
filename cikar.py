#!/usr/bin/env python3
"""Açık kaynak C kodunu x86-64'e derle, her fonksiyonu (isim, assembly) çiftine çevir.

Stripped binary'yi taklit eder: projenin kendi fonksiyon adları asm içinden
silinir (sub_N), dış kütüphane çağrıları (memcpy vb.) görünür kalır — gerçek
binary'de de import adları görünür.

  python3 cikar.py kaynak/zlib -o veri/zlib.jsonl
"""
import argparse, json, re, subprocess, tempfile
from pathlib import Path

OPTS = ["-O0", "-O2"]
HEDEF = "x86_64-apple-macos12"
FONK = re.compile(r"^[0-9a-f]+ <(_?[A-Za-z_][\w.$]*)>:$")


def derle(c: Path, opt: str, cikti: Path) -> bool:
    r = subprocess.run(["clang", "-target", HEDEF, opt, "-w", "-c", str(c), "-o", str(cikti)],
                       capture_output=True, text=True)
    return r.returncode == 0


def ayristir(o: Path) -> dict[str, list[str]]:
    dump = subprocess.run(["objdump", "-d", "-r", "--no-show-raw-insn", "--x86-asm-syntax=intel", str(o)],
                          capture_output=True, text=True).stdout
    fonklar, ad = {}, None
    for satir in dump.splitlines():
        m = FONK.match(satir.strip())
        if m:
            ad = m.group(1).lstrip("_")
            fonklar[ad] = []
        elif ad and satir.strip() and "\t" in satir:
            fonklar[ad].append(satir.strip())
    return fonklar


def anonimlestir(satirlar: list[str], ic_adlar: dict[str, str]) -> str:
    out = []
    for s in satirlar:
        s = re.sub(r"^[0-9a-f]+:\s*", "", s)                  # adres sütunu
        if s.startswith(("X86_64_RELOC", "0000")):          # relokasyon satırı → hedefi yorum olarak ekle
            hedef = s.split()[-1].lstrip("_")
            if "." in hedef:                                # fonk.static_degisken → veri (ad sızmasın)
                hedef = "veri"
            hedef = ic_adlar.get(hedef, hedef)
            if out:                                         # .o'da çözülmemiş hedef adresi yanıltıcı, sil
                out[-1] = re.sub(r"\s*(0x[0-9a-f]+ )?<[^>]*>", "", out[-1]).rstrip() + f"    ; -> {hedef}"
            continue
        s = re.sub(r"\s*##.*$", "", s)                       # objdump'ın rip yorumları
        s = re.sub(r"<_?([\w.$]+)(\+0x[0-9a-f]+)?>", lambda m: f"<{ic_adlar.get(m.group(1), 'loc')}{m.group(2) or ''}>", s)
        out.append(s)
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kaynak", type=Path)
    ap.add_argument("-o", "--cikti", type=Path, required=True)
    ap.add_argument("--min", type=int, default=6)
    ap.add_argument("--max", type=int, default=300)
    a = ap.parse_args()

    ham = []  # (dosya, opt, ad, satirlar)
    with tempfile.TemporaryDirectory() as t:
        for c in sorted(a.kaynak.glob("*.c")):
            for opt in OPTS:
                o = Path(t) / f"{c.stem}{opt}.o"
                if derle(c, opt, o):
                    ham += [(c.name, opt, ad, s) for ad, s in ayristir(o).items()]

    tum_adlar = sorted({ad for _, _, ad, _ in ham})
    ic_adlar = {ad: f"sub_{i:04d}" for i, ad in enumerate(tum_adlar)}
    a.cikti.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with a.cikti.open("w") as f:
        for dosya, opt, ad, s in ham:
            komut = [x for x in s if not x.split(":", 1)[-1].strip().startswith(("X86_64_RELOC",))]
            if not (a.min <= len(komut) <= a.max):
                continue
            f.write(json.dumps({"id": f"{dosya}:{opt}:{ad}", "dosya": dosya, "opt": opt, "ad": ad,
                                "komut_sayisi": len(komut), "asm": anonimlestir(s, ic_adlar)}) + "\n")
            n += 1
    print(f"{n} fonksiyon → {a.cikti}")


if __name__ == "__main__":
    main()
