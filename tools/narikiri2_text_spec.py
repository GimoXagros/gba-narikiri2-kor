"""Fixed-revision text-table specification established from the AN9J pair."""

from __future__ import annotations

import hashlib
import struct
from functools import lru_cache

from source_profiles import source_profile


BASELINE_SHA256 = source_profile("AN9J_CANDIDATE_A").sha256
JAPANESE_SHA256 = source_profile("AN9J_JP_REV0").sha256
GBA_ROM_BASE = 0x08000000

ITEM_TABLE_OFFSET = 0x2B2CAC
ITEM_RECORD_SIZE = 0x14
ITEM_RECORD_COUNT = 157
ITEM_NAME_POINTER_OFFSET = 0x00
ITEM_DESCRIPTION_POINTER_OFFSET = 0x10

JP_TEXT_MIN = 0x2B38F0
JP_TEXT_MAX = 0x2B57AC
KR_DESCRIPTION_MIN = 0x800000
KR_DESCRIPTION_MAX = 0x802100
KR_NAME_MIN = 0x950000
KR_NAME_MAX = 0x9505C0

HANGUL_GLYPH_START = 671
HANGUL_GLYPH_COUNT = 2350
# Reserved only by the local half-space candidate; intercepted before font IO.
HALFWIDTH_SPACE_CODE = 0x8040
ASCII_CONVERSION_TABLE = 0x0CADA4
KANA_MODE0_TABLE = 0x0CAE64
KANA_MODE0_MARK_TABLE = 0x0CAEE0
KANA_MODE1_TABLE = 0x0CAF18
KANA_MODE1_MARK_TABLE = 0x0CAF94


class TextStructureError(ValueError):
    """Raised when the fixed text structure does not match the supported ROM."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rom_pointer_to_offset(value: int, rom_size: int) -> int:
    if not GBA_ROM_BASE <= value < GBA_ROM_BASE + rom_size:
        raise TextStructureError(f"pointer 0x{value:08X} is outside ROM")
    return value - GBA_ROM_BASE


def read_pointer(rom: bytes, storage_offset: int) -> tuple[int, int]:
    if storage_offset < 0 or storage_offset + 4 > len(rom):
        raise TextStructureError(f"pointer storage 0x{storage_offset:X} is outside ROM")
    raw = struct.unpack_from("<I", rom, storage_offset)[0]
    return raw, rom_pointer_to_offset(raw, len(rom))


def read_c_string(rom: bytes, offset: int, limit: int) -> bytes:
    if not 0 <= offset < limit <= len(rom):
        raise TextStructureError(f"invalid string range 0x{offset:X}..0x{limit:X}")
    end = rom.find(b"\0", offset, limit)
    if end < 0:
        raise TextStructureError(f"unterminated string at 0x{offset:X}")
    return rom[offset:end]


def require_range(value: int, start: int, end: int, label: str) -> None:
    if not start <= value < end:
        raise TextStructureError(
            f"{label} target 0x{value:X} is outside 0x{start:X}..0x{end:X}"
        )


def game_sjis_glyph_index(code: int) -> int:
    lead, trail = code >> 8, code & 0xFF
    if 0x81 <= lead <= 0x87:
        adjusted = lead - 0x81
    elif 0x88 <= lead <= 0xFF:
        adjusted = lead - 0x85
    else:
        raise TextStructureError(f"0x{code:04X} is not a game double-byte glyph code")
    return adjusted * 192 + trail - 0x40


@lru_cache(maxsize=1)
def wansung_hangul() -> tuple[str, ...]:
    characters = []
    for value in range(0xAC00, 0xD7A4):
        character = chr(value)
        encoded = character.encode("euc_kr", errors="ignore")
        if len(encoded) == 2 and 0xB0 <= encoded[0] <= 0xC8:
            characters.append(character)
    characters.sort(key=lambda character: character.encode("euc_kr"))
    if len(characters) != HANGUL_GLYPH_COUNT:
        raise TextStructureError("host EUC-KR codec does not expose the 2350 Wansung syllables")
    return tuple(characters)


def hangul_to_game_code(character: str) -> int:
    try:
        glyph_index = HANGUL_GLYPH_START + wansung_hangul().index(character)
    except ValueError as error:
        raise TextStructureError(f"{character!r} is outside the 2350-glyph Wansung repertoire") from error
    quotient, remainder = divmod(glyph_index, 192)
    lead = quotient + 0x85
    trail = remainder + 0x40
    if not 0x88 <= lead <= 0x9F or not 0x40 <= trail <= 0xFF:
        raise TextStructureError(f"{character!r} maps outside the adopted font range")
    return lead << 8 | trail


def glyph_code_to_text(code: int) -> str:
    if code == HALFWIDTH_SPACE_CODE:
        return ' '
    index = game_sjis_glyph_index(code)
    relative = index - HANGUL_GLYPH_START
    if 0 <= relative < HANGUL_GLYPH_COUNT:
        return wansung_hangul()[relative]
    try:
        return bytes((code >> 8, code & 0xFF)).decode("cp932")
    except UnicodeDecodeError:
        return f"{{RAW:{code:04X}}}"


def _table_halfword(rom: bytes, offset: int, index: int) -> int:
    position = offset + index * 2
    if position < 0 or position + 2 > len(rom):
        raise TextStructureError("character conversion table lookup exceeds ROM")
    # The renderer loads a little-endian halfword and writes its low byte first.
    # Keep glyph codes in the same lead<<8|trail form used for direct SJIS pairs.
    little = struct.unpack_from("<H", rom, position)[0]
    return (little & 0xFF) << 8 | little >> 8


def single_byte_to_game_code(rom: bytes, raw: bytes, position: int, mode: int) -> tuple[int, int]:
    value = raw[position]
    if 0x20 <= value <= 0x7E:
        return _table_halfword(rom, ASCII_CONVERSION_TABLE, value - 0x20), 1
    if not 0xA1 <= value <= 0xDF:
        raise TextStructureError(f"unsupported name byte 0x{value:02X} at index {position}")
    next_value = raw[position + 1] if position + 1 < len(raw) else None
    base_table = KANA_MODE1_TABLE if mode else KANA_MODE0_TABLE
    mark_table = KANA_MODE1_MARK_TABLE if mode else KANA_MODE0_MARK_TABLE
    if next_value == 0xDE:
        if value == 0xB3:
            return _table_halfword(rom, KANA_MODE0_TABLE, 0x19), 2
        return _table_halfword(rom, mark_table, value - 0xB6), 2
    if next_value == 0xDF:
        return _table_halfword(rom, mark_table, value - 0xBB), 2
    return _table_halfword(rom, base_table, value - 0xA1), 1


def decode_game_text(rom: bytes, raw: bytes) -> str:
    result: list[str] = []
    position = 0
    mode = 0
    while position < len(raw):
        value = raw[position]
        if value == 0x12:
            mode = 1 - mode
            position += 1
            continue
        if value == 0x0A:
            result.append("\n")
            position += 1
            continue
        if 0x20 <= value <= 0x7E:
            # These bytes are converted through the ROM table for drawing, but
            # retain their ordinary ASCII meaning in stored script data.
            result.append(chr(value))
            position += 1
            continue
        if 0xA1 <= value <= 0xDF:
            # Half-width kana retain CP932 semantics in stored source strings.
            # 0x12 only chooses which renderer-side glyph table is used.
            result.append(bytes((value,)).decode("cp932"))
            position += 1
            continue
        if 0x80 <= value <= 0x9F or value > 0xDF:
            if position + 1 >= len(raw):
                raise TextStructureError("truncated double-byte character")
            code = value << 8 | raw[position + 1]
            consumed = 2
        else:
            code, consumed = single_byte_to_game_code(rom, raw, position, mode)
        result.append(glyph_code_to_text(code))
        position += consumed
    return "".join(result)


def encode_korean_fixed_slot(text: str) -> bytes:
    output = bytearray()
    for character in text:
        if character == "\n":
            output.append(0x0A)
        elif 0x20 <= ord(character) <= 0x7E:
            output.append(ord(character))
        elif 0xAC00 <= ord(character) <= 0xD7A3:
            output.extend(hangul_to_game_code(character).to_bytes(2, "big"))
        else:
            raise TextStructureError(f"cannot encode {character!r} in the adopted name path")
    return bytes(output)
