"""Origin-aware lexical space plans for the remaining compact consumers.

Only private decoded copies may receive markers. ROM strings, saved names,
formatter-generated padding and fixed keyboard/column spacing stay untouched.
This module does not yet install a runtime renderer or authorize a release.
"""
import hashlib

from audit_halfspace import classify
from halfspace_compact import KEYBOARD
from strict_unit_codec import units

MARKER = 0x1f

# Source separators before fixed-width numbers preserve their original column.
NUMERIC_COLUMNS = {
    'EXTRA_UI:00010DD4': (0x082c3d10, 6, 0),
    'EXTRA_UI:00012D64': (0x082c44e0, 16, 1),
    'EXTRA_UI:00012D7C': (0x082c44f8, 16, 1),
    'EXTRA_UI:0001465C': (0x082c4674, 16, 1),
    'EXTRA_UI:00016708': (0x082c49b0, 8, 0),
    'EXTRA_UI:00016710': (0x082c49c0, 8, 0),
    'EXTRA_UI:000176F4': (0x082c4be4, 8, 0),
    'EXTRA_UI:000176FC': (0x082c4bf4, 8, 0),
    'EXTRA_UI:00019564': (0x082c6038, 6, 0),
    'EXTRA_UI:000A51B0': (0x08373824, 9, 0),
    'EXTRA_UI:000A51B4': (0x08373834, 9, 0),
    'EXTRA_UI:000A51BC': (0x08373854, 9, 0),
}


def lexical_offsets(binding, tokens):
    """Offsets refer to decoded token boundaries, never compressed bytes."""
    if binding in KEYBOARD or binding.startswith('FIXED_NAME'):
        return []
    offset, selected = 0, []
    for index, token in enumerate(tokens):
        if token == b' ' and classify(tokens, index, visible_substitutions=True) == 'WORD_SEPARATOR':
            selected.append(offset)
        offset += len(token)
    return selected


def marked_copy(raw, offsets):
    """Fail closed on collisions, duplicate positions or non-space bytes."""
    if not raw or raw[-1] != 0 or 0 in raw[:-1]:
        raise ValueError('One complete native string required')
    tokens = units(raw[:-1], 'compact')
    if bytes([MARKER]) in tokens:
        raise ValueError('Reserved compact marker collides with source')
    boundaries, cursor = set(), 0
    for token in tokens:
        if token == b' ':
            boundaries.add(cursor)
        cursor += len(token)
    if offsets != sorted(set(offsets)):
        raise ValueError('Marker offsets must be unique and increasing')
    result = bytearray(raw)
    for offset in offsets:
        if type(offset) is not int or offset not in boundaries:
            raise ValueError('Marker must address a literal source space')
        result[offset] = MARKER
    restored = bytearray(result)
    for offset in offsets:
        restored[offset] = 0x20
    if bytes(restored) != raw:
        raise ValueError('Marker roundtrip differs')
    return bytes(result)


def prepared_copy(binding, raw, source):
    """Expected private formatter copy; never applied to saved names or ROM."""
    tokens = units(raw[:-1], 'compact')
    offsets = lexical_offsets(binding, tokens)
    result = marked_copy(raw, offsets)
    if binding not in NUMERIC_COLUMNS:
        return result
    address, separator, compensation = NUMERIC_COLUMNS[binding]
    if source != address or separator not in offsets or raw[separator+1:separator+2] != b'%':
        raise ValueError('Numeric column source or token identity differs')
    if len([offset for offset in offsets if offset < separator]) != compensation:
        raise ValueError('Numeric column compensation differs from lexical prefix')
    return result[:separator] + b' ' + bytes([MARKER])*compensation + result[separator+1:]


def source_plan(rows):
    """Bind each transient edit to exact source/variant/native identities."""
    result, identities = [], {}
    for row, tokens in rows:
        raw = b''.join(tokens)+b'\0'
        digest = hashlib.sha256(raw).hexdigest()
        if digest != row['native_sha256']:
            raise ValueError('Source native identity differs')
        offsets = lexical_offsets(row['binding_id'], tokens)
        key = (int(row['original_start'], 16), int(row['variant_selection']))
        marked = prepared_copy(row['binding_id'], raw, 0x08000000+key[0])
        numeric = NUMERIC_COLUMNS.get(row['binding_id'])
        if numeric:
            offsets = [offset for offset in offsets if offset != numeric[1]]
        identity = (digest, hashlib.sha256(marked).hexdigest())
        if key in identities and identities[key] != identity:
            raise ValueError('Shared source/variant has conflicting lexical policy')
        identities[key] = identity
        result.append(dict(binding_id=row['binding_id'], start=key[0], selection=key[1],
            native_sha256=digest, bytes=len(raw), marker_offsets=offsets,
            numeric_separator_offset=numeric[1] if numeric else None,
            column_compensation_markers=numeric[2] if numeric else 0,
            transient_bytes=len(marked), transient_sha256=identity[1],
            status='SOURCE_PLAN_ONLY_RUNTIME_NOT_IMPLEMENTED'))
    return result
