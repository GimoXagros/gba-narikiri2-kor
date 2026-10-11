"""ARTE name context oracle: record index and field select the strict stream.

This proves the shared 158/159 selection from the game's accessor inputs.
It is not yet a game hook: the caller-owned output lifetime remains open.
"""
from __future__ import annotations

import hashlib
import struct

from strict_unit_codec import decode_parts

ARTE_TABLE_OFFSET = 0x374A38
ARTE_COUNT = 232
ARTE_STRIDE = 20


def decode_name(image: bytes, index: int, field: int,
                bindings: list[dict[str, str]], fits: list[dict[str, str]],
                book: bytes) -> bytes:
    if type(index) is not int or not 0 <= index < ARTE_COUNT:
        raise ValueError("Invalid ARTE record context")
    if field != 0:
        raise ValueError("ARTE field 1 is full text, not a compact name")
    storage = ARTE_TABLE_OFFSET + index * ARTE_STRIDE
    rows = [r for r in bindings if int(r["jp_pointer_storage"]) == storage]
    if len(rows) != 1 or rows[0]["id"] != f"ARTE_{index:03d}":
        raise ValueError("ARTE binding context absent or ambiguous")
    row = rows[0]
    if row["category"] != "compact":
        raise ValueError("ARTE name category mismatch")
    fit_rows = [r for r in fits if r["binding_id"] == row["binding_id"]]
    if len(fit_rows) != 1:
        raise ValueError("ARTE fit context absent or ambiguous")
    fit = fit_rows[0]
    ptr = struct.unpack_from("<I", image, storage)[0]
    if ptr != int(row["jp_pointer_value"]):
        raise ValueError("ARTE pointer differs from original")
    start = ptr - 0x08000000
    encoded = int(fit["encoded_length"])
    native = int(fit["native_output_length"])
    if not (1 <= encoded <= int(row["slot_capacity"]) and 1 <= native <= 0xFFFF):
        raise ValueError("ARTE encoded/native extent invalid")
    if not 0 <= start <= len(image) - encoded:
        raise ValueError("ARTE stream outside image")
    result, used = decode_parts(image[start:start + encoded], book, native,
                                int(fit["inline_part_count"]),
                                int(fit["inline_selection"]))
    if used != encoded or len(result) != native or result[-1] != 0:
        raise ValueError("ARTE name output extent differs")
    if hashlib.sha256(result[:-1]).hexdigest() != row["latest_ko_hash"]:
        raise ValueError("ARTE name differs from frozen template")
    return result
