#!/usr/bin/env python3
"""Nesne dosyasındaki ya da yapıştırılan assembly'deki fonksiyonlara ad ve kısa açıklama öner.

  python3 adlandir.py ornek.o --arka-uc sahte                       # model yok: hattı dene
  python3 adlandir.py ornek.o --arka-uc uc --url http://localhost:8000/v1 --model qwen3-8b-asm
  python3 adlandir.py ornek.o --arka-uc hf --taban Qwen/Qwen3-8B --adaptor adaptor-Qwen3-8B
  python3 adlandir.py fonksiyon.s --arka-uc uc ...                   # tek fonksiyonun asm'si (veri biçimi)
  python3 adlandir.py ornek.o --olc -o sonuc/ornek.jsonl              # semboller varsa gerçek adla F1

Girdi:
  ELF ya da Mach-O x86-64 nesne/binary (sembolleri olan): llvm-objdump ile ayrılır, cikar.py'nin
    anonimleştirmesiyle eğitim verisindeki görünüme çevrilir (iç çağrılar sub_XXXX, veri dat_XXXX,
    stringler ; -> "..." yorumu, dış importlar adıyla).
  `objdump -d -r` metni ya da veri setindeki biçimde tek fonksiyonun asm'si.
Sembolleri silinmiş linklenmiş binary'lerde fonksiyon sınırı için Ghidra betiğini kullanın (ghidra/).

Gerçek adlar modele gönderilmez; yalnız --olc ile yerelde puanlama için tutulur.

Arka uçlar:
  uc    OpenAI uyumlu /chat/completions (vLLM, llama.cpp server, Ollama, Evren). Anahtar
        ADLANDIR_API_KEY ya da OPENAI_API_KEY ortam değişkeninden okunur.
  hf    transformers + peft: taban model + LoRA adaptörü (colab/egit.ipynb çıktısı), greedy üretim.
  sahte Model yok; çağrılan importlardan ad uydurur. Hat ve demo denemesi için.
"""

import argparse, json, os, random, re, shutil, subprocess, sys, urllib.request
from pathlib import Path

KOK = Path(__file__).resolve().parent
sys.path.insert(0, str(KOK / "lora"))
import hazirla as h  # noqa: E402
from cikar import FONK, anonimlestir, csym, fonksiyon_ozeti, ic_cagrilar, sizar_mi  # noqa: E402
from taban import f1  # noqa: E402

ELF_RELOK = re.compile(r"^([0-9a-f]+):\s+(R_X86_64_\w+)\s+(\S+)$")
ELF_YORUM = re.compile(r"\s+#\s+0x[0-9a-f]+(?:\s+<[^>]*>)?\s*$")  # llvm-objdump ELF'te tek '#'
EK = re.compile(r"^(.*?)([+-]0x[0-9a-f]+)?$")
SAHTE_ADRES = 0x7F000000  # ELF string bölümlerine anonimlestir'in okuyacağı sahte adresler


# --- ayrıştırma ---------------------------------------------------------------------------------


def objdump_bul() -> str:
    """cikar.py llvm-objdump bayraklarını (--x86-asm-syntax) kullanır; GNU objdump bunları bilmez."""
    if os.environ.get("ADLANDIR_OBJDUMP"):
        return os.environ["ADLANDIR_OBJDUMP"]
    for ad in ("llvm-objdump", *(f"llvm-objdump-{s}" for s in range(22, 13, -1)), "objdump"):
        yol = shutil.which(ad)
        if yol and "LLVM" in subprocess.run([yol, "--version"], capture_output=True, text=True).stdout:
            return yol
    sys.exit(
        "llvm-objdump bulunamadı (macOS'ta Xcode araçları, Linux'ta `apt install llvm`); ADLANDIR_OBJDUMP ile verin"
    )


def bicim(yol: Path) -> str:
    bas = yol.open("rb").read(4)
    if bas == b"\x7fELF":
        return "elf"
    if bas in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf"):
        return "macho"
    return "metin"


def calistir(*komut) -> str:
    r = subprocess.run([str(x) for x in komut], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"{komut[0]} başarısız: {r.stderr.strip()}")
    return r.stdout


def fonksiyonlari_ayir(dump: str) -> dict:
    """`objdump -d -r` çıktısı → ham ad → komut ve relokasyon satırları (cikar.ayristir ile aynı)."""
    fonklar, ad = {}, None
    for satir in dump.splitlines():
        m = FONK.match(satir.strip())
        if m:
            ad = m.group(1)
            fonklar[ad] = []
        elif ad and satir.strip() and "\t" in satir:
            fonklar[ad].append(satir.strip())
    return fonklar


def bolum_stringleri(dump: str) -> dict:
    """`objdump -s --section=X` → ofset/adres → NUL ile biten string (cikar.stringler ile aynı)."""
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


def semboller(arac: str, yol: Path) -> list[tuple]:
    """(değer, bölüm, ad, tanımlı mı) — `objdump -t`."""
    sonuc = []
    for satir in calistir(arac, "-t", yol).splitlines():
        m = re.match(r"^([0-9a-f]{8,16})\s.{7}\s*(\S+)\s+(?:[0-9a-f]{8,16}\s+)?(\S+)$", satir)
        if m:
            sonuc.append((int(m.group(1), 16), m.group(2), m.group(3), m.group(2) != "*UND*"))
    return sonuc


def elf_donustur(satirlar: list[str], str_sembol: dict, str_bolum: dict, strs: dict, veri_sembol=None) -> list[str]:
    """ELF objdump satırlarını cikar.anonimlestir'in beklediği Mach-O görünümüne çevir.

    R_X86_64_* relokasyonu → X86_64_RELOC_* ve '_ad' (Mach-O C sembolü); string bölümüne giden
    relokasyonun komutuna '## 0xADRES' eklenir ve hedef '__cstring' olur, böylece anonimlestir stringi
    yorum olarak yazar. Bölüme göre relokasyon (static değişken: .data-0x4) sembol tablosundan adına
    çözülür (veri_sembol: (bölüm, ofset) → ad); çözülemezse '__data' olur ve 'veri' diye görünür.
    """
    veri_sembol = veri_sembol or {}
    out = []
    for s in satirlar:
        m = ELF_RELOK.match(s)
        if not m:
            out.append(ELF_YORUM.sub("", s))
            continue
        adres, tur, ifade = m.groups()
        ad, ek = EK.match(ifade).groups()
        ek = int(ek, 16) if ek else 0
        hedef = str_sembol.get(ad) or ((ad, 0) if ad in str_bolum else None)
        # PC-göreli relokasyonda ek, alanın komut sonuna uzaklığını (-4) da taşır.
        duzeltme = 4 if tur in ("R_X86_64_PC32", "R_X86_64_PLT32", "R_X86_64_GOTPCREL", "R_X86_64_REX_GOTPCRELX") else 0
        if hedef:
            bolum, deger = hedef
            ofset = deger + ek + duzeltme
            if out:
                out[-1] += f"    ## 0x{str_bolum[bolum] + ofset:x}"
            out.append(f"{adres}:  X86_64_RELOC_SIGNED\t__cstring")
        elif (ad, ek + duzeltme) in veri_sembol:
            out.append(f"{adres}:  X86_64_RELOC_SIGNED\t_{veri_sembol[(ad, ek + duzeltme)]}")
        elif ad.startswith("."):
            out.append(f"{adres}:  X86_64_RELOC_SIGNED\t__data")
        else:
            out.append(f"{adres}:  X86_64_RELOC_BRANCH\t_{ad}")
    return out


def nesneden_fonksiyonlar(yol: Path, arac: str = "") -> tuple:
    """Nesne/binary → (ham ad → satırlar, strings, tanımlı veri adları, biçim)."""
    arac = arac or objdump_bul()
    tur = bicim(yol)
    dump = calistir(arac, "-d", "-r", "--no-show-raw-insn", "--x86-asm-syntax=intel", yol)
    fonklar = fonksiyonlari_ayir(dump)
    sembol = semboller(arac, yol)
    if tur == "macho":
        strs = bolum_stringleri(calistir(arac, "-s", "--section=__cstring", yol))
        veri = {
            csym(ad) for _, b, ad, tanimli in sembol if tanimli and "__text" not in b and not ad.startswith(("l", "L"))
        }
        return {csym(ad): s for ad, s in fonklar.items()}, strs, veri, tur
    str_bolum, strs = {}, {}
    for i, bolum in enumerate(sorted({b for _, b, _, _ in sembol if b.startswith(".rodata.str")})):
        str_bolum[bolum] = SAHTE_ADRES + i * 0x100000
        for ofset, st in bolum_stringleri(calistir(arac, "-s", f"--section={bolum}", yol)).items():
            strs[str_bolum[bolum] + ofset] = st
    str_sembol = {ad: (b, deger) for deger, b, ad, _ in sembol if b in str_bolum}
    veri_sembol = {
        (b, deger): ad
        for deger, b, ad, tanimli in sembol
        if tanimli
        and b.startswith((".data", ".bss", ".rodata"))
        and b not in str_bolum
        and ad != b
        and not ad.startswith(".")
    }
    veri = set(veri_sembol.values())
    fonklar = {ad: elf_donustur(s, str_sembol, str_bolum, strs, veri_sembol) for ad, s in fonklar.items()}
    return fonklar, strs, veri, tur


def kayitlar(fonklar: dict, strs: dict, veri: set, kaynak: str, tohum: int = 7) -> list[dict]:
    """Ham fonksiyonlar → veri setindeki satır biçimi (asm, baglam, kimlik); cikar.cikar ile aynı adımlar."""
    rnd = random.Random(f"{kaynak}-{tohum}")
    fonk_adlari = sorted(fonklar)
    veri_adlari = sorted(set(veri) - set(fonk_adlari))
    rnd.shuffle(fonk_adlari)
    rnd.shuffle(veri_adlari)
    adlar = {ad: f"sub_{i:04x}" for i, ad in enumerate(fonk_adlari)}
    adlar |= {ad: f"dat_{i:04x}" for i, ad in enumerate(veri_adlari)}
    ham = []
    for ad, s in fonklar.items():
        komut = [x for x in s if not x.split(":", 1)[-1].strip().startswith("X86_64_RELOC")]
        asm = anonimlestir(s, adlar, strs, ad)
        ham.append((ad, adlar[ad], len(komut), asm))
    ozet = {kimlik: fonksiyon_ozeti(kimlik, n, asm) for _, kimlik, n, asm in ham}
    sonuc = []
    for ad, kimlik, n, asm in ham:
        if "." in ad or not n:  # derleyici parçası (foo.cold.1) ya da boş
            continue
        baglam = "\n".join(ozet[k] for k in ic_cagrilar(asm) if k in ozet)
        sonuc.append(
            {
                "id": kimlik,
                "ad": ad,
                "komut_sayisi": n,
                "asm": asm,
                "baglam": baglam,
                "baglam_derin": "",
                "sizinti": sizar_mi(ad, asm) or sizar_mi(ad, baglam),
            }
        )
    return sorted(sonuc, key=lambda r: r["id"])


def girdiden_kayitlar(yol: Path, arac: str = "", tohum: int = 7) -> list[dict]:
    if bicim(yol) != "metin":
        fonklar, strs, veri, _ = nesneden_fonksiyonlar(yol, arac)
        return kayitlar(fonklar, strs, veri, yol.name, tohum)
    metin = yol.read_text()
    fonklar = fonksiyonlari_ayir(metin)
    if fonklar:  # objdump -d -r metni; stringler bilinmez
        if any(ELF_RELOK.match(s) for v in fonklar.values() for s in v):
            fonklar = {ad: elf_donustur(s, {}, {}, {}) for ad, s in fonklar.items()}
        else:
            fonklar = {csym(ad): s for ad, s in fonklar.items()}
        return kayitlar(fonklar, {}, set(), yol.name, tohum)
    return [tek_fonksiyon(metin)]


def tek_fonksiyon(asm: str, baglam: str = "") -> dict:
    """Veri setindeki biçimde (zaten anonim) tek fonksiyonun asm'si."""
    asm = asm.strip("\n")
    return {
        "id": "girdi",
        "ad": "",
        "komut_sayisi": sum(1 for s in asm.splitlines() if not s.endswith(":")),
        "asm": asm,
        "baglam": baglam,
        "baglam_derin": "",
        "sizinti": False,
    }


# --- model --------------------------------------------------------------------------------------


def mesajlar(r: dict, baglam: str = "ozet") -> list[dict]:
    """Eğitimdeki istem: hazirla.SISTEM_ACIKLAMA + hazirla.girdi (aynı kesme ve bağlam başlığı)."""
    return [{"role": "system", "content": h.SISTEM_ACIKLAMA}, {"role": "user", "content": h.girdi(r, baglam, 200)}]


def cevap_coz(metin: str) -> dict:
    """lora/olc.py ve Colab ile aynı: son {...} bloğu JSON; yoksa metnin başı ad sayılır."""
    m = re.findall(r"\{[^{}]*\}", metin)
    try:
        cevap = json.loads(m[-1]) if m else {"ad": metin.strip()[:60]}
    except json.JSONDecodeError:
        cevap = {}
    return {"ad": str(cevap.get("ad", "")), "aciklama": str(cevap.get("aciklama", ""))}


class Sahte:
    """Modelsiz: ilk dış importtan ad uydurur. Yalnız hattı ve arayüzü denemek için."""

    def uret(self, msj: list[dict]) -> str:
        asm = msj[1]["content"]
        ithal = [
            m.group(1)
            for m in re.finditer(r";\s*->\s*([A-Za-z_]\w*)\s*$", asm, re.M)
            if not m.group(1).startswith(("sub_", "dat_")) and m.group(1) != "veri"
        ]
        ad = f"{ithal[0]}_sarmalayici" if ithal else "fonksiyon"
        aciklama = f"Sahte model: {', '.join(dict.fromkeys(ithal)) or 'dış çağrı yok'}."
        return json.dumps({"ad": ad, "aciklama": aciklama}, ensure_ascii=False)


class UcNokta:
    """OpenAI uyumlu /chat/completions. Evren gibi X-API-Key isteyenler için --anahtar-basligi."""

    def __init__(self, url: str, model: str, anahtar: str = "", baslik: str = "Authorization", zaman: int = 300):
        self.url, self.model, self.anahtar, self.baslik, self.zaman = url.rstrip("/"), model, anahtar, baslik, zaman

    def uret(self, msj: list[dict]) -> str:
        govde = {"model": self.model, "messages": msj, "temperature": 0, "max_tokens": 256}
        basliklar = {"Content-Type": "application/json"}
        if self.anahtar:
            basliklar[self.baslik] = f"Bearer {self.anahtar}" if self.baslik == "Authorization" else self.anahtar
        istek = urllib.request.Request(
            self.url + "/chat/completions", data=json.dumps(govde).encode(), headers=basliklar
        )
        yanit = json.load(urllib.request.urlopen(istek, timeout=self.zaman))
        return yanit["choices"][0]["message"].get("content") or ""


class HF:
    """transformers + peft; colab/egit.ipynb'in ölçüm hücresiyle aynı üretim (greedy, ≤160 yeni token)."""

    def __init__(self, taban: str = "", adaptor: str = "", model=None, tok=None, maks_token: int = 160):
        self.maks_token = maks_token
        if model is not None:
            self.model, self.tok = model, tok
            return
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError:
            sys.exit("hf arka ucu için: pip install torch transformers peft accelerate")
        kaynak = adaptor or taban
        self.tok = AutoTokenizer.from_pretrained(kaynak)
        self.model = AutoModelForCausalLM.from_pretrained(taban, torch_dtype="auto", device_map="auto")
        if adaptor:
            from peft import PeftModel

            self.model = PeftModel.from_pretrained(self.model, adaptor)
        self.model.eval()

    def uret(self, msj: list[dict]) -> str:
        girdi = self.tok.apply_chat_template(msj, tokenize=True, add_generation_prompt=True, return_tensors="pt").to(
            self.model.device
        )
        cikti = self.model.generate(
            input_ids=girdi,
            max_new_tokens=self.maks_token,
            do_sample=False,
            pad_token_id=self.tok.pad_token_id or self.tok.eos_token_id,
        )
        return self.tok.decode(cikti[0][girdi.shape[1] :], skip_special_tokens=True)


def arka_uc(a) -> object:
    if a.arka_uc == "sahte":
        return Sahte()
    if a.arka_uc == "uc":
        if not (a.url and a.model):
            sys.exit("--arka-uc uc için --url ve --model gerekli")
        anahtar = os.environ.get("ADLANDIR_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        return UcNokta(a.url, a.model, anahtar, a.anahtar_basligi)
    if not a.taban:
        sys.exit("--arka-uc hf için --taban (ve genellikle --adaptor) gerekli")
    return HF(a.taban, a.adaptor)


def adlandir(kayit: dict, model, baglam: str = "ozet") -> dict:
    metin = model.uret(mesajlar(kayit, baglam))
    cevap = cevap_coz(metin)
    sonuc = {"id": kayit["id"], "tahmin": cevap["ad"], "aciklama": cevap["aciklama"], "ham": metin}
    if kayit.get("ad"):
        sonuc |= {"gercek": kayit["ad"], "f1": round(f1(cevap["ad"], kayit["ad"]), 3), "sizinti": kayit["sizinti"]}
    return sonuc


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("girdi", type=Path, help="ELF/Mach-O nesne ya da binary, objdump metni veya tek fonksiyon asm'si")
    ap.add_argument("--arka-uc", choices=("uc", "hf", "sahte"), default="sahte")
    ap.add_argument("--url", help="uc: OpenAI uyumlu taban URL (…/v1)")
    ap.add_argument("--model", help="uc: model adı")
    ap.add_argument("--anahtar-basligi", default="Authorization", help="uc: Evren için X-API-Key")
    ap.add_argument("--taban", help="hf: taban model (ör. Qwen/Qwen3-8B)")
    ap.add_argument("--adaptor", default="", help="hf: LoRA adaptör dizini")
    ap.add_argument("--baglam", choices=("ozet", "yok"), default="ozet", help="çağrılan iç fonksiyonların özeti")
    ap.add_argument("--fonksiyon", nargs="*", help="yalnız bu gerçek adlar (nesne girdisinde)")
    ap.add_argument("--en-az", type=int, default=1, help="en az komut sayısı")
    ap.add_argument("--olc", action="store_true", help="semboller varsa gerçek adla F1 yazdır")
    ap.add_argument("--goster", action="store_true", help="modele giden asm'yi de yazdır")
    ap.add_argument("-o", "--cikti", type=Path, help="JSONL çıktı")
    ap.add_argument("--tohum", type=int, default=7)
    a = ap.parse_args()

    kayit_listesi = [r for r in girdiden_kayitlar(a.girdi, tohum=a.tohum) if r["komut_sayisi"] >= a.en_az]
    if a.fonksiyon:
        kayit_listesi = [r for r in kayit_listesi if r["ad"] in a.fonksiyon]
    if not kayit_listesi:
        sys.exit("fonksiyon bulunamadı")
    model = arka_uc(a)
    sonuclar = []
    for r in kayit_listesi:
        s = adlandir(r, model, a.baglam)
        sonuclar.append(s)
        if a.goster:
            print(mesajlar(r, a.baglam)[1]["content"] + "\n")
        gercek = f"{r['ad']:<28}" if a.olc and r["ad"] else ""
        puan = f"{s['f1']:.2f}  " if a.olc and "f1" in s else ""
        uyari = "  [sızıntı: ad asm'de geçiyor]" if r["sizinti"] else ""
        print(f"{puan}{r['id']}  {gercek}→ {s['tahmin'] or '?'}  — {s['aciklama']}{uyari}")
    if a.olc and any("f1" in s for s in sonuclar):
        puanli = [s["f1"] for s in sonuclar if "f1" in s]
        print(
            f"ortalama F1 {sum(puanli) / len(puanli):.3f}  (n={len(puanli)}, tam isabet {sum(x == 1 for x in puanli)})"
        )
    if a.cikti:
        a.cikti.parent.mkdir(parents=True, exist_ok=True)
        with a.cikti.open("w") as f:
            for s in sonuclar:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
