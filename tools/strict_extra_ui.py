"""Additional source-bound UI streams omitted by the historical denominator.

The 10,172 frozen bindings are not changed.  Every added pointer retains its
original value, and every added stream occupies only its original C-string
extent.  The third tree stores single native glyphs/bytes, never whole labels.
"""
import struct
from strict_layout_core import sha
from strict_unit_codec import fit_parts_book, encode_parts, decode_parts
from strict_packed_tree import pack_tree
from strict_stream_lookup24 import pack_bounds24
from fixed_ui_labels import LABELS

EXCLUDED_UI = {0xA1E4, 0x188C38, 0x9780, 0x9788}
# Original full-name fields excluded by the old full-text extraction filter.
EXTRA_FULL_FIELDS = (0x2B580C, 0x37548C)


def cstring(rom, start):
    if not 0 <= start < len(rom):
        raise ValueError('String outside source')
    end = rom.index(b'\0', start, min(start + 512, len(rom)))
    return rom[start:end]


def plan(japanese, adopted, ui_config, historical, slot_image, compact_book):
    """Return exact writes and a separately counted, lossless UI corpus."""
    existing_storage = {int(r['jp_pointer_storage']) for r in historical}
    existing_starts = {int(r['jp_text_start']): r for r in historical}
    storages = ({int(k, 16) for k in ui_config} - EXCLUDED_UI
                | {r[0] for r in LABELS} | set(EXTRA_FULL_FIELDS))
    if storages & existing_storage:
        raise ValueError('Additional binding duplicated in historical corpus')
    rows, groups, writes = [], {}, []
    for at in sorted(storages):
        start = struct.unpack_from('<I', japanese, at)[0] - 0x08000000
        adopted_start = struct.unpack_from('<I', adopted, at)[0] - 0x08000000
        original, native = cstring(japanese, start), cstring(adopted, adopted_start)
        capacity = len(original) + 1
        overlap = [s for s, r in existing_starts.items()
                   if start < s + int(r['slot_capacity']) and start + capacity > s]
        old = existing_starts.get(start)
        if old:
            if old['category'] != 'compact' or overlap != [start]:
                raise ValueError('Unexpected historical overlap')
            size = int(old['encoded_length'])
            decoded, used = decode_parts(slot_image[start:start+size], compact_book,
                                         288, 1, 1)
            if decoded != native + b'\0' or used != size:
                raise ValueError('Added pointer does not match existing stream')
        elif overlap:
            raise ValueError('Partial historical overlap')
        row = dict(storage=at, start=start, adopted_start=adopted_start,
                   slot_capacity=capacity, native_hex=native.hex(),
                   output_sha256=sha(native+b'\0'),
                   existing_binding=old['binding_id'] if old else None)
        rows.append(row)
        if not old:
            previous = groups.setdefault(start, row)
            if previous['native_hex'] != row['native_hex']:
                raise ValueError('Additional divergent alias requires context')
        writes.append(('extra_ui_pointer_%06x' % at, at, japanese[at:at+4]))
    ordered = sorted(groups.values(), key=lambda r: r['start'])
    for left, right in zip(ordered, ordered[1:]):
        if left['start'] + left['slot_capacity'] > right['start']:
            raise ValueError('Additional stream slot overlap')
    payloads = [[bytes.fromhex(r['native_hex'])] for r in ordered]
    book, fit = fit_parts_book(payloads, 'compact', [r['slot_capacity'] for r in ordered], 256)
    if fit['best_overflow_count']:
        raise ValueError('Additional UI stream exceeds original slot')
    for row in ordered:
        encoded = encode_parts([bytes.fromhex(row['native_hex'])], 'compact', book)
        actual, used = decode_parts(encoded, book, 288, 1, 1)
        if sha(actual) != row['output_sha256'] or used != len(encoded):
            raise ValueError('Additional native output differs')
        row['encoded_length'] = len(encoded)
        writes.append(('extra_ui_stream_%06x' % row['start'], row['start'], encoded))
    packed = pack_tree(book)
    bounds = pack_bounds24([(0x08000000+r['start'], r['slot_capacity']) for r in ordered])
    report = dict(format='ADDITIONAL_UI_GLYPH_TREE_V2', historical_bindings=len(historical),
                  extra_bindings=len(rows), extra_unique_starts=len({r['start'] for r in rows}),
                  new_streams=len(ordered),
                  historical_stream_bindings=sum(r['existing_binding'] is not None for r in rows),
                  additional_shared_bindings=sum(r['existing_binding'] is None for r in rows)-len(ordered),
                  max_output=max(len(p[0])+1 for p in payloads),
                  book_sha256=sha(packed), bounds_sha256=sha(bounds), fit=fit, rows=rows)
    return writes, packed, bounds, report
