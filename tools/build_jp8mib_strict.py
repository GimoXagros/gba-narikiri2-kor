#!/usr/bin/env python3
"""Plan and exercise strict JP slots without issuing a misleading product ROM.

The fixed-buffer assembler below is executable, but the real product remains
gated on alias, slot, consumer, buffer and asset-linker evidence. Inspection
mode emits reports even when product assembly is blocked; --require-product
returns a failure status and never writes a partial .gba under the candidate
name. Historical expanded builders are intentionally left untouched.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
from pathlib import Path

from strict_layout_core import Binding, assemble_fixed, sha, slot_write, verify_decoded
from strict_text_bindings import (BASELINE_SHA256, JP_SHA256, FIELDS, build_bindings,
                                   load_csv, require_image)
from v09c_io import atomic_write_new

ROOT = Path(__file__).resolve().parents[1]


def encode_corpus(jp, baseline, rows, encoding="native"):
    payloads = [baseline[int(r["baseline_text_start"]):int(r["baseline_raw_end"])]
                for r in rows]
    inline_details = None
    if encoding == "unit_inline":
        from strict_inline_layout import encode_inline
        streams, books, inline_details, _ = encode_inline(rows, payloads)
    elif encoding == "unit_by_kind":
        from strict_unit_codec import fit_book, decode, encode
        categories = sorted({str(r["category"]) for r in rows})
        books = {}
        for kind in categories:
            selected = [(r, raw) for r, raw in zip(rows, payloads) if r["category"] == kind]
            books[kind], _ = fit_book([raw for _, raw in selected], kind,
                                      [int(r["slot_capacity"]) for r, _ in selected])
        streams = []
        for row, raw in zip(rows, payloads):
            kind = str(row["category"])
            stream = encode(raw, kind, books[kind])
            if decode(stream, books[kind], len(raw)+1) != (raw+b"\0", len(stream)):
                raise ValueError("Unit codec roundtrip mismatch")
            streams.append(stream)
    elif encoding in ("phrase", "phrase_by_kind"):
        from strict_text_codec import build_codebook, decode, encode
        categories = sorted({str(r["category"]) for r in rows})
        if encoding == "phrase":
            books = {"shared": build_codebook(payloads)}
            selected = [books["shared"]] * len(rows)
        else:
            books = {kind: build_codebook([raw for r, raw in zip(rows, payloads)
                                          if r["category"] == kind]) for kind in categories}
            selected = [books[str(r["category"])] for r in rows]
        streams = [encode(raw, book) for raw, book in zip(payloads, selected)]
        for raw, stream, book in zip(payloads, streams, selected):
            if decode(stream, book, len(raw)+1) != raw+b"\0":
                raise ValueError("Phrase codec roundtrip mismatch")
    elif encoding == "native":
        books = {}
        streams = [raw+b"\0" for raw in payloads]
    else:
        raise ValueError("Unverified encoding")
    aliases = collections.defaultdict(set)
    for row, raw in zip(rows, payloads):
        aliases[int(row["jp_text_start"])].add(raw)
    details, bindings = [], []
    for row, raw, stream in zip(rows, payloads, streams):
        start, end = int(row["jp_text_start"]), int(row["proven_slot_end"])
        storage = int(row["jp_pointer_storage"])
        overflow = max(0, len(stream) - (end-start))
        conflict = len(aliases[start]) > 1
        fit = "SLOT_OVERFLOW" if overflow else "INLINE_VARIANT_STORAGE_FIT_ONLY" if conflict and encoding == "unit_inline" else "ALIAS_SEMANTIC_CONFLICT" if conflict else "STORAGE_FIT_ONLY"
        bindings.append(Binding(str(row["binding_id"]), storage, jp[storage:storage+4],
                                start, end, raw+b"\0"))
        details.append(dict(binding_id=row["binding_id"], category=row["category"],
            jp_text_start=start, proven_slot_end=end, slot_capacity=end-start,
            encoding={"native":"STRICT_DIRECT_EXPERIMENT", "phrase":"STRICT_PHRASE_EXPERIMENT",
                      "phrase_by_kind":"STRICT_PHRASE_EXPERIMENT",
                      "unit_by_kind":"STRICT_GLYPH_PREFIX_EXPERIMENT",
                      "unit_inline":"STRICT_INLINE_GLYPH_EXPERIMENT"}[encoding],
            encoded_length=len(stream), native_output_length=len(raw)+1,
            overflow_bytes=overflow, semantic_alias_conflict=conflict, fit_status=fit,
            stream_sha256=sha(stream), native_output_sha256=sha(raw+b"\0"),
            runtime_status="UNINTEGRATED_CONSUMERS_AND_BUFFER_LIFETIME_UNKNOWN"))
    if inline_details is not None:
        for detail, selected in zip(details, inline_details):
            detail.update(selected)
    return bindings, streams, books, details


def assemble_text_slots(jp, bindings, streams, encoding, decode):
    """Actual fixed-size text-slot experiment, not a full product linker.

    Distinct template aliases fail in assemble_fixed; no majority selection.
    This accepts one write per identical shared start, preserving all pointer
    bytes. Game code/font/assets are still a separate mandatory product gate.
    """
    if len(bindings) != len(streams) or not bindings:
        raise ValueError("Missing text stream")
    seen, writes = {}, []
    for binding, stream in zip(bindings, streams):
        if binding.start in seen:
            if seen[binding.start] != stream:
                raise ValueError("ALIAS_SEMANTIC_CONFLICT: different streams at one start")
            continue
        seen[binding.start] = stream
        writes.append(slot_write(jp, binding, stream, encoding=encoding,
            consumer="bounded experiment decoder; game consumers unintegrated",
            provenance="independent source oracle and latest baseline bytes"))
    result, manifest = assemble_fixed(jp, writes, bindings)
    verify_decoded(result, bindings, decode)
    return result, manifest


def write_csv(path, rows, fields=None):
    if not rows:
        raise ValueError("Cannot emit empty required table")
    with path.open("x", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields or list(rows[0]), extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--japanese", type=Path, default=ROOT/"Japanese.gba")
    p.add_argument("--baseline", type=Path, default=ROOT/"private_validation/listperf-20261002/root/credits-build-a/Xagros_Narikiri2_KOR_v1.0_listperf-pass01_credits_TEST.gba")
    p.add_argument("--catalog", type=Path, default=ROOT/"private_validation/listperf-20261002/luna-audit/TEXT_SLOT_MAP.csv")
    p.add_argument("--audit", type=Path, default=ROOT/"analysis/v0.9c/pointer_audit.csv")
    p.add_argument("--encoding", choices=("native", "phrase", "phrase_by_kind", "unit_by_kind", "unit_inline"), default="unit_inline")
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--require-product", action="store_true")
    args = p.parse_args()
    if args.out_dir.exists():
        raise ValueError("Output directory exists; choose a new path")
    jp, baseline = args.japanese.read_bytes(), args.baseline.read_bytes()
    require_image(jp, JP_SHA256, 0x800000, "JP")
    require_image(baseline, BASELINE_SHA256, 13270790, "adopted Korean")
    rows = build_bindings(jp, baseline, load_csv(args.catalog), load_csv(args.audit))
    bindings, streams, books, slots = encode_corpus(jp, baseline, rows, args.encoding)
    over = [r for r in slots if r["overflow_bytes"]]
    conflicts = {r["jp_text_start"] for r in slots if r["semantic_alias_conflict"]}
    # Actually exercise the all-or-nothing assembler. Failure occurs before
    # mutation and is recorded, not bypassed by deleting troublesome rows.
    assembly_error = None
    try:
        if args.encoding == "native":
            from verify_jp8mib_strict import read_native
            def decoder(image, start, end, capacity):
                value = read_native(image, start, end-start)
                if len(value) > capacity:
                    raise ValueError("Native output buffer overflow")
                return value
        else:
            from strict_text_codec import decode
            by_start = {b.start: len(s) for b, s in zip(bindings, streams)}
            kind_by_start = {}
            for row in rows:
                start, kind = int(row["jp_text_start"]), str(row["category"])
                if start in kind_by_start and kind_by_start[start] != kind:
                    raise ValueError("Shared start requires inconsistent codebook dispatch")
                kind_by_start[start] = kind
            def decoder(image, start, end, capacity):
                if args.encoding == "unit_by_kind":
                    from strict_unit_codec import decode as decode_units
                    return decode_units(image[start:end], books[kind_by_start[start]],
                                        capacity, allow_suffix=True)[0]
                extent = by_start[start]
                if start+extent > end:
                    raise ValueError("Compressed stream exceeds slot")
                book = books["shared"] if args.encoding == "phrase" else books[kind_by_start[start]]
                return decode(image[start:start+extent], book, capacity)
        if args.encoding == "unit_inline":
            from strict_inline_layout import assemble_inline_slots
            text_image, writes = assemble_inline_slots(jp, bindings, streams, books, slots)
        else:
            text_image, writes = assemble_text_slots(jp, bindings, streams, args.encoding, decoder)
        text_experiment = "TEXT_SLOT_ROUNDTRIP_ONLY"
    except ValueError as exc:
        assembly_error = str(exc)
        text_image, writes = None, []
        text_experiment = "REJECTED_BEFORE_OUTPUT"
    blockers = ["runtime consumers/length/copy/format/page paths not integrated",
                "work buffer lifetime and metadata bounds not proved",
                "8MiB code/font/notice/title/credits placement and reference closure unresolved"]
    if over:
        blockers.insert(0, f"{len(over)} binding streams exceed proven slots")
    if conflicts:
        blockers.insert(0, f"{len(conflicts)} inline alias runtime selectors unproved" if args.encoding == "unit_inline"
                        else f"{len(conflicts)} semantic alias groups unresolved")
    report = dict(schema="an9j-strict-layout-build-experiment-v1",
        source_rom_sha256=JP_SHA256, baseline_rom_sha256=BASELINE_SHA256,
        target_rom_sha256=None, target_size=None, intended_target_size=0x800000,
        pointer_bindings_total=len(rows), unique_jp_starts=len({b.start for b in bindings}),
        encoding=args.encoding, dictionary_bytes=sum(map(len, books.values())),
        dictionaries={kind:dict(bytes=len(book), sha256=sha(book)) for kind, book in books.items()},
        codebook_dispatch="UNPROVED_GAME_CONSUMER_DISPATCH" if args.encoding.endswith("by_kind") else "UNINTEGRATED",
        input_extent_metadata_bytes=None, output_buffer_lifetime="UNKNOWN",
        slot_overflow_count=len(over), unique_overflow_starts=len({r["jp_text_start"] for r in over}),
        overflow_bytes_binding_occurrences=sum(r["overflow_bytes"] for r in over),
        alias_conflict_groups=len(conflicts), python_roundtrip_count=len(rows),
        inline_alias_storage_groups=len(conflicts) if args.encoding == "unit_inline" and not over else 0,
        text_assembler_status=text_experiment, assembly_error=assembly_error,
        data_only_image_sha256=sha(text_image) if text_image is not None else None,
        data_only_image_size=len(text_image) if text_image is not None else None,
        layout_status="PARTIAL_LAYOUT__CONSTRAINT_CONFLICTS", content_status="CODEC_ROUNDTRIP_ONLY",
        save_status="NOT_RUN", performance_status="PERF_OPEN", hardware_status="NOT_RUN",
        deterministic_build="NOT_RUN_NO_PRODUCT", bps_roundtrip="NOT_RUN_NO_PRODUCT",
        product_created=False, blockers=blockers)
    args.out_dir.mkdir(parents=True)
    write_csv(args.out_dir/"SLOT_FIT_REPORT.csv", slots)
    for row, slot in zip(rows, slots):
        row.update(new_encoding=slot["encoding"], encoded_length=slot["encoded_length"],
                   fit_status=slot["fit_status"])
        # These remain null: there is no target whose locations can be verified.
    write_csv(args.out_dir/"TEXT_BINDINGS.csv", rows, FIELDS)
    for kind, book in books.items():
        atomic_write_new(args.out_dir/f"EXPERIMENT_CODEBOOK_{kind}.bin", book)
    if text_image is not None:
        # Never call this data-only image a playable 8MiB candidate.
        atomic_write_new(args.out_dir/"TEXT_SLOT_IMAGE_NOT_PLAYABLE.bin", text_image)
    for name, value in (("BUILD_MANIFEST.json", report), ("WRITE_MANIFEST.json",
        dict(status=text_experiment, product_created=False, writes=writes))):
        atomic_write_new(args.out_dir/name, (json.dumps(value, ensure_ascii=False, indent=2)+"\n").encode("utf-8"))
    print(json.dumps(report, ensure_ascii=True))
    return 2 if args.require_product else 0


if __name__ == "__main__":
    raise SystemExit(main())
