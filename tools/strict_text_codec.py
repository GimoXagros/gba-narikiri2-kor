#!/usr/bin/env python3
"""Bounded experimental strict-slot phrase codec (not wired to game consumers).

Each stream ends in 00 and decodes to the exact baseline bytes plus a NUL.
The ROM codebook is address-neutral: escape byte, 256-byte token map (FF means
literal), then 96 fixed nine-byte entries (length, eight raw bytes).  A caller
must supply a proven stream bound and an owned output buffer; neither is
provided by the format or by the current game integration.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path

TOKEN_COUNT = 96
ENTRY_SIZE = 9
BOOK_SIZE = 1 + 256 + TOKEN_COUNT * ENTRY_SIZE


class CodecError(ValueError):
    pass


def _check_payload(payload: bytes) -> None:
    if not isinstance(payload, bytes) or b"\0" in payload:
        raise CodecError("payload must be bytes without embedded NUL")


def build_codebook(payloads: list[bytes]) -> bytes:
    if not payloads:
        raise CodecError("empty corpus")
    for payload in payloads:
        _check_payload(payload)
    frequency = collections.Counter(byte for p in payloads for byte in p)
    # Rare original byte values minimize escape cost. Zero remains EOS.
    reserved = sorted(range(1, 256), key=lambda b: (frequency[b], b))[:TOKEN_COUNT + 1]
    escape, tokens = reserved[0], reserved[1:]
    reserved_set = set(reserved)
    literal_cost = lambda b: 2 if b in reserved_set else 1
    appearances: collections.Counter[bytes] = collections.Counter()
    # A shared phrase must occur in at least two distinct raw templates.
    # Counting distinct templates prevents a single long sentence from being
    # moved wholesale to an external dictionary under a one-byte ID.
    for payload in set(payloads):
        seen = set()
        for size in range(2, 9):
            seen.update(payload[i:i + size] for i in range(len(payload) - size + 1))
        appearances.update(seen)
    ranked = sorted(
        ((count * (sum(map(literal_cost, phrase)) - 1) - ENTRY_SIZE, phrase)
         for phrase, count in appearances.items() if count >= 2),
        key=lambda item: (-item[0], -len(item[1]), item[1]),
    )
    selected: list[bytes] = []
    for gain, phrase in ranked:
        if gain <= 0 or len(selected) == TOKEN_COUNT:
            break
        if len(phrase) == 1 or phrase in selected:
            continue
        selected.append(phrase)
    token_map = bytearray([0xFF] * 256)
    entries = bytearray(TOKEN_COUNT * ENTRY_SIZE)
    for index, (token, phrase) in enumerate(zip(tokens, selected)):
        token_map[token] = index
        offset = index * ENTRY_SIZE
        entries[offset] = len(phrase)
        entries[offset + 1: offset + 1 + len(phrase)] = phrase
    return bytes([escape]) + bytes(token_map) + bytes(entries)


def validate_book(book: bytes) -> None:
    if len(book) != BOOK_SIZE:
        raise CodecError(f"codebook length {len(book)} != {BOOK_SIZE}")
    escape = book[0]
    mapping = book[1:257]
    if escape == 0 or mapping[0] != 0xFF or mapping[escape] != 0xFF:
        raise CodecError("invalid reserved codebook byte")
    used = set()
    for index in mapping:
        if index == 0xFF:
            continue
        if index >= TOKEN_COUNT or index in used:
            raise CodecError("invalid or duplicate token mapping")
        used.add(index)
        offset = 257 + ENTRY_SIZE * index
        size = book[offset]
        if not 2 <= size <= 8 or 0 in book[offset + 1:offset + 1 + size]:
            raise CodecError("invalid dictionary entry")


def _token_phrases(book: bytes) -> dict[bytes, int]:
    return {
        book[257 + index * ENTRY_SIZE + 1:257 + index * ENTRY_SIZE + 1 + book[257 + index * ENTRY_SIZE]]: token
        for token, index in enumerate(book[1:257]) if index != 0xFF
    }


def encode(payload: bytes, book: bytes) -> bytes:
    _check_payload(payload)
    validate_book(book)
    escape = book[0]
    mapping = book[1:257]
    phrases = _token_phrases(book)
    by_first: dict[int, list[tuple[bytes, int]]] = collections.defaultdict(list)
    for phrase, token in phrases.items():
        by_first[phrase[0]].append((phrase, token))
    n = len(payload)
    cost = [0] * (n + 1)
    choice: list[bytes] = [b""] * n
    for i in range(n - 1, -1, -1):
        byte = payload[i]
        literal = bytes((escape, byte)) if byte == escape or mapping[byte] != 0xFF else bytes((byte,))
        best_cost = len(literal) + cost[i + 1]
        best = literal
        for phrase, token in by_first[byte]:
            # A complete entry may occur inside other entries, but never store
            # that entry itself as one external dictionary ID.
            if i == 0 and len(phrase) == n:
                continue
            if payload.startswith(phrase, i) and 1 + cost[i + len(phrase)] < best_cost:
                best_cost = 1 + cost[i + len(phrase)]
                best = bytes((token,))
        cost[i] = best_cost
        choice[i] = best
    output = bytearray()
    i = 0
    while i < n:
        part = choice[i]
        output.extend(part)
        if len(part) == 1 and mapping[part[0]] != 0xFF:
            index = mapping[part[0]]
            i += book[257 + index * ENTRY_SIZE]
        else:
            i += 1
    output.append(0)
    return bytes(output)


def decode(stream: bytes, book: bytes, output_capacity: int) -> bytes:
    validate_book(book)
    if output_capacity < 1:
        raise CodecError("output capacity lacks terminator")
    result = bytearray()
    i = 0
    while i < len(stream):
        code = stream[i]
        i += 1
        if code == 0:
            if i != len(stream):
                raise CodecError("trailing stream bytes")
            result.append(0)
            return bytes(result)
        if code == book[0]:
            if i == len(stream) or stream[i] == 0:
                raise CodecError("truncated or invalid escape")
            chunk = stream[i:i + 1]
            i += 1
        else:
            index = book[1 + code]
            if index == 0xFF:
                chunk = bytes((code,))
            else:
                if index >= TOKEN_COUNT:
                    raise CodecError("token index out of range")
                offset = 257 + index * ENTRY_SIZE
                length = book[offset]
                if not 2 <= length <= 8:
                    raise CodecError("bad token length")
                chunk = book[offset + 1:offset + 1 + length]
                if 0 in chunk:
                    raise CodecError("NUL in token")
        if len(result) + len(chunk) + 1 > output_capacity:
            raise CodecError("output capacity exceeded")
        result.extend(chunk)
    raise CodecError("missing stream terminator")


def corpus_report(jp_rom: bytes, baseline_rom: bytes, rows: list[dict[str, str]]) -> tuple[bytes, dict, list[dict]]:
    from strict_text_bindings import BASELINE_SHA256, JP_SHA256, EXPECTED_BINDINGS, require_image
    require_image(jp_rom, JP_SHA256, 0x800000, "Japanese")
    require_image(baseline_rom, BASELINE_SHA256, 13270790, "baseline")
    if len(rows) != EXPECTED_BINDINGS:
        raise CodecError("catalog denominator changed")
    payloads = []
    slots = []
    for row in rows:
        start = int(row["latest_text_start_offset"], 16)
        length = int(row["latest_encoded_bytes_excluding_nul"])
        payload = baseline_rom[start:start + length]
        jp_start = int(row["jp_start_offset"], 16)
        capacity = int(row["jp_min_owner_bytes_including_nul"])
        if len(payload) != length or hashlib.sha256(payload).hexdigest() != row["latest_encoded_sha256"]:
            raise CodecError("baseline payload disagrees with catalog")
        if jp_rom[jp_start:jp_start + capacity][-1:] != b"\0":
            raise CodecError("JP slot boundary disagrees with ROM")
        payloads.append(payload)
        slots.append((jp_start, capacity))
    book = build_codebook(payloads)
    unique = {}
    overflow = 0
    overbytes = 0
    total = 0
    kinds: dict[str, dict[str, int]] = collections.defaultdict(lambda: collections.Counter())
    details = []
    for row, payload, (start, capacity) in zip(rows, payloads, slots):
        stream = encode(payload, book)
        if decode(stream, book, len(payload) + 1) != payload + b"\0":
            raise CodecError("roundtrip mismatch")
        excess = max(0, len(stream) - capacity)
        overflow += excess > 0
        overbytes += excess
        total += len(stream)
        kind = kinds[row["kind"]]
        kind["bindings"] += 1
        kind["encoded_occurrence_bytes"] += len(stream)
        kind["overflow_bindings"] += excess > 0
        kind["overflow_bytes"] += excess
        unique.setdefault(start, set()).add(payload)
        details.append({"binding_id": row["binding_id"], "jp_start": f"{start:08X}",
                        "slot_capacity": capacity, "encoded_length": len(stream),
                        "overflow_bytes": excess, "encoded_sha256": hashlib.sha256(stream).hexdigest()})
    report = {"schema": "strict-phrase-codec-trial-v1", "bindings": len(rows),
              "roundtrip_bindings": len(rows), "encoded_occurrence_bytes": total,
              "overflow_bindings": overflow, "overflow_bytes": overbytes,
              "overflow_unique_starts": len({int(x["jp_start"], 16) for x in details if x["overflow_bytes"]}),
              "alias_conflict_starts": sum(len(v) > 1 for v in unique.values()),
              "by_kind": {name: dict(counts) for name, counts in sorted(kinds.items())},
              "book_bytes": len(book), "book_sha256": hashlib.sha256(book).hexdigest(),
              "shared_token_count": sum(index != 0xFF for index in book[1:257]),
              "stream_boundary": "explicit NUL; caller input length is external metadata, not included in these byte totals",
              "decoder_code_bytes": "separately measured", "output_ram_bytes_max": max(map(len, payloads)) + 1,
              "placement_status": "UNPROVED; interior aliases, consumer integration, input bounds and table storage unresolved"}
    return book, report, details


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--jp-rom", type=Path, default=root / "Japanese.gba")
    parser.add_argument("--baseline-rom", type=Path, default=root / "private_validation/listperf-20261002/root/credits-build-a/Xagros_Narikiri2_KOR_v1.0_listperf-pass01_credits_TEST.gba")
    parser.add_argument("--catalog", type=Path, default=root / "private_validation/listperf-20261002/luna-audit/TEXT_SLOT_MAP.csv")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.catalog.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    book, report, details = corpus_report(args.jp_rom.read_bytes(), args.baseline_rom.read_bytes(), rows)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "CODEBOOK.bin").write_bytes(book)
    (args.output / "CODEC_REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (args.output / "CODEC_SLOT_RESULTS.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=details[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(details)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
