import json

import pytest

from alttan_yukari import (
    components_leaf_first,
    context_symbols,
    graph_for,
    identity,
    indexed,
    orchestrate,
    parse_name,
    rewrite,
)
from alttan_yukari_sim import lexical_metrics, name_candidates, simulate
from lora.hazirla import BAGLAM_BASLIK, DECOMPILE_BASLIK


def raw(symbol, name, calls=(), project="p", opt="-O0", source="a.c"):
    return {
        "id": f"{project}/{source}:{opt}:tam:{symbol}:{name}",
        "proje": project,
        "ad": name,
        "asm": "\n".join(f"call\t{s}" for s in calls) or "ret",
    }


def prepared(row, context=""):
    return {
        "id": row["id"],
        "proje": row["proje"],
        "gercek_ad": row["ad"],
        "oneksiz_onek": ["p"],
        "messages": [
            {"role": "system", "content": "system"},
            {
                "role": "user",
                "content": row["asm"] + (BAGLAM_BASLIK + context if context else "") + DECOMPILE_BASLIK + "sub_0002();",
            },
            {"role": "assistant", "content": json.dumps({"ad": row["ad"]})},
        ],
    }


def test_rewriting_keeps_asm_decompile_literals_and_substrings():
    context = 'sub_0002 (2 komut): çağırır sub_0003; string "sub_0002"\nsub_00020 (1 komut)'
    text = "call sub_0002" + BAGLAM_BASLIK + context + DECOMPILE_BASLIK + "sub_0002();"
    result = rewrite(text, {"sub_0002": "read_file", "sub_0003": "close_file"})
    assert result.startswith("call sub_0002" + BAGLAM_BASLIK + "read_file (2 komut)")
    assert 'string "sub_0002"' in result
    assert result.endswith(DECOMPILE_BASLIK + "sub_0002();")
    assert "sub_00020 (1 komut)" in result
    assert context_symbols('string "sub_0009" sub_0002') == {"sub_0002"}


def test_identity_scopes_project_opt_mode_but_not_source():
    a = raw("sub_0001", "a", source="a.c")
    b = raw("sub_0001", "b", source="b.c")
    assert identity(a) == identity(b)
    with pytest.raises(ValueError, match="duplicate"):
        indexed([a, b])
    assert identity(a) != identity(raw("sub_0001", "a", project="other"))
    assert identity(a) != identity(raw("sub_0001", "a", opt="-O2"))


def test_leaf_first_chain_cycle_self_and_disconnected():
    graph = {"a": {"b"}, "b": {"c"}, "c": set(), "d": {"e", "c"}, "e": {"d"}, "f": {"f"}, "g": set()}
    groups = list(components_leaf_first(graph))
    position = {node: i for i, group in enumerate(groups) for node in group}
    assert position["c"] < position["b"] < position["a"]
    assert position["c"] < position["d"] == position["e"]
    assert len(position) == len(graph)


def test_large_chain_is_iterative():
    graph = {n: {n + 1} if n < 2499 else set() for n in range(2500)}
    assert list(components_leaf_first(graph)) == [[n] for n in reversed(range(2500))]


def test_orchestration_propagates_without_gold_or_cross_scope():
    leaf = raw("sub_0001", "GOLD_LEAF")
    caller = raw("sub_0002", "GOLD_CALLER", ["sub_0001", "sub_0099"])
    other = raw("sub_0001", "OTHER_GOLD", project="other")
    inputs = indexed([prepared(leaf), prepared(caller, "sub_0001 (1 komut)"), prepared(other)])
    source = indexed([leaf, caller, other])
    results = []

    def predict(row, messages):
        assert all(m["role"] != "assistant" for m in messages)
        assert not any("GOLD" in m["content"] for m in messages)
        if row["id"] == caller["id"]:
            assert "predicted_leaf (1 komut)" in messages[1]["content"]
        return {"ad": "predicted_leaf" if row["id"] == leaf["id"] else "another_prediction"}

    orchestrate(inputs, source, predict, results.append)
    record = next(r for r in results if r["id"] == caller["id"])
    assert record["missing_direct_callees"] == 1
    assert record["rewritten_symbols"] == 1


def test_cycle_predictions_commit_simultaneously_and_self_stays_anonymous():
    a = raw("sub_0001", "gold_a", ["sub_0002"])
    b = raw("sub_0002", "gold_b", ["sub_0001"])
    own = raw("sub_0003", "gold_self", ["sub_0003"])
    source = indexed([a, b, own])
    inputs = indexed(
        [prepared(a, "sub_0002 (1 komut)"), prepared(b, "sub_0001 (1 komut)"), prepared(own, "sub_0003 (1 komut)")]
    )
    records = []

    def predict(row, messages):
        assert "predicted" not in messages[1]["content"]
        return {"ad": "predicted"}

    orchestrate(inputs, source, predict, records.append)
    assert all(r["recursive"] for r in records)
    assert all(not r["context_changed"] for r in records)
    assert sorted(r["component_size"] for r in records) == [1, 2, 2]


def test_call_graph_does_not_treat_context_grandchildren_as_direct_edges():
    a = raw("sub_0001", "a", ["sub_0002"])
    b = raw("sub_0002", "b")
    c = raw("sub_0003", "c")
    rows = [prepared(a, "sub_0002 (1 komut): çağırır sub_0003"), prepared(b), prepared(c)]
    graph, _ = graph_for(indexed(rows), indexed([a, b, c]))
    assert graph[identity(a)] == {identity(b)}


def test_missing_raw_fails_instead_of_inventing_graph():
    row = prepared(raw("sub_0001", "a"))
    with pytest.raises(ValueError, match="missing raw"):
        graph_for(indexed([row]), {})


def test_lexical_diagnostics_are_not_model_predictions():
    assert name_candidates('sub_0001 (10 komut): çağırır malloc; string "read_file"') == ["malloc"]
    score = lexical_metrics("read_file", ["read_buffer", "write_file"])
    assert score["all_shared"]
    assert score["token_recall"] == 1
    assert score["best_copy_f1"] == 0.5


def test_simulator_gold_prediction_coverage_and_self_exclusion():
    a = raw("sub_0001", "p_read_file", ["sub_0002", "sub_0001"])
    b = raw("sub_0002", "p_read_buffer")
    row = prepared(a, "sub_0002 (1 komut): çağırır sub_0001")
    summary, exports = simulate([row], indexed([a, b]), [{**b, "tahmin": "write_buffer"}])
    assert summary["counts"]["self_symbol_slots_excluded"] == 1
    assert summary["modes"]["gold"]["macro_token_recall"] == 0.5
    assert summary["modes"]["v5_predicted"]["macro_token_recall"] == 0
    assert summary["modes"]["gold_prediction_coverage"]["macro_token_recall"] == 0.5
    assert "sub_0001" in exports[0]["prompts"]["gold"][1]["content"]
    assert all(m["role"] != "assistant" for m in exports[0]["prompts"]["gold"])


def test_prediction_identity_mismatch_fails():
    a = raw("sub_0001", "a")
    changed = raw("sub_0001", "changed")
    with pytest.raises(ValueError, match="not aligned"):
        simulate([prepared(a)], indexed([a]), [{**changed, "tahmin": "valid_name"}])


@pytest.mark.parametrize("content", ['{"ad": "bad name"}', '{"ad": "sub_0001"}', '{"ad": null}'])
def test_invalid_model_name_fails(content):
    with pytest.raises(ValueError):
        parse_name(content)


def test_fenced_model_json():
    assert parse_name('```json\n{"ad": "read_file"}\n```')["ad"] == "read_file"
