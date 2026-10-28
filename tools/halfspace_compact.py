"""Guarded compact compositors for fixed lists and immutable normal UI sources.

Only singleton interior wordspaces advance4px; glyphs retain their native8px
shape and complete labels return to the8px grid. Saved names and guarded
alignment/debug/unsupported contexts keep the original renderer.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path

from audit_halfspace import BASE, classify
from strict_packed_tree import unpack_tree
from strict_unit_codec import decode_parts, units

ROOT = Path(__file__).resolve().parents[1]
LINK_SHA = '82b143f8f7328a45a3a9af41d8284d6362dcda5003be6851a93095e0ce2260ee'
CORPUS_SHA = 'b1ccdd128a6b75917f0b7f010c6a1e2d032c01c7cf9844320a2e5f4aea8e4ad1'
COMPONENTS_SHA = '5d45d6a100b95cff594c66c1308ac983198994de5a0c33f922f99cb81e3b9468'
DRAW, DRAW_END = 0x2264, 0x23b8
DISPATCH, DISPATCH_END = 0x1438, 0x14e0
VALIDATE, VALIDATE_END = 0x34eae6, 0x34eafa
VARARGS_STUB, VARARGS_STUB_END = 0xcab4c, 0xcab58
BATCH_OWNERS = {'lookup': (0x3631c4, 0x363264), 'allocate': (0x35d23c, 0x35d2c6),
                'init': (0x36eb30, 0x36ebc2), 'mark': (0x34eac0, 0x34eae6),
                'wrap': (0x34eafa, 0x34eb10), 'getter': (0x36fd24, 0x36fd88)}
C_GATE, C_GATE_END = 0x3ad818, 0x3ad840
CONVERTER_SHA = 'c2e2b5434cb166aa3eb0bf7edc0b26a38637e82d77bd257206d4eb9bf296012b'
KEYBOARD = {'EXTRA_UI:'+address for address in ('003A7A70', '003A7A74', '003A7A78', '003A7A88', '003A7A8C', '003A7A90', '003A7AA0', '003A7AA4', '003A7AA8')}
CALLERS = {'ITEM_': ['080117A5'], 'JOB_': ['0800FED5', '0800F4C9'],
           'MONSTER_': ['08019155', '0800F54B'], 'ARTE_': ['080140F5']}


def normal_marker_sources():
    """Keep the complete approved marker validation across two bounded owners."""
    source = (ROOT/'asm/halfspace_compact_consumers_mark.s').read_text(encoding='utf-8')
    if hashlib.sha256(source.encode('utf-8')).hexdigest() != 'cf6a1d9d86d077966a8636f7e99ccd323fe92e6f8466f0f6d466e5756519fa34':
        raise ValueError('Approved compact marker source differs')
    boundary = '    movs r2,#0\nmark:'
    if source.count(boundary) != 1:
        raise ValueError('Compact marker split boundary differs')
    validate, marking = source.split(boundary)
    validate += '''    ldr r3,mark_loop
    bx r3
bad:
    movs r0,#0
    pop {r4-r6}
    pop {r3}
    bx r3
    .balign 4,0
mark_loop: .word MARK_LOOP
'''
    marking = boundary+marking
    marking = marking.replace('bad:\n    movs r0,#0\n    b done\n', '')
    return {'marker_validate': validate, 'marker_loop': marking}


NORMAL_NAMES = ('draw', 'loop', 'glyph', 'emit', 'flush', 'space', 'control', 'wrap', 'store', 'validate',
                'prepare', 'has_format', 'render_gate', 'small', 'simple', 'simple_finish',
                'format', 'format_finish', 'format_prepare', 'format_has_string', 'argument',
                'copy_argument', 'native_format', 'format_leave', 'prompt', 'format_gate', 'label_draw', 'plain_label')


def normal_overlay(image, baseline, link, corpus, components):
    """Add source-aware consumers only to the independently frozen H3 image."""
    from build_halfspace_prototype import assemble
    from halfspace_retired_owners import manifest, checked_writes
    from halfspace_compact_consumers import NUMERIC_COLUMNS
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_ARM
    if hashlib.sha256(image).hexdigest() != 'e149505b0ae1c6faec86acc5fdeefd86c44e31c486004e4e6ce3070831ac6982':
        raise ValueError('Normal consumer stage requires exact H3')
    if image[0x2c49a4:0x2c49b0] != b'%5g\0%4d\0%2d\0':
        raise ValueError('Numeric fast-path immutable templates differ')
    if (image[0x2c4c64:0x2c4c70] != b' \0\0\0%6g\0%7g\0' or
            image[0x2c3e40:0x2c3e54] != b'00%1d\0\0\x000%2d\0\0\0\0%3d\0'):
        raise ValueError('Costume native padding templates differ')
    segments=accepted_segments(baseline,link)
    if len(corpus['rows'])!=10371:raise ValueError('Normal source population differs')
    rows=compact_rows(baseline,corpus,link,components)
    exclusions={0x082b95bc,0x082bd510,0x082c7810,0x082c78b8}
    exclusions|={0x08000000+int(r['original_start'],16) for r,_ in rows if r['binding_id'] in KEYBOARD}
    # Known templates have at most three numeric arguments or one first-position string.
    for row,tokens in rows:
        raw=b''.join(tokens)
        if b'%s' in raw and (raw.count(b'%s')!=1 or raw[:raw.find(b'%s')].replace(b'%l',b'').find(b'%')!=-1):
            raise ValueError('Unproved string argument position')
        if len(raw)+1>64:raise ValueError('Prepared template capacity exceeded')
    source={ 'normal_'+name:(ROOT/('asm/halfspace_compact_normal_'+name+'.s')).read_text(encoding='utf8') for name in NORMAL_NAMES}
    for name in ('source_gate','source_lookup','numeric_policy','pair'):
        source[name]=(ROOT/('asm/halfspace_compact_'+name+'.s')).read_text(encoding='utf8')
    source.update(normal_marker_sources())
    source['scan_thumb_copy']=(ROOT/'asm/halfspace_compact_scan_thumb_copy.s').read_text(encoding='utf8')
    symbols={'normal_'+name:'NORMAL_'+name.upper() for name in NORMAL_NAMES}
    symbols.update(source_gate='SOURCE_GATE',source_lookup='COMPACT_SOURCE_LOOKUP',numeric_policy='NUMERIC_COPY',
                   pair='NORMAL_PAIR',marker_validate='MARK_COPY',marker_loop='MARK_LOOP')
    symbols.update(scan_thumb_copy='SCAN_COPY',scan_thumb='SCAN_THUMB')
    values={'BATCH_INIT':0x08000000+BATCH_OWNERS['init'][0],'BATCH_LOOKUP':0x08000000+BATCH_OWNERS['lookup'][0],
            'BATCH_WRAP':0x08000000+BATCH_OWNERS['wrap'][0],'SOURCE_EXCLUSION_COUNT':len(exclusions),
            'COMPACT_FONT':0x08000000+segments['clear_font']['new'],'DIAGNOSTIC_STOP':0x080b9de4}
    lo,hi=BATCH_OWNERS['allocate']
    calls=[i.address+5 for i in Cs(CS_ARCH_ARM,CS_MODE_THUMB).disasm(image[lo:hi],0x08000000+lo)
           if i.mnemonic=='bl' and int(i.op_str.lstrip('#'),0)==0x080c5d4a]
    if len(calls)!=2:raise ValueError('Batch scan caller proof differs')
    values.update(SCAN_CALL1=calls[0],SCAN_CALL2=calls[1])
    payloads={'exclusions':b''.join(struct.pack('<I',x) for x in sorted(exclusions)),
              'numeric_table':b''.join(struct.pack('<IBBxx',*x) for x in NUMERIC_COLUMNS.values())}
    policies=list(NUMERIC_COLUMNS.values())
    if policies[0][0]!=min(x[0] for x in policies) or policies[-1][0]!=max(x[0] for x in policies):
        raise ValueError('Numeric policy bounds differ')
    native=bytearray(image[0xc5d4a:0xc5dac])
    for offset in (48,78):
        if native[offset:offset+2]!=bytes.fromhex('6b44'):raise ValueError('Native bitmap SP address differs')
        native[offset:offset+2]=assemble('add r3,r4',0)
    # The copied 98-byte scanner ends in BX LR; these two alignment bytes
    # are unreachable data, retained for exact frozen candidate identity.
    payloads['scan_thumb']=bytes(native)+bytes.fromhex('00bf')
    symbols.update(exclusions='SOURCE_EXCLUSIONS',numeric_table='NUMERIC_POLICY')
    placeholder=dict(values,**{symbol:0x08350000+(1 if symbol=='MARK_LOOP' else 0) for symbol in symbols.values()})
    def compile_text(text,at,refs):
        for key,value in sorted(refs.items(),key=lambda x:-len(x[0])):text=text.replace(key,hex(value))
        return assemble(text,at)
    sizes={name:len(compile_text(text,0x350000,placeholder)) for name,text in source.items()}
    sizes.update({name:len(data) for name,data in payloads.items()})
    owners=manifest()['owners'][5:]
    free=[]
    for o in owners:
        lo,hi=o['reclaim_start'],o['reclaim_end']
        if (hashlib.sha256(image[o['start']:lo]).hexdigest()!=o['prefix_sha256'] or
                hashlib.sha256(image[lo:hi]).hexdigest()!=o['suffix_before_sha256']):raise ValueError('New suffix preimage changed')
        free.append([lo,hi&~1])
    positions={}
    for name,size in sorted(sizes.items(),key=lambda x:(-x[1],x[0])):
        matches=[(hi-((lo+3)&~3)-size,n,(lo+3)&~3) for n,(lo,hi) in enumerate(free) if ((lo+3)&~3)+size<=hi]
        if not matches:raise ValueError('No positively owned suffix fits '+name)
        _,n,at=min(matches);positions[name]=at;free[n][0]=at+size
        values[symbols[name]]=0x08000000+at+(1 if name=='marker_loop' else 0)
    result=bytearray(image);writes=[]
    def write(at,data,owner,retired=True):
        if retired and checked_writes([{'start':at,'end':at+len(data)}])!=[(at,at+len(data))]:raise ValueError('Owner bounds')
        if any(at<w['end'] and w['start']<at+len(data) for w in writes):raise ValueError('Normal writer overlap')
        writes.append(dict(start=at,end=at+len(data),owner=owner,before_sha256=hashlib.sha256(image[at:at+len(data)]).hexdigest(),after_sha256=hashlib.sha256(data).hexdigest()))
        result[at:at+len(data)]=data
    decoder=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
    for name,at in positions.items():
        refs=values
        assembly_at=at
        data=payloads[name] if name in payloads else compile_text(source[name],assembly_at,refs)
        if len(data)!=sizes[name]:raise ValueError('Alignment changed component extent '+name)
        if name in source:
            # Check each written BL against its literal source operand at final placement.
            text=source[name]
            for key,value in sorted(refs.items(),key=lambda x:-len(x[0])):text=text.replace(key,hex(value))
            expected=[int(line.strip()[3:],0) for line in text.splitlines() if line.strip().startswith('bl 0x')]
            active_decoder=decoder
            instructions=list(active_decoder.disasm(data,0x08000000+assembly_at))
            actual=[int(i.op_str.lstrip('#'),0) for i in instructions if i.mnemonic=='bl']
            if name=='scan_thumb_copy':
                if expected or len(actual)!=2 or any(not 0x08000000+at<=target<0x08000000+at+len(data) for target in actual):
                    raise ValueError('Scanner local Thumb call differs')
            elif actual!=expected:raise ValueError('Final Thumb BL target differs '+name)
        write(at,data,'normal_'+name)
    for at,symbol,expected in ((0x1acc,'NORMAL_SMALL',0x080b9f15),(0x1df4,'NORMAL_SIMPLE',0x080b9f71)):
        if struct.unpack_from('<I',image,at)[0]!=expected:raise ValueError('Native wrapper literal differs')
        write(at,struct.pack('<I',values[symbol]|1),'normal_hook_'+symbol,False)
    if image[0x1dbc:0x1dc4]!=bytes.fromhex('30b5051c0432054c'):raise ValueError('Native formatter prefix differs')
    write(0x1dbc,assemble('ldr r3,[pc,#0]\nbx r3\n.word '+hex(values['NORMAL_FORMAT_GATE']|1),0x1dbc),'normal_hook_formatter',False)
    # ARM7TDMI requires MOV r8,r8; assembler NOP emits an unsupported BF00 hint.
    for index, replacement in ((1,assemble('bl '+hex(values['SCAN_COPY']),values['SCAN_CALL1']-0x08000005)),
                                (2,assemble('mov r8,r8\nmov r8,r8',0))):
        if index==2 and replacement!=bytes.fromhex('c046c046'):
            raise ValueError('Private scanner skip must use ARMv4T instructions')
        at=values['SCAN_CALL'+str(index)]-0x08000005
        if image[at:at+4]!=assemble('bl 0x080c5d4a',at):raise ValueError('Private scan call preimage differs')
        write(at,replacement,'normal_private_scan_call'+str(index))
    if len(result)!=0x800000:raise ValueError('Normal overlay changed ROM size')
    return bytes(result),dict(status='NORMAL_CONSUMER_CANDIDATE_REQUIRES_RUNTIME_QA',writes=writes,
        symbols=values,source_lexical_candidates=488,column_compensation_markers=3,
        native_exceptions=['mutable_RAM_SAV_names','keyboard_alignment','hidden_SELECT16_capacity','unsupported_native_controls'],
        temporary_lifetime='stack-only: template64 argument64 output160; no pointer escapes')


def pair(pending: bytes, glyph: bytes, clear: int) -> tuple[bytes, bytes]:
    """Complete one tile at phase4 while retaining the next right half."""
    if len(pending) != 32 or len(glyph) != 32 or clear not in (0, 11):
        raise ValueError('Expected two 8x8 tiles and palette profile0/11')
    blank = bytes([clear * 17]) * 2
    complete = b''.join(pending[y:y+2] + glyph[y:y+2] for y in range(0, 32, 4))
    following = b''.join(glyph[y+2:y+4] + blank for y in range(0, 32, 4))
    return complete, following


def compose(tiles: list[bytes], advances: list[int], clear: int = 0):
    """Compose already-resolved glyphs without changing any glyph's 8px shape.

    A 4px entry must be a uniform clear tile. Padding/alignment spaces use8px.
    Returns completed tiles, exact pixel width and glyph start coordinates.
    """
    if len(tiles) != len(advances) or clear not in (0, 11):
        raise ValueError('Tile/advance count or palette mismatch')
    blank = bytes([clear * 17]) * 32
    output, pending, x, starts = [], None, 0, []
    for tile, advance in zip(tiles, advances):
        if len(tile) != 32 or advance not in (4, 8) or (advance == 4 and tile != blank):
            raise ValueError('Only a uniform word-space may advance4px')
        starts.append(x)
        if pending is None:
            if advance == 8:
                output.append(tile)
            else:
                pending = blank
        else:
            complete, pending = pair(pending, tile, clear)
            output.append(complete)
            if advance == 4:
                pending = None
        x += advance
    if pending is not None:
        output.append(pending)
    if len(output) != (x + 7) // 8:
        raise AssertionError('Tile count does not cover exact advance')
    return output, x, starts


def accepted_segments(image: bytes, link: dict) -> dict:
    if len(image) != 0x800000 or hashlib.sha256(image).hexdigest() != BASE:
        raise ValueError('Exact original 8MiB v1.1a baseline required')
    segments = {s['name']: s for s in link['layout']['segments']}
    # Resolve the live getter's literal, then require agreement with LINK.
    getter = segments['compact_get_tile']['new']
    font = struct.unpack_from('<I', image, getter + 0x5c)[0] - 0x08000000
    if font != segments['clear_font']['new']:
        raise ValueError('Live compact getter/font owner differs from accepted LINK')
    return segments


def repair_simple_trampoline(image: bytes, link: dict):
    """Bounded existing-owner repair; never overwrite the frozen baseline file."""
    segments = accepted_segments(image, link)
    segment = segments['simple_trampoline']
    at = segment['new'] + 8
    before, after = b'\x00\x4b\x18\x47', b'\x00\x4c\x20\x47'
    if segment['size'] != 16 or image[at:at+4] != before:
        raise ValueError('Current simple trampoline differs from verified4byte owner')
    result = bytearray(image)
    result[at:at+4] = after
    return bytes(result), {'start': at, 'end': at+4, 'before_hex': before.hex(),
        'after_hex': after.hex(), 'before_sha256': hashlib.sha256(before).hexdigest(),
        'owner': 'LINK.layout.simple_trampoline',
        'reason': 'Branch through saved scratchr4; retain native string pointer inr3'}


def cache_home_overlay(image: bytes, baseline: bytes, link: dict):
    """Content hints for composed tiles within the exact existing cache owner."""
    from build_halfspace_prototype import assemble
    segments = accepted_segments(baseline, link)
    cache = segments['tile_cache']
    at = cache['new']
    original = assemble((ROOT / 'asm/strict_perf_tile_first_home_prefilter_balanced.s').read_text(encoding='utf-8'), at)
    if len(original) != 680 or original != baseline[at:at+680] or image[at:at+680] != original:
        raise ValueError('Explicit current680byte cache assembler owner required')
    home, second, padding = at+0x204, at+0xfe, at+0x27a
    if (home, second, padding) != (0xc5dac, 0xc5ca6, 0xc5e22):
        raise ValueError('Fixed cache owner offsets changed')
    if hashlib.sha256(baseline[home:home+34]).hexdigest() != 'cea87c759b64d46e3733c9e1762ba6317041894eadd497a9f542d99e2eeebf06':
        raise ValueError('Cache get_home before hash')
    if baseline[padding:padding+6] != bytes.fromhex('c046c04600bf'):
        raise ValueError('Explicit assembler NOP padding changed')
    if struct.unpack_from('<I', baseline, at+0x280)[0] != 0x08000000+segments['clear_font']['new']:
        raise ValueError('Existing font literal moved')
    result, writes = bytearray(image), []
    changes = [(home, assemble((ROOT / 'asm/halfspace_compact_cache_home.s').read_text(encoding='utf-8'), home), 'cache_get_home34'),
               (second, assemble('bl 0x080c5e22', second), 'cache_second_home_reload_call'),
               (padding, assemble('ldr r1,[r4,#12]\nb 0x080c5dac', padding), 'cache_explicit_NOP_reload4')]
    if [len(data) for _, data, _ in changes] != [34, 4, 4]:
        raise ValueError('Cache fixed owner extents changed')
    for lo, data, name in changes:
        result[lo:lo+len(data)] = data
        writes.append({'start': lo, 'end': lo+len(data), 'owner': name,
                       'before_sha256': hashlib.sha256(image[lo:lo+len(data)]).hexdigest(),
                       'after_sha256': hashlib.sha256(data).hexdigest()})
    return bytes(result), writes


def compact_overlay(image: bytes, baseline: bytes, link: dict, corpus: dict, components: dict):
    """Apply the four proven compact families after full-runtime and C stages."""
    from build_halfspace_prototype import assemble
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    from halfspace_retired_owners import check_preimages, checked_writes
    segments = accepted_segments(baseline, link)
    retired = check_preimages(image)
    sources = []
    for row, tokens in compact_rows(baseline, corpus, link, components):
        if not row['binding_id'].startswith(('ITEM_', 'JOB_', 'MONSTER_', 'ARTE_')): continue
        if any(classify(tokens, n, visible_substitutions=False) != 'WORD_SEPARATOR' for n, t in enumerate(tokens) if t == b' '):
            raise ValueError('New source padding/control space requires a runtime policy review')
        if any((t[1]-1)*31+t[2]-1 >= 512 for t in tokens if len(t) == 3 and t[0] == 0x7f):
            raise ValueError('Registered private glyph outside preserved font')
        sources.append((row['binding_id'], tokens.count(b' ')))
    if len(sources) != 755:
        raise ValueError('Registered source classification denominator changed')
    from strict_relative_assets import read_resource
    c_native, c_used = read_resource(image, 0x3ad774)
    if (c_used != 146 or hashlib.sha256(c_native).hexdigest() != '8dc70118cb49132e8210b001918fccb17d59c477e98ced1f211226c1b00609ac'
            or image[0x1a3be:0x1a3c2] != bytes.fromhex('93f323fa')
            or hashlib.sha256(image[0x3ad774:C_GATE]).hexdigest() != 'bd1c35e2a53697a83819ee187b7fa92be8c3e4f03e1ea04d8c4e7069bc1fd64e'
            or hashlib.sha256(image[0x3ad808:C_GATE]).hexdigest() != 'd1b25bdb7a67a1d5bd99afb4e0b3dee12c247cd739f8e046f2717714fd148d25'
            or image[C_GATE_END:C_GATE_END+2] != bytes.fromhex('8100')):
        raise ValueError('Exact C stream/pixels/hook/helper must precede nested-tail use')
    # These exact immutable paths establish prefix widths and the next reset;
    # runtime still checks source identity, mode, palette and core wrap/clipping.
    callback_guards = [(0x1730, 0x1920), (0x4830, 0x48ba), (0xf48c, 0xf4d0),
                       (0xf500, 0xf550), (0xfe98, 0xff20), (0x11754, 0x117e4),
                       (0x12484, 0x124b8), (0x14080, 0x14104), (0x1911c, 0x19178)]
    for lo, hi in callback_guards:
        if image[lo:hi] != baseline[lo:hi]:
            raise ValueError('Proven compact caller/prefix/reset geometry changed: ' + hex(lo))
    irq_guards = [(0x104, 0x240), (0x4b0, 0x4e0), (0x41a4, 0x4234), (0x58b0, 0x58fc),
                  (0x5b5c, 0x5b64), (0x6310, 0x63ec)]
    if any(image[lo:hi] != baseline[lo:hi] for lo, hi in irq_guards):
        raise ValueError('Default IRQ sound/serial-only map-lifetime proof changed')
    if (image[0x1dbc:0x1ddc] != baseline[0x1dbc:0x1ddc]
            or hashlib.sha256(image[0xcaa10:VARARGS_STUB_END]).hexdigest() != '610198e54ae677c534546ff6b9ff9eb4a3389dda13a0d0459bfaae85b8fe573b'
            or image[VARARGS_STUB:VARARGS_STUB_END] != b'\xc0\x46'*6):
        raise ValueError('Exact native generic formatter/full-Z unused12byte tail required')
    cache = segments['tile_cache']
    if image[cache['new']:cache['end']] != baseline[cache['new']:cache['end']]:
        raise ValueError('Exact accepted native tile-cache owner changed')
    if len(image) != len(baseline) or hashlib.sha256(image[0x21fc:DRAW]).hexdigest() != CONVERTER_SHA:
        raise ValueError('Proven bitmap converter replacement must precede reclaimed-tail use')
    regions = [(DRAW, DRAW_END, '76dc57b2daae3b45f4a28081db8a7e1d8283fe73803e38ea6af188c78a466c96'),
               (DISPATCH, DISPATCH_END, 'dec34516db2c6f5783a6b1282137bf0c14e391f9bfce9727ac3c0d63f36697d5'),
               (C_GATE, C_GATE_END, 'df58ab54d5bb02e657be3adcfb4ac80984ce483dbb964dc6ebe080100d4c6cac')]
    for lo, hi, digest in regions:
        if hashlib.sha256(baseline[lo:hi]).hexdigest() != digest or image[lo:hi] != baseline[lo:hi]:
            raise ValueError('Compact allocation proof/before bytes differ')
    values = {'COMPACT_GET_TILE': 0x08000001 + segments['compact_get_tile']['new'],
              'COMPACT_FONT': 0x08000000 + segments['clear_font']['new'],
              'TILE_CACHE': 0x08000001 + segments['tile_cache']['new'],
              'DIAGNOSTIC_STOP': struct.unpack_from('<I', baseline, segments['small_wrapper']['new'] + 0x50)[0],
              'COMPACT_DRAW': 0x08000000 + DRAW,
              'VALIDATE_LABEL': 0x08000000 + VALIDATE,
              'FINISH_DISPATCH': 0x08000000 + DRAW + 288,
              'GET_TILE_DIRECT': 0x08000000 + BATCH_OWNERS['getter'][0],
              'CACHE_DIRECT': 0x08000000 + BATCH_OWNERS['lookup'][0],
              'BATCH_INIT': 0x08000000 + BATCH_OWNERS['init'][0],
              'WRAP_DIRECT': 0x08000000 + BATCH_OWNERS['wrap'][0],
              'MON_GATE': 0x08000000 + C_GATE}
    result, writes = bytearray(image), []

    def write(at, data, owner, *, retired_owner=False):
        if retired_owner:
            if checked_writes([{'start': at, 'end': at+len(data)}]) != [(at, at+len(data))]:
                raise ValueError('Unapproved retired text suffix extent')
        elif image[at:at+len(data)] != baseline[at:at+len(data)]:
            raise ValueError('Existing owner already differs: ' + owner)
        writes.append({'start': at, 'end': at+len(data), 'owner': owner,
                       'before_sha256': hashlib.sha256(image[at:at+len(data)]).hexdigest(),
                       'after_sha256': hashlib.sha256(data).hexdigest()})
        result[at:at+len(data)] = data

    for name, lo, hi, data_size in (('draw', DRAW, DRAW_END, 32),
                                    ('dispatch', DISPATCH, DISPATCH_END, 36),
                                    ('validate', VALIDATE, VALIDATE_END, 0),
                                    ('mon_gate', C_GATE, C_GATE_END, 8)):
        source = (ROOT / ('asm/halfspace_compact_' + name + '.s')).read_text(encoding='utf-8')
        for key, value in values.items(): source = source.replace(key, hex(value))
        code = assemble(source, lo)
        if len(code) > hi-lo:
            raise ValueError('Compact code exceeds proven owner: ' + name)
        if name == 'draw':
            if len(assemble(source.split('/* Fixed288byte')[0], lo)) != 288:
                raise ValueError('Internal validate helper entry moved')
            code_ranges = [(0, 268), (288, len(code))]
        else:
            code_ranges = [(0, len(code)-data_size)]
        for begin, end in code_ranges:
            for ins in Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(code[begin:end], 0x08000000 + lo + begin):
                if ins.size == 4 and ins.mnemonic != 'bl':
                    raise ValueError('Non-ARMv4T instruction: ' + str(ins))
        if name == 'draw':
            from collections import Counter
            targets = Counter(int(ins.op_str.lstrip('#'), 0)
                for begin, end in code_ranges
                for ins in Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(code[begin:end], 0x08000000+lo+begin)
                if ins.mnemonic == 'bl')
            expected = {values['WRAP_DIRECT']: 2, values['GET_TILE_DIRECT']: 1, values['CACHE_DIRECT']: 2, values['BATCH_INIT']: 1,
                        values['VALIDATE_LABEL']: 1, values['COMPACT_DRAW']: 1, 0x08001ac8: 1}
            if any(targets[address] != count for address, count in expected.items()):
                raise ValueError('Fixed Thumb BL targets changed during assembly/alignment')
        write(lo, code, 'coordinated_compact_' + name, retired_owner=name == 'validate')
    native = {'NATIVE_CACHE': 0x080c5ba8, 'NATIVE_COMPARE_REST': 0x080c5d0e,
              'NATIVE_DONE': 0x080c5cf4, 'NATIVE_MARK_LIVE': 0x080c5d4a,
              'NATIVE_SLOT_IS_LIVE': 0x080c5cfc, 'NATIVE_COPY_SETUP': 0x080c5cd2,
              'ALLOCATE': 0x08000000+BATCH_OWNERS['allocate'][0],
              'MARK_RETURNED': 0x08000000+BATCH_OWNERS['mark'][0],
              'BATCH_INIT': values['BATCH_INIT'],
              'BANKED_DECODER': struct.unpack_from('<I', baseline, segments['compact_get_tile']['new']+0x50)[0],
              'TILE_CACHE': 0x08000001+BATCH_OWNERS['lookup'][0],
              'CLEAR_FONT': 0x08000000+segments['clear_font']['new']}
    for name, (lo, hi) in BATCH_OWNERS.items():
        path = ROOT / ('asm/strict_compact_font_clear.s' if name == 'getter' else 'asm/halfspace_compact_batch_'+name+'.s')
        source = path.read_text(encoding='utf-8')
        for key, value in native.items(): source = source.replace(key, hex(value))
        code = assemble(source, lo)
        if len(code) > hi-lo:
            raise ValueError('Private batch helper exceeds exact retired owner: '+name)
        write(lo, code, 'private_batch_'+name, retired_owner=True)
    stub = assemble('push {r1-r3,lr}\nmov r2,sp\nbl 0x08001438\npop {r1-r3,pc}', VARARGS_STUB)
    if len(stub) != 10:
        raise ValueError('Private fixed-Thumb variadic stub extent changed')
    write(VARARGS_STUB, stub, 'full_Z_unused12byte_tail_private_variadic_stub10')
    for caller in (int(value, 16) for values in CALLERS.values() for value in values):
        at = caller-0x08000005
        if image[at:at+4] != assemble('bl 0x08001ddc', at):
            raise ValueError('Exact native six-caller BL preimage changed')
        write(at, assemble('bl '+hex(0x08000000+VARARGS_STUB), at), 'exact_compact_caller_'+hex(caller))
    repaired, repair = repair_simple_trampoline(baseline, link)
    write(repair['start'], repaired[repair['start']:repair['end']], repair['owner'])
    for lo, hi in ((0x14e0, 0x14e0+32), (0x23b8, 0x23b8+64)):
        if bytes(result[lo:hi]) != image[lo:hi]:
            raise AssertionError('Next native entry changed')
    if bytes(result[0x1dbc:0x1df0]) != image[0x1dbc:0x1df0] or bytes(result[VARARGS_STUB+10:VARARGS_STUB_END]) != image[VARARGS_STUB+10:VARARGS_STUB_END]:
        raise AssertionError('Generic interworking path or remaining full-Z padding changed')
    if read_resource(result, 0x3ad774) != (c_native, 146):
        raise AssertionError('Compact tail changed C native pixels or compressed consumption')
    return bytes(result), {'status': 'FOUR_PROVEN_COMPACT_FAMILIES_DISPLAY_ONLY',
        'writes': writes, 'converter_prerequisite_sha256': CONVERTER_SHA,
        'source_gate': 'O1 nativecallerregister proof: JOBrecordR4+FED5/F4C9; ITEMidR6+117A5; ARTEidR4+140F5; MONSTERentryR4+19155/F54B',
        'source_classification': {'bindings_checked': len(sources), 'wordspace_occurrences': sum(s[1] for s in sources), 'padding_control_run_exceptions': 0},
        'mode_gate': 'markmode1; paletteprofile0/11; source-bound callback geometry guarded by exact immutable bytes',
        'native_text_slots_dictionary_pointer_save_changes': 0,
        'cache_policy': 'Exact accepted native cache retained; experimental RAM content hints omitted after critical-path profile',
        'dispatch_scope': 'Only six exact fixed-Thumb BL callsites use private10byte variadic stub; generic1DBC/1DDC interworking bytes unchanged',
        'batch_lifetime': 'Stack-owned20byte conservative pin set; private getter keeps original decoder/font and marks every returned slot; actual wrapped XY changes reset; full set forces fresh scan; native generic cache unchanged',
        'batch_guards': 'IE2001/defaultIRQ/VBlank only sound+serial; guardedSoundInit finalmagic proves FIFO A0/A4 destinations; DMA0/3disabled, DMA1/2disabled or exactB600; otherwise native cache',
        'retired_suffix_owners': [{'binding': row['binding'], 'start': row['reclaim_start'], 'end': row['reclaim_end']} for row in retired],
        'irq_guards': [{'start': lo, 'end': hi, 'sha256': hashlib.sha256(baseline[lo:hi]).hexdigest()} for lo, hi in irq_guards],
        'end_cursor': 'ceil(pixel_width/8); nonlexical ITEMstatusicon boundary retains0or4pxCOLUMN_ALIGNMENT; quantity resetsright-3',
        'caller_guards': [{'start': lo, 'end': hi, 'sha256': hashlib.sha256(baseline[lo:hi]).hexdigest()} for lo, hi in callback_guards],
        'C_nested_owner': {'start': C_GATE, 'end': C_GATE_END, 'parent_resource': [0x3ad774, 0x3ad842], 'stream_consumed': 146, 'helper_end': C_GATE, 'native_pixels_preserved': True},
        'uncovered': 'SELECT16row, BATTLEdebug-like and mixed EXTRA/ASCII/UI callers remain native8px pending proofs'}


def compact_rows(image: bytes, corpus: dict, link: dict, components: dict):
    segments = accepted_segments(image, link)
    books = {}
    for kind in ('compact', 'extra'):
        s = segments[kind + '_book']
        books[kind] = unpack_tree(image[s['new']:s['new'] + s['size']])
    extra = {r['storage']: r for r in components['extra_ui']['rows']}
    result = []
    for row in corpus['rows']:
        if row['category'] != 'compact':
            continue
        storage = int(row['pointer_storage'], 16)
        start, cap = int(row['current_start'], 16), row['original_slot_bytes']
        if start != int(row['original_start'], 16) or struct.unpack_from('<I', image, storage)[0] != start + 0x08000000:
            raise ValueError('Original pointer/string start changed')
        kind = 'extra' if storage in extra and not extra[storage]['existing_binding'] else 'compact'
        selection = row['variant_selection']
        raw, used = decode_parts(image[start:start+cap], books[kind], 288,
                                 1 if selection == 1 else 4, selection, allow_suffix=True)
        if used > cap or hashlib.sha256(raw).hexdigest() != row['native_sha256']:
            raise ValueError('Native slot/variant mismatch: ' + row['binding_id'])
        result.append((row, units(raw[:-1], 'compact')))
    return result


def resolved_hangul(tokens: list[bytes], image: bytes, segments: dict, clear: int):
    """Only the live private complete-syllable bank and ASCII blank are proven."""
    font = segments['clear_font']
    output = []
    for token in tokens:
        if token == b' ':
            tile = bytes(32)
        elif len(token) == 3 and token[0] == 0x7f:
            index = (token[1] - 1) * 31 + token[2] - 1
            if index * 32 >= font['size']:
                raise ValueError('Private glyph outside current live font')
            at = font['new'] + index * 32
            tile = image[at:at+32]
        else:
            raise ValueError('Consumer marks/native ASCII font not proven')
        if clear:
            tile = bytes(b | 0xbb for b in tile)
        output.append(tile)
    return output


def proposed_advances(row: dict, tokens: list[bytes]):
    """Only registered item/job/monster label proposals; runtime gate is narrower."""
    allowed = row['category'] == 'compact' and row['binding_id'].startswith(('ITEM_', 'JOB_', 'MONSTER_', 'ARTE_'))
    return [4 if allowed and t == b' ' and classify(tokens, n, visible_substitutions=False) == 'WORD_SEPARATOR' else 8
            for n, t in enumerate(tokens)]


def cache_cpu(image: bytes, segments: dict, tiles: list[bytes], *, clear=0, battle=False,
              displayed: list[bytes] | None = None, display_clear=None):
    """Run the exact accepted cache, pinning each emitted tile immediately."""
    from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB
    from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    for at, size in ((0x08000000, 0x800000), (0x02000000, 0x40000),
                     (0x03000000, 0x8000), (0x06000000, 0x20000)):
        cpu.mem_map(at, size)
    cpu.mem_write(0x08000000, image)
    cpu.mem_write(0x0300004c, struct.pack('<III', 0x0600f800, 0x0600c000, 0))
    display_clear = clear if display_clear is None else display_clear
    cpu.mem_write(0x0300145a, bytes([display_clear]))
    cpu.mem_write(0x03000010, struct.pack('<H', 0x100 | int(battle)))
    entry = 0x08000000 + segments['tile_cache']['new']
    written = []

    def insert(tile, map_at, palette):
        cpu.mem_write(0x02001000, tile)
        cpu.reg_write(UC_ARM_REG_R0, 0x02001000)
        cpu.reg_write(UC_ARM_REG_SP, 0x03007e00)
        cpu.reg_write(UC_ARM_REG_LR, 0x02020001)
        cpu.emu_start(entry | 1, 0x02020000, count=20000)
        if cpu.reg_read(UC_ARM_REG_PC) != 0x02020000:
            raise AssertionError('Exact current cache did not return')
        slot = cpu.reg_read(UC_ARM_REG_R0)
        if slot == 0xffffffff:
            return None
        cpu.mem_write(map_at, struct.pack('<H', slot | palette << 12))
        return slot

    def check_lifetime():
        if any(bytes(cpu.mem_read(0x0600c000 + s*32, 32)) != t for s, t in written):
            raise AssertionError('Previously displayed/pending glyph pixels were evicted')
    for n, tile in enumerate(displayed or []):
        slot = insert(tile, 0x0600f800 + 2*n, display_clear)
        if slot is None:
            check_lifetime()
            return {'status': 'DISPLAYED_PROFILE_EXHAUSTED', 'inserted': n}
        written.append((slot, tile))
    cpu.mem_write(0x0300145a, bytes([clear]))
    for n, tile in enumerate(tiles):
        slot = insert(tile, 0x03000058 + 2*n, clear)
        if slot is None:
            check_lifetime()
            return {'status': 'EXHAUSTED', 'inserted': n, 'requested': len(tiles)}
        written.append((slot, tile))
        # Pixel verification after each later insertion detects live eviction.
        check_lifetime()
    return {'status': 'PASS', 'inserted': len(tiles), 'unique_tiles': len(set(tiles))}


def probe(image, corpus, link, components, row_count=6):
    segments = accepted_segments(image, link)
    rows, skipped = [], []
    for row, tokens in compact_rows(image, corpus, link, components):
        # These fixed tables have the actual native compact consumer fixture;
        # dynamic templates, keyboard rows and saved-name fields stay excluded.
        if not row['binding_id'].startswith(('ITEM_', 'JOB_', 'MONSTER_')):
            continue
        try:
            glyphs = resolved_hangul(tokens, image, segments, 0)
        except ValueError:
            skipped.append(row['binding_id'])
            continue
        advances = proposed_advances(row, tokens)
        composed, width, starts = compose(glyphs, advances)
        rows.append({'binding_id': row['binding_id'], 'text': row['Korean_actual_output'],
                     'tokens': tokens, 'source': glyphs, 'composed': composed,
                     'width': width, 'starts': starts,
                     'spaces': sum(a == 4 for a in advances)})
    windows = []
    for kind in ('ITEM_', 'JOB_', 'MONSTER_'):
        group = [r for r in rows if r['binding_id'].startswith(kind)]
        for n in range(max(0, len(group) - row_count + 1)):
            current = group[n:n+row_count]
            previous = group[max(0, n-row_count):n]
            tiles = [t for r in current for t in r['composed']]
            originals = [t for r in current for t in r['source'] if t != bytes(32)]
            prior = [t for r in previous for t in r['composed']]
            prior_originals = [t for r in previous for t in r['source'] if t != bytes(32)]
            windows.append({'bindings': [r['binding_id'] for r in current],
                            'unique_original_glyphs': len(set(originals)),
                            'original_pending_display_union': len(set(originals + prior_originals)),
                            'unique_composed_tiles': len(set(tiles)),
                            'pending_display_union': len(set(tiles + prior)),
                            'tiles': tiles, 'displayed': prior})
    worst = max(windows, key=lambda w: w['unique_composed_tiles'])
    pending = max(windows, key=lambda w: w['pending_display_union'])
    profiles = []
    for clear in (0, 11):
        for battle in (False, True):
            transform = lambda ts: [bytes(b | 0xbb for b in t) for t in ts] if clear else ts
            profiles.append({'palette': clear, 'battle': battle,
                'current_page': cache_cpu(image, segments, transform(worst['tiles']), clear=clear, battle=battle),
                'pending_and_display': cache_cpu(image, segments, transform(pending['tiles']),
                    clear=clear, battle=battle, displayed=transform(pending['displayed']))})
    public = lambda w: {k: v for k, v in w.items() if k not in ('tiles', 'displayed')}
    return {'status': 'FEASIBILITY_ONLY_NO_ROM_WRITES', 'baseline_sha256': BASE,
            'resolved_consumers': {n: segments[n] for n in ('small_wrapper', 'simple_wrapper', 'compact_get_tile', 'tile_cache', 'clear_font')},
            'probed_rows': len(rows), 'unsupported_native_rows': skipped,
            'wordspace_occurrences_in_probe': sum(r['spaces'] for r in rows),
            'fixture_row_count': row_count,
            'worst_current_rows': public(worst), 'worst_pending_display': public(pending),
            'exact_current_cache_fixtures': profiles,
            'limitations': ['Native consumer hooks, ownership/allocation and descriptor halfphase NOT integrated',
                           'Row windows are corpus-order stress fixtures, not natural play evidence',
                           'Other compact consumers, keyboard alignment, saved names remain unchanged',
                           'No ROM/text/pointer/save bytes changed; natural offscreen/hardware NOT_RUN']}, rows


def coverage(baseline, corpus, link, components, output_sha, normal_report=None):
    """Export source occurrences separately from their exact verified callers."""
    from collections import Counter
    from strict_default_names import unpack_name
    segments = accepted_segments(baseline, link)
    source = {r['binding_id']: t for r, t in compact_rows(baseline, corpus, link, components)}
    extra = {r['storage']: r for r in components['extra_ui']['rows']}
    books = {k: unpack_tree(baseline[segments[k+'_book']['new']:segments[k+'_book']['end']]) for k in ('compact', 'extra')}
    export, occurrences = [], []
    for row in corpus['rows']:
        category, binding = row['category'], row['binding_id']
        if category not in ('compact', 'keyboard_glyph_row', 'fixed_name'): continue
        if binding not in source:
            lo, cap = int(row['current_start'], 16), row['original_slot_bytes']
            if category == 'fixed_name':
                raw = unpack_name(baseline[lo:lo+cap], (row['native_bytes']-1)//3)
            else:
                storage = int(row['pointer_storage'], 16)
                kind = 'extra' if storage in extra and not extra[storage]['existing_binding'] else 'compact'
                selection = row['variant_selection']
                raw, _ = decode_parts(baseline[lo:lo+cap], books[kind], 288, 1 if selection == 1 else 4, selection, allow_suffix=True)
            if hashlib.sha256(raw).hexdigest() != row['native_sha256']:
                raise ValueError('Coverage source hash mismatch')
            source[binding] = units(raw[:-1], 'compact')
        tokens = source[binding]
        spaces = [n for n, t in enumerate(tokens) if t == b' ']
        callers = next((v for k, v in CALLERS.items() if binding.startswith(k)), [])
        fallback = any(t != b' ' and not (len(t) == 3 and t[0] == 0x7f) for t in tokens)
        if category == 'fixed_name':
            status, reason, callers = 'PRESERVED_FIXED_SAVED_NAME', 'SAV IDs/names/field padding unchanged; RAM/SAV source never enabled', []
        elif binding in KEYBOARD:
            status, reason, callers = 'PRESERVED_KEYBOARD_ALIGNMENT', 'Nine source-defined keyboard glyph/command rows retain8px grid and original IDs/padding', []
        elif callers and fallback:
            status, reason, callers = 'ASCII_SOURCE_FALLBACK', 'Six mixed/native ASCII labels remain with original renderer', []
        elif callers:
            status, reason = 'CONVERTED_EXACT_CALLERS_ONLY', 'Other callers retain8px; complete label end cursor rounds to8px grid'
            if binding.startswith('ITEM_') and baseline[int(row['pointer_storage'], 16)+6] & 8:
                reason += '; status-icon control%5g boundary is explicit nonlexical COLUMN_ALIGNMENT0or4px; quantity resetsright-3'
        elif not spaces:
            status, reason = 'NO_SPACE_UNCHANGED', 'No native space occurrences'
        else:
            purposes = {classify(tokens, n, visible_substitutions=False) for n in spaces}
            status = 'UNRESOLVED_NATIVE8' if 'WORD_SEPARATOR' in purposes else 'PRESERVED_PENDING_CONTEXT'
            reason = 'Actual consumer/geometry remains pending; ordinary UI is not excluded; source purposes='+','.join(sorted(purposes))
        advance = 4 if callers else 8
        physical = len(tokens)*8 - len(spaces)*(8-advance)
        export.append({'binding_id': binding, 'native_spaces': len(spaces), 'selected_callers': callers,
                       'word_space_px4_or8': advance, 'tail_alignment_px0_or4': (-physical) % 8 if callers else 0,
                       'status': status, 'exception_reason': reason})
        for index in spaces:
            occurrences.append({'binding_id': binding, 'native_space_index': index,
                'source_sha256': row['native_sha256'], 'selected_callers': ';'.join(callers),
                'word_space_px4_or8': advance,
                'purpose': 'KEYBOARD_ALIGNMENT' if binding in KEYBOARD else classify(tokens, index, visible_substitutions=False),
                'status': status, 'exception_reason': reason})
    if len(export) != 1424 or len(occurrences) != 683:
        raise ValueError('Compact coverage denominator changed')
    report = {'candidate_rom_sha256': output_sha, 'bindings': len(export), 'space_occurrences': len(occurrences),
              'converted_space_occurrences_in_listed_callers': sum(r['word_space_px4_or8'] == 4 for r in occurrences),
              'status_counts': dict(Counter(r['status'] for r in occurrences)), 'rows': export,
              'scope': 'Only six verified caller contexts in ITEM/JOB/MONSTER/ARTE; ordinary unresolved UI remains native8px',
              'cursor_contract': 'Interior word separators4px; complete field end rounds0or4px to native8px grid; no4px cross-call cursor claim',
              'not_run': ['Physical hardware', 'Unlisted compact consumers', 'Natural acquisition of RAM catalog fixtures']}
    if normal_report is not None:
        from halfspace_compact_consumers import lexical_offsets, prepared_copy, NUMERIC_COLUMNS
        if normal_report.get('status')!='NORMAL_CONSUMER_CANDIDATE_REQUIRES_RUNTIME_QA':
            raise ValueError('Installed normal consumer report required')
        hidden=set()
        for table,count,stride in ((0x2c7b60,13,8),(0x3ae8e0,4,4),(0x3ae92c,3,4),(0x3ae93c,5,4)):
            hidden|={struct.unpack_from('<I',baseline,table+n*stride)[0] for n in range(count)}
        native={r['binding_id']:(r,t) for r,t in compact_rows(baseline,corpus,link,components)}
        exports={r['binding_id']:r for r in export}
        for binding,(row,tokens) in native.items():
            record=exports[binding];original=0x08000000+int(row['original_start'],16)
            raw=b''.join(tokens)+b'\0';off=lexical_offsets(binding,tokens)
            numeric=NUMERIC_COLUMNS.get(binding)
            if numeric:off=[x for x in off if x!=numeric[1]]
            hidden_row=binding.startswith(('SELECT_','BATTLE_COMMAND_')) or original in hidden
            preserve=binding in KEYBOARD or hidden_row or original in {0x082b95bc,0x082bd510,0x082c7810,0x082c78b8}
            if preserve:
                if hidden_row:
                    record.update(status='PRESERVED_HIDDEN_DEBUG_NATIVE8',word_space_px4_or8=8,selected_callers=[],tail_alignment_px0_or4=0,
                                  exception_reason='Hidden debug owned-heap/SELECT16 context retains native spacing; actual battle64-slot capacity cannot hold worst67 composed tiles')
                continue
            if off:
                record.update(status='CONVERTED_IMMUTABLE_NORMAL_CONTEXTS',word_space_px4_or8=4,
                              selected_callers=['08001AC8 immutable/actor-ROM','08001DF0 immutable source','08001DBC immutable template/ROM argument'],
                              exception_reason='Source-gated private-copy rendering; mutable RAM/SAV, unsupported controls and nonstandard geometry retain native fallback; rounded final tile')
                transformed=prepared_copy(binding,raw,original)
                ts=units(transformed[:-1],'compact');width=sum(4 if t==b'\x1f' else 8 for t in ts)
                record['tail_alignment_px0_or4']=(-width)%8
            elif numeric:
                record.update(status='PRESERVED_NUMERIC_COLUMN',word_space_px4_or8=8,selected_callers=[],tail_alignment_px0_or4=0,
                              exception_reason='Fixed-width numeric field separator remains8px and digit anchor unchanged')
            elif record['native_spaces']:
                record.update(status='PRESERVED_COLUMN_ALIGNMENT',word_space_px4_or8=8,selected_callers=[],tail_alignment_px0_or4=0,
                              exception_reason='Leading/trailing or repeated source alignment spaces retain native grid')
            record['numeric_separator_byte_offset']=numeric[1] if numeric else None
            record['column_compensation_halfspaces']=numeric[2] if numeric else 0
            cursor=0;positions={}
            for n,t in enumerate(tokens):positions[n]=cursor;cursor+=len(t)
            for occurrence in (x for x in occurrences if x['binding_id']==binding):
                pos=positions[occurrence['native_space_index']]
                occurrence.update(word_space_px4_or8=4 if pos in off else 8,status=record['status'],
                                  selected_callers=';'.join(record['selected_callers']),exception_reason=record['exception_reason'])
                if numeric and pos==numeric[1]:occurrence['purpose']='NUMERIC_COLUMN_ALIGNMENT'
        for occurrence in occurrences:
            row=exports[occurrence['binding_id']]
            if row['status']=='PRESERVED_HIDDEN_DEBUG_NATIVE8':
                occurrence.update(word_space_px4_or8=8,status=row['status'],selected_callers='',exception_reason=row['exception_reason'])
        report.update(converted_space_occurrences_in_listed_callers=sum(x['word_space_px4_or8']==4 for x in occurrences),
                      status_counts=dict(Counter(x['status'] for x in occurrences)),
                      scope='Installed immutable-source consumers plus preserved fixed/keyboard/numeric/debug cases; source census is not whole-game runtime proof',
                      normal_consumer_writes=len(normal_report['writes']),
                      not_run=['Physical hardware','Every gameplay scene/path','Natural acquisition of RAM catalog fixtures'])
    return report, occurrences


def main():
    p = argparse.ArgumentParser()
    old = ROOT.parent / 'narikiri2-v09d-graphics-test/private_validation'
    stage = old / 'v11-runtime-20261003/stage4-integrated-source-a-20261011'
    defaults = {'baseline': ROOT / 'private_validation/halfspace-graphics-20261025/runtime/BASE_v11a.gba',
                'corpus': old / 'kr-patch-qa-20261019/reviewed-dialogue-data.json',
                'link': stage / 'linked/LINK.json', 'components': stage / 'components/BUILD.json'}
    for name, default in defaults.items(): p.add_argument('--'+name, type=Path, default=default)
    p.add_argument('--input', type=Path, help='Already integrated full-runtime+C ROM; never a plain baseline')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--rows', type=int, choices=(6, 8), default=6)
    a = p.parse_args()
    for path, digest in ((a.link, LINK_SHA), (a.corpus, CORPUS_SHA), (a.components, COMPONENTS_SHA)):
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen private input mismatch: ' + str(path))
    base = a.baseline.read_bytes()
    corpus, link, components = (json.loads(path.read_text(encoding='utf-8')) for path in (a.corpus, a.link, a.components))
    if a.input:
        before = a.input.read_bytes()
        image, report = compact_overlay(before, base, link, corpus, components)
        allowed = bytearray(len(image))
        for w in report['writes']: allowed[w['start']:w['end']] = b'\1'*(w['end']-w['start'])
        if any(x != y and not allowed[n] for n, (x, y) in enumerate(zip(before, image))):
            raise ValueError('Unplanned compact writer')
        for row in corpus['rows']:
            storage, lo = int(row['pointer_storage'], 16), int(row['current_start'], 16)
            hi = lo+row['original_slot_bytes']
            if (image[storage:storage+4] != before[storage:storage+4]
                    or image[storage:storage+4] != base[storage:storage+4]):
                raise ValueError('Original pointer/encoded slot changed')
        from halfspace_retired_owners import check_text_slots
        retired_spans = check_text_slots(before, image, corpus, report['writes'])
        output_sha = hashlib.sha256(image).hexdigest()
        report.update(input_rom_sha256=hashlib.sha256(before).hexdigest(), candidate_rom_sha256=output_sha,
                      size=len(image), text_pointer_storage_value_start_bindings_preserved=10371,
                      all_native_slots_unchanged_from_input=not retired_spans,
                      live_native_streams_unchanged=True, retired_suffix_write_spans=retired_spans,
                      changed_bytes=sum(x != y for x, y in zip(before, image)),
                      space_render_status='PARTIAL_EXACT_CALLERS_ONLY', measured_perf_note='Earlier R prototypes had one extra cold-page display frame; final candidate requires independent actual-frame benchmark')
        cov, occurrences = coverage(base, corpus, link, components, output_sha)
        a.out.mkdir(parents=True, exist_ok=False)
        (a.out/'Xagros_Narikiri2_KOR_v1.1a_halfspace-graphics-test01.gba').write_bytes(image)
        (a.out/'COMPACT_WRITE_PLAN.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        (a.out/'COMPACT_COVERAGE_683.json').write_text(json.dumps(cov, indent=2)+'\n', encoding='utf-8')
        with (a.out/'COMPACT_COVERAGE_683.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(occurrences[0])); writer.writeheader(); writer.writerows(occurrences)
        print(json.dumps({'status': report['status'], 'candidate_rom_sha256': output_sha, 'size': len(image),
                          'declared_writers': len(report['writes']), 'covered_spaces': cov['converted_space_occurrences_in_listed_callers'],
                          'all_compact_spaces': 683, 'space_render_status': report['space_render_status']}))
        return
    report, rows = probe(base, corpus, link, components, a.rows)
    a.out.mkdir(parents=True, exist_ok=False)
    (a.out / 'COMPACT_FEASIBILITY.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (a.out / 'COMPACT_ROWS.json').write_text(json.dumps([{k: v for k, v in row.items() if k not in ('tokens', 'source', 'composed')} for row in rows], indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('resolved_consumers', 'unsupported_native_rows')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
