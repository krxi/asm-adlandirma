#!/usr/bin/env python3
"""GitHub'dan izin verici lisanslı C projesi adayları topla → projeler.json biçimi.

  python3 aday_bul.py -o .notlar/aday-projeler.json

gh CLI (oturum açık) kullanır. Eğitim adayları: ≥300 yıldız. Test adayları: 20–200 yıldız,
2024+ oluşturulmuş. Test, vendored, örnek, doküman, platform dizinleri `haric` ile dışarıda kalır;
otomatik üretilmiş dosyalar çıkarım sırasında içerikten ayıklanır (olcekle.py).
"""
import argparse, hashlib, json, re, subprocess, sys, time
from pathlib import Path, PurePosixPath

LISANSLAR = {"mit": "MIT", "bsd-2-clause": "BSD-2-Clause", "bsd-3-clause": "BSD-3-Clause",
             "apache-2.0": "Apache-2.0", "zlib": "Zlib", "isc": "ISC", "0bsd": "0BSD"}
# Bu dizinlerin altındaki kaynaklar alınmaz (yol bileşeni, büyük/küçük harf duyarsız).
HARIC_DIZIN = re.compile(r"^(tests?|testing|testsuite|t|unittests?|check|examples?|samples?|demos?|"
    r"bench|benchmarks?|perf|fuzz|fuzzing|fuzzers?|oss-fuzz|docs?|documentation|"
    r"third[_-]?party|3rd[_-]?party|vendor|vendored|deps|dep|external|externals?|extern|contrib|"
    r"submodules?|ext|build|cmake|scripts?|tools?|win32|win64|windows|msvc|vs\d*|"
    r"visualc|android|ios|wasm|emscripten|mingw|cygwin|dos|os2|amiga|haiku|arm|arm64|aarch64|mips|"
    r"riscv|ppc|powerpc|sparc|esp32|esp8266|stm32|avr|arduino|zephyr|freertos|bindings?|python|"
    r"java|jni|go|rust|node|lua|ruby|php|perl|csharp|dotnet|swift|js|web|gui|qt|gtk|old|legacy|"
    r"obsolete|deprecated|attic|archive|experimental|sandbox|playground|research|"
    r"cli|programs?|apps?|bin|cmd|shell)$", re.I)
HARIC_DOSYA = re.compile(r"(^test|_test\.c$|_tests\.c$|^bench|_bench\.c$|^example|^demo|^fuzz|"
                         r"_fuzz(er)?\.c$|^main\.c$|_main\.c$|^sqlite3\.c$|^shell\.c$|^amalgamation)", re.I)
UYGUNSUZ_AD = re.compile(r"(awesome|tutorial|leetcode|homework|exercise|course|kernel|bootloader|"
                         r"firmware|linux|bsd$|-os$|^os|interview|cheat|learn|book|ctf|exploit|"
                         r"malware|rootkit|keylogger|ransom|cracker)", re.I)
# Ad + açıklamada: saldırı aracı ya da macOS'ta derlenmeyecek platforma bağlı proje.
UYGUNSUZ_ACIKLAMA = re.compile(r"\b(keygen|crack(ed|er)?|cheats?|game ?hack|c2|command[- ]and[- ]control|implant|"
    r"beacon|shellcode|payload|injector|injection|bypass|edr|evasion|lateral|malware|stealer|exploit|"
    r"rootkit|ransomware|red ?team|offensive|pentest)\b", re.I)
# Yalnız test seçiminde: macOS'ta dosya dosya derlenmesi beklenmeyen platforma bağlı projeler.
PLATFORM = re.compile(r"\b(flipper|esp32|esp8266|esp-idf|arduino|stm32|rp2040|"
    r"pico|nrf5\d|zephyr|freertos|firmware|kernel|bootloader|operating system|\bos\b|windows|win32|"
    r"winapi|android|ios|ndk|psp|nintendo|switch homebrew|wii|3ds|gameboy|playstation|xbox|dreamcast|"
    r"uefi|bios|microcontroller|mcu|fpga|embedded)\b", re.I)
KUTUPHANE = re.compile(r"\b(librar(y|ies)|lib|parser|parsing|json|yaml|toml|ini|csv|xml|hash(map|ing)?|"
    r"compress\w*|encod\w*|decod\w*|allocator|arena|regex|string|data structures?|vector|containers?|"
    r"math|crypto\w*|base64|utf-?8|unicode|serializ\w*|interpreter|virtual machine|vm|tokenizer|lexer|"
    r"header|format|protocol|codec|algorithm|bignum|matrix|tree|queue|buffer|logging|test framework)\b", re.I)


def gh(yol, sayfa_basina=None):
    for deneme in range(6):
        r = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github+json", yol],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return json.loads(r.stdout)
        if "rate limit" in r.stderr.lower() or "403" in r.stderr or "secondary" in r.stderr.lower():
            time.sleep(30 * (deneme + 1))
            continue
        if "404" in r.stderr or "409" in r.stderr:      # boş repo / bulunamadı
            return None
        time.sleep(3)
    print(f"gh api başarısız: {yol}: {r.stderr.strip()[:200]}", file=sys.stderr)
    return None


def ara(sorgu, sayfa_sayisi):
    sonuc = []
    for s in range(1, sayfa_sayisi + 1):
        d = gh(f"search/repositories?q={sorgu}&sort=stars&order=desc&per_page=100&page={s}")
        time.sleep(2.2)                                 # arama: 30 istek/dk
        if not d or not d.get("items"):
            break
        sonuc += d["items"]
        if len(d["items"]) < 100:
            break
    return sonuc


def haric_mi(yol):
    p = PurePosixPath(yol)
    parcalar = [x.lower() for x in p.parts[:-1]]
    if any(HARIC_DIZIN.match(x) or x.startswith(".") for x in parcalar):
        return True
    return bool(HARIC_DOSYA.search(p.name))


def agac_incele(repo, dal):
    d = gh(f"repos/{repo}/git/trees/{dal}?recursive=1")
    if not d or d.get("truncated") or "tree" not in d:
        return None
    dosyalar = [x["path"] for x in d["tree"] if x["type"] == "blob"]
    boylar = {x["path"]: x.get("size", 0) for x in d["tree"] if x["type"] == "blob"}
    c_hepsi = [f for f in dosyalar if f.endswith(".c")]
    c = [f for f in c_hepsi if not haric_mi(f) and boylar[f] < 1_500_000]
    cpp = sum(f.endswith((".cc", ".cpp", ".cxx")) for f in dosyalar)
    h_dizin = sorted({str(PurePosixPath(f).parent) for f in dosyalar
                      if f.endswith(".h") and not haric_mi(f)}, key=lambda x: (x.count("/"), x))
    # haric: alınmayan .c'leri içeren en üst dizinler + tek tek elenen dosyalar.
    haric = set()
    for f in c_hepsi:
        if f in c:
            continue
        p = PurePosixPath(f)
        for i, x in enumerate(p.parts[:-1]):
            if HARIC_DIZIN.match(x) or x.startswith("."):
                haric.add("/".join(p.parts[:i + 1]) + "/**/*.c")
                break
        else:
            haric.add(f)
    return {"sha": d["sha"], "c": c, "c_hepsi": len(c_hepsi), "cpp": cpp, "h_dizin": h_dizin,
            "haric": sorted(haric), "kb": sum(boylar[f] for f in c) // 1024}


def kayit(it, agac, rol, adlar):
    ad = re.sub(r"[^A-Za-z0-9_.-]", "_", it["name"]).lower()
    if ad in adlar:
        ad = f"{ad}__{it['owner']['login'].lower()}"
    adlar.add(ad)
    bayraklar = ["-I."] + [f"-I{d}" for d in agac["h_dizin"] if d != "."][:40]
    return {"ad": ad, "rol": rol, "url": it["html_url"], "surum": agac["sha"],
            "lisans": LISANSLAR.get(it["license"]["key"], it["license"]["spdx_id"]),
            "kok": f"kaynak/aday/{ad}", "dosyalar": ["**/*.c"], "haric": agac["haric"],
            "bayraklar": bayraklar, "hazirlik": [],
            "yildiz": it["stargazers_count"], "olusturma": it["created_at"][:10],
            "c_dosya": len(agac["c"]), "c_kb": agac["kb"],
            "not": (it.get("description") or "")[:120]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--cikti", type=Path, default=Path(".notlar/aday-projeler.json"))
    ap.add_argument("--egitim", type=int, default=450)
    ap.add_argument("--test", type=int, default=28)
    ap.add_argument("--dogrulama-orani", type=float, default=0.08)
    ap.add_argument("--mevcut", type=Path, default=Path("projeler.json"))
    ap.add_argument("--yalniz-test", action="store_true",
                    help="var olan çıktıdaki test adaylarını yeniden seç; eğitim/doğrulama korunur")
    a = ap.parse_args()
    eski = json.loads(a.cikti.read_text()) if a.yalniz_test else []
    korunan = [p for p in eski if p["rol"] != "test"
               and not UYGUNSUZ_ACIKLAMA.search(f"{p['ad']} {p.get('not', '')}".replace("-", " ").replace("_", " "))]

    mevcut = {p["url"].lower().rstrip("/") for p in json.loads(a.mevcut.read_text())}
    gorulen, havuz_e, havuz_t = set(mevcut), [], []
    gorulen |= {p["url"].lower() for p in korunan}
    for key in LISANSLAR:
        if not a.yalniz_test:
            for it in ara(f"language:C+license:{key}+stars:>=300+size:<150000+archived:false",
                          5 if key in ("mit", "bsd-3-clause", "apache-2.0") else 3):
                havuz_e.append(it)
        for yildiz in ("20..60", "61..200"):
            for it in ara(f"language:C+license:{key}+stars:{yildiz}+created:>=2024-01-01+pushed:>=2025-01-01"
                          f"+size:<30000+archived:false", 3 if key == "mit" else 1):
                havuz_t.append(it)
        print(f"{key}: eğitim havuzu {len(havuz_e)}, test havuzu {len(havuz_t)}", flush=True)

    def uygun(it):
        u = it["html_url"].lower()
        metin = f"{it['name']} {it.get('description') or ''} {' '.join(it.get('topics') or [])}"
        if u in gorulen or it.get("fork") or UYGUNSUZ_AD.search(it["name"]) or not it.get("license") \
                or UYGUNSUZ_ACIKLAMA.search(metin.replace("-", " ").replace("_", " ")):
            return False
        if rol_su_an == "test" and (not KUTUPHANE.search(metin.replace("-", " ").replace("_", " "))
                                    or PLATFORM.search(metin.replace("-", " ").replace("_", " "))):
            return False
        gorulen.add(u)
        return True

    adlar = {p["ad"] for p in json.loads(a.mevcut.read_text())} | {p["ad"] for p in korunan}
    secilen, elenen, rol_su_an = list(korunan), [], None
    havuz_e = sorted({it["html_url"]: it for it in havuz_e}.values(), key=lambda x: -x["stargazers_count"])
    havuz_t = sorted({it["html_url"]: it for it in havuz_t}.values(), key=lambda x: -x["stargazers_count"])
    for rol, havuz, hedef, en_az, en_cok in (("test", havuz_t, a.test, 3, 150),
                                              ("egitim", havuz_e, 0 if a.yalniz_test else a.egitim, 3, 900)):
        n, rol_su_an = 0, rol
        for it in havuz:
            if n >= hedef:
                break
            if not uygun(it):
                continue
            agac = agac_incele(it["full_name"], it["default_branch"])
            if agac is None:
                elenen.append({"repo": it["full_name"], "neden": "ağaç alınamadı/kesik"})
                continue
            if not en_az <= len(agac["c"]) <= en_cok:
                elenen.append({"repo": it["full_name"], "neden": f"{len(agac['c'])} uygun .c"})
                continue
            if agac["cpp"] > len(agac["c"]):
                elenen.append({"repo": it["full_name"], "neden": "çoğunluk C++"})
                continue
            p = kayit(it, agac, rol, adlar)
            if rol == "egitim":
                h = int(hashlib.sha1(p["ad"].encode()).hexdigest()[:8], 16) / 2**32
                if h < a.dogrulama_orani:
                    p["rol"] = "dogrulama"
            secilen.append(p)
            n += 1
            print(f"[{rol} {n}/{hedef}] {it['full_name']} ★{it['stargazers_count']} "
                  f"{p['lisans']} {p['c_dosya']} .c", flush=True)
    a.cikti.parent.mkdir(parents=True, exist_ok=True)
    a.cikti.write_text(json.dumps(secilen, ensure_ascii=False, indent=1) + "\n")
    a.cikti.with_suffix(".elenen.json").write_text(json.dumps(elenen, ensure_ascii=False, indent=1) + "\n")
    from collections import Counter
    print(json.dumps(Counter(p["rol"] for p in secilen)), json.dumps(Counter(p["lisans"] for p in secilen)))


if __name__ == "__main__":
    main()
