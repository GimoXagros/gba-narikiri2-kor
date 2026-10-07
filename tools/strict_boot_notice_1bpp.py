"""Lossless two-color boot-notice diagnostic with an offscreen VRAM scratch.

The original append-only boot build owns C90000..C91000 for code and
C91000..CA3C00 for pixels. This diagnostic retains the original entry,
button-release/press/release sequence, 96 KiB VRAM clear and main return.
It is not an 8 MiB product placement plan.
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
WRAPPER_END = 0xC91000
PIXELS_START = 0xC91000
PIXELS_END = 0xCA3C00
VRAM_START = 0x06000000
VISIBLE_END = VRAM_START + 240 * 160 * 2
SCRATCH_START = 0x06014000
SCRATCH_END = SCRATCH_START + 4800
VRAM_END = VRAM_START + 0x18000
RAW_BYTES = 240 * 160 * 2
PLANE_BYTES = 240 * 160 // 8


def make_lut() -> bytes:
    return b"".join(struct.pack("<4H", *(
        0x7FFF if nibble & (1 << (3 - pixel)) else 0
        for pixel in range(4))) for nibble in range(16))


def pack_1bpp(raw: bytes) -> bytes:
    if len(raw) != RAW_BYTES:
        raise ValueError("Notice RGB555 geometry must be 240x160")
    pixels = struct.unpack("<38400H", raw)
    if any(pixel not in (0, 0x7FFF) for pixel in pixels):
        raise ValueError("Notice contains a color outside the exact 0/32767 palette")
    plane = bytes(sum((pixels[group * 8 + bit] == 0x7FFF) << (7 - bit)
                      for bit in range(8)) for group in range(PLANE_BYTES))
    if expand_1bpp(plane) != raw:
        raise ValueError("Notice bitplane-to-RGB555 round trip changed a pixel")
    return plane


def expand_1bpp(plane: bytes) -> bytes:
    if len(plane) != PLANE_BYTES:
        raise ValueError("Notice 1bpp geometry must be exactly 4,800 bytes")
    lut = make_lut()
    return b"".join(lut[(value >> 4) * 8:(value >> 4) * 8 + 8]
                    + lut[(value & 15) * 8:(value & 15) * 8 + 8]
                    for value in plane)


def plan_notice_1bpp(base: bytes, japanese: bytes) -> tuple[list[Write], dict]:
    if len(base) != BASE_SIZE or sha(base) != KO_SHA:
        raise ValueError("Exact adopted Korean diagnostic baseline required")
    if len(japanese) != 0x800000 or sha(japanese) != JP_SHA:
        raise ValueError("Exact 8 MiB Japanese reference required")
    old_code = assemble(ROOT / "asm/boot_notice.s", WRAPPER_START, 0,
                        WRAPPER_END - WRAPPER_START)
    if base[WRAPPER_START:WRAPPER_START + len(old_code)] != old_code:
        raise ValueError("Original notice wrapper source mismatch")
    if struct.unpack_from("<I", base, 0x100)[0] != 0x08C90001:
        raise ValueError("Notice entry pointer changed")
    new_code = assemble(ROOT / "asm/strict_boot_notice_1bpp.s",
                        WRAPPER_START, 0, WRAPPER_END - WRAPPER_START)
    if (len(new_code) <= len(old_code)
            or base[WRAPPER_START + len(old_code):WRAPPER_START + len(new_code)]
            != b"\xff" * (len(new_code) - len(old_code))):
        raise ValueError("Expanded wrapper crosses non-padding in its declared code owner")
    if (new_code.count(b"\x12\xdf") != 1
            or struct.pack("<I", 0x08000000 + PIXELS_START) not in new_code
            or struct.pack("<I", SCRATCH_START) not in new_code
            or struct.pack("<I", 0x08007401) not in new_code
            or new_code[-128:] != make_lut()):
        raise ValueError("Wrapper SWI, stream, scratch, return, or LUT binding changed")
    if not VISIBLE_END <= SCRATCH_START < SCRATCH_END <= VRAM_END:
        raise ValueError("Packed scratch is not offscreen inside 96 KiB mode-3 VRAM")
    raw = base[PIXELS_START:PIXELS_END]
    plane = pack_1bpp(raw)
    packed = compress_lz77(plane, vram_safe=True)
    decoded, used = decompress_lz77_stream(packed, 0, PLANE_BYTES)
    if (decoded != plane or not used <= len(packed) < used + 4
            or any(packed[used:]) or len(packed) & 3):
        raise ValueError("VRAM-safe 1bpp LZ stream round trip/padding failed")
    if PIXELS_START + len(packed) >= PIXELS_END:
        raise ValueError("1bpp stream is not smaller than its original owner")
    literal = WRAPPER_START + old_code.index(struct.pack("<I", 0x08000000 + PIXELS_START))
    hits = []
    for storage in range(0, len(base) - 3, 4):
        value = struct.unpack_from("<I", base, storage)[0]
        if 0x08000000 + PIXELS_START <= value < 0x08000000 + PIXELS_END:
            hits.append((storage, value))
    if (literal, 0x08000000 + PIXELS_START) not in hits:
        raise ValueError("Original notice pixel pointer was not found")
    if any((storage >= len(japanese)
            or base[storage:storage + 4] != japanese[storage:storage + 4])
           for storage, _ in hits if storage != literal):
        raise ValueError("Unclassified expanded-ROM pointer-shaped notice reference")
    writes = [
        Write("diagnostic:boot_notice_1bpp_wrapper", WRAPPER_START,
              base[WRAPPER_START:WRAPPER_START + len(new_code)], new_code,
              "offscreen VRAM SWI12 decode, LUT expansion, accepted boot input/return",
              "original C90000 boot entry and C90000..C91000 code owner",
              "exact adopted wrapper plus append-only boot build allocation",
              ("entry_return", "thumb1", "lut", "offscreen_scratch")),
        Write("diagnostic:boot_notice_1bpp_pixels", PIXELS_START,
              base[PIXELS_START:PIXELS_START + len(packed)], packed,
              "lossless 240x160 two-color bitmap packed to VRAM-safe 1bpp LZ",
              "C90000 wrapper stream literal and offscreen VRAM scratch",
              "exact adopted RGB555 notice pixels",
              ("two_colors", "bitplane_roundtrip", "lz_roundtrip", "vram_safe")),
    ]
    pixels = struct.unpack("<38400H", raw)
    report = dict(status="DIAGNOSTIC_ARENA_ONLY_NOT_8MIB_PRODUCT",
                  source_sha256=KO_SHA, source_size=BASE_SIZE,
                  raw_sha256=sha(raw), raw_bytes=len(raw),
                  colors={"0000": pixels.count(0), "7FFF": pixels.count(0x7FFF)},
                  bitplane_sha256=sha(plane), bitplane_bytes=len(plane),
                  lz_sha256=sha(packed), lz_bytes=len(packed), lz_consumed_bytes=used,
                  wrapper_old_bytes=len(old_code), wrapper_new_bytes=len(new_code),
                  code_owner=[WRAPPER_START, WRAPPER_END],
                  vram_visible=[VRAM_START, VISIBLE_END],
                  vram_scratch=[SCRATCH_START, SCRATCH_END],
                  vram_total=[VRAM_START, VRAM_END],
                  expansion_lut_bytes=len(make_lut()),
                  arena_start=PIXELS_START + len(packed), arena_end=PIXELS_END,
                  arena_bytes=PIXELS_END - PIXELS_START - len(packed),
                  arena_condition="new boot wrapper installed before reclaimed pixel suffix use",
                  pointer_shaped_hits=[dict(storage=f"{storage:08X}", value=f"{value:08X}",
                                       classification=("matched_notice_wrapper_literal"
                                                       if storage == literal else
                                                       "identical_preexisting_JP_bytes"))
                                       for storage, value in hits],
                  remaining_gate="diagnostic only; no JP 8 MiB notice placement")
    return writes, report


def assemble_diagnostic(base: bytes, japanese: bytes,
                        extra_writes: tuple[Write, ...] = ()) -> tuple[bytes, dict]:
    writes, report = plan_notice_1bpp(base, japanese)
    for row in extra_writes:
        if not report["arena_start"] <= row.start < row.end <= report["arena_end"]:
            raise ValueError("Diagnostic payload exceeds reclaimed notice owner")
    output = bytearray(base)
    previous_end = 0
    for row in sorted((*writes, *extra_writes), key=lambda write: write.start):
        if (row.start < previous_end or row.end > len(base) or not row.after
                or len(row.before) != len(row.after)
                or base[row.start:row.end] != row.before):
            raise ValueError("Overlapping or stale expected-source diagnostic write")
        output[row.start:row.end] = row.after
        previous_end = row.end
    if len(output) != len(base):
        raise ValueError("Diagnostic image size changed")
    return bytes(output), dict(report, diagnostic_sha256=sha(output),
                               writes=[row.manifest() for row in (*writes, *extra_writes)],
                               extra_writes=len(extra_writes))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adopted", type=Path, required=True)
    parser.add_argument("--japanese", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--emit-diagnostic-rom", action="store_true")
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Choose a new output folder")
    base, jp = args.adopted.read_bytes(), args.japanese.read_bytes()
    writes, report = plan_notice_1bpp(base, jp)
    args.out.mkdir(parents=True)
    for row in writes:
        (args.out / f"{row.writer_id.replace(':', '_')}.bin").write_bytes(row.after)
    report["writes"] = [row.manifest() for row in writes]
    if args.emit_diagnostic_rom:
        image, assembled = assemble_diagnostic(base, jp)
        (args.out / "BOOT_1BPP_DIAGNOSTIC_NOT_PRODUCT.gba").write_bytes(image)
        report["diagnostic_sha256"] = assembled["diagnostic_sha256"]
    (args.out / "BOOT_1BPP_PLAN.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
