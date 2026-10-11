import json
from pathlib import Path
import subprocess
import sys

import pytest

from lora.imzalar import (
    AES_SBOX_PREFIX,
    DECOMPILE_MARKER,
    MD5_T,
    SHA256_K,
    crc_table,
    detect,
    hint_block,
)


def names(text):
    return {hint["signature"] for hint in detect(text)}


def asm(values):
    return "\n".join(f"mov eax, {hex(value)}" for value in values)


@pytest.mark.parametrize(
    "values,expected",
    [
        (SHA256_K[:4], "sha256_round_k"),
        (MD5_T[:4], "md5_round_t"),
        (crc_table(0xEDB88320)[:4], "crc32_ieee_table_values"),
        (crc_table(0x82F63B78)[:4], "crc32c_table_values"),
        ((0xCC9E2D51, 0x1B873593), "murmur3_x86_32"),
    ],
)
def test_known_constants(values, expected):
    assert expected in names(asm(values))


def test_threshold_counts_distinct_values_not_repeated_occurrences():
    assert not names(asm([SHA256_K[0]] * 20))
    assert "sha256_round_k" not in names(asm(SHA256_K[:3]))


def test_asm_and_decompile_are_not_independent_votes():
    hints = detect(asm(SHA256_K[:4]) + DECOMPILE_MARKER + asm(SHA256_K[:4]))
    assert {hint["source"] for hint in hints} == {"asm", "decompile"}
    assert not names(asm(SHA256_K[:2]) + DECOMPILE_MARKER + asm(SHA256_K[2:4]))


def test_signed_decimal_suffix_and_sign_extension():
    source = "\n".join(f"v += {value - (1 << 32) if value >= (1 << 31) else value}L;" for value in MD5_T[:4])
    assert "md5_round_t" in names(DECOMPILE_MARKER + source)
    assert "crc32_ieee_polynomial" in names("xor eax, 0xffffffffedb88320")
    assert "crc32_ieee_polynomial" in names("xor eax, -0x12477ce0")


def test_packed_iv_is_ambiguous_not_md5_proof():
    hints = detect("mov rax, 0xefcdab8967452301\nmov rax, 0x1032547698badcfe")
    assert [hint["signature"] for hint in hints] == ["md4_md5_sha1_ripemd160_iv"]
    assert hints[0]["distinct_constants"] == 4
    assert hints[0]["strength"] == "ambiguous_shared_iv"


def test_sha512_blake2b_words_are_not_packed_sha256_iv():
    # Real monocypher BLAKE2b inputs exposed this important width ambiguity.
    text = asm((0xBB67AE8584CAA73B, 0x3C6EF372FE94F82B, 0xA54FF53A5F1D36F1, 0x510E527FADE682D1))
    assert names(text) == {"sha512_or_blake2b_iv"}
    assert "sha256_or_blake2s_iv" not in names(text)


def test_packed_sha256_iv_requires_two_matching_halves():
    assert names(asm((0xBB67AE856A09E667, 0xA54FF53A3C6EF372))) == {"sha256_or_blake2s_iv"}
    assert not names(asm((0xBB67AE8500000001, 0xA54FF53A00000002)))


@pytest.mark.parametrize("endian", ["little", "big"])
def test_aes_packed_prefix(endian):
    value = int.from_bytes(AES_SBOX_PREFIX[:8], endian)
    assert "aes_sbox_prefix" in names(f"mov rax, {hex(value)}")


def test_aes_requires_ordered_bytes_not_a_bag():
    assert "aes_sbox_prefix" in names(asm(AES_SBOX_PREFIX[:8]))
    assert "aes_sbox_prefix" not in names(asm(reversed(AES_SBOX_PREFIX[:8])))
    assert "aes_sbox_prefix" not in names(asm(AES_SBOX_PREFIX[:7]))


def test_ignore_strings_comments_addresses_identifiers_and_assistant_labels():
    body = asm(SHA256_K[:4])
    assert not names("\n".join(f"mov rax, [rip + {hex(v)}] ; -> {hex(v)}" for v in SHA256_K[:4]))
    assert not names(DECOMPILE_MARKER + f'puts("{body}"); /* {body} */ // {body}')
    assert not names(DECOMPILE_MARKER + "\n".join(f"DAT_{hex(v)[2:]};" for v in SHA256_K[:4]))
    assert not names("mov eax, 0x428a2f98bad_identifier")


def test_weak_hint_and_label_free_format():
    hints = detect("xor eax, 0xedb88320")
    assert hints[0]["strength"] == "weak_single_constant"
    block = hint_block(hints)
    assert "crc32_ieee_polynomial" in block
    assert "0xedb88320" in block
    assert "gercek" not in block and "id=" not in block
    assert hint_block([]) == ""


def test_md5_catalog_matches_standard_endpoints():
    assert MD5_T[0] == 0xD76AA478
    assert MD5_T[-1] == 0xEB86D391


def test_cli_real_label_scoring_and_prediction_id_join(tmp_path):
    data = tmp_path / "data.jsonl"
    predictions = tmp_path / "predictions.jsonl"
    output = tmp_path / "hints.jsonl"
    summary = tmp_path / "summary.json"
    rows = [
        {
            "id": "p/x.c:-O0:tam:sub_1:md5_transform",
            "gercek_ad": "md5_transform",
            "proje": "p",
            "messages": [
                {"role": "user", "content": asm(MD5_T[:4])},
                {"role": "assistant", "content": "md5_transform"},
            ],
        },
        {
            "id": "p/x.c:-O0:tam:sub_2:read",
            "gercek_ad": "read",
            "proje": "p",
            "messages": [{"role": "user", "content": "ret"}, {"role": "assistant", "content": asm(MD5_T[:4])}],
        },
    ]
    data.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    predictions.write_text(
        json.dumps({"id": rows[0]["id"], "gercek": "transform", "tahmin": "transform", "f1": 1}) + "\n"
    )
    script = Path(__file__).resolve().parents[1] / "lora/imzalar.py"
    command = [
        sys.executable,
        str(script),
        "--dataset",
        f"test={data}",
        "--predictions",
        f"test={predictions}",
        "--output",
        str(output),
        "--summary",
        str(summary),
    ]
    subprocess.run(command, check=True, capture_output=True)
    result = json.loads(summary.read_text())["splits"]["test"]
    assert result["rows"] == 2 and result["hit_rows"] == 1
    assert result["hit_name_related_rows"] == 1
    assert result["baseline"]["hits"]["real_name_f1"] == pytest.approx(2 / 3)
    assert result["baseline"]["hits"]["literal_exact_names"] == 0
    assert len(output.read_text().splitlines()) == 1
    forbidden = command.copy()
    forbidden[forbidden.index("--output") + 1] = str(data)
    process = subprocess.run(forbidden, capture_output=True)
    assert process.returncode != 0
    assert "output paths must differ" in process.stderr.decode()
    assert len(data.read_text().splitlines()) == 2
