"""Rebuild the three reviewed tone edits inside their original v1.0 text slots.

This is a local retest candidate after a VBA-M regression report. It preserves
the ROM length and the three event pointers. It does not claim that the reported
VBA-M failure is resolved until the same consumer has been retested.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from bps import apply_bps, create_bps
from build_dialogue_tone import (build as build_relocated, final_dataset, inventory,
                                 require_identity, scene_map, sha)
from extract_dialogue_book_data import source_text
from narikiri2_text_spec import decode_game_text

STEM = "Xagros_Narikiri2_KOR_v1.0_tone-pass01-inplace-retest"


def slot_refs(rom: bytes, start: int, end: int) -> list[tuple[int, int]]:
    """Find every ROM byte-pattern resembling a GBA pointer into this slot."""
    refs = []
    for target in range(start, end):
        pattern = struct.pack("<I", 0x08000000 + target)
        pos = rom.find(pattern)
        while pos != -1:
            refs.append((target, pos))
            pos = rom.find(pattern, pos + 1)
    return refs


def build_inplace(base: bytes, jp: bytes, decisions: list[dict]) -> tuple[bytes, dict]:
    # The existing builder owns the source/scene/actor/control/numeric guards.
    relocated, prior = build_relocated(base, jp, decisions)
    result = bytearray(base)
    writes = []
    allowed = set()
    for row in prior["writes"]:
        storage = int(row["storage"], 16)
        start, old_raw = source_text(base, storage)
        _, new_raw = source_text(relocated, storage)
        end = start + len(old_raw) + 1
        if len(new_raw) > len(old_raw):
            raise ValueError(f"Edited text exceeds original slot: {row['binding']}")
        if slot_refs(base, start, end) != [(start, storage)]:
            raise ValueError(f"Shared or interior pointer enters original slot: {row['binding']}")
        if base[start:end] != old_raw + b"\0":
            raise ValueError(f"Original slot boundary changed: {row['binding']}")
        pointer = base[storage:storage + 4]
        if struct.unpack("<I", pointer)[0] != 0x08000000 + start:
            raise ValueError(f"Original pointer mismatch: {row['binding']}")
        encoded = new_raw + b"\0" + bytes(len(old_raw) - len(new_raw))
        result[start:end] = encoded
        allowed.update(range(start, end))
        writes.append({**row, "offset": f"{start:08X}", "before_pointer": pointer.hex(),
                       "after_pointer": pointer.hex(), "old_payload_bytes": len(old_raw),
                       "new_payload_bytes": len(new_raw), "slot_bytes": end - start,
                       "slot_sha256_before": sha(base[start:end]),
                       "slot_sha256_after": sha(encoded), "padding_bytes": len(old_raw) - len(new_raw)})
    if len(result) != len(base):
        raise ValueError("In-place candidate changed ROM length")
    if any(left != right and i not in allowed for i, (left, right) in enumerate(zip(base, result))):
        raise ValueError("Unexpected ROM byte changed outside reviewed slots")
    for row in writes:
        storage = int(row["storage"], 16)
        if result[storage:storage + 4] != base[storage:storage + 4]:
            raise ValueError("Event pointer changed")
        _, raw = source_text(result, storage)
        if decode_game_text(result, raw).replace("\u3000", " ") != row["after"]:
            raise ValueError("In-place text readback failed")
    output = bytes(result)
    return output, {"status": "LOCAL_RETEST_CANDIDATE_VBA_UNVERIFIED",
                    "base_sha256": sha(base), "japanese_sha256": sha(jp),
                    "target_sha256": sha(output), "changed_bindings": len(writes),
                    "rom_length_unchanged": True, "event_pointers_unchanged": True,
                    "all_changes_confined_to_original_text_slots": True,
                    "original_data_moved": False, "writes": writes}


def verify_prior_text_identity(old_book: dict, new_book: dict) -> dict:
    if len(old_book["full"]) != len(new_book["full"]) or len(old_book["compact"]) != len(new_book["compact"]):
        raise ValueError("Prior candidate corpus denominator differs")
    if old_book["compact"] != new_book["compact"]:
        raise ValueError("Compact corpus changed")
    for old, new in zip(old_book["full"], new_book["full"]):
        if old[0] != new[0] or old[5] != new[5] or old[6] != new[6]:
            raise ValueError(f"Prior candidate text differs: {old[0]}")
    return {"full_binding_count": len(new_book["full"]),
            "compact_binding_count": len(new_book["compact"]),
            "all_full_korean_text_and_readable_fields_equal": True,
            "all_compact_records_equal": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("base", "japanese", "changes", "dialogue-book", "prior-candidate-book", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Output directory must be new")
    base, jp = args.base.read_bytes(), args.japanese.read_bytes()
    require_identity(base, jp)
    decisions = json.loads(args.changes.read_text("utf-8"))
    result, report = build_inplace(base, jp, decisions)
    patch = create_bps(jp, result)
    if apply_bps(jp, patch) != result:
        raise ValueError("JP cumulative BPS round trip failed")
    book = final_dataset(base, result, args.dialogue_book, report["writes"])
    prior_bytes = args.prior_candidate_book.read_bytes()
    prior_book = json.loads(prior_bytes)
    text_identity = verify_prior_text_identity(prior_book, book)
    final_corpus = json.dumps(book, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    mapping = scene_map(jp, base, result, inventory(), args.dialogue_book.read_bytes(), final_corpus)
    mapping["scope"] += " Pub Rose was naturally traversed in mGBA on the old candidate; this in-place candidate requires its own runtime retest."
    report["prior_relocated_candidate_corpus_sha256"] = sha(prior_bytes)
    report["text_identity_to_prior_candidate"] = text_identity
    report["bps_sha256"] = sha(patch)
    args.out.mkdir(parents=True)
    (args.out / (STEM + ".gba")).write_bytes(result)
    (args.out / (STEM + "_FROM_JP.bps")).write_bytes(patch)
    (args.out / "BUILD_MANIFEST.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    (args.out / "scene_map.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), "utf-8")
    (args.out / "final-dialogue-book.json").write_bytes(final_corpus)
    print(json.dumps({"rom_sha256": sha(result), "rom_bytes": len(result), "bps_sha256": sha(patch),
                      "bps_bytes": len(patch), "changed_bindings": len(report["writes"]),
                      "text_identity": text_identity}, ensure_ascii=False))


if __name__ == "__main__":
    main()
