"""Give the native skill-button heading four pixels of top margin in place."""
import hashlib

CONTEXT_START = 0x134C2
CONTEXT = bytes.fromhex('03203021002201f09afc')
OFFSET = 0x134C6
BEFORE = bytes.fromhex('0022')
AFTER = bytes.fromhex('0422')


def apply_title_margin(image: bytes):
    # Only this case-3 caller changes; shared sprite code and glyphs stay intact.
    if len(image) != 0x800000:
        raise ValueError('Skill-title correction requires the 8 MiB layout')
    if image[CONTEXT_START:CONTEXT_START + len(CONTEXT)] != CONTEXT:
        raise ValueError('Skill-title caller context differs')
    result = image[:OFFSET] + AFTER + image[OFFSET + len(BEFORE):]
    return result, dict(offset=OFFSET, before=BEFORE.hex(), after=AFTER.hex(),
        kind='thumb_movs_r2_immediate', old_y=0, new_y=4,
        source_sha256=hashlib.sha256(image).hexdigest(),
        target_sha256=hashlib.sha256(result).hexdigest(),
        scope='Case-3 skill-button heading top margin; no glyph or pointer relocation')
