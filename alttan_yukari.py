#!/usr/bin/env python3
"""Leaf-first naming over prepared v6 prompts; never reads gold labels for inference."""
import argparse
import heapq
import json
import os
import re
from pathlib import Path
from urllib.request import Request, urlopen

from lora.hazirla import BAGLAM_BASLIK, DECOMPILE_BASLIK

SUB = re.compile(r"\bsub_[0-9a-fA-F]+\b")
# Literal strings in summaries are data, not graph references.
CONTEXT_TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|\bsub_[0-9a-fA-F]+\b')
CALL = re.compile(r"(?m)^\s*(?:call|jmp)\s+(sub_[0-9a-fA-F]+)\b")
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def read_rows(path):
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def identity(row):
    """sub labels are scoped to project + optimization + stripping mode, not source file."""
    source, opt, mode, symbol, _ = row["id"].rsplit(":", 4)
    project = row.get("proje") or source.split("/", 1)[0]
    return project, opt, mode, symbol


def indexed(rows):
    result = {}
    for row in rows:
        key = identity(row)
        if key in result:
            raise ValueError("duplicate graph identity: " + str(key))
        result[key] = row
    return result


def context_parts(text):
    asm, marker, tail = text.partition(BAGLAM_BASLIK)
    if not marker:
        return text, "", ""
    context, decompile, code = tail.partition(DECOMPILE_BASLIK)
    return asm, context, decompile + code


def context_symbols(text):
    return {m.group() for m in CONTEXT_TOKEN.finditer(text) if not m.group().startswith('"')}


def rewrite(text, names):
    asm, context, decompile = context_parts(text)
    if not context:
        return text
    context = CONTEXT_TOKEN.sub(lambda m: names.get(m.group(), m.group()), context)
    return asm + BAGLAM_BASLIK + context + decompile


def prompt(row, names):
    messages = []
    for message in row["messages"]:
        if message["role"] not in ("system", "user"):
            continue
        messages.append({"role": message["role"], "content": (
            rewrite(message["content"], names) if message["role"] == "user" else message["content"])})
    if not any(m["role"] == "user" for m in messages):
        raise ValueError("missing user prompt")
    return messages


def graph_for(prompts, raw):
    graph, missing = {}, {}
    for key, row in prompts.items():
        source = raw.get(key)
        if source is None:
            raise ValueError("missing raw graph row: " + row["id"])
        calls = {key[:3] + (symbol,) for symbol in CALL.findall(source["asm"])}
        graph[key] = calls & prompts.keys()
        missing[key] = calls - prompts.keys()
    return graph, missing


def components_leaf_first(graph):
    """Iterative Kosaraju + sink-first condensation; recursive SCCs commit together."""
    seen, order = set(), []
    for start in sorted(graph):
        if start in seen:
            continue
        stack = [(start, False)]
        while stack:
            node, finished = stack.pop()
            if finished:
                order.append(node)
            elif node not in seen:
                seen.add(node)
                stack.append((node, True))
                stack.extend((child, False) for child in sorted(graph[node], reverse=True) if child not in seen)
    reverse = {key: set() for key in graph}
    for caller, callees in graph.items():
        for callee in callees:
            reverse[callee].add(caller)
    groups, membership = [], {}
    for start in reversed(order):
        if start in membership:
            continue
        number = len(groups)
        group, stack = [], [start]
        membership[start] = number
        while stack:
            node = stack.pop()
            group.append(node)
            for child in reverse[node]:
                if child not in membership:
                    membership[child] = number
                    stack.append(child)
        groups.append(sorted(group))
    dependencies = [set() for _ in groups]
    parents = [set() for _ in groups]
    for caller, callees in graph.items():
        a = membership[caller]
        for callee in callees:
            b = membership[callee]
            if a != b:
                dependencies[a].add(b)
                parents[b].add(a)
    ready = [(groups[n][0], n) for n, deps in enumerate(dependencies) if not deps]
    heapq.heapify(ready)
    while ready:
        _, n = heapq.heappop(ready)
        yield groups[n]
        for parent in sorted(parents[n]):
            dependencies[parent].remove(n)
            if not dependencies[parent]:
                heapq.heappush(ready, (groups[parent][0], parent))


def parse_name(content):
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    value = json.loads(content)
    name = value.get("ad")
    if not isinstance(name, str) or not NAME.fullmatch(name) or SUB.fullmatch(name):
        raise ValueError("model must return a valid non-anonymous function identifier")
    return value


def request_model(endpoint, model, messages, max_tokens):
    body = {"model": model, "messages": messages, "temperature": 0, "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": False}}
    headers = {"Content-Type": "application/json"}
    if os.environ.get("OPENAI_API_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["OPENAI_API_KEY"]
    request = Request(endpoint.rstrip("/") + "/chat/completions",
                      json.dumps(body).encode(), headers)
    with urlopen(request, timeout=900) as response:
        result = json.load(response)
    return parse_name(result["choices"][0]["message"]["content"])


def orchestrate(prompts, raw, predict, emit):
    graph, missing = graph_for(prompts, raw)
    named = {}
    for component, group in enumerate(components_leaf_first(graph)):
        pending = {}
        for key in group:
            row = prompts[key]
            # A recursive component never consumes one of its peers' current predictions.
            available = named.get(key[:3], {})
            user = next(m["content"] for m in row["messages"] if m["role"] == "user")
            symbols = context_symbols(context_parts(user)[1]) - {key[3]}
            names = {symbol: available[symbol] for symbol in symbols if symbol in available}
            messages = prompt(row, names)
            result = predict(row, messages)
            if not NAME.fullmatch(result.get("ad", "")) or SUB.fullmatch(result["ad"]):
                raise ValueError("invalid predicted name for " + row["id"])
            pending[key] = result["ad"]
            context = "\n".join(context_parts(m["content"])[1] for m in messages if m["role"] == "user")
            original = "\n".join(context_parts(m["content"])[1] for m in row["messages"] if m["role"] == "user")
            emit({"id": row["id"], "proje": key[0], "opt": key[1], "tahmin": result["ad"],
                  "aciklama_en": result.get("aciklama_en", ""), "aciklama": result.get("aciklama", ""),
                  "component": component, "component_size": len(group),
                  "recursive": len(group) > 1 or key in graph[key],
                  "missing_direct_callees": len(missing[key]),
                  "rewritten_symbols": len(context_symbols(original) & names.keys()),
                  "context_changed": context != original, "messages": messages})
        for key, name in pending.items():
            named.setdefault(key[:3], {})[key[3]] = name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompts", required=True, type=Path)
    parser.add_argument("--raw", required=True, type=Path, help="raw JSONL or directory containing project JSONL files")
    parser.add_argument("--project", help="restrict to one project")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--model", help="served v6 adapter name; required for live inference")
    parser.add_argument("--replay", type=Path, help="offline orchestration using saved predictions; no model evaluation")
    parser.add_argument("--max-tokens", type=int, default=512)
    args = parser.parse_args()
    if not args.replay and not args.model:
        parser.error("--model is required unless --replay is specified")
    prompts = indexed(r for r in read_rows(args.prompts) if not args.project or r["proje"] == args.project)
    if not prompts:
        parser.error("no selected prompts")
    projects = {key[0] for key in prompts}
    paths = sorted(args.raw.glob("*.jsonl")) if args.raw.is_dir() else [args.raw]
    raw = indexed(r for path in paths for r in read_rows(path) if r.get("proje") in projects)
    if args.replay:
        saved = {r["id"]: r for r in read_rows(args.replay)}
        def predict(row, messages):
            return {"ad": saved[row["id"]]["tahmin"]}
    else:
        def predict(row, messages):
            return request_model(args.endpoint, args.model, messages, args.max_tokens)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation: no accidental overwrite of an expensive inference run.
    with args.output.open("x", encoding="utf-8") as stream:
        def emit(result):
            stream.write(json.dumps(result, ensure_ascii=False) + "\n")
            stream.flush()
        orchestrate(prompts, raw, predict, emit)
    print(json.dumps({"rows": len(prompts), "mode": "replay" if args.replay else "live"}))


if __name__ == "__main__":
    main()
