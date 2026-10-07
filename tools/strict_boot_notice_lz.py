"""Diagnostic notice LZ write plan for the frozen 13.27 MiB Korean image.

Replacing the exact C90000 raw-copy wrapper with BIOS LZ77UnCompVram makes
the old 76,800-byte notice pixel allocation available after the 9,156-byte
compressed stream. This establishes a bounded *diagnostic* ROM arena for
runtime experiments. It does not solve placement in the original 8 MiB ROM.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from build_banked_font import assemble
from find_gba_lz77_asset import decompress_lz77_stream
from narikiri2_item_ui_font import compress_lz77
from strict_layout_core import Write, sha
from verify_jp8mib_strict import JP_SHA, KO_SHA

ROOT = Path(__file__).resolve().parents[1]
BASE_SIZE = 13270790
WRAPPER_START = 0xC90000
WRAPPER_LIMIT = 0x200
PIXELS_START = 0xC91000
PIXELS_END = 0xCA3C00


def plan_notice_lz(base: bytes, japanese: bytes) -> tuple[list[Write], dict]:
    if len(base) != BASE_SIZE or sha(base) != KO_SHA:
        raise ValueError("Exact adopted Korean diagnostic baseline required")
    old_code = assemble(ROOT / "asm/boot_notice.s", WRAPPER_START, 0, WRAPPER_LIMIT)
    if base[WRAPPER_START:WRAPPER_START + len(old_code)] != old_code:
        raise ValueError("Original notice wrapper source mismatch")
    if struct.unpack_from("<I", base, 0x100)[0] != 0x08C90001:
        raise ValueError("Notice entry pointer changed")
    if struct.unpack_from("<I", old_code, len(old_code) - 4)[0] != 0x08007401:
        raise ValueError("Original main return target changed")
    new_code = assemble(ROOT / "asm/strict_boot_notice_lz.s",
                        WRAPPER_START, 0, WRAPPER_LIMIT)
    if len(new_code) > len(old_code) or new_code.count(b"\x12\xdf") != 1:
        raise ValueError("Replacement wrapper exceeds owner or lacks unique SWI 12h")
    if struct.pack("<I", 0x08000000 + PIXELS_START) not in new_code:
        raise ValueError("Packed pixel symbol does not resolve to owned stream")
    if struct.pack("<I", 0x08007401) not in new_code:
        raise ValueError("Original main return address was not retained")
    raw = base[PIXELS_START:PIXELS_END]
    if len(raw) != 240 * 160 * 2:
        raise ValueError("Notice geometry changed")
    packed = compress_lz77(raw, vram_safe=True)
    decoded = decompress_lz77_stream(packed, 0, len(raw))
    if (decoded is None or decoded[0] != raw
            or not decoded[1] <= len(packed) < decoded[1] + 4
            or any(packed[decoded[1]:]) or len(packed) & 3):
        raise ValueError("VRAM-safe notice stream roundtrip/padding failed")
    # Exhaustively inspect aligned absolute-pointer shaped values. The sole
    # new reference to this allocation belongs to the matched old wrapper.
    # All other hits must be unchanged Japanese-source bytes and are recorded,
    # not silently treated as proven pointers or as a blanket free-space scan.
    jp = japanese
    if len(jp) != 0x800000 or sha(jp) != JP_SHA:
        raise ValueError("Exact Japanese reference required")
    hits = []
    for at in range(0, len(base) - 3, 4):
        value = struct.unpack_from("<I", base, at)[0]
        if 0x08000000 + PIXELS_START <= value < 0x08000000 + PIXELS_END:
            hits.append((at, value))
    if (WRAPPER_START + old_code.index(struct.pack("<I", 0x08000000 + PIXELS_START)),
            0x08000000 + PIXELS_START) not in hits:
        raise ValueError("Original wrapper pixel reference missing")
    wrapper_literal = WRAPPER_START + old_code.index(
        struct.pack("<I", 0x08000000 + PIXELS_START))
    if any((at >= len(jp) or base[at:at + 4] != jp[at:at + 4])
           for at, _ in hits if at != wrapper_literal):
        raise ValueError("Unclassified new pointer-shaped notice reference")
    replacement = new_code + old_code[len(new_code):]
    writes = [
        Write("diagnostic:boot_notice_lz_wrapper", WRAPPER_START,
              old_code, replacement, "replace raw-copy loop with BIOS SWI 12h",
              "matched C90000 notice entry and original-main return",
              "exact adopted Korean wrapper, symbol-assembled replacement",
              ("exact_wrapper", "swi12_opcode", "entry_return")),
        Write("diagnostic:boot_notice_lz_pixels", PIXELS_START,
              base[PIXELS_START:PIXELS_START + len(packed)], packed,
              "lossless VRAM-safe 240x160 RGB555 LZ stream",
              "C90000 wrapper's packed-pixel literal",
              "unchanged adopted notice pixel bytes",
              ("bounded_lz_roundtrip", "vram_safe", "pointer_shape_audit")),
    ]
    report = dict(status="DIAGNOSTIC_ARENA_ONLY_NOT_8MIB_PRODUCT",
                  source_sha256=KO_SHA, source_size=BASE_SIZE,
                  notice_raw_sha256=sha(raw), notice_raw_bytes=len(raw),
                  notice_lz_sha256=sha(packed), notice_lz_bytes=len(packed),
                  wrapper_old_bytes=len(old_code), wrapper_new_bytes=len(new_code),
                  arena_start=PIXELS_START + len(packed), arena_end=PIXELS_END,
                  arena_bytes=PIXELS_END - PIXELS_START - len(packed),
                  arena_condition="new wrapper installed before any write into reclaimed range",
                  pointer_shaped_hits=[dict(storage=f"{a:08X}", value=f"{v:08X}",
                      classification=("matched_notice_wrapper_literal" if a == wrapper_literal
                                      else "preexisting_jp_value_beyond_8mib_source"))
                                       for a, v in hits],
                  pointer_audit_limit=(
                      "Aligned absolute-pointer shape scan only; identical JP words had "
                      "out-of-range targets before expansion. Dynamic/mirror reference "
                      "closure for the full product remains unproved."),
                  runtime_screen_verification="NOT_RUN",
                  product_8mib_placement="UNRESOLVED")
    return writes, report


def assemble_diagnostic(base: bytes, japanese: bytes,
                        extra_writes: tuple[Write, ...] = ()) -> tuple[bytes, dict]:
    """Apply only expected-source writes; extra payloads must fit the arena."""
    notice_writes, report = plan_notice_lz(base, japanese)
    ordered = sorted((*notice_writes, *extra_writes), key=lambda row: row.start)
    for row in extra_writes:
        if not (report["arena_start"] <= row.start < row.end <= report["arena_end"]):
            raise ValueError("Diagnostic payload exceeds reclaimed notice owner")
    output = bytearray(base)
    prior_end = 0
    for row in ordered:
        if row.start < prior_end or row.end > len(base):
            raise ValueError("Overlapping or out-of-range diagnostic write")
        if (not row.after or len(row.before) != len(row.after)
                or base[row.start:row.end] != row.before):
            raise ValueError("Diagnostic expected-source bytes changed")
        output[row.start:row.end] = row.after
        prior_end = row.end
    if len(output) != len(base):
        raise ValueError("Diagnostic image size changed")
    report = dict(report, diagnostic_sha256=sha(output),
                  writes=[row.manifest() for row in ordered],
                  extra_writes=len(extra_writes))
    return bytes(output), report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--adopted", type=Path, required=True)
    p.add_argument("--japanese", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--emit-diagnostic-rom", action="store_true")
    args = p.parse_args()
    if args.out.exists():
        raise ValueError("Choose a new output folder")
    base, jp = args.adopted.read_bytes(), args.japanese.read_bytes()
    writes, report = plan_notice_lz(base, jp)
    args.out.mkdir(parents=True)
    for row in writes:
        (args.out / f"{row.writer_id.replace(':', '_')}.bin").write_bytes(row.after)
    report["writes"] = [row.manifest() for row in writes]
    if args.emit_diagnostic_rom:
        image, assembled = assemble_diagnostic(base, jp)
        (args.out / "BOOT_LZ_DIAGNOSTIC_NOT_PRODUCT.gba").write_bytes(image)
        report["diagnostic_sha256"] = assembled["diagnostic_sha256"]
    (args.out / "BOOT_LZ_PLAN.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
