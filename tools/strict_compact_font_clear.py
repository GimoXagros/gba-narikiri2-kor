"""Preserve hot clear-bank reads while deriving the solid bank exactly."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def validate_banks(clear, solid):
    if len(clear) != 512 * 32 or len(solid) != len(clear):
        raise ValueError('Expected two adopted 512-glyph banks')
    if any(b not in (0, 15, 240, 255) for b in clear):
        raise ValueError('Clear bank is not binary 4bpp')
    if bytes(b | 0xbb for b in clear) != solid:
        raise ValueError('Solid bank cannot be derived without changing pixels')


def assemble(address, *, decoder, cache, clear_font):
    from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
    from strict_compact_font import validate_thumb
    if address & 3 or clear_font & 3 or not decoder & 1 or not cache & 1:
        raise ValueError('ARMv4T code/font alignment')
    source = (ROOT / 'asm/strict_compact_font_clear.s').read_text()
    for key, value in dict(BANKED_DECODER=decoder, TILE_CACHE=cache,
                           CLEAR_FONT=clear_font).items():
        source = re.sub(r'\b' + key + r'\b', str(value), source)
    code = bytes(Ks(KS_ARCH_ARM, KS_MODE_THUMB).asm(source, addr=address)[0])
    validate_thumb(code, 5)
    return code
