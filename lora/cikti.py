"""Model çıktısından ad ve isteğe bağlı açıklamaları bağımlılıksız ayıkla."""

import json
import re


def ad_ayikla(metin: str) -> tuple[str, str, str, bool]:
    """JSON, kesik JSON ve düz metin için (ad, İngilizce, Türkçe, geçerli JSON)."""
    metin = metin.strip()
    # Kod çiti veya ön açıklama içindeki tamamlanmış JSON da kabul edilir.
    decoder = json.JSONDecoder()
    for bas in (m.start() for m in re.finditer(r"\{", metin)):
        try:
            veri, _ = decoder.raw_decode(metin[bas:])
        except ValueError:
            continue
        if isinstance(veri, dict) and isinstance(veri.get("ad"), str):
            return (veri["ad"], veri.get("aciklama_en") or "", veri.get("aciklama") or "", True)

    def alan(ad):
        es = re.search(r'"' + ad + r'"\s*:\s*("(?:\\.|[^"\\])*")', metin)
        if es:
            try:
                return json.loads(es[1])
            except ValueError:
                pass
        return ""

    ad = alan("ad")
    if ad:
        return ad, alan("aciklama_en"), alan("aciklama"), False
    es = re.search(r"[A-Za-z_][A-Za-z0-9_]*", metin)
    return (es[0] if es else ""), "", "", False
