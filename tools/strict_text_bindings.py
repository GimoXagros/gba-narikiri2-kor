#!/usr/bin/env python3
"""Source-bound AN9J text pointer oracle for strict 8 MiB experiments.

The old pointer audit supplies *coordinates and identities*, not pointer truth.
JP pointer values, text starts, and first-NUL ends are reread from the exact
Japanese ROM.  The current Korean ROM is checked independently against the
later slot catalog.  No gap after a NUL is granted to a writer.

This is a conservative source oracle, not a complete runtime consumer proof.
Its CSV stays private because it contains precise original text locations.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import struct
from pathlib import Path

JP_SHA256 = "a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7"
BASELINE_SHA256 = "eac45b3345e865f1fea68bbb07f62aff0f6ccdf03004090f57b55f75b6f82b73"
ROM_BASE = 0x08000000
ROM_SIZE = 0x800000
EXPECTED_BINDINGS = 10172

FIELDS = (
    "id", "binding_id", "use_site_id", "category", "pointer_kind",
    "jp_pointer_storage", "pointer_width", "jp_pointer_value", "jp_text_start",
    "jp_raw_end", "proven_slot_end", "slot_capacity", "alias_group",
    "interior_alias", "consumer_ids", "latest_ko_hash", "control_signature",
    "new_encoding", "encoded_length", "new_text_start", "storage_equal",
    "pointer_equal", "start_equal", "fit_status", "evidence", "unresolved_reason",
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_image(image: bytes, expected: str, size: int, label: str) -> None:
    if len(image) != size:
        raise ValueError(f"{label} size {len(image)} != {size}")
    actual = sha(image)
    if actual != expected:
        raise ValueError(f"{label} SHA-256 {actual} != {expected}")


def parse_hex(value: str, label: str) -> int:
    try:
        return int(value, 16)
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid {label}: {value!r}") from error


def read_pointer_and_end(image: bytes, storage: int, label: str) -> tuple[int, int, int]:
    if storage < 0 or storage + 4 > len(image):
        raise ValueError(f"{label} storage out of range: {storage:08X}")
    pointer = struct.unpack_from("<I", image, storage)[0]
    start = pointer - ROM_BASE
    if not 0 <= start < len(image):
        raise ValueError(f"{label} target out of range: {pointer:08X}")
    # The audited text reader uses a 4096-byte bound. Do not let an accidental
    # later zero in unrelated ROM storage silently enlarge an entry.
    end = image.find(b"\0", start, min(start + 4096, len(image)))
    if end < 0:
        raise ValueError(f"{label} has no bounded NUL: {start:08X}")
    return pointer, start, end


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def consumer_identity(binding_id: str, category: str) -> str:
    family = binding_id.split("_", 1)[0]
    if category == "full_text":
        return "FULL_TEXT_CONSUMER_UNRESOLVED"
    if family == "ARTE":
        return "ARTE_INDEX_SELECTOR_08008C54;DOWNSTREAM_TEXT_CONSUMERS_UNRESOLVED"
    if binding_id.startswith("SELECT_JOB_"):
        return ("SELECT_JOB_INDEXED_TABLE;MENU_CALL_0801C3B4_TO_08004D98;"
                "LENGTH_CALL_08004DBA_TO_080A6BDC;OTHER_CALLERS_UNRESOLVED")
    return f"{family}_TABLE_CONSUMER_UNRESOLVED"


def build_bindings(
    jp_rom: bytes,
    baseline_rom: bytes,
    catalog_rows: list[dict[str, str]],
    audit_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    """Return numeric-address oracle rows; raise on any source disagreement.

    Callers needing current Korean bytes can read baseline_rom at each row's
    independently checked ``baseline_text_start`` through ``baseline_raw_end``.
    These two helper fields are intentionally available in Python/JSON only;
    the requested TEXT_BINDINGS CSV schema remains fixed at FIELDS.
    """
    if len(jp_rom) != ROM_SIZE:
        raise ValueError("JP ROM is not 8 MiB")
    if len(catalog_rows) != EXPECTED_BINDINGS:
        raise ValueError(f"catalog denominator {len(catalog_rows)} != {EXPECTED_BINDINGS}")
    audit = {}
    for item in audit_rows:
        if item["kind"] not in ("full_text", "compact"):
            continue
        storage = parse_hex(item["storage"], "audit storage")
        if storage in audit:
            raise ValueError(f"duplicate pointer audit storage {storage:08X}")
        audit[storage] = item
    if len(audit) != EXPECTED_BINDINGS:
        raise ValueError(f"pointer audit denominator {len(audit)} != {EXPECTED_BINDINGS}")

    result: list[dict[str, object]] = []
    seen_storage: set[int] = set()
    starts: dict[int, list[dict[str, object]]] = collections.defaultdict(list)
    for source in catalog_rows:
        storage = parse_hex(source["storage_offset"], "catalog storage")
        if storage in seen_storage:
            raise ValueError(f"duplicate catalog storage {storage:08X}")
        seen_storage.add(storage)
        audit_item = audit.get(storage)
        if audit_item is None:
            raise ValueError(f"storage {storage:08X} absent from old independent pointer audit")
        binding_id = source["binding_id"]
        identity = binding_id.split(":", 1)[0]
        if audit_item["id"] != identity or audit_item["kind"] != source["kind"]:
            raise ValueError(f"audit identity/type disagreement: {binding_id}")
        jp_pointer, start, end = read_pointer_and_end(jp_rom, storage, "JP " + binding_id)
        ko_pointer, ko_start, ko_end = read_pointer_and_end(baseline_rom, storage, "KO " + binding_id)
        jp_body = jp_rom[start:end]
        ko_body = baseline_rom[ko_start:ko_end]
        checks = {
            "jp_pointer_value": jp_pointer,
            "jp_start_offset": start,
            "jp_raw_bytes_excluding_nul": len(jp_body),
            "jp_min_owner_bytes_including_nul": len(jp_body) + 1,
            "latest_pointer_value": ko_pointer,
            "latest_text_start_offset": ko_start,
            "latest_encoded_bytes_excluding_nul": len(ko_body),
            "latest_encoded_bytes_including_nul": len(ko_body) + 1,
        }
        for key, actual in checks.items():
            recorded = (parse_hex(source[key], key) if key.endswith(("value", "offset"))
                        else int(source[key]))
            if recorded != actual:
                raise ValueError(f"catalog {key} differs from ROM for {binding_id}")
        if source["jp_raw_sha256"] != sha(jp_body):
            raise ValueError(f"JP body hash differs for {binding_id}")
        if source["latest_encoded_sha256"] != sha(ko_body):
            raise ValueError(f"KO body hash differs for {binding_id}")
        row: dict[str, object] = {
            "id": identity,
            "binding_id": binding_id,
            "use_site_id": f"{source['kind']}:{storage:08X}",
            "category": source["kind"],
            "pointer_kind": "GBA_ROM_ABSOLUTE_LE32",
            "jp_pointer_storage": storage,
            "pointer_width": 4,
            "jp_pointer_value": jp_pointer,
            "jp_text_start": start,
            "jp_raw_end": end,
            "proven_slot_end": end + 1,
            "slot_capacity": end + 1 - start,
            "alias_group": f"JP_START_{start:08X}",
            "interior_alias": False,
            "consumer_ids": consumer_identity(identity, source["kind"]),
            "latest_ko_hash": sha(ko_body),
            "control_signature": "UNKNOWN_UNCLASSIFIED_CONTROL_BYTES",
            "new_encoding": "UNASSIGNED",
            "encoded_length": None,
            "new_text_start": None,
            "storage_equal": None,
            "pointer_equal": None,
            "start_equal": None,
            "fit_status": "UNCLASSIFIED",
            "evidence": "JP_ROM_READ;KO_BASELINE_READ;OLD_POINTER_AUDIT_COORDINATE;CATALOG_HASH_MATCH",
            "unresolved_reason": "runtime consumer closure and new encoding not proved",
            "baseline_text_start": ko_start,
            "baseline_raw_end": ko_end,
            "jp_raw_sha256": sha(jp_body),
            "jp_terminated_sha256": sha(jp_rom[start:end + 1]),
        }
        result.append(row)
        starts[start].append(row)
    if seen_storage != set(audit):
        raise ValueError("pointer audit and catalog storages differ")

    sorted_starts = sorted(starts)
    for start, peers in starts.items():
        payload_hashes = {r["latest_ko_hash"] for r in peers}
        if len(payload_hashes) > 1:
            for row in peers:
                row["fit_status"] = "ALIAS_SEMANTIC_CONFLICT"
                row["unresolved_reason"] = "same JP start has distinct latest Korean raw templates; consumer discriminator unproved"
        else:
            for row in peers:
                if int(row["baseline_raw_end"]) + 1 - int(row["baseline_text_start"]) <= int(row["slot_capacity"]):
                    row["fit_status"] = "CURRENT_RAW_FITS_MIN_JP_EXTENT"
                else:
                    row["fit_status"] = "CURRENT_RAW_EXCEEDS_MIN_JP_EXTENT"
    # Shared suffix/interior starts constrain the entire owning entry. We do
    # not grant the prefix as a standalone writable slot without proving a
    # representation that preserves both entry points and their terminator.
    import bisect
    for row in result:
        start, end = int(row["jp_text_start"]), int(row["jp_raw_end"])
        i = bisect.bisect_right(sorted_starts, start)
        if i < len(sorted_starts) and sorted_starts[i] <= end:
            row["interior_alias"] = True
            row["proven_slot_end"] = start
            row["slot_capacity"] = 0
            row["fit_status"] = "UNKNOWN_INTERIOR_ALIAS"
            row["unresolved_reason"] = f"other JP entry starts inside raw body at {sorted_starts[i]:08X}"
    return result


def summary(rows: list[dict[str, object]]) -> dict[str, object]:
    counts = collections.Counter(str(row["fit_status"]) for row in rows)
    conflicts = sorted({int(row["jp_text_start"]) for row in rows if row["fit_status"] == "ALIAS_SEMANTIC_CONFLICT"})
    conflict_details = []
    for start in conflicts:
        peers = [row for row in rows if row["jp_text_start"] == start]
        family = "ARTE" if any(str(row["id"]).startswith("ARTE_") for row in peers) else "SELECT_JOB"
        conflict_details.append({
            "jp_text_start": start,
            "jp_pointer_value": ROM_BASE + start,
            "family": family,
            "minimum_jp_owner_bytes_including_nul": int(peers[0]["jp_raw_end"]) + 1 - start,
            "bindings": [{
                "binding_id": row["binding_id"],
                "pointer_storage": row["jp_pointer_storage"],
                "latest_raw_sha256": row["latest_ko_hash"],
                "latest_owner_bytes_including_nul": int(row["baseline_raw_end"]) + 1 - int(row["baseline_text_start"]),
            } for row in peers],
            "indexed_source_evidence": (
                "08008C54 computes ARTE record*20 plus selector*4 and returns the stored pointer; "
                "downstream text-use discrimination has not been demonstrated"
                if family == "ARTE" else
                "SELECT_JOB at 003AE0E0 has 201 stride-4 entries; JP literal at 001C3E4 "
                "is loaded at 0801C3B2 and passed at 0801C3B4 to menu routine 08004D98; "
                "that routine iterates the pointers and calls string-length routine 080A6BDC"
            ),
            "strict_same_pointer_resolution": "UNKNOWN_CONSUMER_DISCRIMINATOR_REQUIRED",
        })
    return {
        "schema": "strict-text-bindings-source-oracle-v1",
        "status": "SOURCE_BOUND_ONLY_RUNTIME_CONSUMERS_UNRESOLVED",
        "pointer_bindings_total": len(rows),
        "unique_jp_text_starts": len({row["jp_text_start"] for row in rows}),
        "fit_status_counts": dict(sorted(counts.items())),
        "semantic_conflict_jp_starts": [f"{start:08X}" for start in conflicts],
        "semantic_conflict_details": conflict_details,
        "slot_policy": "first NUL inclusive only; interior-alias owners have zero independently proven writable capacity",
        "source_truth": "old pointer audit coordinates + exact JP ROM reread; latest KO baseline independently reread and hash checked",
        "consumer_closure": "UNKNOWN",
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jp-rom", type=Path, default=root / "Japanese.gba")
    parser.add_argument("--baseline-rom", type=Path, default=root / "private_validation/listperf-20261002/root/credits-build-a/Xagros_Narikiri2_KOR_v1.0_listperf-pass01_credits_TEST.gba")
    parser.add_argument("--catalog", type=Path, default=root / "private_validation/listperf-20261002/luna-audit/TEXT_SLOT_MAP.csv")
    parser.add_argument("--pointer-audit", type=Path, default=root / "analysis/v0.9c/pointer_audit.csv")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    jp_rom = args.jp_rom.read_bytes()
    baseline_rom = args.baseline_rom.read_bytes()
    require_image(jp_rom, JP_SHA256, ROM_SIZE, "Japanese")
    require_image(baseline_rom, BASELINE_SHA256, 13270790, "baseline")
    rows = build_bindings(jp_rom, baseline_rom, load_csv(args.catalog), load_csv(args.pointer_audit))
    report = summary(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row[field] for field in FIELDS} for row in rows)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
