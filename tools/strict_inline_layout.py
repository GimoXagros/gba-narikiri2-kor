"""Storage-only inline alternatives. Runtime selector/RAM integration is open."""
from collections import defaultdict
from dataclasses import replace

from strict_unit_codec import factor_variants, fit_parts_book, encode_parts, decode_parts


def encode_inline(rows, payloads):
    if not rows or len(rows) != len(payloads):
        raise ValueError('Missing inline payload/binding denominator')
    groups = {}
    for row, raw in zip(rows, payloads):
        start = int(row['jp_text_start'])
        group = groups.setdefault(start, dict(kind=str(row['category']),
                 capacity=int(row['slot_capacity']), members=[]))
        if group['kind'] != row['category'] or group['capacity'] != int(row['slot_capacity']):
            raise ValueError('Inconsistent shared slot or category')
        group['members'].append((int(row['jp_pointer_storage']), raw))
    # Variant order is explicitly anchored in original pointer storage order.
    for group in groups.values():
        group['raws'] = list(dict.fromkeys(raw for _, raw in sorted(group['members'])))
        group['parts'] = factor_variants(group['raws'], group['kind'])
    books, fits = {}, {}
    for kind in sorted({g['kind'] for g in groups.values()}):
        selected = [g for g in groups.values() if g['kind'] == kind]
        books[kind], fits[kind] = fit_parts_book([g['parts'] for g in selected],kind,
                                                [g['capacity'] for g in selected],128)
        for group in selected:
            group['stream'] = encode_parts(group['parts'],kind,books[kind])
    streams, selections = [], []
    for row, raw in zip(rows, payloads):
        group = groups[int(row['jp_text_start'])]
        count = len(group['parts'])
        selection = 1 if count == 1 else (11,13)[group['raws'].index(raw)]
        output, used = decode_parts(group['stream'],books[group['kind']],len(raw)+1,count,selection)
        if output != raw+b'\0' or used != len(group['stream']):
            raise ValueError('Inline template reconstruction mismatch')
        streams.append(group['stream'])
        selections.append(dict(inline_part_count=count,inline_selection=selection,
                               selector_status='UNPROVED_GAME_USE_SITE' if count==4 else 'SINGLE_TEMPLATE'))
    return streams, books, selections, fits


def assemble_inline_slots(jp, bindings, streams, books, details):
    """Verify *both* alternatives in physical shared slots, without a game hook.

    The fixed writer validates one common physical representation per start.
    Its expected group output includes every distinct template, with NULs,
    rather than silently choosing one alias. Text pointers remain unchanged.
    """
    from build_jp8mib_strict import assemble_text_slots
    if not bindings or len(bindings) != len(streams) or len(bindings) != len(details):
        raise ValueError('Missing inline stream/context denominator')
    groups = defaultdict(list)
    for binding, detail in zip(bindings, details):
        groups[binding.start].append((binding, detail))
    expected, selected = {}, {}
    for start, members in groups.items():
        variants = {}
        for binding, detail in sorted(members, key=lambda pair:pair[0].storage):
            variants.setdefault(binding.expected_output, detail)
        expected[start] = b''.join(variants)
        selected[start] = list(variants.values())
    physical = [replace(b, expected_output=expected[b.start]) for b in bindings]
    def decoder(image,start,end,capacity):
        outputs=[]
        for detail in selected[start]:
            value,_=decode_parts(image[start:end],books[detail['category']],capacity,
                detail['inline_part_count'],detail['inline_selection'],allow_suffix=True)
            outputs.append(value)
        return b''.join(outputs)
    return assemble_text_slots(jp,physical,streams,'INLINE_GLYPH_STORAGE_EXPERIMENT',decoder)
