"""Extract OAM-assembled title assets from exact private AN9J/Korean ROMs."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import struct

from PIL import Image, ImageDraw
from build_title_credits import LOGO_SPRITES, COPYRIGHT_SPRITES, unpack, pack_into
from strict_relative_assets import read_resource
from narikiri2_item_ui_font import compress_lz77

JP_SHA = 'a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7'
KR_SHA = '8823db1cb72f1328136ccfd8fff1fbdca0c8489cbc7ccf90f7e4ecdbb1c37776'
TABLE = 0x3768F8
RAW_PALETTES = {(TABLE, 0): 128, (TABLE, 1): 32, (TABLE, 2): 32,
                (TABLE, 5): 128, (TABLE, 6): 32, (TABLE, 7): 32,
                (0x380F08, 78): 128, (0x380F08, 79): 64,
                (0x380F08, 80): 320, (0x380F08, 81): 320, (0x380F08, 82): 32,
                (0x3A7ADC, 85): 128, (0x3A7ADC, 86): 512}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def diagnose_legacy_rl(image, start):
    """Read-only packet diagnostic; overrun output is never a valid asset."""
    if start < 0 or start + 4 > len(image) or image[start] != 0x30:
        raise ValueError('Legacy diagnostic requires an RL header')
    size = int.from_bytes(image[start + 1:start + 4], 'little')
    if not 0 < size <= 0x20000:
        raise ValueError('Legacy diagnostic output bound')
    cursor, produced = start + 4, 0
    while produced < size:
        if cursor >= len(image):
            raise ValueError('Truncated legacy RL control')
        control = image[cursor]
        cursor += 1
        length = (control & 127) + (3 if control & 128 else 1)
        payload = 1 if control & 128 else length
        if cursor + payload > len(image):
            raise ValueError('Truncated legacy RL packet')
        cursor += payload
        produced += length
    return dict(declared_bytes=size, produced_packet_bytes=produced,
                output_overshoot=produced - size, consumed_bytes=cursor - start,
                accepted_asset=False, diagnostic_only=True)


def render(raw, image, sprites):
    layers = unpack(raw, sprites)
    result = Image.new('RGB', (240, 160), (24, 32, 64))
    # Logo OAM lists foreground ribbon, gold face, then emblem/white halo.
    for bank in (1, 2, 0) if set(layers) == {0, 1, 2} else sorted(layers):
        for y, row in enumerate(layers[bank]):
            for x, index in enumerate(row):
                if index:
                    color = struct.unpack_from('<H', image, 0x37694C + 32 * bank + 2 * index)[0]
                    result.putpixel((x, y), tuple(((color >> shift) & 31) * 255 // 31 for shift in (0, 5, 10)))
    return result


def font_source(table, index):
    if table == TABLE and index in (10, 12, 13, 14, 15, 16):
        return 'build_v09d.py/title_trade_glyphs.json' if index == 12 else 'translated_ui_graphics.py/title_plans; build_title_credits.py/copyright_raw'
    if table == 0x380F08:
        if index == 5:
            return 'translated_ui_graphics.py/info_stream'
        if index in (6, 7):
            return 'build_hint_graphics.py'
        if 9 <= index <= 30:
            return 'build_place_names.py; strict_map_assets.py'
    if table == 0x3A7ADC and index in (32, 33, 35, 36, 37, 38, 39, 41, 42, 43, 45, 59, 60, 70, 71, 73, 74):
        return 'build_hint_graphics.py'
    return ''


def inventory(jp, kr, out):
    rows = []
    for table, count in ((TABLE, 20), (0x380F08, 135), (0x3A7ADC, 87)):
        assert struct.unpack_from('<I', jp, table)[0] == struct.unpack_from('<I', kr, table)[0] == count
        for index in range(count):
            starts = [(table + struct.unpack_from('<I', image, table + 4 + index * 4)[0]) & 0xFFFFFFFF for image in (jp, kr)]
            row = dict(asset_id=f'rel_{table:06x}_{index:03d}', table=f'{table:08X}', resource_index=index,
                       pointer_storage=f'{table + 4 + index * 4:08X}', jp_offset=f'{starts[0]:08X}', current_offset=f'{starts[1]:08X}',
                       jp_rom_sha256=sha(jp), current_rom_sha256=sha(kr), format='RESOURCE_NOT_YET_CLASSIFIED',
                       jp_raw_bytes='', current_raw_bytes='', jp_native_sha256='', current_native_sha256='',
                       changed_native='UNKNOWN', source='', classification='', visual_status='NOT_REVIEWED',
                       runtime_status='NOT_RUN', repack_roundtrip='', editable_mask='NONE_NO_EDIT', shared_uses='relative resource table consumers; unenumerated states require audit',
                       evidence='', notes='')
            try:
                original, old_used = read_resource(jp, starts[0])
                native, used = read_resource(kr, starts[1])
                row.update(jp_raw_bytes=len(original), current_raw_bytes=len(native), jp_native_sha256=sha(original),
                           current_native_sha256=sha(native), changed_native=str(native != original),
                           format=f'JP {jp[starts[0]]:02X}/KR {kr[starts[1]]:02X}; bounded decoder',
                           notes=f'JP consumed {old_used}; KR consumed {used}')
                if native != original:
                    packed = compress_lz77(native, vram_safe=True)
                    assert read_resource(packed, 0)[0] == native
                    row['repack_roundtrip'] = 'PASS_NATIVE_IDENTICAL_NOT_WRITTEN'
                    source = font_source(table, index)
                    if source:
                        row.update(source=source, classification='FONT_DERIVED_BAKED_EXCLUDED', visual_status='EXCLUDED_FONT_APPROVED_KEEP')
                    elif table == TABLE and index == 9:
                        row.update(source='build_title_credits.py/logo_raw; strict_asset_writeplan.py', classification='BESPOKE_LOCALIZED_LOGO',
                                   visual_status='REVIEWED_KEEP_PENDING_INDEPENDENT_QA', runtime_status='CURRENT_TITLE_MENU_OBSERVED',
                                   evidence='title_logo_COMPARISON_NATIVE.png; ../runtime-current-title/CURRENT_title_menu_RUNTIME.png')
                    elif table == 0x3A7ADC and index <= 4:
                        row.update(source='inherited FFR atlas; strict_relative_assets.py (0 includes translated_ui_graphics.py/shop_stream)',
                                   classification='INHERITED_BAKED_LETTERING_MIXED_FONT' if index == 0 else 'INHERITED_BAKED_LETTERING',
                                   visual_status='REVIEWED_KEEP_PENDING_INDEPENDENT_QA',
                                   runtime_status='CURRENT_BG_NATIVE_BYTES_MATCH' if index < 4 else 'NOT_RUN',
                                   evidence='MENU_ATLASES_CURRENT_NATIVE.png; ../runtime-current-menu/CURRENT_mainmenu_RUNTIME.png',
                                   notes=row['notes'] + '; atlas0 SHOP x192..255 y0..23 is approved Dalmoori and excluded')
                    elif table == 0x380F08 and index >= 31:
                        row.update(classification='INHERITED_MAP_LETTERING_RESIDUAL', visual_status='NOT_REVIEWED',
                                   notes=row['notes'] + '; active map rows now use resources9..30; remaining consumers unverified')
                    elif table == 0x3A7ADC and index in (34, 40, 72):
                        row.update(classification='LOCALIZED_EMPTY_SUFFIX', visual_status='NOT_REVIEWED', source='docs/RESOURCE_RESTORATION_AUDIT.md')
                    else:
                        row.update(classification='INHERITED_LOCALIZED_RESOURCE_NEEDS_ASSEMBLY', visual_status='NOT_REVIEWED')
                else:
                    row.update(classification='NATIVE_UNCHANGED', visual_status='OUTSIDE_LOCALIZED_DENOMINATOR')
            except ValueError as exc:
                if (table, index) in RAW_PALETTES:
                    size = RAW_PALETTES[table, index]
                    original, native = jp[starts[0]:starts[0] + size], kr[starts[1]:starts[1] + size]
                    assert len(original) == len(native) == size and original == native
                    row.update(classification='RAW_RGB555_PALETTE_UNCHANGED', format='uncompressed RGB555; bit15 ignored by hardware',
                               jp_raw_bytes=size, current_raw_bytes=size, jp_native_sha256=sha(original), current_native_sha256=sha(native),
                               changed_native='False', visual_status='OUTSIDE_LOCALIZED_DENOMINATOR',
                               source='native relative-table palette owner', notes='Exact JP/current palette bytes; not a compressed resource')
                elif table == 0x380F08 and index in (32, 43):
                    diagnostic = diagnose_legacy_rl(kr, starts[1])
                    following = (table + struct.unpack_from('<I', kr, table + 8 + index * 4)[0]) & 0xFFFFFFFF
                    diagnostic['source_overread_into_next_resource'] = max(0, starts[1] + diagnostic['consumed_bytes'] - following)
                    row.update(classification='LEGACY_OVERLONG_RL_RESIDUAL', format='RL final packet exceeds declared output; product decoder rejects',
                               visual_status='NEEDS_REFERENCE', runtime_status='UNUSED_BY_AUDITED_CONSUMERS_NOT_GLOBAL_PROOF',
                               notes=json.dumps(diagnostic, sort_keys=True),
                               source='inherited FFR payload; current map rows no longer select this resource')
                else:
                    row.update(classification='UNCLASSIFIED_RAW_OR_LEGACY_RESOURCE', notes=str(exc))
            rows.append(row)
    with (out / 'GRAPHICS_INVENTORY.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    counts = {kind: sum(r['classification'] == kind for r in rows) for kind in sorted({r['classification'] for r in rows})}
    return dict(relative_entries_scanned=len(rows), localized_native_changed=sum(r['changed_native'] == 'True' for r in rows),
                classifications=counts, scope='242 entries in three known relative resource tables; raw battle/font/notice writers listed separately; not every game asset',
                candidate_pixel_changes=0, independent_visual_qa='PENDING', runtime_all_states='NOT_RUN')


def menu_atlases(jp, kr, out):
    for label, rom in (('JP', jp), ('CURRENT', kr), ('CANDIDATE', kr)):
        sheet = Image.new('RGB', (256, 240), (24, 32, 64))
        draw = ImageDraw.Draw(sheet)
        for index in range(5):
            table = 0x3A7ADC
            start = (table + struct.unpack_from('<I', rom, table + 4 + index * 4)[0]) & 0xFFFFFFFF
            raw, _ = read_resource(rom, start)
            assert len(raw) == 4096
            picture = Image.new('RGB', (256, 32))
            for y in range(32):
                for x in range(256):
                    value = raw[((y // 8) * 32 + x // 8) * 32 + y % 8 * 4 + x % 8 // 2] >> (4 * (x % 2)) & 15
                    color = struct.unpack_from('<H', rom, 0x3AD8F0 + 2 * value)[0]
                    picture.putpixel((x, y), tuple(((color >> shift) & 31) * 255 // 31 for shift in (0, 5, 10)))
            draw.text((2, index * 48), str(index), fill='white')
            sheet.paste(picture, (0, index * 48 + 16))
        sheet.save(out / f'MENU_ATLASES_{label}_NATIVE.png')
        sheet.resize((1024, 960), Image.Resampling.NEAREST).save(out / f'MENU_ATLASES_{label}_4x.png')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('japanese', 'current', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    jp, kr = args.japanese.read_bytes(), args.current.read_bytes()
    if sha(jp) != JP_SHA or sha(kr) != KR_SHA or len(jp) != 0x800000 or len(kr) != 0x800000:
        raise ValueError('Exact 8MiB inputs required')
    args.out.mkdir(parents=True, exist_ok=False)
    records = []
    for asset_id, index, sprites in (('title_logo', 9, LOGO_SPRITES), ('title_copyright', 16, COPYRIGHT_SPRITES)):
        images = []
        for label, image in (('JP', jp), ('CURRENT', kr), ('CANDIDATE', kr)):
            entry = TABLE + 4 + 4 * index
            start = (TABLE + struct.unpack_from('<I', image, entry)[0]) & 0xFFFFFFFF
            raw, used = read_resource(image, start)
            layers = unpack(raw, sprites)
            # Overlapping OAM pieces hide distinct source pixels; verify the
            # assembled image separately from a lossless raw-index roundtrip.
            flattened = pack_into(raw, sprites, layers, lambda bank, x, y: True)
            assert unpack(flattened, sprites) == layers
            indices = [nibble for byte in raw for nibble in (byte & 15, byte >> 4)]
            assert bytes(indices[i] | indices[i + 1] << 4 for i in range(0, len(indices), 2)) == raw
            output = render(raw, image, sprites)
            output.save(args.out / f'{asset_id}_{label}_EXTRACTED.png')
            output.resize((960, 640), Image.Resampling.NEAREST).save(args.out / f'{asset_id}_{label}_EXTRACTED_4x.png')
            images.append(output)
            records.append(dict(asset_id=asset_id, label=label, rom_sha256=sha(image), table=hex(TABLE), index=index,
                                start=hex(start), compression=hex(image[start]), consumed=used, native_bytes=len(raw),
                                native_sha256=sha(raw), visible_oam_repack_identical=True,
                                hidden_overlap_raw_difference=sum(a != b for a, b in zip(raw, flattened)),
                                raw_index_roundtrip_identical=True))
        sheet = Image.new('RGB', (720, 180), (24, 32, 64))
        draw = ImageDraw.Draw(sheet)
        for x, (label, output) in enumerate(zip(('JP', 'CURRENT', 'CANDIDATE_KEEP'), images)):
            draw.text((x * 240 + 4, 2), label, fill='white')
            sheet.paste(output, (x * 240, 20))
        sheet.save(args.out / f'{asset_id}_COMPARISON_NATIVE.png')
        sheet.resize((2880, 720), Image.Resampling.NEAREST).save(args.out / f'{asset_id}_COMPARISON_4x.png')
    summary = inventory(jp, kr, args.out)
    menu_atlases(jp, kr, args.out)
    (args.out / 'INVENTORY_SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    (args.out / 'EXTRACTION.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
