import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import aciklama_puan_v6 as ap
import olcum_v6 as ov


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


def sample():
    kimlik = "demo/src/a.c:-O2:tam:sub_0000:demo_read"
    d = {"id": kimlik, "gercek_ad": "demo_read", "opt": "-O2", "proje": "demo",
         "oneksiz_onek": ["demo"], "decompile_var": True, "decompile_kirpildi": True}
    r = {"id": kimlik, "gercek": "demo_read", "tahmin": "read", "opt": "-O2", "proje": "demo", "f1": 0.667}
    return kimlik, d, r


def test_canonical_and_prefix_metrics():
    k, d, r = sample()
    rows = ov.eslestir({k: d}, {k: r}, {k: r}, 1)
    result = ov.ozet(rows)
    assert result["f1"] == pytest.approx(2 / 3)
    assert result["oneksiz_f1"] == 1
    assert result["fark"] == 0
    assert result["tam_isabet"] == 0
    assert result["f1_tam_isabet"] == 0
    assert result["oneksiz_f1_tam_isabet"] == 1
    assert result["kayitli_f1_uyumsuz"] == 0
    assert rows[0]["decompile"] == "kirpildi"


@pytest.mark.parametrize("change", ["ids", "label", "metadata", "opt", "prediction"])
def test_pairing_rejects_invalid_inputs(change):
    k, d, r = sample()
    other = {k: dict(r)}
    if change == "ids":
        other = {}
    elif change == "label":
        other[k]["gercek"] = "wrong"
    elif change == "metadata":
        del d["decompile_var"]
    elif change == "opt":
        other[k]["opt"] = "-O0"
    else:
        other[k]["tahmin"] = None
    with pytest.raises(ValueError):
        ov.eslestir({k: d}, other, {k: r}, 1)


def test_empty_groups_are_explicit():
    assert ov.ozet([])["n"] == 0
    assert ov.ozet([])["f1"] is None


def test_duplicate_ids_rejected(tmp_path):
    k, d, r = sample()
    with pytest.raises(ValueError):
        ov.oku(write_jsonl(tmp_path / "duplicate.jsonl", [r, r]))


def test_explanation_errors_remain_in_denominator(tmp_path):
    rows = [{"id": f"p/file:-O0:tam:sub_000{i}:read", "f1": 0, "puan_en": p, "puan_tr": p}
            for i, p in enumerate([2, None, 0])]
    path = write_jsonl(tmp_path / "scores.jsonl", rows)
    s = ap.ozet(path, path, tekrar=100)
    assert s["diller"]["en"]["dogru_orani"] == pytest.approx(1 / 3)
    assert s["diller"]["en"]["tam_karar_dogru_orani"] == 0.5
    assert s["diller"]["en"]["hata"] == 1
    assert not s["diller"]["en"]["hedef_gecildi"]
    assert s["diller"]["en"]["ga95"] == [0, 0]


def test_explanation_same_ids_required(tmp_path):
    a = write_jsonl(tmp_path / "a.jsonl", [{"id": "a"}])
    b = write_jsonl(tmp_path / "b.jsonl", [{"id": "b"}])
    with pytest.raises(ValueError):
        ap.ozet(a, b)


def test_real_judge_prompt_contract(tmp_path):
    k, d, r = sample()
    r.update(aciklama="Okur.", aciklama_en="Reads.")
    pred = write_jsonl(tmp_path / "pred.jsonl", [r])
    scores = write_jsonl(tmp_path / "scores.jsonl", [{"id": k}])
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    ref = write_jsonl(tmp_path / "ref.jsonl", [{"anahtar": ap.anahtar(r), "aciklama": "Okur"}])
    write_jsonl(source_dir / "p.jsonl", [{"anahtar": ap.anahtar(r), "kaynak": "int read(void) {return 1;}"}])
    jobs = ap.istemleri_hazirla(pred, scores, source_dir, ref, "mimo-v2.6-pro")
    assert len(jobs) == 2
    assert jobs[1]["istem"]["chat_template_kwargs"]["enable_thinking"] is False
    assert jobs[1]["istem"]["max_tokens"] == 200
    assert "Reads." in jobs[1]["istem"]["messages"][1]["content"]
    (source_dir / "p.jsonl").unlink()
    with pytest.raises(ValueError, match="eksik"):
        ap.istemleri_hazirla(pred, scores, source_dir, ref, "mimo-v2.6-pro")


def test_download_pins_revision_and_checks_completion(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "unit-test-secret")
    monkeypatch.setattr(ov, "BOLUMLER", {"test_sabit": 1, "eval115": 1})
    k, d, r = sample()
    best, run = {"adim": 12, "f1": 0.1}, {"surum": "v6"}
    calls = []
    def download(repo, name, revision, token, local_dir):
        assert revision == "commit-sha"
        calls.append(name)
        path = Path(local_dir, name)
        if name.endswith("-sonuc.jsonl"):
            write_jsonl(path, [r])
        else:
            content = best if name == "en_iyi.json" else run if name == "kosu.json" else {"en_iyi": best, "kosu": run}
            path.write_text(json.dumps(content))
        return str(path)
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(
        HfApi=lambda token: SimpleNamespace(repo_info=lambda repo, revision: SimpleNamespace(sha="commit-sha")),
        hf_hub_download=download))
    manifest = ov.indir("owner/repo", "main", tmp_path)
    assert manifest["revision"] == "commit-sha"
    assert len(calls) == 6
    assert "unit-test-secret" not in json.dumps(manifest)
    assert not any(name.startswith("son/") for name in calls)


def test_hf_errors_do_not_expose_token(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "never-print-this")
    def fail(*args, **kwargs):
        raise ValueError("never-print-this")
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(HfApi=fail, hf_hub_download=fail))
    with pytest.raises(RuntimeError) as error:
        ov.indir("owner/repo", "main", tmp_path)
    assert "never-print-this" not in str(error.value)
