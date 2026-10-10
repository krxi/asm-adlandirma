#!/usr/bin/env python3
"""v5/v6 eğitim verisini çevrimdışı incelenebilen tek HTML'e dönüştürür."""

import argparse
import html
import json
import random
import re
from pathlib import Path


BAGLAM_BASLIK = "\n\n; --- çağrılan fonksiyonlar ---\n"
DECOMPILE_BASLIK = "\n\n/* --- Ghidra decompile --- */\n"
BAYRAK_ADLARI = {
    "ad_string": "ad string sabitinde",
    "aciklama_yok": "açıklama yok",
    "cok_kisa": "çok kısa (<8 komut)",
    "cok_uzun": "çok uzun / girdi kesilmiş",
    "en_ad_iceriyor": "İngilizce açıklama adı içeriyor",
    "kisa_aciklama": "açıklama çok kısa (<5 sözcük)",
    "decompile_kirpildi": "decompile kırpıldı",
    "decompile_sizinti": "hedef adı sızıntısı; decompile atıldı",
    "decompile_yok": "decompile yok",
}


def jsonl_oku(yol):
    """Boş satırları atlayarak JSONL okur."""
    with Path(yol).open(encoding="utf-8") as dosya:
        for no, satir in enumerate(dosya, 1):
            if satir.strip():
                try:
                    yield json.loads(satir)
                except json.JSONDecodeError as hata:
                    raise ValueError(f"{yol}:{no}: geçersiz JSON") from hata


def hedef_ayristir(satir):
    try:
        hedef = json.loads(satir["messages"][2]["content"])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as hata:
        raise ValueError(f"{satir.get('id', '?')}: assistant hedefi geçersiz") from hata
    if not isinstance(hedef, dict) or not hedef.get("ad"):
        raise ValueError(f"{satir.get('id', '?')}: hedef adı eksik")
    return hedef


def girdi_ayristir(satir):
    try:
        girdi = satir["messages"][1]["content"]
    except (KeyError, IndexError, TypeError) as hata:
        raise ValueError(f"{satir.get('id', '?')}: user girdisi geçersiz") from hata
    asm_baglam, _, _ = girdi.partition(DECOMPILE_BASLIK)
    asm, ayirici, baglam = asm_baglam.partition(BAGLAM_BASLIK)
    return asm, baglam if ayirici else ""


def girdi_bol(satir):
    """Kullanıcı girdisini asm, bağlam ve decompile olarak ayır."""
    try:
        girdi = satir["messages"][1]["content"]
    except (KeyError, IndexError, TypeError) as hata:
        raise ValueError(f"{satir.get('id', '?')}: user girdisi geçersiz") from hata
    asm_baglam, ayirici, decompile = girdi.partition(DECOMPILE_BASLIK)
    asm, baglam_ayirici, baglam = asm_baglam.partition(BAGLAM_BASLIK)
    return asm, baglam if baglam_ayirici else "", decompile if ayirici else ""


def kelime_sayisi(metin):
    return len(re.findall(r"[^\W_]+(?:['’][^\W_]+)?", metin or "", re.UNICODE))


def string_sabitleri(asm):
    """ASM yorumlarındaki çift tırnaklı stringleri, kaçışları tolere ederek bulur."""
    return re.findall(r'"((?:\\.|[^"\\])*)"', asm or "")


def bayraklari_bul(satir, ham=None):
    """Bir hazırlanmış kayıt için kullanıcıya gösterilecek kalite bayraklarını döndürür."""
    ham = ham or {}
    hedef = hedef_ayristir(satir)
    asm, baglam = girdi_ayristir(satir)
    ad = str(hedef.get("ad", ""))
    en = str(hedef.get("aciklama_en", "") or "")
    tr = str(hedef.get("aciklama", "") or "")
    bayraklar = []

    sabitler = string_sabitleri(ham.get("asm", ""))
    # Ham üreticinin sizinti alanı hızlı ön elemedir; eski/sahte kayıtlarda alan
    # yoksa stringleri yine doğrudan denetlemek faydalıdır.
    sizinti_adayi = ham.get("sizinti", True)
    if ad and sizinti_adayi and any(ad.casefold() in s.casefold() for s in sabitler):
        bayraklar.append("ad_string")
    if satir.get("hedef_tur") == "ad" or not en or not tr:
        bayraklar.append("aciklama_yok")
    komut_sayisi = ham.get("komut_sayisi")
    if komut_sayisi is None:
        komut_sayisi = len([s for s in asm.splitlines() if s.strip()])
    if komut_sayisi < 8:
        bayraklar.append("cok_kisa")
    ham_asm = str(ham.get("asm", "") or "")
    hazir_asm_satir = len(asm.splitlines())
    ham_asm_satir = len(ham_asm.splitlines())
    if "... kesildi" in (asm + "\n" + baglam) or (ham_asm and ham_asm_satir > hazir_asm_satir):
        bayraklar.append("cok_uzun")
    if ad and en and ad.casefold() in en.casefold():
        bayraklar.append("en_ad_iceriyor")
    if (en and kelime_sayisi(en) < 5) or (tr and kelime_sayisi(tr) < 5):
        bayraklar.append("kisa_aciklama")
    if satir.get("decompile_kirpildi"):
        bayraklar.append("decompile_kirpildi")
    if satir.get("decompile_sizinti"):
        bayraklar.append("decompile_sizinti")
    if "decompile_var" in satir and not satir.get("decompile_var"):
        bayraklar.append("decompile_yok")
    return bayraklar


def ham_kayitlari_oku(yol, idler):
    """Büyük ham JSONL'den yalnız hazırlanmış train ID'lerini belleğe alır."""
    bulunan = {}
    kalan = set(idler)
    if not yol.exists():
        raise FileNotFoundError(f"ham veri bulunamadı: {yol}")
    for kayit in jsonl_oku(yol):
        kimlik = kayit.get("id")
        if kimlik in kalan:
            bulunan[kimlik] = {
                "komut_sayisi": kayit.get("komut_sayisi"),
                "sizinti": kayit.get("sizinti"),
                "asm": kayit.get("asm", ""),
            }
            kalan.remove(kimlik)
            if not kalan:
                break
    return bulunan


def ornekleri_sec(train, hamlar, tohum=42, rastgele_sayi=60, bayrakli_sayi=20):
    """Belirlenimci rastgele örnekler ve bunlara ek bayraklı örnekler seçer."""
    rng = random.Random(tohum)
    rastgele_ornekler = rng.sample(train, min(rastgele_sayi, len(train)))
    secilen_idler = {r["id"] for r in rastgele_ornekler}
    bayrakli = [r for r in train if bayraklari_bul(r, hamlar.get(r["id"]))]
    ek_adaylar = [r for r in bayrakli if r["id"] not in secilen_idler]
    ekler = rng.sample(ek_adaylar, min(bayrakli_sayi, len(ek_adaylar)))
    return [(r, "rastgele") for r in rastgele_ornekler] + [(r, "bayraklı") for r in ekler]


def _sayi(deger):
    return f"{deger:,}".replace(",", ".") if isinstance(deger, int) else str(deger)


def _dagilim(baslik, veriler):
    veriler = veriler or {}
    en_buyuk = max(veriler.values(), default=1)
    cubuklar = "".join(
        f'<div class="bar-row"><span>{html.escape(str(ad))}</span>'
        f'<i style="--w:{100 * sayi / en_buyuk:.2f}%"></i><b>{_sayi(sayi)}</b></div>'
        for ad, sayi in veriler.items()
    ) or '<p class="muted">Veri yok</p>'
    return f'<section class="panel"><h2>{html.escape(baslik)}</h2>{cubuklar}</section>'


def _tablo(baslik, satirlar, basliklar):
    govde = "".join("<tr>" + "".join(f"<td>{html.escape(_sayi(d))}</td>" for d in satir) + "</tr>"
                    for satir in satirlar)
    kafa = "".join(f"<th>{html.escape(str(b))}</th>" for b in basliklar)
    return f'<section class="panel table-wrap"><h2>{html.escape(baslik)}</h2><table><thead><tr>{kafa}</tr></thead><tbody>{govde}</tbody></table></section>'


def ozet_html(ozet):
    bolum_adlari = [ad for ad in ("train", "valid_300", "test_sabit", "eval115") if ad in ozet]
    sayilar = [(ad, ozet[ad].get("satir", 0), ozet[ad].get("proje", 0), ozet[ad].get("fonksiyon", 0))
               for ad in bolum_adlari]
    parcaciklar = [_tablo("Veri sayıları", sayilar, ("bölüm", "satır", "proje", "fonksiyon"))]
    train = ozet.get("train", {})
    parcaciklar += [_dagilim("Train opt dağılımı", train.get("opt")),
                    _dagilim("Train hedef türü", train.get("hedef_tur"))]

    token_satirlari = []
    for bolum in bolum_adlari:
        for tur, yuzde in ozet[bolum].get("token", {}).items():
            token_satirlari.append((bolum, tur, yuzde.get("p50", 0), yuzde.get("p90", 0),
                                    yuzde.get("p99", 0), yuzde.get("maks", 0)))
    parcaciklar.append(_tablo("Token yüzdelikleri", token_satirlari,
                              ("bölüm", "tür", "p50", "p90", "p99", "maks")))

    decompile_satirlari = []
    for bolum in bolum_adlari:
        b = ozet[bolum]
        if "decompile_var" in b:
            decompile_satirlari.append((bolum, b.get("decompile_var", 0),
                                        f"{100 * b.get('decompile_var_oran', 0):.1f}%",
                                        b.get("decompile_kirpildi", 0),
                                        b.get("decompile_sizinti", 0), b.get("decompile_yok", 0)))
    if decompile_satirlari:
        parcaciklar.append(_tablo("Decompile durumu", decompile_satirlari,
                                  ("bölüm", "var", "oran", "kırpılmış", "sızıntı", "yok")))

    filtreler = ozet.get("filtreler", {})
    filtre_adlari = sorted({k for f in filtreler.values() for k in f})
    filtre_satirlari = [(bolum,) + tuple(filtreler[bolum].get(k, 0) for k in filtre_adlari)
                        for bolum in filtreler]
    parcaciklar.append(_tablo("Filtre etkileri", filtre_satirlari, ("bölüm", *filtre_adlari)))
    asan = ozet.get("secim", {}).get("tavan_asan_projeler", {})
    parcaciklar.append(_dagilim("Tavanı aşan projeler", asan))
    return "".join(parcaciklar)


def kart_html(satir, kaynak, ham):
    hedef = hedef_ayristir(satir)
    asm, baglam, decompile = girdi_bol(satir)
    bayraklar = bayraklari_bul(satir, ham)
    kimlik = str(satir["id"])
    rozetler = "".join(f'<span class="flag flag-{b}">{html.escape(BAYRAK_ADLARI[b])}</span>' for b in bayraklar)
    if not rozetler:
        rozetler = '<span class="flag clean">bayrak yok</span>'
    dugmeler = "".join(f'<button type="button" data-decision="{k}">{a}</button>'
                        for k, a in (("iyi", "İyi"), ("supheli", "Şüpheli"), ("kotu", "Kötü")))
    token = satir.get("token") or {}
    token_ozeti = (f"girdi {token.get('girdi', '?')} · hedef {token.get('hedef', '?')} · "
                   f"toplam {token.get('toplam', '?')}")
    decompile_neden = satir.get("decompile_yok_neden") or "decompile yok"
    return f'''<article class="card" data-id="{html.escape(kimlik, quote=True)}"
      data-flags="{html.escape(' '.join(bayraklar), quote=True)}" data-decision="bos">
      <header><div><span class="source">{kaynak}</span><code>{html.escape(kimlik)}</code></div>
      <span>{html.escape(str(satir.get("proje", "?")))} · {html.escape(str(satir.get("opt", "?")))}</span></header>
      <h3>{html.escape(str(hedef.get("ad", "")))}</h3>
      <div class="flags">{rozetler}</div>
      <p class="muted">Token: {html.escape(token_ozeti)}</p>
      <dl><dt>EN</dt><dd>{html.escape(str(hedef.get("aciklama_en", "—") or "—"))}</dd>
      <dt>TR</dt><dd>{html.escape(str(hedef.get("aciklama", "—") or "—"))}</dd></dl>
      <details><summary>ASM'nin ilk 25 satırı</summary><pre>{html.escape(chr(10).join(asm.splitlines()[:25]))}</pre></details>
      <details><summary>Bağlam</summary><pre>{html.escape(baglam or "Bağlam yok")}</pre></details>
      <details><summary>Ghidra decompile</summary><pre>{html.escape(decompile or decompile_neden)}</pre></details>
      <div class="review" role="group" aria-label="Karar">{dugmeler}</div>
      <label class="note">Not<textarea rows="2" placeholder="İsteğe bağlı not"></textarea></label>
    </article>'''


CSS = r'''
:root{color-scheme:light dark;--bg:#f2f0e9;--panel:#fffdf8;--text:#20221f;--muted:#676b63;--line:#d7d4ca;--accent:#176b5b;--soft:#dfeee8;--warn:#a15812;--bad:#a23832;--code:#171b1a}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}main{width:min(1180px,calc(100% - 28px));margin:auto;padding:36px 0 80px}h1{font-size:clamp(2rem,5vw,4.2rem);line-height:1;margin:.15em 0}h2{font-size:1.05rem;margin:0 0 14px}p{margin:.35em 0}.eyebrow,.muted,.source{color:var(--muted)}.theme{float:right}.summary-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:28px 0}.panel,.controls,.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;box-shadow:0 5px 18px #0000000a}.panel{padding:18px;overflow:auto}.bar-row{display:grid;grid-template-columns:minmax(80px,1fr) 3fr auto;align-items:center;gap:10px;margin:8px 0}.bar-row i{display:block;height:10px;width:var(--w);min-width:2px;background:var(--accent);border-radius:9px}.bar-row b{font-variant-numeric:tabular-nums}table{width:100%;border-collapse:collapse;font-size:.87rem}th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);white-space:nowrap}.controls{position:sticky;top:8px;z-index:3;display:flex;gap:12px;align-items:end;flex-wrap:wrap;padding:14px;margin:24px 0}.controls label{display:grid;gap:4px;font-size:.8rem;color:var(--muted)}select,button,textarea{font:inherit;color:inherit;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 10px}button{cursor:pointer}.primary{margin-left:auto;background:var(--accent);color:white;border-color:var(--accent)}.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.card{padding:18px;min-width:0}.card header{display:flex;justify-content:space-between;gap:10px;font-size:.78rem;color:var(--muted)}.card header div{min-width:0}.card header code{display:block;overflow-wrap:anywhere}.source{text-transform:uppercase;font-weight:750;letter-spacing:.08em}.card h3{font:750 clamp(1.45rem,4vw,2.25rem)/1.15 ui-monospace,SFMono-Regular,monospace;margin:18px 0 11px;color:var(--accent);overflow-wrap:anywhere}.flags{display:flex;gap:6px;flex-wrap:wrap}.flag{font-size:.72rem;padding:3px 7px;border-radius:99px;background:#f0dfc6;color:#70400e}.flag-ad_string,.flag-en_ad_iceriyor{background:#f3d5d1;color:#782520}.clean{background:var(--soft);color:var(--accent)}dl{display:grid;grid-template-columns:30px 1fr;gap:5px 10px;margin:15px 0}dt{font-size:.75rem;font-weight:bold;color:var(--muted)}dd{margin:0}details{border-top:1px solid var(--line);padding:10px 0}summary{cursor:pointer;font-weight:650}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--code);color:#e8eee9;border-radius:9px;padding:13px;max-height:380px;overflow:auto;font:12px/1.5 ui-monospace,SFMono-Regular,monospace}.review{display:flex;gap:7px;margin-top:12px}.review button.active{color:white;border-color:transparent}.review button[data-decision=iyi].active{background:#277a58}.review button[data-decision=supheli].active{background:#a96820}.review button[data-decision=kotu].active{background:#a23832}.note{display:grid;gap:5px;margin-top:9px;font-size:.78rem;color:var(--muted)}textarea{resize:vertical;width:100%}.empty{grid-column:1/-1;text-align:center;padding:50px}.hidden{display:none!important}:root[data-theme=dark]{--bg:#111513;--panel:#191e1b;--text:#e7ebe5;--muted:#a5ada5;--line:#343b36;--accent:#74cbb5;--soft:#263f37;--warn:#e1a55d;--bad:#ef8b83;--code:#0b0e0d}:root[data-theme=dark] .flag{background:#533b20;color:#f3ca96}:root[data-theme=dark] .flag-ad_string,:root[data-theme=dark] .flag-en_ad_iceriyor{background:#522e2c;color:#f1aaa5}@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#111513;--panel:#191e1b;--text:#e7ebe5;--muted:#a5ada5;--line:#343b36;--accent:#74cbb5;--soft:#263f37;--warn:#e1a55d;--bad:#ef8b83;--code:#0b0e0d}:root:not([data-theme=light]) .flag{background:#533b20;color:#f3ca96}:root:not([data-theme=light]) .flag-ad_string,:root:not([data-theme=light]) .flag-en_ad_iceriyor{background:#522e2c;color:#f1aaa5}}@media(max-width:760px){main{width:min(100% - 18px,1180px);padding-top:22px}.summary-grid,.cards{grid-template-columns:1fr}.controls{position:static}.primary{margin-left:0;width:100%}.card header{display:block}.table-wrap{padding:12px}}
'''


JS = r'''
const KEY="veri-v5-inceleme-isaretleri";
let marks={};
try{marks=JSON.parse(localStorage.getItem(KEY)||"{}")||{}}catch(_){marks={}}
let theme="";try{theme=localStorage.getItem(KEY+"-tema")||""}catch(_){}if(theme)document.documentElement.dataset.theme=theme;
const cards=[...document.querySelectorAll(".card")];
function save(){try{localStorage.setItem(KEY,JSON.stringify(marks))}catch(_){}}
function paint(card){const m=marks[card.dataset.id]||{};card.dataset.decision=m.karar||"bos";card.querySelectorAll("[data-decision]").forEach(b=>b.classList.toggle("active",b.dataset.decision===m.karar));card.querySelector("textarea").value=m.not||""}
function filter(){const f=document.querySelector("#flag-filter").value,d=document.querySelector("#decision-filter").value;let n=0;cards.forEach(c=>{const okf=f==="hepsi"||(f==="bayrakli"?c.dataset.flags:!c.dataset.flags)||c.dataset.flags.split(" ").includes(f);const okd=d==="hepsi"||c.dataset.decision===d;c.classList.toggle("hidden",!(okf&&okd));if(okf&&okd)n++});document.querySelector("#visible").textContent=n+" / "+cards.length+" kart"}
cards.forEach(c=>{paint(c);c.querySelectorAll("[data-decision]").forEach(b=>b.addEventListener("click",()=>{const m=marks[c.dataset.id]||{};m.karar=m.karar===b.dataset.decision?"":b.dataset.decision;if(!m.karar&&!m.not)delete marks[c.dataset.id];else marks[c.dataset.id]=m;save();paint(c);filter()}));c.querySelector("textarea").addEventListener("input",e=>{const m=marks[c.dataset.id]||{};m.not=e.target.value;if(!m.karar&&!m.not)delete marks[c.dataset.id];else marks[c.dataset.id]=m;save()})});
document.querySelectorAll("select").forEach(s=>s.addEventListener("change",filter));
document.querySelector("#theme").addEventListener("click",()=>{const now=document.documentElement.dataset.theme;const dark=now?now!=="dark":!matchMedia("(prefers-color-scheme: dark)").matches;document.documentElement.dataset.theme=dark?"dark":"light";try{localStorage.setItem(KEY+"-tema",document.documentElement.dataset.theme)}catch(_){}});
document.querySelector("#download").addEventListener("click",()=>{const out={};Object.keys(marks).sort().forEach(id=>{if(marks[id].karar||marks[id].not)out[id]={karar:marks[id].karar||"",not:marks[id].not||""}});const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],{type:"application/json"}));a.download="veri-v5-isaretler.json";a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)});filter();
'''


def html_uret(veri, cikti, tohum=42, ham_yolu=None):
    veri, cikti = Path(veri), Path(cikti)
    train_yolu, ozet_yolu = veri / "train.jsonl", veri / "ozet.json"
    if not train_yolu.exists() or not ozet_yolu.exists():
        raise FileNotFoundError(f"train.jsonl veya ozet.json bulunamadı: {veri}")
    train = list(jsonl_oku(train_yolu))
    ham_yolu = Path(ham_yolu) if ham_yolu else Path("veri/bin/olcek/egitim.jsonl")
    hamlar = ham_kayitlari_oku(ham_yolu, (r["id"] for r in train))
    secilenler = ornekleri_sec(train, hamlar, tohum)
    ozet = json.loads(ozet_yolu.read_text(encoding="utf-8"))
    surum = str(ozet.get("surum") or "v5")
    kartlar = "".join(kart_html(r, kaynak, hamlar.get(r["id"], {})) for r, kaynak in secilenler)
    secenekler = "".join(f'<option value="{k}">{html.escape(v)}</option>' for k, v in BAYRAK_ADLARI.items())
    js = JS.replace("veri-v5", f"veri-{surum}")
    belge = f'''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(surum)} veri inceleme</title><style>{CSS}</style></head><body><main>
    <button class="theme" id="theme" type="button" aria-label="Açık veya koyu temaya geç">◐ Tema</button><p class="eyebrow">EĞİTİM ÖNCESİ DENETİM · TOHUM {tohum}</p><h1>{html.escape(surum)} veri inceleme</h1>
    <p class="muted">{len(secilenler)} örnek · kararlar yalnız bu tarayıcıda saklanır</p>
    <div class="summary-grid">{ozet_html(ozet)}</div>
    <div class="controls"><label>Bayrak<select id="flag-filter"><option value="hepsi">Hepsi</option><option value="bayrakli">Herhangi bir bayrak</option><option value="">Bayraksız</option>{secenekler}</select></label><label>Karar<select id="decision-filter"><option value="hepsi">Hepsi</option><option value="bos">İşaretsiz</option><option value="iyi">İyi</option><option value="supheli">Şüpheli</option><option value="kotu">Kötü</option></select></label><span id="visible" class="muted"></span><button class="primary" id="download" type="button">İşaretleri JSON indir</button></div>
    <div class="cards">{kartlar}<p class="empty hidden">Bu filtrede kart yok.</p></div>
    </main><script>{js}</script></body></html>'''
    cikti.parent.mkdir(parents=True, exist_ok=True)
    cikti.write_text(belge, encoding="utf-8")
    return {"rastgele": sum(k == "rastgele" for _, k in secilenler),
            "bayrakli": sum(k == "bayraklı" for _, k in secilenler), "toplam": len(secilenler)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--veri", type=Path, default=Path("lora/veri-v5"), help="v5 veri dizini")
    ap.add_argument("--cikti", type=Path, default=Path("rapor/veri-v5-inceleme.html"), help="HTML çıktı yolu")
    ap.add_argument("--tohum", type=int, default=42, help="örnekleme tohumu")
    a = ap.parse_args(argv)
    sayilar = html_uret(a.veri, a.cikti, a.tohum)
    print(f"{a.cikti}: {sayilar['rastgele']} rastgele + {sayilar['bayrakli']} bayraklı örnek")


if __name__ == "__main__":
    main()
