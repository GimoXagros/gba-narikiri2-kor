"""Build the reviewed pass02 script in the original Korean text slots.

All edits are bound to the user-confirmed in-place pass01 ROM.  This builder
never relocates text, rewrites pointers, or enlarges the ROM.  Layout checks
are conservative static checks; they do not replace in-game rendering tests.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import struct
import unicodedata
from collections import defaultdict
from pathlib import Path

from bps import apply_bps, create_bps
from build_dialogue_tone import ascii_marker_controls
from confirmed_text_edits import encode_full, normalized
from extract_dialogue_book_data import readable, source_text
from narikiri2_text_spec import decode_game_text

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "8d4c8dca40d7fdaa561dfa64fecc6ef42c04a11cdd345553e7bc5bb30313c142"
JP_SHA = "a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7"
CATALOG_SHA = "8bc337e9d514e5f0bbd79f69f4f07c1d3d8ffc03dd4d2d9e14b36ca4878c3892"
BASE_CORPUS_SHA = "17628a5ae6af1c5c7c5682b8a09990700265798754e9e4ac8e507d30dc2ca07f"
CONTROL = re.compile(r"@[A-Za-z]|%[0-9]*[A-Za-z]")
ROM_STEM = "Xagros_Narikiri2_KOR_v1.0_tone-pass02-inplace-candidate"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def catalog_bindings(raw: bytes) -> dict[int, str]:
    if sha(raw) != CATALOG_SHA:
        raise ValueError("Pointer catalog identity changed")
    result = {}
    for row in csv.DictReader(raw.decode("utf-8-sig").splitlines()):
        if row["kind"] != "full_text":
            continue
        storage = int(row["storage"], 16)
        binding = f"{row['id']}:{storage:08X}"
        if storage in result:
            raise ValueError(f"Duplicate catalog storage {storage:08X}")
        result[storage] = binding
    if len(result) != 8945:
        raise ValueError("Unexpected full-binding denominator")
    return result


def pointer_sightings(rom: bytes) -> dict[int, list[int]]:
    """Inventory exact 32-bit ROM-address byte patterns, including unaligned hits."""
    sightings: dict[int, list[int]] = defaultdict(list)
    pos = rom.find(b"\x08", 3)
    while pos >= 0:
        at = pos - 3
        target = struct.unpack_from("<I", rom, at)[0] - 0x08000000
        if 0 <= target < len(rom):
            sightings[target].append(at)
        pos = rom.find(b"\x08", pos + 1)
    return sightings


def validate_pattern_exception(row: dict, hit: tuple[int, int], base: bytes,
                               jp: bytes, catalog: dict[int, str]) -> None:
    target, position = hit
    declarations = []
    if "slot_pattern_exception" in row:
        declarations.append(row["slot_pattern_exception"])
    if "slot_pattern_exceptions" in row:
        declarations.extend(row["slot_pattern_exceptions"]["hits"])
    matching = [entry for entry in declarations
                if int(entry["pattern_position"], 16) == position
                and int(entry["pattern_target"], 16) == target]
    if len(matching) != 1:
        raise ValueError(f"Undeclared interior pointer-like pattern {row['binding']} {hit}")
    entry = matching[0]
    if position % 4 == 0 or position in catalog or target < len(jp):
        raise ValueError("Pattern exception is aligned, cataloged, or inside JP ROM")
    region_start = int(entry.get("baseline_and_japanese_region_offset",
                                 entry.get("aligned_region_offset")), 16)
    length = entry.get("region_length", 32 if "aligned_region_offset" in entry else 48)
    expected_sha = entry.get("region_sha256", entry.get("aligned_region_sha256"))
    if not (region_start <= position < region_start + length <= len(jp)):
        raise ValueError("Pattern exception region does not cover its sighting")
    if base[region_start:region_start + length] != jp[region_start:region_start + length]:
        raise ValueError("Pattern exception differs from the original JP region")
    if sha(base[region_start:region_start + length]) != expected_sha:
        raise ValueError("Pattern exception region hash changed")
    if struct.unpack_from("<I", base, position)[0] != 0x08000000 + target:
        raise ValueError("Pattern exception bytes changed")
    for key, address in (("aligned_u32_at_409308", 0x409308),
                         ("aligned_u32_at_40930C", 0x40930C),
                         ("aligned_u32_at_409310", 0x409310),
                         ("aligned_u32_at_38C568", 0x38C568),
                         ("aligned_u32_at_38C56C", 0x38C56C),
                         ("aligned_u32_at_38C570", 0x38C570)):
        if key in entry and struct.unpack_from("<I", base, address)[0] != int(entry[key], 16):
            raise ValueError("Pattern exception aligned words changed")
    if "aligned_u32_before" in entry or "aligned_u32_after" in entry:
        preceding_word = position & ~3
        following_word = preceding_word + 4
        if (struct.unpack_from("<I", base, preceding_word)[0]
                != int(entry["aligned_u32_before"], 16)
                or struct.unpack_from("<I", base, following_word)[0]
                != int(entry["aligned_u32_after"], 16)):
            raise ValueError("Pattern exception adjacent aligned records changed")
    if entry.get("catalog_binding_at_pattern_position", False):
        raise ValueError("Pattern exception unexpectedly claims a catalog binding")
    if not entry.get("target_outside_original_8mb_jp_rom", False):
        raise ValueError("Pattern exception lacks original-ROM boundary evidence")


def static_layout(before: str, after: str, binding: str) -> dict:
    """Compare a conservative 12px-per-printable-glyph upper bound per page.

    The observed full-width dialogue wrap is 18 cells.  Dynamic marker widths
    and consumer-specific layout are not inferred; controls must be identical.
    """
    def pages(value: str) -> list[list[int]]:
        result = []
        for page in re.split(r"@P|%k", value):
            result.append([len(CONTROL.sub("", line)) for line in page.split("\n")])
        return result

    old_pages, new_pages = pages(before), pages(after)
    if len(old_pages) != len(new_pages) or any(
        len(old) != len(new) for old, new in zip(old_pages, new_pages)
    ):
        raise ValueError(f"Page or explicit line count changed: {binding}")
    def wrapped(lines: list[int]) -> int:
        return sum(max(1, math.ceil(cells / 18)) for cells in lines)
    if any(wrapped(new) > wrapped(old)
           for old, new in zip(old_pages, new_pages)):
        raise ValueError(f"Conservative 18-cell wrapped row count grew: {binding}")
    growth = [{"page": page, "line": line, "before_cells": old,
               "after_cells": new, "upper_bound_before_px": old * 12,
               "upper_bound_after_px": new * 12}
              for page, (old_lines, new_lines) in enumerate(zip(old_pages, new_pages), 1)
              for line, (old, new) in enumerate(zip(old_lines, new_lines), 1)
              if new > old]
    return {"assumption": "12px upper bound per printable glyph; renderer path unverified",
            "old_page_cells": old_pages, "new_page_cells": new_pages,
            "static_glyph_growth": growth,
            "dynamic_token_width": "UNKNOWN; source tokens kept in original order"}


def numeric_tokens(value: str) -> list[str]:
    return re.findall(r"\d+", unicodedata.normalize("NFKC", CONTROL.sub("", value)))


def build(base: bytes, jp: bytes, decisions: list[dict],
          catalog_raw: bytes, book_raw: bytes) -> tuple[bytes, bytes, dict, dict]:
    if sha(base) != BASE_SHA or len(base) != 13270790 or sha(jp) != JP_SHA or len(jp) != 8388608:
        raise ValueError("Unrecognized pass01 in-place / AN9J ROM identity")
    catalog = catalog_bindings(catalog_raw)
    all_catalog_storages = {int(row["storage"], 16) for row in
                            csv.DictReader(catalog_raw.decode("utf-8-sig").splitlines())}
    if len(all_catalog_storages) != 10380:
        raise ValueError("Complete pointer catalog denominator changed")
    if sha(book_raw) != BASE_CORPUS_SHA:
        raise ValueError("Frozen baseline dialogue corpus identity changed")
    book = json.loads(book_raw)
    if book["meta"]["korean_sha256"] != BASE_SHA:
        raise ValueError("Input corpus is not bound to the active baseline")
    if len(book["full"]) != 8945 or len(book["compact"]) != 1227:
        raise ValueError("Input corpus denominator changed")
    book_rows = {row[0]: row for row in book["full"]}
    if len(book_rows) != 8945 or set(book_rows) != set(catalog.values()):
        raise ValueError("Original record ID duplicated/merged or binding catalog changed")
    target_aliases: dict[int, set[str]] = defaultdict(set)
    for storage, binding in catalog.items():
        target, _ = source_text(base, storage)
        target_aliases[target].add(binding)
    patterns = pointer_sightings(base)
    result = bytearray(base)
    occupied: list[tuple[int, int, str]] = []
    writes = []
    declared: set[str] = set()
    for row in decisions:
        binding = row["binding"]
        storage = int(row["storage"], 16)
        if catalog.get(storage) != binding or binding != f"{row['id']}:{storage:08X}":
            raise ValueError(f"Unknown or duplicate-ID-merged binding: {binding}")
        start, old_raw = source_text(base, storage)
        end = start + len(old_raw) + 1
        if any(start < prior_end and prior_start < end
               for prior_start, prior_end, _ in occupied):
            raise ValueError(f"Overlapping or duplicate writer slot: {binding}")
        occupied.append((start, end, binding))
        aliases = target_aliases[start]
        affected = row["affected_bindings"]
        if len(set(affected)) != len(affected) or set(affected) != aliases or binding not in aliases:
            raise ValueError(f"Incomplete shared-slot consumer set: {binding}")
        source_map = row.get("affected_source_jp_sha256")
        if not isinstance(source_map, dict) or set(source_map) != aliases:
            raise ValueError(f"Incomplete per-binding JP source hashes: {binding}")
        for alias in aliases:
            alias_storage = int(alias.split(":")[1], 16)
            _, alias_jp = source_text(jp, alias_storage)
            if sha(alias_jp.decode("cp932").encode()) != source_map[alias]:
                raise ValueError(f"Shared-slot Japanese source changed: {alias}")
        if declared.intersection(affected):
            raise ValueError(f"Binding affected by more than one writer: {binding}")
        declared.update(affected)
        if start != int(row["old_slot_offset"], 16) or sha(old_raw) != row["before_raw_sha256"]:
            raise ValueError(f"Source slot mismatch: {binding}")
        if base[end - 1] != 0:
            raise ValueError(f"Unterminated original slot: {binding}")
        _, jp_raw = source_text(jp, storage)
        source = jp_raw.decode("cp932")
        before = normalized(decode_game_text(base, old_raw))
        if before == normalized(row["after"]):
            raise ValueError(f"No-op decision cannot enter candidate: {binding}")
        if (row.get("source_hash_policy") != "SHA256_UTF8_EXACT_CP932_DECODED_JP"
                or sha(source.encode()) != row["source_sha256"]
                or sha(before.encode()) != row["before_sha256"]):
            raise ValueError(f"JP/KR source text identity mismatch: {binding}")
        payload = bytes.fromhex(row["after_raw_hex"]) if row.get("after_raw_hex") else encode_full(row["after"])
        if (len(payload) != row["new_payload_bytes"] or len(old_raw) != row["old_payload_bytes"]
                or len(payload) > len(old_raw) or b"\0" in payload):
            raise ValueError(f"Original slot byte capacity exceeded: {binding}")
        if normalized(decode_game_text(base, payload)) != normalized(row["after"]):
            raise ValueError(f"After text does not round-trip: {binding}")
        if (ascii_marker_controls(old_raw) != ascii_marker_controls(payload)
                or old_raw.count(b"\n") != payload.count(b"\n")
                or old_raw.count(b"\x12") != payload.count(b"\x12")):
            raise ValueError(f"Raw marker/mode/newline sequence changed: {binding}")
        if numeric_tokens(before) != numeric_tokens(row["after"]):
            raise ValueError(f"Numeric literal changed: {binding}")
        if row.get("raw_edit_policy"):
            policy = row["raw_edit_policy"]
            if policy["kind"] != "EXACT_SUFFIX_REPLACEMENT":
                raise ValueError("Unsupported raw segment edit")
            old_suffix, new_suffix = bytes.fromhex(policy["old_suffix_hex"]), bytes.fromhex(policy["new_suffix_hex"])
            if (old_raw.count(old_suffix) != 1 or old_raw.endswith(old_suffix) is False
                    or payload != old_raw[:-len(old_suffix)] + new_suffix
                    or start + len(old_raw) - len(old_suffix) != int(policy["suffix_start_offset"], 16)):
                raise ValueError(f"Raw segment replacement changed adjacent bytes: {binding}")
        layout = static_layout(before, normalized(row["after"]), binding)
        actual_patterns = {(target, pos) for target in range(start, end)
                           for pos in patterns.get(target, [])}
        expected_patterns = {(start, int(alias.split(":")[1], 16)) for alias in aliases}
        if not expected_patterns.issubset(actual_patterns):
            raise ValueError(f"Declared alias pointer is missing: {binding}")
        extras = actual_patterns - expected_patterns
        for hit in extras:
            validate_pattern_exception(row, hit, base, jp, catalog)
        if extras and not (row.get("slot_pattern_exception") or row.get("slot_pattern_exceptions")):
            raise ValueError(f"Undeclared pointer-like interior hit: {binding}")
        for alias in aliases:
            alias_storage = int(alias.split(":")[1], 16)
            if source_text(base, alias_storage)[0] != start:
                raise ValueError(f"Shared-slot alias points elsewhere: {alias}")
            if result[alias_storage:alias_storage + 4] != base[alias_storage:alias_storage + 4]:
                raise ValueError(f"Pointer storage overlapped a text write: {alias}")
        slot = payload + bytes(len(old_raw) + 1 - len(payload))
        result[start:end] = slot
        writes.append({"binding": binding, "affected_bindings": affected, "slot_offset": f"{start:08X}",
                       "slot_bytes": end - start, "old_payload_bytes": len(old_raw),
                       "new_payload_bytes": len(payload), "old_slot_sha256": sha(base[start:end]),
                       "new_slot_sha256": sha(slot), "layout": layout,
                       "noncatalog_pointer_like_hits": len(extras)})
    if len(result) != len(base):
        raise ValueError("ROM length changed")
    changed_positions = {pos for start, end, _ in occupied for pos in range(start, end)}
    if any(old != new and pos not in changed_positions
           for pos, (old, new) in enumerate(zip(base, result))):
        raise ValueError("Byte changed outside approved original text slots")
    for storage in all_catalog_storages:
        if result[storage:storage + 4] != base[storage:storage + 4]:
            raise ValueError(f"Pointer catalog storage changed: {storage:08X}")
    candidate = bytes(result)
    for binding in declared:
        storage = int(binding.split(":")[1], 16)
        row = next(entry for entry in decisions if binding in entry["affected_bindings"])
        start, raw = source_text(candidate, storage)
        if start != int(row["old_slot_offset"], 16) or normalized(decode_game_text(candidate, raw)) != normalized(row["after"]):
            raise ValueError(f"Affected binding readback failed: {binding}")
    original_by_binding = {row[0]: row for row in book["full"]}
    for record in book["full"]:
        binding = record[0]
        storage = int(record[10], 16)
        target, raw = source_text(candidate, storage)
        text = decode_game_text(candidate, raw)
        if binding not in declared and text != record[5]:
            raise ValueError(f"Undeclared binding text changed: {binding}")
        if target != int(record[12], 16):
            raise ValueError(f"Catalog target changed: {binding}")
        record[5] = text
        record[6] = readable(text)
        if binding in declared:
            record[7] = "말투 교정 pass02"
    if len(original_by_binding) != 8945:
        raise ValueError("Full corpus binding count changed")
    book["meta"]["korean_sha256"] = sha(candidate)
    book["meta"]["tone_review_scope"] = (
        "8,945 full-binding JP/KO texts read at least once; 3,944 have static event context. "
        "Speaker, branch, and runtime execution remain UNKNOWN where no evidence exists. "
        "70 original-slot writers affect 75 bindings in this pass."
    )
    book["meta"]["tone_review_status"] = "LOCAL_CANDIDATE_STATIC_REVIEW; RUNTIME_PARTIAL_OR_NOT_RUN"
    corpus = json.dumps(book, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    growth = [{"binding": row["binding"], **item}
              for row in writes for item in row["layout"]["static_glyph_growth"]]
    report = {"status": "LOCAL_CANDIDATE_RUNTIME_NOT_YET_RUN", "base_sha256": sha(base),
              "japanese_sha256": sha(jp), "candidate_sha256": sha(candidate),
              "corpus_sha256": sha(corpus), "decision_count": len(decisions),
              "writer_count": len(writes), "affected_bindings": len(declared),
              "catalog_full_bindings": len(catalog),
              "catalog_pointer_locations_unchanged": len(all_catalog_storages),
              "compact_fields_preserved": len(book["compact"]),
              "rom_bytes": len(candidate), "rom_length_unchanged": True,
              "catalog_pointers_unchanged": True, "all_changes_original_slots": True,
              "static_layout_growth": growth,
              "layout_limit": "Conservative 12px/cell comparison only; each consumer and dynamic width need runtime review",
              "writes": writes}
    return candidate, corpus, report, {"affected_bindings": sorted(declared),
                                        "candidate_corpus_sha256": sha(corpus)}


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("base", "japanese", "changes", "dialogue-book", "catalog", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Output directory must be new")
    base, jp = args.base.read_bytes(), args.japanese.read_bytes()
    decision_raw = args.changes.read_bytes()
    decisions = json.loads(decision_raw)
    candidate, corpus, report, mapping = build(
        base, jp, decisions, args.catalog.read_bytes(), args.dialogue_book.read_bytes())
    patch = create_bps(jp, candidate)
    if apply_bps(jp, patch) != candidate:
        raise ValueError("JP cumulative BPS did not reproduce the candidate")
    report["decision_sha256"] = sha(decision_raw)
    report["bps_sha256"] = sha(patch)
    mapping.update({"source_base_sha256": sha(base), "candidate_rom_sha256": sha(candidate),
                    "decision_sha256": sha(decision_raw), "pointer_catalog_sha256": CATALOG_SHA,
                    "review_ledger": "private_validation/tone-pass02/SUMMARY.json"})
    args.out.mkdir(parents=True)
    (args.out / (ROM_STEM + ".gba")).write_bytes(candidate)
    (args.out / (ROM_STEM + "_FROM_JP.bps")).write_bytes(patch)
    (args.out / "final-dialogue-book.json").write_bytes(corpus)
    (args.out / "BUILD_MANIFEST.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    (args.out / "SOURCE_MAPPING.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "writes"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
