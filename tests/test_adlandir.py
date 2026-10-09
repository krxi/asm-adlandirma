"""adlandir.py: nesne dosyasından fonksiyon ayırma/anonimleştirme, arka uçlar ve CLI; demo işleyicileri."""

import json
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

import adlandir
import hazirla as h

KOK = Path(__file__).resolve().parent.parent

KAYNAK = r"""
extern int puts(const char *);
extern void *malloc(unsigned long);
int genel_sayac = 1;
static int gizli_tablo = 3;

__attribute__((noinline)) static int kontrol_et(int n) {
    puts("kontrol_et: gecersiz deger");
    return n + gizli_tablo;
}

__attribute__((noinline)) int tampon_ayir(int n) {
    void *p = malloc(n);
    if (!p) return kontrol_et(n);
    genel_sayac++;
    return n * 2 + kontrol_et(n + 1);
}
"""


def objdump_var() -> bool:
    try:
        adlandir.objdump_bul()
    except SystemExit:
        return False
    return shutil.which("clang") is not None


gerekli = pytest.mark.skipif(not objdump_var(), reason="clang ve llvm-objdump gerekli")


@pytest.fixture(scope="module")
def nesneler(tmp_path_factory):
    d = tmp_path_factory.mktemp("nesne")
    (d / "a.c").write_text(KAYNAK)
    hedefler = {
        "elf-O0": [],
        "elf-O2": ["-O2"],
        "macho-O0": ["-target", "x86_64-apple-macos12"],
        "macho-O2": ["-target", "x86_64-apple-macos12", "-O2"],
    }
    yollar = {}
    for ad, bayrak in hedefler.items():
        if "elf" in ad:
            bayrak = ["-target", "x86_64-linux-gnu", *bayrak]
        yollar[ad] = d / f"{ad}.o"
        subprocess.run(["clang", "-c", "-w", *bayrak, str(d / "a.c"), "-o", str(yollar[ad])], check=True)
    return yollar


@gerekli
@pytest.mark.parametrize("hedef", ["elf-O0", "elf-O2", "macho-O0", "macho-O2"])
def test_nesneden_kayitlar_egitim_gorunumunde(nesneler, hedef):
    yol = nesneler[hedef]
    assert adlandir.bicim(yol) == hedef.split("-")[0]
    kayitlar = {r["ad"]: r for r in adlandir.girdiden_kayitlar(yol)}
    assert set(kayitlar) == {"kontrol_et", "tampon_ayir"}
    ana, yardimci = kayitlar["tampon_ayir"], kayitlar["kontrol_et"]
    assert {ana["id"], yardimci["id"]} == {"sub_0000", "sub_0001"}
    # Gerçek iç adlar ve semboller görünmez; dış importlar ve stringler görünür.
    for gizli in ("tampon_ayir", "genel_sayac", "gizli_tablo"):
        assert gizli not in ana["asm"] + yardimci["asm"]
    assert '; -> "kontrol_et: gecersiz deger"' in yardimci["asm"]
    assert "; -> puts" in yardimci["asm"]
    assert yardimci["sizinti"] and not ana["sizinti"]  # ad kendi hata mesajında geçiyor
    assert "rip +" not in ana["asm"] and "<" not in ana["asm"] and "#" not in ana["asm"]
    if hedef.endswith("O0"):
        assert "; -> malloc" in ana["asm"]
        assert yardimci["id"] in ana["asm"]  # iç çağrı sub_XXXX olarak
        assert ana["baglam"].startswith(f"{yardimci['id']} (")  # çağrılan fonksiyonun özeti
        assert "dat_" in ana["asm"] and "dat_" in yardimci["asm"]  # global ve static veri
        assert "veri" not in ana["asm"].split()


@gerekli
def test_elf_ve_macho_ayni_istem(nesneler):
    """İki biçim de eğitimdeki Mach-O görünümüne iner: string, import ve veri yorumları aynı."""

    def yorumlar(yol):
        return {
            r["ad"]: sorted(s.split("; -> ")[1] for s in r["asm"].splitlines() if "; -> " in s and "sub_" not in s)
            for r in adlandir.girdiden_kayitlar(yol)
        }

    assert yorumlar(nesneler["elf-O0"]) == yorumlar(nesneler["macho-O0"])


@gerekli
def test_objdump_metni_girdisi(nesneler, tmp_path):
    arac = adlandir.objdump_bul()
    metin = adlandir.calistir(arac, "-d", "-r", "--no-show-raw-insn", "--x86-asm-syntax=intel", nesneler["elf-O0"])
    (tmp_path / "d.txt").write_text(metin)
    kayitlar = {r["ad"]: r for r in adlandir.girdiden_kayitlar(tmp_path / "d.txt")}
    assert set(kayitlar) == {"kontrol_et", "tampon_ayir"}
    assert "; -> malloc" in kayitlar["tampon_ayir"]["asm"]
    assert "tampon_ayir" not in kayitlar["tampon_ayir"]["asm"]


def test_tek_fonksiyon_girdisi(tmp_path):
    satir = json.loads((KOK / "veri" / "test.jsonl").open().readline())
    (tmp_path / "f.s").write_text(satir["asm"])
    (kayit,) = adlandir.girdiden_kayitlar(tmp_path / "f.s")
    assert kayit["asm"] == satir["asm"] and kayit["id"] == "girdi" and kayit["ad"] == ""


def test_mesajlar_egitim_istemi():
    r = adlandir.tek_fonksiyon("push\trbp\nret", "sub_0001 (3 komut): çağırır free")
    m = adlandir.mesajlar(r)
    assert m[0] == {"role": "system", "content": h.SISTEM_ACIKLAMA}
    assert m[1]["content"] == "push\trbp\nret" + h.BAGLAM_BASLIK + "sub_0001 (3 komut): çağırır free"
    assert adlandir.mesajlar(r, "yok")[1]["content"] == "push\trbp\nret"


@pytest.mark.parametrize(
    "metin, ad, aciklama",
    [
        ('{"ad": "buf_alloc", "aciklama": "Tampon ayırır."}', "buf_alloc", "Tampon ayırır."),
        ('düşünce...\n{"ad": "x"}\n{"ad": "buf_free", "aciklama": "Bırakır."}', "buf_free", "Bırakır."),
        ("buf_alloc", "buf_alloc", ""),
        ('{"ad": bozuk}', "", ""),
    ],
)
def test_cevap_coz(metin, ad, aciklama):
    assert adlandir.cevap_coz(metin) == {"ad": ad, "aciklama": aciklama}


def test_uc_nokta_istek_bicimi():
    gelen = {}

    class Isleyici(BaseHTTPRequestHandler):
        def do_POST(self):
            gelen["yol"] = self.path
            gelen["basliklar"] = {k.lower(): v for k, v in self.headers.items()}
            gelen["govde"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            cevap = {"choices": [{"message": {"content": '{"ad": "tampon_ayir", "aciklama": "Ayırır."}'}}]}
            veri = json.dumps(cevap).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(veri)))
            self.end_headers()
            self.wfile.write(veri)

        def log_message(self, *a):
            pass

    sunucu = HTTPServer(("127.0.0.1", 0), Isleyici)
    threading.Thread(target=sunucu.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{sunucu.server_port}/v1/"
        uc = adlandir.UcNokta(url, "asm-model", "gizli", zaman=10)
        s = adlandir.adlandir({**adlandir.tek_fonksiyon("ret"), "ad": "tampon_ayir"}, uc)
        assert gelen["yol"] == "/v1/chat/completions"
        assert gelen["basliklar"]["authorization"] == "Bearer gizli"
        assert gelen["govde"]["model"] == "asm-model" and gelen["govde"]["temperature"] == 0
        assert gelen["govde"]["messages"][0]["content"] == h.SISTEM_ACIKLAMA
        assert (s["tahmin"], s["aciklama"], s["f1"]) == ("tampon_ayir", "Ayırır.", 1.0)
        # Evren: anahtar X-API-Key başlığında, Bearer'sız.
        adlandir.UcNokta(url, "m", "gizli", "X-API-Key", zaman=10).uret(
            adlandir.mesajlar(adlandir.tek_fonksiyon("ret"))
        )
        assert gelen["basliklar"]["x-api-key"] == "gizli" and "authorization" not in gelen["basliklar"]
    finally:
        sunucu.shutdown()


class SahteTensor(list):
    shape = property(lambda self: (1, len(self[0])))

    def to(self, aygit):
        return self


class SahteTok:
    pad_token_id, eos_token_id = None, 0

    def apply_chat_template(self, msj, tokenize, add_generation_prompt, return_tensors):
        assert tokenize and add_generation_prompt and msj[0]["content"] == h.SISTEM_ACIKLAMA
        return SahteTensor([[1, 2, 3]])

    def decode(self, ids, skip_special_tokens):
        assert list(ids) == [7, 8]
        return '{"ad": "buf_alloc", "aciklama": "Ayırır."}'


class SahteModel:
    device = "cpu"

    def generate(self, input_ids, max_new_tokens, do_sample, pad_token_id):
        assert not do_sample and max_new_tokens == 160 and pad_token_id == 0
        return [[*input_ids[0], 7, 8]]


def test_hf_uretimi_yalniz_yeni_tokenlari_cozer():
    model = adlandir.HF(model=SahteModel(), tok=SahteTok())
    s = adlandir.adlandir(adlandir.tek_fonksiyon("ret"), model)
    assert (s["tahmin"], s["aciklama"]) == ("buf_alloc", "Ayırır.")


@gerekli
def test_cli_sahte_olc(nesneler, tmp_path):
    cikti = tmp_path / "s.jsonl"
    s = subprocess.run(
        [sys.executable, str(KOK / "adlandir.py"), str(nesneler["elf-O0"]), "--olc", "-o", str(cikti)],
        capture_output=True,
        text=True,
    )
    assert s.returncode == 0, s.stderr
    assert "ortalama F1" in s.stdout and "sızıntı" in s.stdout
    satirlar = [json.loads(x) for x in cikti.open()]
    assert {r["gercek"] for r in satirlar} == {"kontrol_et", "tampon_ayir"}
    assert {r["tahmin"] for r in satirlar} == {"puts_sarmalayici", "malloc_sarmalayici"}


def test_demo_isleyicileri():
    sys.path.insert(0, str(KOK / "demo"))
    import app

    ad, aciklama, istem = app.asm_adlandir(adlandir.Sahte(), app.ORNEK)
    assert ad == "strlen_sarmalayici" and "malloc" in aciklama and istem.startswith("push")
    assert app.asm_adlandir(adlandir.Sahte(), "  ")[1] == "Assembly yapıştırın."
    assert app.dosya_adlandir(adlandir.Sahte(), "") == []


def test_demo_arayuzu_kurulur():
    pytest.importorskip("gradio")
    sys.path.insert(0, str(KOK / "demo"))
    import app

    assert app.arayuz(adlandir.Sahte(), "sahte") is not None
