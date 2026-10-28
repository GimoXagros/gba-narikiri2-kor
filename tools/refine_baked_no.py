"""Historical A/B alternatives; user rejected B and neither is approved for integration."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from PIL import Image, ImageDraw
from bps import apply_bps, create_bps
from narikiri2_item_ui_font import compress_lz77
from strict_relative_assets import read_resource

BASE_SHA = '8823db1cb72f1328136ccfd8fff1fbdca0c8489cbc7ccf90f7e4ecdbb1c37776'
JP_SHA = 'a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7'
RAW_SHA = 'ea96083fef75c607b42d6d6473f7028579d57b3640aeced3a81f41dbf32e1915'
START, CAPACITY, POINTER = 0x3AD774, 206, 0x3A7C30
GLYPHS = (
    ('.......##..', '.......##..', '.####..##..', '######.##..', '##..##.####',
     '##..##.####', '######.##..', '.####..##..', '.......##..', '.......##..', '.......##..'),
    ('##...##', '##...##', '##...##', '##...##', '##...##', '##...##',
     '##...##', '##...##', '####.##', '####.##', '.....##'),
    ('.#####.', '#######', '##...##', '##...##', '#######', '.#####.',
     '...##..', '...##..', '...##..', '#######', '#######'),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unpack(raw):
    if len(raw) != 256:
        raise ValueError('NO label must be 32x16 native 4bpp')
    return [[raw[((y // 8) * 4 + x // 8) * 32 + y % 8 * 4 + x % 8 // 2] >> (4 * (x % 2)) & 15
             for x in range(32)] for y in range(16)]


def pack(pixels):
    if len(pixels) != 16 or any(len(row) != 32 or set(row) - {0, 8, 15} for row in pixels):
        raise ValueError('Unexpected geometry or palette indices')
    result = bytes(pixels[ty * 8 + y][tx * 8 + x] | pixels[ty * 8 + y][tx * 8 + x + 1] << 4
                   for ty in range(2) for tx in range(4) for y in range(8) for x in range(0, 8, 2))
    assert unpack(result) == pixels
    return result


def alternatives(original):
    pixels = unpack(original)
    if any(any(row) for row in pixels[:3]):
        raise ValueError('Upward alternative would crop nonempty pixels')
    upward = pixels[3:] + [[0] * 32 for _ in range(3)]
    ink = set()
    for left, rows in zip((4, 16, 24), GLYPHS):
        assert len(rows) == 11 and len({len(row) for row in rows}) == 1
        ink.update((left + x, 4 + y) for y, row in enumerate(rows) for x, value in enumerate(row) if value == '#')
    assert min(x for x, _ in ink) == 4 and max(x for x, _ in ink) == 30
    hand = [[0] * 32 for _ in range(16)]
    for x, y in ink:
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            xx, yy = x + dx, y + dy
            if 0 <= xx < 32 and 0 <= yy < 16:
                hand[yy][xx] = 8
    for x, y in ink:
        hand[y][x] = 15
    assert sum(value != 0 for row in upward for value in row) == sum(value != 0 for row in pixels for value in row)
    return {'A_up3': pack(upward), 'B_native_letters': pack(hand)}


def indexed(raw, palette):
    picture = Image.new('P', (32, 16))
    picture.putpalette(palette)
    picture.putdata([value for row in unpack(raw) for value in row])
    picture.info['transparency'] = 0
    return picture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'japanese', 'live-palette', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    base, jp = args.baseline.read_bytes(), args.japanese.read_bytes()
    if sha(base) != BASE_SHA or sha(jp) != JP_SHA or len(base) != 0x800000 or len(jp) != 0x800000:
        raise ValueError('Exact Japanese and accepted v1.1a required')
    raw, used = read_resource(base, START)
    if sha(raw) != RAW_SHA or used != CAPACITY or struct.unpack_from('<I', base, POINTER)[0] + 0x3A7ADC != START:
        raise ValueError('Current NO asset/owner changed')
    palette_bytes = args.live_palette.read_bytes()
    if len(palette_bytes) != 1024:
        raise ValueError('Full captured BG/OBJ palette required')
    palette = []
    for value in struct.unpack_from('<16H', palette_bytes, 512 + 7 * 32):
        palette.extend(((value >> shift) & 31) * 255 // 31 for shift in (0, 5, 10))
    palette += [0] * (768 - len(palette))
    args.out.mkdir(parents=True, exist_ok=False)
    jp_raw, _ = read_resource(jp, START)
    pictures = [('JP', indexed(jp_raw, palette)), ('CURRENT', indexed(raw, palette))]
    report = dict(status='TWO_UNAPPROVED_GRAPHIC_ALTERNATIVES', before_rom_sha256=sha(base),
                  asset_id='rel_3a7adc_084', offset=START, capacity=CAPACITY,
                  before_owner_sha256=sha(base[START:START + CAPACITY]), before_native_sha256=sha(raw),
                  palette_indices=[0, 8, 15], glyph_source='authored GLYPHS pixel rows; no font file/rasterizer',
                  reason='Selected NO cursor occludes current first syllable ink at asset x0..3', alternatives=[])
    for name, candidate in alternatives(raw).items():
        packed = compress_lz77(candidate, vram_safe=True)
        if len(packed) > CAPACITY or read_resource(packed, 0)[0] != candidate:
            raise ValueError('Alternative exceeds current consumed owner or fails readback')
        payload = packed + base[START + len(packed):START + CAPACITY]
        image = bytearray(base)
        image[START:START + CAPACITY] = payload
        assert image[:START] == base[:START] and image[START + CAPACITY:] == base[START + CAPACITY:]
        assert len(image) == 0x800000 and image[POINTER:POINTER + 4] == base[POINTER:POINTER + 4]
        assert read_resource(image, START)[0] == candidate
        folder = args.out / name
        folder.mkdir()
        (folder / 'asset_owner_payload.bin').write_bytes(payload)
        (folder / 'asset_native_4bpp.bin').write_bytes(candidate)
        (folder / 'GRAPHICS_ONLY_UNAPPROVED.gba').write_bytes(image)
        patch = create_bps(base, bytes(image), b'Private unapproved baked NO cursor alternative')
        assert apply_bps(base, patch) == image
        (folder / 'FROM_V11A_GRAPHICS_ONLY.bps').write_bytes(patch)
        picture = indexed(candidate, palette)
        pictures.append((name, picture))
        mask = Image.new('1', (32, 16))
        mask.putdata([a != b for row_a, row_b in zip(unpack(raw), unpack(candidate)) for a, b in zip(row_a, row_b)])
        mask.save(folder / 'CHANGED_PIXEL_MASK.png')
        report['alternatives'].append(dict(id=name, after_rom_sha256=sha(image), after_owner_sha256=sha(payload),
                                           after_native_sha256=sha(candidate), packed_bytes=len(packed),
                                           write_bytes=CAPACITY, changed_rom_bytes=sum(a != b for a, b in zip(base, image)),
                                           pointers_changed=0, outside_owner_changed=0,
                                           limitation='NO baseline raised3px relative to YES' if name == 'A_up3' else 'Native manual lettering requires independent Hangul/style approval'))
    for name, picture in pictures:
        picture.save(args.out / f'{name}_NATIVE_INDEXED.png')
        picture.resize((128, 64), Image.Resampling.NEAREST).save(args.out / f'{name}_4x.png')
    sheet = Image.new('RGB', (128, 30), (24, 32, 64))
    draw = ImageDraw.Draw(sheet)
    for n, (name, picture) in enumerate(pictures):
        draw.text((n * 32, 0), ('JP', 'CURRENT', 'A', 'B')[n], fill='white')
        sheet.paste(picture.convert('RGB'), (n * 32, 14))
    sheet.save(args.out / 'JP_CURRENT_A_B_NATIVE_COMPARISON.png')
    sheet.resize((512, 120), Image.Resampling.NEAREST).save(args.out / 'JP_CURRENT_A_B_4x_COMPARISON.png')
    (args.out / 'GRAPHICS_ALTERNATIVES.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
