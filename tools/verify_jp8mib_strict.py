"""Independent ROM-side strict text checks, without reading builder PASS files.

The historic source catalog supplies coordinates, not pointer values. All JP
values and adopted Korean byte templates are read from immutable ROMs. This
verifier deliberately does not infer whole-product compatibility from a text
comparison. Runtime/linker/reference closure is recorded separately.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import struct

JP_SHA = "a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7"
KO_SHA = "eac45b3345e865f1fea68bbb07f62aff0f6ccdf03004090f57b55f75b6f82b73"
SIZE = 8388608


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source_identity(jp, ko):
    if len(jp) != SIZE or digest(jp) != JP_SHA:
        raise ValueError("Japanese source identity mismatch")
    if len(ko) != 13270790 or digest(ko) != KO_SHA:
        raise ValueError("Adopted Korean source identity mismatch")


def read_native(rom, offset, bound=4096):
    if not 0 <= offset < len(rom):
        raise ValueError("Native text address outside image")
    stop = rom.find(b"\0", offset, min(offset + bound, len(rom)))
    if stop < 0:
        raise ValueError("Native text has no bounded terminator")
    return rom[offset:stop + 1]


def phrase_decoder_from_image(jp, target, audit_rows, offsets):
    """Read codebooks *from the candidate ROM*, never an external text table.

    Category and original slot extent are recovered from the independent JP
    coordinate audit. These are verifier parameters, not implemented runtime
    dispatch or evidence of game integration.
    """
    from strict_text_codec import BOOK_SIZE, decode, validate_book
    books, starts = {}, {}
    for kind in ("full_text", "compact"):
        offset = offsets[kind]
        if not 0 <= offset <= min(len(target), SIZE)-BOOK_SIZE:
            raise ValueError("Codebook outside 8MiB candidate address space")
        book = target[offset:offset+BOOK_SIZE]
        validate_book(book)
        books[kind] = book
    for row in audit_rows:
        kind = row["kind"]
        if kind not in books:
            continue
        storage = int(row["storage"], 16)
        start = struct.unpack_from("<I", jp, storage)[0]-0x08000000
        if start in starts and starts[start] != kind:
            raise ValueError("Mixed-category shared start cannot choose a codebook")
        starts[start] = kind
    def decoder(image, start, end, capacity, storage=None):
        # Encoded literal zero is forbidden: the first zero is exactly EOS.
        # Bound comes from JP, not an encoded_length in the builder report.
        stream = read_native(image, start, end-start)
        return decode(stream, books[starts[start]], capacity)
    return decoder


def unit_decoder_from_image(jp, target, audit_rows, offsets, baseline=None):
    """Reconstruct glyph trees only from bounded candidate bytes, not a plan."""
    from strict_unit_codec import code_table, decode, decode_parts
    books, starts = {}, {}
    for kind in ("full_text", "compact"):
        offset = offsets[kind]
        if not 0 <= offset <= min(len(target), SIZE)-4:
            raise ValueError("Unit codebook header outside candidate")
        count = struct.unpack_from("<H", target, offset)[0]
        end = offset+4+count*8
        if end > min(len(target), SIZE):
            raise ValueError("Unit codebook extent outside candidate")
        book = target[offset:end]
        code_table(book)
        books[kind] = book
    for row in audit_rows:
        kind = row["kind"]
        if kind not in books:
            continue
        storage = int(row["storage"], 16)
        start = struct.unpack_from("<I", jp, storage)[0]-0x08000000
        if start in starts and starts[start] != kind:
            raise ValueError("Mixed-category shared start cannot choose a codebook")
        starts[start] = kind
    selections = {}
    if baseline is not None:
        groups = {}
        for row in audit_rows:
            if row['kind'] not in books:
                continue
            storage = int(row['storage'],16)
            start = struct.unpack_from('<I',jp,storage)[0]-0x08000000
            original_ko = struct.unpack_from('<I',baseline,storage)[0]-0x08000000
            groups.setdefault(start,[]).append((storage,read_native(baseline,original_ko)))
        for start, members in groups.items():
            values = list(dict.fromkeys(raw for _,raw in sorted(members)))
            if len(values) not in (1,2):
                raise ValueError('Unexpected inline variant count')
            for storage, raw in members:
                selections[storage] = (1,1) if len(values)==1 else (4,(11,13)[values.index(raw)])
    def decoder(image, start, end, capacity, storage=None):
        if baseline is not None:
            if storage not in selections:
                raise ValueError('Inline verifier requires an independent pointer storage identity')
            count,selection=selections[storage]
            return decode_parts(image[start:end],books[starts[start]],capacity,count,
                                selection,allow_suffix=True)[0]
        return decode(image[start:end], books[starts[start]], capacity, allow_suffix=True)[0]
    return decoder


def audit_image(jp, ko, target, audit_rows, decode_slot=None):
    """Check actual bytes against JP/KO, not proposed slot writes.

    If supplied, decode_slot(image, start, end, capacity, storage) must return native
    bytes including NUL. Input bounds come from the JP source, independently
    of whatever slot metadata the builder may have emitted.
    """
    source_identity(jp, ko)
    rows = [r for r in audit_rows if r["kind"] in ("full_text", "compact")]
    if len(rows) != 10172:
        raise ValueError("Source audit denominator changed")
    coordinates = [int(r["storage"], 16) for r in rows]
    if len(set(coordinates)) != len(coordinates):
        raise ValueError("Duplicate source coordinates")
    errors, comparisons, outputs = [], [], {}
    pointer_bad = start_bad = text_bad = slot_bad = 0
    alias_values = {}
    for row, storage in zip(rows, coordinates):
        if not 0 <= storage <= len(jp)-4 or storage+4 > len(target):
            raise ValueError("Source or target coordinate outside image")
        jp_value = struct.unpack_from("<I", jp, storage)[0]
        ko_value = struct.unpack_from("<I", ko, storage)[0]
        actual = struct.unpack_from("<I", target, storage)[0]
        start = jp_value - 0x08000000
        native = read_native(jp, start)
        expected = read_native(ko, ko_value - 0x08000000)
        key = f"{row['id']}:{storage:08X}"
        equal = actual == jp_value
        pointer_bad += not equal
        start_bad += not equal
        alias_values.setdefault(start, set()).add(expected)
        content_error = ""
        try:
            if not equal:
                raise ValueError("target pointer no longer has original JP value")
            if decode_slot is None:
                actual_output = read_native(target, start, len(native))
            else:
                actual_output = decode_slot(target, start, start+len(native), len(expected), storage)
            if actual_output != expected:
                raise ValueError("decoded template differs from latest adopted Korean")
            outputs[key] = digest(actual_output)
        except (ValueError, IndexError, struct.error) as exc:
            text_bad += 1
            content_error = str(exc)
            if any(token in content_error.lower() for token in
                   ("bound", "terminator", "truncated", "missing eos")):
                slot_bad += 1
            errors.append({"binding_id": key, "error": content_error})
        comparisons.append(dict(binding_id=key, pointer_storage=storage,
            pointer_width=4, pointer_kind="GBA_ROM_ABSOLUTE_LE32",
            jp_pointer_value=jp_value, target_pointer_value=actual,
            jp_text_start=start, target_text_start=actual-0x08000000,
            slot_capacity=len(native), storage_equal=True, pointer_equal=equal,
            start_equal=equal, content_error=content_error))
    conflicts = sum(len(values) > 1 for values in alias_values.values())
    size_ok = len(target) == SIZE
    return dict(source_rom_sha256=JP_SHA, baseline_rom_sha256=KO_SHA,
        target_rom_sha256=digest(target), target_size=len(target),
        pointer_bindings_total=len(rows), storage_mismatch_count=0,
        pointer_value_mismatch_count=pointer_bad, text_start_mismatch_count=start_bad,
        # A failed decode can be corruption, not evidence of a particular
        # encoded length. Only successful bounded decoding proves zero.
        slot_overflow_count=0 if decode_slot and not text_bad else None,
        slot_boundary_failure_count=slot_bad, translation_mismatch_count=text_bad,
        semantic_alias_conflict_groups=conflicts,
        unresolved_binding_count=len(rows), invalid_reference_count=None,
        reference_closure_status="UNKNOWN", deterministic_build="NOT_RUN",
        bps_roundtrip="NOT_RUN",
        layout_status="FAIL" if not size_ok or pointer_bad or slot_bad else "CATALOG_ONLY",
        content_status="FAIL" if text_bad else "CATALOG_ONLY",
        save_status="NOT_RUN", performance_status="NOT_RUN", hardware_status="NOT_RUN",
        product_status="NOT_VERIFIED", errors=errors, comparisons=comparisons,
        expected_output_hashes=outputs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--japanese", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--full-codebook-offset", type=lambda s:int(s, 0))
    parser.add_argument("--compact-codebook-offset", type=lambda s:int(s, 0))
    parser.add_argument("--encoding", choices=("native", "phrase", "unit", "unit_inline"))
    args = parser.parse_args()
    if args.out_dir.exists():
        raise ValueError("Choose a new output directory")
    with args.audit.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    jp, ko, target = args.japanese.read_bytes(), args.baseline.read_bytes(), args.candidate.read_bytes()
    source_identity(jp, ko)
    offsets = (args.full_codebook_offset, args.compact_codebook_offset)
    if (offsets[0] is None) != (offsets[1] is None):
        raise ValueError("Both codebook offsets are required for phrase verification")
    mode = args.encoding or ("native" if offsets[0] is None else "phrase")
    if (mode == "native") != (offsets[0] is None):
        raise ValueError("Compressed verification requires both ROM codebook offsets; native requires neither")
    book_offsets=dict(full_text=offsets[0], compact=offsets[1])
    decoder = None if mode == "native" else (unit_decoder_from_image if mode.startswith("unit")
              else phrase_decoder_from_image)(jp, target, rows,book_offsets,
                  **({'baseline':ko} if mode=='unit_inline' else {}))
    result = audit_image(jp, ko, target, rows, decoder)
    result["encoding_verification"] = mode.upper()+"_CODEBOOKS_READ_FROM_TARGET" if decoder else "NATIVE"
    comparisons = result.pop("comparisons")
    result.pop("expected_output_hashes")
    args.out_dir.mkdir(parents=True)
    with (args.out_dir / "POINTER_COMPARISON.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(comparisons[0]))
        writer.writeheader()
        writer.writerows(comparisons)
    (args.out_dir / "VERIFY_8MIB_REPORT.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k != "errors"}))
    return 0 if result["product_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
