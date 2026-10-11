#!/usr/bin/env python3
"""Offline lexical-information bounds for callee naming, NOT model accuracy bounds."""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from statistics import mean

from alttan_yukari import (SUB, components_leaf_first, context_parts, context_symbols,
                          graph_for, identity, indexed, prompt, read_rows)
from taban import f1, kelimeler

IDENTIFIER = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
LITERAL = re.compile(r'"(?:\\.|[^"\\])*"')


def strip_prefix(name, prefixes):
    for prefix in sorted(prefixes, key=len, reverse=True):
        stripped = re.sub(r"^(?i:" + re.escape(prefix) + r")_?", "", name)
        if stripped and stripped != name:
            return stripped
    return name


def name_candidates(context):
    """Only summary labels and named callees, not strings/size/summary prose."""
    names = []
    for line in context.splitlines():
        line = LITERAL.sub("", line)
        head = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\(", line)
        if head:
            names.append(head.group(1))
        if "çağırır " in line:
            calls = line.split("çağırır ", 1)[1].split(";", 1)[0]
            names.extend(IDENTIFIER.findall(calls))
    return sorted({name for name in names if not SUB.fullmatch(name)})


def lexical_metrics(target, names):
    tokens = set(kelimeler(target))
    available = {token for name in names for token in kelimeler(name)}
    shared = tokens & available
    return {"target_tokens": len(tokens), "shared_tokens": len(shared),
            "token_recall": len(shared) / len(tokens) if tokens else 0.0,
            "any_shared": bool(shared), "all_shared": bool(tokens) and tokens <= available,
            "best_copy_f1": max((f1(name, target) for name in names), default=0.0)}


def aggregate(rows):
    return {"rows": len(rows),
            "any_shared_rows": sum(r["any_shared"] for r in rows),
            "all_shared_rows": sum(r["all_shared"] for r in rows),
            "shared_tokens": sum(r["shared_tokens"] for r in rows),
            "target_tokens": sum(r["target_tokens"] for r in rows),
            "micro_token_recall": (sum(r["shared_tokens"] for r in rows) /
                                   sum(r["target_tokens"] for r in rows)) if rows else 0.0,
            "macro_token_recall": mean(r["token_recall"] for r in rows) if rows else 0.0,
            "raw_macro_token_recall": mean(r["raw_token_recall"] for r in rows) if rows else 0.0,
            "oracle_best_copy_f1": mean(r["best_copy_f1"] for r in rows) if rows else 0.0}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def simulate(rows, raw, predictions):
    prompts = indexed(rows)
    prediction_map = {}
    for prediction in predictions:
        key = identity(prediction)
        if key in prediction_map:
            raise ValueError("duplicate prediction identity")
        source = raw.get(key)
        if source is None or source["id"] != prediction["id"]:
            raise ValueError("prediction identity is not aligned with raw data")
        name = prediction.get("tahmin", "")
        if isinstance(name, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) and not SUB.fullmatch(name):
            prediction_map[key] = name
    modes = ("anonymised", "gold", "v5_predicted", "gold_prediction_coverage")
    diagnostics = {mode: [] for mode in modes}
    per_project = {mode: {} for mode in modes}
    counts = Counter()
    exports = []
    for row in rows:
        key = identity(row)
        if key not in raw or raw[key]["id"] != row["id"] or raw[key]["ad"] != row["gercek_ad"]:
            raise ValueError("prompt/raw identity or gold label mismatch")
        user = next(m["content"] for m in row["messages"] if m["role"] == "user")
        context = context_parts(user)[1]
        symbols = context_symbols(context)
        counts["rows_with_context"] += bool(context)
        counts["context_characters"] += len(context)
        counts["prompt_characters"] += len(user)
        counts["context_symbol_slots"] += len(symbols)
        counts["self_symbol_slots_excluded"] += key[3] in symbols
        prefixes = row.get("oneksiz_onek", [])
        maps = {mode: {} for mode in modes}
        for symbol in symbols - {key[3]}:
            callee = key[:3] + (symbol,)
            source = raw.get(callee)
            counts["resolved_gold_slots"] += source is not None
            if source:
                maps["gold"][symbol] = source["ad"]
            if callee in prediction_map:
                maps["v5_predicted"][symbol] = prediction_map[callee]
                maps["gold_prediction_coverage"][symbol] = source["ad"]
                counts["resolved_prediction_slots"] += 1
        counts["rows_with_gold_rewrite"] += bool(maps["gold"])
        counts["rows_with_prediction_rewrite"] += bool(maps["v5_predicted"])
        counts["direct_summary_slots"] += len(re.findall(r"(?m)^sub_[0-9a-fA-F]+\s*\(", context))
        counts["rows_with_strings"] += 'string ' in context or 'string:' in context
        target = strip_prefix(row["gercek_ad"], prefixes)
        record = {"id": row["id"], "metrics": {}, "prompts": {}}
        for mode in modes:
            messages = prompt(row, maps[mode])
            rewritten = next(m["content"] for m in messages if m["role"] == "user")
            names = name_candidates(context_parts(rewritten)[1])
            metrics = lexical_metrics(target, [strip_prefix(n, prefixes) for n in names])
            metrics["raw_token_recall"] = lexical_metrics(row["gercek_ad"], names)["token_recall"]
            diagnostics[mode].append(metrics)
            per_project[mode].setdefault(key[0], []).append(metrics)
            record["metrics"][mode] = metrics
            record["prompts"][mode] = messages
        exports.append(record)
    graph, missing = graph_for(prompts, raw)
    groups = list(components_leaf_first(graph))
    counts["graph_nodes"] = len(graph)
    counts["known_direct_edges"] = sum(map(len, graph.values()))
    counts["missing_direct_edges"] = sum(map(len, missing.values()))
    counts["leaf_nodes_with_no_raw_internal_calls"] = sum(not graph[k] and not missing[k] for k in graph)
    counts["induced_sink_nodes"] = sum(not graph[k] for k in graph)
    counts["scc_count"] = len(groups)
    counts["recursive_nodes"] = sum(len(g) for g in groups if len(g) > 1 or g[0] in graph[g[0]])
    full_graph, full_missing = graph_for(raw, raw)
    full_groups = list(components_leaf_first(full_graph))
    full_stats = {"nodes": len(full_graph), "known_edges": sum(map(len, full_graph.values())),
                  "missing_edges": sum(map(len, full_missing.values())), "scc_count": len(full_groups),
                  "recursive_nodes": sum(len(g) for g in full_groups if len(g) > 1 or g[0] in full_graph[g[0]])}
    paired = {"gold_minus_anonymised_macro_recall": mean(
        b["token_recall"] - a["token_recall"] for a, b in zip(diagnostics["anonymised"], diagnostics["gold"])),
        "predicted_minus_anonymised_macro_recall": mean(
        b["token_recall"] - a["token_recall"] for a, b in zip(diagnostics["anonymised"], diagnostics["v5_predicted"]))}
    summary = {"interpretation": "Lexical information bounds only; no model inference, causal gain or accuracy bound.",
               "counts": dict(counts), "paired": paired,
               "prediction_rows": len(predictions), "valid_prediction_rows": len(prediction_map),
               "full_raw_graph": full_stats,
               "modes": {mode: aggregate(values) for mode, values in diagnostics.items()},
               "projects": {mode: {p: aggregate(rs) for p, rs in project.items()}
                            for mode, project in per_project.items()}}
    return summary, exports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompts", required=True, type=Path)
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--export", type=Path, help="optional per-row rewritten prompts + diagnostic metrics JSONL")
    args = parser.parse_args()
    rows = list(read_rows(args.prompts))
    if not rows:
        parser.error("empty prompts")
    projects = {row["proje"] for row in rows}
    paths = sorted(args.raw.glob("*.jsonl")) if args.raw.is_dir() else [args.raw]
    paths = [path for path in paths if not path.name.endswith(".rapor.jsonl")]
    raw = indexed(r for path in paths for r in read_rows(path) if r.get("proje") in projects)
    summary, exports = simulate(rows, raw, list(read_rows(args.predictions)))
    summary["provenance"] = {"prompts_sha256": sha256(args.prompts),
                             "predictions_sha256": sha256(args.predictions),
                             "raw_sha256": {path.name: sha256(path) for path in paths},
                             "raw_nodes_loaded": len(raw)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.export:
        args.export.parent.mkdir(parents=True, exist_ok=True)
        with args.export.open("w", encoding="utf-8") as stream:
            for row in exports:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"counts": summary["counts"], "modes": summary["modes"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
