"""Build a pinned, readback-verified Issue #25 name overlay candidate.

This is an investigation artifact, not a release builder. It keeps original
ROM text starts and pointer bytes. One full-text Huffman leaf is exchanged with
an eligible lower-frequency leaf, then every affected full-text start is
re-encoded against the revised packed book.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from strict_packed_tree import pack_tree, unpack_tree
from strict_unit_codec import code_table, decode_parts, encode_parts, units
from narikiri2_text_spec import hangul_to_game_code

JP_SHA256 = "a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7"
V11C_SHA256 = "bf9e425dc172fb36b0f3ab221a14299898768a8bf5e7e7c36feaf7242f86334c"
MASTER_SHA256 = "12ae86f40dc77c913cab9066a379aa012328e07f5dbd525d7312df88d7410d04"
EXPECTED_FULL_ROWS = 8945
EXPECTED_FULL_STARTS = 8203
EXPECTED_COMPACT_ROWS = 1420
EXPECTED_FULL_LEAF_SWAP = (bytes.fromhex("8EE0"), bytes.fromhex("8969"))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _csv(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter=delimiter))


def _segment(link: dict, name: str) -> tuple[int, int]:
    rows = link["layout"]["segments"]
    matches = [r for r in rows if r["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"LINK segment is missing or ambiguous: {name}")
    row = matches[0]
    return int(row["new"]), int(row["size"])


def _swap_leaf_payload(book: bytes, left: bytes, right: bytes) -> bytes:
    """Exchange two native unit labels while preserving the Huffman tree."""
    code_table(book)
    count, reserved = struct.unpack_from("<HH", book)
    if reserved != 0:
        raise ValueError("Expected unpacked glyph-prefix tree")
    found: dict[bytes, int] = {}
    for index in range(count):
        at = 4 + index * 8
        marker, _ = struct.unpack_from("<HH", book, at)
        if marker & 0x8000:
            size = marker & 0x7FFF
            label = book[at + 4:at + 4 + size]
            if label in (left, right):
                found[label] = at + 4
    if set(found) != {left, right} or len(left) != len(right):
        raise ValueError("Requested full-book leaf pair is absent or incompatible")
    out = bytearray(book)
    out[found[left]:found[left] + len(left)] = right
    out[found[right]:found[right] + len(right)] = left
    result = bytes(out)
    table = code_table(result)
    if table[left][1] != code_table(book)[right][1] or table[right][1] != code_table(book)[left][1]:
        raise ValueError("Leaf exchange did not exchange the intended code lengths")
    return result


def _compact_native(text: str, glyphs: list[str]) -> bytes:
    index = {char: i for i, char in enumerate(glyphs)}
    out = bytearray()
    for char in text:
        if char == " ":
            out.append(0x20)
        elif char in index:
            value = index[char]
            out.extend((0x7F, value // 31 + 1, value % 31 + 1))
        else:
            raise ValueError(f"Compact name glyph is not registered: {char!r}")
    return bytes(out)


def _full_native(text: str) -> bytes:
    out = bytearray()
    for char in text:
        if char == " ":
            # Full-text names use the native 6-pixel separator leaf.
            out.extend(b"\x80\x40")
        else:
            out.extend(hangul_to_game_code(char).to_bytes(2, "big"))
    return bytes(out)


def _decode_compact_name(raw: bytes, glyphs: list[str]) -> str:
    out: list[str] = []
    pos = 0
    while pos < len(raw):
        value = raw[pos]
        if value == 0x7F:
            if pos + 3 > len(raw):
                raise ValueError("Truncated compact private-glyph token")
            index = (raw[pos + 1] - 1) * 31 + raw[pos + 2] - 1
            if not 0 <= index < len(glyphs):
                raise ValueError("Compact private-glyph index is outside registry")
            out.append(glyphs[index])
            pos += 3
        elif value == 0x20:
            out.append(" ")
            pos += 1
        else:
            raise ValueError(f"Unexpected compact name byte {value:02X}")
    return "".join(out)


def _rows_for_start(image: bytes, book: bytes, rows: list[dict[str, str]]) -> dict[int, tuple[bytes, int, list[dict[str, str]]]]:
    groups: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[int(row["current_start"], 16)].append(row)
    result = {}
    for start, members in groups.items():
        outputs = set()
        extents = set()
        capacities = set()
        for row in members:
            encoded = int(row["encoded_bytes"])
            stream = image[start:start + encoded]
            raw, used = decode_parts(stream, book, 1024, 1, 1)
            if used != encoded:
                raise ValueError(f"Frozen full stream extent mismatch: {row['binding_id']}")
            outputs.add(raw[:-1])
            extents.add(encoded)
            capacities.add(int(row["slot_bytes"]))
        if len(outputs) != 1 or len(extents) != 1 or len(capacities) != 1:
            raise ValueError(f"Shared full-text start has inconsistent owner data: {start:06X}")
        result[start] = (outputs.pop(), capacities.pop(), members)
    return result


def build(
    base_rom: bytes,
    jp_rom: bytes,
    master_csv: Path,
    link_json: Path,
    name_map_csv: Path,
    build_json: Path,
) -> tuple[bytes, list[dict], dict]:
    """Return ``(candidate image, exact name records, build evidence)``."""
    if len(base_rom) != 0x800000 or sha(base_rom) != V11C_SHA256:
        raise ValueError("Expected the pinned v1.1c candidate ROM")
    if len(jp_rom) != 0x800000 or sha(jp_rom) != JP_SHA256:
        raise ValueError("Expected the pinned Japanese source ROM")
    if sha(master_csv.read_bytes()) != MASTER_SHA256:
        raise ValueError("Pinned v11c corpus/master CSV changed")
    map_rows = _csv(name_map_csv)
    if len(map_rows) != 6:
        raise ValueError("Versioned Issue #25 name map must contain six rows")
    map_by_id = {int(row["rom_job_id"][4:]): row for row in map_rows}
    expected_ids = {131, 132, 145, 146, 164, 165}
    if set(map_by_id) != expected_ids:
        raise ValueError("Versioned Issue #25 map has an unexpected JOB id set")
    link = json.loads(link_json.read_text(encoding="utf-8"))
    build_manifest = json.loads(build_json.read_text(encoding="utf-8"))
    if build_manifest.get("symbols", {}).get("FULL_COUNT") != EXPECTED_FULL_STARTS:
        raise ValueError("Pinned BUILD full-text population changed")
    full_at, full_size = _segment(link, "full_book")
    compact_at, compact_size = _segment(link, "compact_book")
    if (full_at, full_size, compact_at, compact_size) != (762476, 9312, 771788, 3696):
        raise ValueError("Pinned LINK book layout changed")

    full_book = unpack_tree(base_rom[full_at:full_at + full_size])
    compact_book = unpack_tree(base_rom[compact_at:compact_at + compact_size])
    master_rows = _csv(master_csv)
    full_rows_all = [r for r in master_rows if r["category"] == "full_text"]
    full_rows = [r for r in full_rows_all if not r["binding_id"].startswith("EXTRA_UI:")]
    compact_rows = [r for r in master_rows if r["category"] == "compact"]
    source_starts = sorted({int(r["original_start"], 16) for r in master_rows})

    def verify_source_owner(storage: int, start: int, capacity: int, label: str) -> int:
        pointer = struct.unpack_from("<I", jp_rom, storage)[0]
        if pointer != 0x08000000 + start:
            raise ValueError(f"Japanese pointer does not resolve to catalog start: {label}")
        source = jp_rom[start:start + capacity]
        if len(source) != capacity or source[-1:] != b"\0" or b"\0" in source[:-1]:
            raise ValueError(f"Japanese source extent/NUL disagrees with catalog: {label}")
        next_start = next((value for value in source_starts if value > start), 0x800000)
        if start + capacity > next_start:
            raise ValueError(f"Catalog slot overlaps the next live source start: {label}")
        return next_start
    if len(full_rows_all) != 8947 or len(full_rows) != EXPECTED_FULL_ROWS or len(compact_rows) != EXPECTED_COMPACT_ROWS:
        raise ValueError("Pinned v11c text binding denominator changed")
    full_groups = _rows_for_start(base_rom, full_book, full_rows)
    if len(full_groups) != EXPECTED_FULL_STARTS:
        raise ValueError("Pinned v11c full-text start denominator changed")

    glyphs = json.loads((ROOT / "config/private_glyph_order.json").read_text(encoding="utf-8"))["glyphs"]
    full_targets: dict[int, tuple[bytes, dict[str, str]]] = {}
    full_target_rows: list[tuple[int, bytes, dict[str, str], int]] = []
    target_164_owner = None
    compact_targets: dict[str, tuple[bytes, dict[str, str]]] = {}
    for job_id, mapping in map_by_id.items():
        native_full = _full_native(mapping["proposed_korean"])
        full_storages = [mapping["full_binding_storage"], mapping["gallery_full_binding_storage"]]
        for storage_text in full_storages:
            full_storage = int(storage_text, 16)
            full_row = next((r for r in full_rows if int(r["pointer_storage"], 16) == full_storage), None)
            if full_row is None:
                raise ValueError(f"Full-name binding missing for JOB_{job_id:03} at {storage_text}")
            full_start = int(full_row["current_start"], 16)
            if int(full_row["original_start"], 16) != full_start:
                raise ValueError("Full name text start is not the original source start")
            next_start = verify_source_owner(full_storage, full_start, int(full_row["slot_bytes"]), full_row["binding_id"])
            if full_start in full_targets and full_targets[full_start][0] != native_full:
                raise ValueError(f"Shared full-name start has conflicting proposed names: {full_start:06X}")
            full_targets[full_start] = (native_full, full_row)
            full_target_rows.append((job_id, native_full, full_row, full_storage))
            if full_start == 0x2B8CC0 and (int(full_row["slot_bytes"]) != 7 or next_start != 0x2B8CC8):
                raise ValueError("JOB_164_FULL physical source owner boundary changed")
            if job_id == 164 and full_storage == 0x002B810C:
                target_164_owner = {
                    "storage": f"{full_storage:08X}",
                    "japanese_pointer": f"{struct.unpack_from('<I', jp_rom, full_storage)[0]:08X}",
                    "source_start": f"{full_start:06X}",
                    "source_bytes_hex_including_nul": jp_rom[full_start:full_start + int(full_row["slot_bytes"])].hex().upper(),
                    "slot_bytes_including_nul": int(full_row["slot_bytes"]),
                    "next_live_source_start": f"{next_start:06X}",
                    "unused_gap_bytes_before_next_start": next_start - full_start - int(full_row["slot_bytes"]),
                }
        for binding_field in ("compact_binding_id", "selector_binding_id"):
            binding_id = mapping[binding_field]
            row = next((r for r in compact_rows if r["binding_id"] == binding_id), None)
            if row is None:
                raise ValueError(f"Compact binding missing from master: {binding_id}")
            verify_source_owner(int(row["pointer_storage"], 16), int(row["original_start"], 16), int(row["slot_bytes"]), binding_id)
            native_compact = _compact_native(mapping["proposed_korean"], glyphs)
            compact_targets[binding_id] = (native_compact, row)

    # The full book's native 6-pixel half-space spelling saves one bit, but its
    # frozen tree still produces 57 bits (8 bytes) for JOB_164_FULL. Exchange
    # the 11-bit `예` leaf with a lower-frequency 10-bit leaf; this keeps the
    # book extent fixed and allows a whole-population bounded re-encode.
    left, right = EXPECTED_FULL_LEAF_SWAP
    old_table = code_table(full_book)
    frequencies = Counter(unit for raw, _, _ in full_groups.values() for unit in units(raw, "full_text"))
    for start, (native, _) in full_targets.items():
        for unit in units(full_groups[start][0], "full_text"):
            frequencies[unit] -= 1
        frequencies.update(units(native, "full_text"))
    if old_table[left][1] != 11 or old_table[right][1] != 10 or frequencies[left] != 82 or frequencies[right] != 60:
        raise ValueError("Frozen full-book leaf swap evidence changed")
    revised_full_book = _swap_leaf_payload(full_book, left, right)
    revised_full_packed = pack_tree(revised_full_book)
    if len(revised_full_packed) != full_size:
        raise ValueError("Revised full book does not fit its existing linker allocation")
    target_164_native = _full_native("유랑 예술가")
    target_164_8140_bytes = len(encode_parts([target_164_native.replace(b"\x80\x40", b"\x81\x40")], "full_text", full_book))
    try:
        encode_parts([target_164_native.replace(b"\x80\x40", b"\x20")], "full_text", full_book)
        ascii_space_supported = True
    except KeyError:
        ascii_space_supported = False

    changed_full: dict[int, bytes] = {}
    expected_full: dict[int, bytes] = {start: row[0] for start, row in full_groups.items()}
    for start, (native, row) in full_targets.items():
        prior = full_targets.get(start)
        if prior and prior[0] != native:
            raise ValueError(f"Shared full-name start has conflicting proposed names: {start:06X}")
        expected_full[start] = native
    impacted_starts = set()
    full_records = []
    for start, (native, capacity, members) in full_groups.items():
        if start in expected_full and expected_full[start] != native:
            native = expected_full[start]
        old_units = units(full_groups[start][0], "full_text")
        new_units = units(native, "full_text")
        if left in old_units or right in old_units or left in new_units or right in new_units or native != full_groups[start][0]:
            stream = encode_parts([native], "full_text", revised_full_book)
            if len(stream) > capacity:
                raise ValueError(f"Full-text slot overflow at {start:06X}: {len(stream)} > {capacity}")
            decoded, used = decode_parts(stream, revised_full_book, len(native) + 1, 1, 1)
            if used != len(stream) or decoded != native + b"\0":
                raise ValueError(f"Revised full stream failed local readback at {start:06X}")
            changed_full[start] = stream
            impacted_starts.add(start)
        full_records.append((start, native, capacity, members))

    image = bytearray(base_rom)
    image[full_at:full_at + full_size] = revised_full_packed
    for start, stream in changed_full.items():
        image[start:start + len(stream)] = stream

    # Apply the six proposed names to both compact consumers, deduplicating
    # identical shared starts and failing on any conflicting proposal.
    compact_writes: dict[int, tuple[bytes, int, str]] = {}
    records: list[dict] = []
    for binding_id, (native, row) in compact_targets.items():
        start = int(row["current_start"], 16)
        capacity = int(row["slot_bytes"])
        stream = encode_parts([native], "compact", compact_book)
        if len(stream) > capacity:
            raise ValueError(f"Compact name slot overflow at {binding_id}: {len(stream)} > {capacity}")
        decoded, used = decode_parts(stream, compact_book, len(native) + 1, 1, 1)
        if used != len(stream) or decoded != native + b"\0":
            raise ValueError(f"Compact name stream failed local readback: {binding_id}")
        if start in compact_writes and compact_writes[start][0] != stream:
            raise ValueError(f"Shared compact start has conflicting proposed names: {start:06X}")
        compact_writes[start] = (stream, capacity, binding_id)
        if struct.unpack_from("<I", base_rom, int(row["pointer_storage"], 16))[0] != 0x08000000 + start:
            raise ValueError(f"Compact pointer no longer resolves to its original start: {binding_id}")
        records.append({
            "binding_id": binding_id,
            "storage": row["pointer_storage"],
            "start": f"{start:06X}",
            "slot_bytes": capacity,
            "new_native_hex": native.hex().upper(),
            "new_stream_hex": stream.hex().upper(),
            "new_stream_bytes": len(stream),
            "decoded_name": map_by_id[int(binding_id.split(":", 1)[0].rsplit("JOB_", 1)[1])]["proposed_korean"],
            "status": "OVERLAID_AND_READBACK_VERIFIED",
        })
    for start, (stream, capacity, binding_id) in compact_writes.items():
        image[start:start + len(stream)] = stream

    # Record full-name bindings separately, with current and candidate stream
    # lengths. Several rows may share one full-text start (JOB_131/132).
    for job_id, native, row, storage in full_target_rows:
        start = int(row["current_start"], 16)
        stream = changed_full[start]
        if len(stream) > int(row["slot_bytes"]):
            raise ValueError(f"Full name stream exceeds its source slot: {row['binding_id']}")
        if struct.unpack_from("<I", base_rom, int(row["pointer_storage"], 16))[0] != 0x08000000 + start:
            raise ValueError(f"Full pointer no longer resolves to its original start: {row['binding_id']}")
        records.append({
            "binding_id": row["binding_id"],
            "storage": row["pointer_storage"],
            "start": f"{start:06X}",
            "slot_bytes": int(row["slot_bytes"]),
            "new_native_hex": native.hex().upper(),
            "new_stream_hex": stream.hex().upper(),
            "new_stream_bytes": len(stream),
            "decoded_name": map_by_id[job_id]["proposed_korean"],
            "status": "OVERLAID_AND_READBACK_VERIFIED",
        })

    # Fresh-image verification: every full binding is decoded under the
    # revised tree; every compact target is decoded under the frozen compact
    # tree. All full-text start and pointer values remain unchanged.
    fresh = bytes(image)
    fresh_full_book = unpack_tree(fresh[full_at:full_at + full_size])
    fresh_compact_book = unpack_tree(fresh[compact_at:compact_at + compact_size])
    if fresh_full_book != revised_full_book or fresh_compact_book != compact_book:
        raise ValueError("Fresh candidate books differ from the planned full/compact books")
    full_readback_count = 0
    for row in full_rows:
        start = int(row["current_start"], 16)
        expected = expected_full[start]
        stream_size = len(changed_full[start]) if start in changed_full else int(row["encoded_bytes"])
        stream = fresh[start:start + stream_size]
        decoded, used = decode_parts(stream, fresh_full_book, len(expected) + 1, 1, 1)
        if decoded != expected + b"\0" or used != len(stream):
            raise ValueError(f"Fresh full-name readback mismatch: {row['binding_id']}")
        if struct.unpack_from("<I", fresh, int(row["pointer_storage"], 16))[0] != struct.unpack_from("<I", base_rom, int(row["pointer_storage"], 16))[0]:
            raise ValueError(f"Pointer changed during full re-encoding: {row['binding_id']}")
        full_readback_count += 1
    prose_guards = []
    for binding_id in ("D02179:00325B70", "D07983:007F923C"):
        row = next((r for r in full_rows if r["binding_id"] == binding_id), None)
        if row is None:
            raise ValueError(f"Required job-prose preservation binding missing: {binding_id}")
        start = int(row["current_start"], 16)
        expected = full_groups[start][0]
        if expected_full[start] != expected:
            raise ValueError(f"Job prose was included in a name overlay: {binding_id}")
        prose_guards.append({"binding_id": binding_id, "start": f"{start:06X}", "native_sha256": sha(expected)})
    compact_readback_count = 0
    for binding_id, (native, row) in compact_targets.items():
        start = int(row["current_start"], 16)
        stream_size = len(compact_writes[start][0])
        stream = fresh[start:start + stream_size]
        decoded, used = decode_parts(stream, fresh_compact_book, len(native) + 1, 1, 1)
        if decoded != native + b"\0" or used != len(stream):
            raise ValueError(f"Fresh compact readback mismatch: {binding_id}")
        if struct.unpack_from("<I", fresh, int(row["pointer_storage"], 16))[0] != struct.unpack_from("<I", base_rom, int(row["pointer_storage"], 16))[0]:
            raise ValueError(f"Pointer changed during compact update: {binding_id}")
        compact_readback_count += 1

    # No bytes outside the existing book and owned compressed text extents
    # may change. Linker placement and every original start remain fixed.
    allowed: set[int] = set(range(full_at, full_at + full_size))
    for start, stream in changed_full.items():
        allowed.update(range(start, start + len(stream)))
    for start, (stream, _, _) in compact_writes.items():
        allowed.update(range(start, start + len(stream)))
    unexpected = [i for i, (before, after) in enumerate(zip(base_rom, fresh)) if before != after and i not in allowed]
    if unexpected:
        raise ValueError(f"Overlay changed unowned bytes: {unexpected[:8]}")
    if len(fresh) != 0x800000:
        raise ValueError("Overlay changed ROM extent")

    details = {
        "schema": "issue25-name-overlay-v1",
        "status": "LOCAL_OVERLAY_CANDIDATE_NOT_RELEASE",
        "base_rom_sha256": sha(base_rom),
        "source_rom_sha256": sha(jp_rom),
        "output_rom_sha256": sha(fresh),
        "rom_bytes": len(fresh),
        "link_book_offsets": {"full": [full_at, full_size], "compact": [compact_at, compact_size]},
        "full_population": {"bindings": len(full_rows), "unique_starts": len(full_groups), "fresh_readbacks": full_readback_count},
        "compact_name_readbacks": compact_readback_count,
        "full_name_binding_readbacks": len(full_target_rows),
        "job_prose_guards": prose_guards,
        "full_book_swap": {
            "unit_promoted": left.hex().upper(),
            "unit_demoted": right.hex().upper(),
            "old_code_lengths": {left.hex().upper(): old_table[left][1], right.hex().upper(): old_table[right][1]},
            "frequency_unique_full_starts": {left.hex().upper(): frequencies[left], right.hex().upper(): frequencies[right]},
            "old_book_sha256": sha(pack_tree(full_book)),
            "new_book_sha256": sha(revised_full_packed),
            "packed_bytes_before_after": [full_size, len(revised_full_packed)],
            "reencoded_unique_starts": len(changed_full),
            "full_bindings_read_back": full_readback_count,
            "slot_overflow_count": 0,
            "target_164_full_bits_before": sum(old_table[u][1] for u in units(_full_native("유랑 예술가"), "full_text") + [b""]),
            "target_164_full_bits_after": sum(code_table(revised_full_book)[u][1] for u in units(_full_native("유랑 예술가"), "full_text") + [b""]),
            "target_164_full_stream_bytes_before_after": [8, len(changed_full[int(next(r["current_start"] for r in full_rows if int(r["pointer_storage"], 16) == 0x002B810C), 16)])],
            "separator_encoding_test": {"native_halfspace_hex": "8040", "halfspace_stream_bytes_old_book": 8, "native_fullspace_hex": "8140", "fullspace_stream_bytes_old_book": target_164_8140_bytes, "ascii_space_supported_by_frozen_book": ascii_space_supported},
        },
        "target_164_physical_owner": target_164_owner,
        "pointer_writes": 0,
        "reused_text_starts": True,
        "borrowed_tail_bytes_written": 0,
        "extra_ui_book_or_streams_changed": False,
        "record_count": len(records),
        "full_stream_updates": [
            {"start": f"{start:06X}", "bytes": len(stream), "sha256": sha(stream)}
            for start, stream in sorted(changed_full.items())
        ],
        "full_stream_update_bytes": sum(len(stream) for stream in changed_full.values()),
    }
    return fresh, records, details


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-rom", type=Path, required=True)
    parser.add_argument("--japanese-rom", type=Path, required=True)
    parser.add_argument("--master-csv", type=Path, required=True)
    parser.add_argument("--link-json", type=Path, required=True)
    parser.add_argument("--build-json", type=Path, required=True)
    parser.add_argument("--name-map-csv", type=Path, default=ROOT / "docs/issue25-names.csv")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.out_dir.exists():
        raise ValueError("Output folder already exists; choose a fresh path")
    args.out_dir.mkdir(parents=True)
    image, records, details = build(
        args.base_rom.read_bytes(), args.japanese_rom.read_bytes(), args.master_csv,
        args.link_json, args.name_map_csv, args.build_json,
    )
    (args.out_dir / "issue25-names-candidate.gba").write_bytes(image)
    (args.out_dir / "NAME_OVERLAY.json").write_text(
        json.dumps({"details": details, "records": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({k: v for k, v in details.items() if k != "full_stream_updates"}, ensure_ascii=False))


if __name__ == "__main__":
    main()

