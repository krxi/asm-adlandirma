#!/usr/bin/env python3
"""Offline constant hints for anonymized asm + Ghidra inputs (no model calls).

Usage:
    python3 lora/imzalar.py --dataset train=data/train.jsonl \
        --dataset test_sabit=data/test_sabit.jsonl --dataset eval115=data/eval115.jsonl \
        --predictions test_sabit=sonuc/test2000-molab-qwen3-8b-v5.jsonl \
        --predictions eval115=sonuc/eval115-molab-qwen3-8b-v5.jsonl \
        --output hints.jsonl --summary summary.json

The sidecar contains matching rows only; original datasets are never rewritten.
Only user messages feed detection. Labels are used afterward for descriptive
counts, never to select a hint. These are hints, NOT algorithm classifications:
a polynomial alone is weak, shared SHA-1/MD5 IVs are explicitly ambiguous.
Absent hints do not rule out an algorithm, especially with opaque dat_/DAT_
references or truncated decompilation. No referenced binary bytes are fetched.
"""

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
import sys

DECOMPILE_MARKER = "/* --- Ghidra decompile --- */"
SHA256_K = tuple(int(x, 16) for x in """
428a2f98 71374491 b5c0fbcf e9b5dba5 3956c25b 59f111f1 923f82a4 ab1c5ed5
 d807aa98 12835b01 243185be 550c7dc3 72be5d74 80deb1fe 9bdc06a7 c19bf174
 e49b69c1 efbe4786 0fc19dc6 240ca1cc 2de92c6f 4a7484aa 5cb0a9dc 76f988da
 983e5152 a831c66d b00327c8 bf597fc7 c6e00bf3 d5a79147 06ca6351 14292967
 27b70a85 2e1b2138 4d2c6dfc 53380d13 650a7354 766a0abb 81c2c92e 92722c85
 a2bfe8a1 a81a664b c24b8b70 c76c51a3 d192e819 d6990624 f40e3585 106aa070
 19a4c116 1e376c08 2748774c 34b0bcb5 391c0cb3 4ed8aa4a 5b9cca4f 682e6ff3
 748f82ee 78a5636f 84c87814 8cc70208 90befffa a4506ceb bef9a3f7 c67178f2
""".split())
MD5_T = tuple(int(abs(math.sin(i)) * (1 << 32)) for i in range(1, 65))
AES_SBOX_PREFIX = bytes.fromhex("637c777bf26b6fc53001672bfed7ab76")
AES_INV_SBOX_PREFIX = bytes.fromhex("52096ad53036a538bf40a39e81f3d7fb")


@dataclass(frozen=True)
class Signature:
    name: str
    values: tuple[int, ...]
    minimum: int
    strength: str = "multi_constant"


def crc_table(poly):
    values = []
    for i in range(256):
        value = i
        for _ in range(8):
            value = (value >> 1) ^ (poly if value & 1 else 0)
        values.append(value)
    return tuple(values[1:])  # zero is not distinctive


SIGNATURES = (
    Signature("crc32_ieee_polynomial", (0xedb88320, 0x04c11db7), 1, "weak_single_constant"),
    Signature("crc32c_polynomial", (0x82f63b78, 0x1edc6f41), 1, "weak_single_constant"),
    Signature("crc32_ieee_table_values", crc_table(0xedb88320), 4),
    Signature("crc32c_table_values", crc_table(0x82f63b78), 4),
    Signature("sha256_round_k", SHA256_K, 4),
    Signature("sha256_or_blake2s_iv", (0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
              0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19), 4, "ambiguous_shared_iv"),
    Signature("sha512_or_blake2b_iv", (0x6a09e667f3bcc908, 0xbb67ae8584caa73b,
              0x3c6ef372fe94f82b, 0xa54ff53a5f1d36f1, 0x510e527fade682d1,
              0x9b05688c2b3e6c1f, 0x1f83d9abfb41bd6b, 0x5be0cd19137e2179),
              4, "ambiguous_shared_iv"),
    Signature("md5_round_t", MD5_T, 4),
    Signature("md4_md5_sha1_ripemd160_iv", (0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476,
              0xc3d2e1f0), 3, "ambiguous_shared_iv"),
    Signature("sha1_round_k", (0x5a827999, 0x6ed9eba1, 0x8f1bbcdc, 0xca62c1d6), 2),
    Signature("sha512_round_k_prefix", (0x428a2f98d728ae22, 0x7137449123ef65cd,
              0xb5c0fbcfec4d3b2f, 0xe9b5dba58189dbbc, 0x3956c25bf348b538,
              0x59f111f1b605d019, 0x923f82a4af194f9b, 0xab1c5ed5da6d8118), 3),
    Signature("adler32_modulus", (65521,), 1, "weak_single_constant"),
    Signature("murmur3_x86_32", (0xcc9e2d51, 0x1b873593), 2),
    Signature("murmur3_fmix32", (0x85ebca6b, 0xc2b2ae35), 2),
    Signature("xxhash64_primes", (0x9e3779b185ebca87, 0xc2b2ae3d27d4eb4f,
              0x165667b19e3779f9, 0x85ebca77c2b2ae63, 0x27d4eb2f165667c5), 2),
)
VALUE_SIGNATURES = defaultdict(list)
for _signature in SIGNATURES:
    for _value in _signature.values:
        VALUE_SIGNATURES[_value].append(_signature.name)

# Strip quoted strings/comments before tokenizing: diagnostics are not constants.
NON_CODE = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*', re.S)
NUMBER = re.compile(r"(?<![\w.])[-+]?(?:0[xX][0-9a-fA-F]+|[0-9]+)(?:[uU](?:[lL]{1,2})?|[lL]{1,2}[uU]?)?(?![\w.])")
NAME_RELATED = re.compile(r"crc|sha(?:1|2|3|5|_|$)|md[245]|aes|adler|hash|crypt|digest|checksum|murmur|xxh|chacha|blake|siphash|hmac|poly1305|ripemd", re.I)


def literal_value(text):
    body = re.sub(r"[uUlL]+$", "", text)
    return int(body, 16 if "x" in body.lower() else 10)


def equivalent_values(value):
    yield value
    if -(1 << 31) <= value < 0:
        yield value & 0xffffffff
    elif -(1 << 63) <= value < -(1 << 31):
        yield value & 0xffffffffffffffff
    elif 0xffffffff80000000 <= value <= 0xffffffffffffffff:
        yield value & 0xffffffff
    # Split packed words only when BOTH halves match the same family.
    # SHA-512/BLAKE2b IV high halves resemble SHA-256 IVs, but are not
    # packed SHA-256 words; accepting either half would mislabel them.
    unsigned = value & 0xffffffffffffffff if value < 0 else value
    if 0xffffffff < unsigned < 0xffffffff80000000:
        low, high = unsigned & 0xffffffff, unsigned >> 32
        if set(VALUE_SIGNATURES.get(low, ())) & set(VALUE_SIGNATURES.get(high, ())):
            yield low
            yield high


def numeric_literals(text, source):
    # Replace with whitespace but retain line numbers for reproducible evidence.
    text = NON_CODE.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), text)
    values = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if source == "asm":
            line = line.split(";", 1)[0]
            # Address displacements, stack offsets, and branch labels are not immediates.
            line = re.sub(r"\[[^\]]*\]", " ", line)
        for match in NUMBER.finditer(line):
            values.append((literal_value(match.group()), match.group(), line_number))
    return values


def detect(text):
    """Return label-free hints; require thresholds within one representation."""
    asm, _, decompile = text.partition(DECOMPILE_MARKER)
    hints = []
    for source, section in (("asm", asm), ("decompile", decompile)):
        literals = numeric_literals(section, source)
        evidence = defaultdict(dict)
        for value, raw, line in literals:
            for candidate in equivalent_values(value):
                for name in VALUE_SIGNATURES.get(candidate, ()):
                    evidence[name].setdefault(candidate, {"value": hex(candidate), "literal": raw, "line": line})
        for signature in SIGNATURES:
            matches = evidence[signature.name]
            if len(matches) >= signature.minimum:
                hints.append({"signature": signature.name, "source": source,
                              "strength": signature.strength, "distinct_constants": len(matches),
                              "evidence": list(matches.values())[:8]})
        # AES bytes are common individually: only an ordered 8-byte prefix window
        # (including a packed 64-bit immediate) qualifies, never an unordered set.
        for name, prefix in (("aes_sbox_prefix", AES_SBOX_PREFIX),
                             ("aes_inverse_sbox_prefix", AES_INV_SBOX_PREFIX)):
            found = None
            for index, (value, raw, line) in enumerate(literals):
                window = literals[index:index + 8]
                if len(window) == 8 and all(0 <= v <= 255 for v, _, _ in window):
                    sequence = bytes(v for v, _, _ in window)
                    if sequence in prefix:
                        found = {"line": line, "bytes": sequence.hex(), "encoding": "ordered_byte_literals"}
                        break
                if value < 0:
                    value &= 0xffffffffffffffff
                if 255 < value < (1 << 64):
                    for endian in ("little", "big"):
                        sequence = value.to_bytes(8, endian)
                        if sequence in prefix:
                            found = {"line": line, "literal": raw, "bytes": sequence.hex(), "encoding": f"packed_u64_{endian}"}
                            break
                if found:
                    break
            if found:
                hints.append({"signature": name, "source": source, "strength": "ordered_8_bytes",
                              "distinct_constants": 8, "evidence": [found]})
    return hints


def hint_block(hints):
    """Proposed v7 block: no ID, project, target name or model prediction."""
    lines = ["/* --- Constant signature hints (not verified algorithm names) --- */"]
    for hint in hints:
        values = [e.get("value", e.get("bytes")) for e in hint["evidence"]]
        lines.append(f"{hint['signature']} | source={hint['source']} | evidence={','.join(values)} | strength={hint['strength']}")
    return "\n".join(lines) if hints else ""


def records(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def binding(value):
    name, separator, path = value.partition("=")
    if not separator or not name or not path:
        raise argparse.ArgumentTypeError("expected SPLIT=PATH")
    return name, Path(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", action="append", required=True, type=binding)
    parser.add_argument("--predictions", action="append", default=[], type=binding)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    args = parser.parse_args()
    if len(dict(args.dataset)) != len(args.dataset) or len(dict(args.predictions)) != len(args.predictions):
        parser.error("split names must be unique")
    inputs = {p.resolve() for _, p in args.dataset + args.predictions}
    if args.output.resolve() in inputs or args.summary.resolve() in inputs or args.output.resolve() == args.summary.resolve():
        parser.error("output paths must differ from inputs and each other")
    unknown = set(dict(args.predictions)) - set(dict(args.dataset))
    if unknown:
        parser.error(f"prediction split has no dataset: {sorted(unknown)}")
    # Reuse the repository's canonical real-name F1, not rounded saved values.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from taban import f1

    predictions = {}
    for split, path in args.predictions:
        pred = {}
        for row in records(path):
            if row["id"] in pred:
                raise ValueError(f"duplicate prediction ID in {split}: {row['id']}")
            pred[row["id"]] = row
        predictions[split] = pred
    summary = {"schema": "asmsense.constant_hints.v1", "splits": {}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output:
        for split, path in args.dataset:
            counts = Counter()
            families = Counter()
            sources = Counter()
            projects = Counter()
            unique_all, unique_hits, unique_related, seen_ids = set(), set(), set(), set()
            scores = defaultdict(list)
            exact = Counter()
            matched_predictions = set()
            for row in records(path):
                if row["id"] in seen_ids:
                    raise ValueError(f"duplicate dataset ID in {split}: {row['id']}")
                seen_ids.add(row["id"])
                counts["rows"] += 1
                name = row["gercek_ad"]
                identity = (row["id"].split(":")[0], name)
                unique_all.add(identity)
                related = bool(NAME_RELATED.search(name))
                counts["name_related_rows"] += related
                texts = [m["content"] for m in row["messages"] if m["role"] == "user"]
                hints = detect("\n".join(texts))
                if hints:
                    counts["hit_rows"] += 1
                    counts["hit_name_related_rows"] += related
                    unique_hits.add(identity)
                    if related:
                        unique_related.add(identity)
                    if any(h["strength"] not in ("weak_single_constant", "ambiguous_shared_iv") for h in hints):
                        counts["strong_hit_rows"] += 1
                    families.update({h["signature"] for h in hints})
                    sources.update({h["source"] for h in hints})
                    projects.update([row["proje"]])
                    output.write(json.dumps({"split": split, "id": row["id"], "signature_hints": hints,
                                             "input_block": hint_block(hints)}, ensure_ascii=False) + "\n")
                prediction = predictions.get(split, {}).get(row["id"])
                if prediction is not None:
                    matched_predictions.add(row["id"])
                    guess = str(prediction.get("tahmin") or "")
                    groups = ["all", "hits" if hints else "nonhits"]
                    if related:
                        groups.append("name_related")
                    if hints and related:
                        groups.append("hits_name_related")
                    groups.extend("signature:" + name for name in {h["signature"] for h in hints})
                    for group in groups:
                        scores[group].append(f1(guess, name))
                        exact[group] += guess == name
            result = {key: counts[key] for key in ("rows", "name_related_rows", "hit_rows", "hit_name_related_rows", "strong_hit_rows")}
            result.update({"unique_source_functions": len(unique_all), "unique_hit_source_functions": len(unique_hits),
                           "unique_hit_name_related_source_functions": len(unique_related),
                           "signatures": dict(sorted(families.items())), "sources": dict(sources), "projects": dict(projects),
                           "baseline_prediction_rows": len(predictions.get(split, {})),
                           "baseline_unmatched_prediction_rows": len(set(predictions.get(split, {})) - matched_predictions),
                           "baseline": {group: {"n": len(values), "real_name_f1": sum(values) / len(values),
                                       "literal_exact_names": exact[group], "zero_f1": sum(v == 0 for v in values)}
                                        for group, values in sorted(scores.items())}})
            summary["splits"][split] = result
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
