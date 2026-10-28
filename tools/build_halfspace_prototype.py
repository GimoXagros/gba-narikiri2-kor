"""Guarded full-window half-space prototype, never a release candidate.

The existing native space bytes and all text slots stay untouched. This first
prototype intentionally applies to every native full-window space; its audit
must not be mistaken for a reviewed exception-aware final implementation.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
from bps import create_bps, apply_bps

ROOT = Path(__file__).resolve().parents[1]
BASE = '8823db1cb72f1328136ccfd8fff1fbdca0c8489cbc7ccf90f7e4ecdbb1c37776'
JP = 'a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7'
DRAW, END = 0xCAA10, 0xCAB58
# The original even renderer is bypassed by the accepted LUT compositor. Its
# only literal caller is removed when that complete328byte owner is replaced.
HELPER, LIMIT = 0x11C8, 0x1350
EVENT_HELPER, EVENT_LIMIT = 0x1350, 0x1438
sha = lambda b: hashlib.sha256(b).hexdigest()

# Reviewed native replacements. Keep this independent of generated writer
# metadata: a larger assembler output must never grant itself more ownership.
REVIEWED_RUNTIME_SPANS = (
    (0xCAA10,0xCAB58),(0x11C8,0x1350),(0x1350,0x1438),
    (0x9AA0C,0x9AA14),
    (0x25164,0x2516C),(0x25208,0x25212),(0xB9584,0xB9588),
    (0x25192,0x25196),(0x21FC,0x2264),(0x1616,0x161A),
    (0x16B0,0x16B4),(0x1620,0x1626),(0x16BA,0x16C0),
    (0x152C,0x1534),(0x1710,0x1718),(0x107E,0x1082),
    (0x25D08,0x25DA8),
)


def validate_runtime_spans(writes):
    if len(writes)!=len(REVIEWED_RUNTIME_SPANS):raise ValueError('Runtime writer denominator changed')
    actual=[]
    for name,at,payload in writes:
        if not payload or not any(at==lo and at+len(payload)<=hi for lo,hi in REVIEWED_RUNTIME_SPANS):
            raise ValueError('Runtime writer exceeds reviewed native owner: '+name)
        actual.append((at,at+len(payload)))
    if len({a for a,b in actual})!=len(actual):raise ValueError('Duplicate runtime owner')
    if any(a<d and c<b for n,(a,b) in enumerate(actual) for c,d in actual[n+1:]):raise ValueError('Runtime owners overlap')


def assemble(source, at):
    return bytes(Ks(KS_ARCH_ARM, KS_MODE_THUMB).asm(source, addr=0x08000000+at)[0])


def helpers(*, selective=False):
    source = '''
draw:
    push {r3,r4,lr}
    ldr r3,window
    ldrb r4,[r3,#6]
    movs r3,#1
    ands r4,r3
    cmp r2,#0
    bne nonspace
    adds r4,#2
nonspace:
    ldr r3,window
    strb r4,[r3,#6]
    bl 0x080014e0
    pop {r3,r4,pc}
advance:
    ldr r1,window
    ldrb r0,[r1,#6]
    movs r2,#2
    tst r0,r2
    beq normal
    movs r2,#1
    ands r0,r2
    eors r0,r2
    strb r0,[r1,#6]
    cmp r0,#0
    bne advanced
normal:
    ldrb r0,[r1,#4]
    adds r0,#1
    strb r0,[r1,#4]
advanced:
    bx lr
wrap:
    push {r4,lr}
    mov r3,r4
    ldr r4,window
    ldrb r0,[r4,#4]
    ldrb r1,[r4,#2]
    cmp r0,r1
    blo return_wrap
    mov r1,r0
    movs r0,#0
    strb r0,[r4,#6]
    ldr r3,native_wrap
    bx r3
return_wrap:
    pop {r4,pc}
reset:
    ldr r3,window
    movs r2,#0
    strb r2,[r3,#6]
    ldrb r2,[r3]
    adds r2,r2,r0
    strb r2,[r3,#4]
    ldrb r0,[r3,#1]
    adds r0,r0,r1
    strb r0,[r3,#5]
    bx lr
clear:
    strb r1,[r0,#4]
    strb r2,[r0,#5]
    strb r2,[r0,#6]
    bx lr
    .balign 4,0
window: .word 0x03000040
native_wrap: .word 0x08001535
entry_table: .word draw,advance,wrap,reset,clear
'''
    if selective:
        source=source.replace('cmp r2,#0\n    bne nonspace\n    adds r4,#2','movs r3,#192\n    negs r3,r3\n    cmp r2,r3\n    bne nonspace\n    movs r2,#0\n    adds r4,#2')
        source=source.replace('cmp r0,r1\n    blo return_wrap\n    mov r1,r0','''cmp r0,r1
    bhs do_wrap
    ldrb r2,[r4,#6]
    lsls r2,r2,#31
    bpl return_wrap
    adds r0,#1
    cmp r0,r1
    blo return_wrap
    ldrb r0,[r3]
    cmp r0,#128
    bne do_wrap
    ldrb r0,[r3,#1]
    cmp r0,#64
    beq return_wrap
do_wrap:
    ldrb r1,[r4,#2]''')
    source=source.replace('entry_table: .word draw,advance,wrap,reset,clear',
        (ROOT/'asm/halfspace_aligned_fast.s').read_text(encoding='utf-8')+'\n'+
        (ROOT/'asm/halfspace_sprite_postprocess.s').read_text(encoding='utf-8')+
        '\nentry_table: .word draw,advance,wrap,reset,clear,halfspace_aligned_fast,sprite_postprocess,sprite_old_post_load')
    probe=assemble(source.replace('SHARED_POST_OFFSET','0'),HELPER)
    load_site=struct.unpack('<I',probe[-4:])[0]
    offset=0x08001434-((load_site+4)&~3)
    if not 0<=offset<=1020 or offset%4:raise ValueError('Postprocess literal no longer Thumb1-reachable')
    code = assemble(source.replace('SHARED_POST_OFFSET',str(offset)), HELPER)
    # Keystone resolves these exact labels. Never infer an entry from the
    # first instruction mnemonic: wrap also contains a PC-relative r3 load.
    entries={name:at-0x08000000 for name,at in zip(('draw','advance','wrap','reset','clear','aligned_fast','sprite_postprocess','sprite_old_post_load'),struct.unpack('<8I',code[-32:]))}
    if entries['draw']!=HELPER or any(at&1 or not HELPER<=at<HELPER+len(code)-32 for at in entries.values()):
        raise ValueError('Resolved helper entry table changed')
    return code[:-32], entries


def build(base, japanese, layout, *, selective=False):
    if len(base)!=0x800000 or sha(base)!=BASE or sha(japanese)!=JP:
        raise ValueError('Exact v1.1a and Japanese sources required')
    if base[HELPER:LIMIT]!=japanese[HELPER:LIMIT]:raise ValueError('Original even-renderer owner changed')
    from strict_runtime_trace import thumb_bl_xrefs
    if thumb_bl_xrefs(base,0x08000000+HELPER,end=len(base)):
        raise ValueError('Original even-renderer has a direct caller')
    needle=(0x08000001+HELPER).to_bytes(4,'little')
    hits=[i for i in range(len(base)-3) if base.startswith(needle,i)]
    if hits!=[0xCAB08]:raise ValueError('Original even-renderer literal callers changed')
    if base[EVENT_HELPER:EVENT_LIMIT]!=japanese[EVENT_HELPER:EVENT_LIMIT]:raise ValueError('Original odd-renderer owner changed')
    if thumb_bl_xrefs(base,0x08000000+EVENT_HELPER,end=len(base)):raise ValueError('Original odd-renderer direct caller')
    odd_needle=(0x08000001+EVENT_HELPER).to_bytes(4,'little')
    odd_hits=[i for i in range(len(base)-3) if base.startswith(odd_needle,i)]
    if odd_hits!=[0xCAB0C]:raise ValueError('Original odd-renderer literal callers changed')
    segments=layout['segments']
    if sha(json.dumps(segments,sort_keys=True,separators=(',',':')).encode('ascii'))!='a93613327898e83876d0a5561d0dabf5bf1d71221cde47f88b1f664b1aeea179':
        raise ValueError('Frozen canonical52 segment addresses changed')
    if len(segments)!=52 or any(s['new']<END and s['new']+s['size']>DRAW for s in segments):
        raise ValueError('Helper overlaps a protected segment')
    code,entries=helpers(selective=selective)
    draw_source=(ROOT/'asm/halfspace_full_draw.s').read_text(encoding='utf-8').replace('ALIGNED_FAST',str(0x08000001+entries['aligned_fast'])).replace('SHARED_LUT',str(0x08002244))
    draw_source=draw_source.replace('sprite_descriptor_entry_table: .word sprite_descriptor',(ROOT/'asm/halfspace_sprite_font.s').read_text(encoding='utf-8')+'\nentry_table: .word sprite_descriptor,sprite_font')
    draw = assemble(draw_source, DRAW)
    entries.update({name:at-0x08000000 for name,at in zip(('sprite_descriptor','sprite_font'),struct.unpack('<2I',draw[-8:]))})
    draw=draw[:-8]
    descriptor=entries['sprite_descriptor']-DRAW
    if base[0x374670:0x374674]!=b'\x0c\0\0\0' or draw[descriptor:descriptor+52]!=bytes(52):raise ValueError('Native text descriptor shape changed')
    draw=draw[:descriptor]+base[0x374670:0x3746A4]+draw[descriptor+52:]
    if len(draw)>END-DRAW or HELPER+len(code)>LIMIT:
        raise ValueError('Prototype code owner overflow')
    draw+=b'\xc0\x46'*((END-DRAW-len(draw))//2)
    writes=[('full_draw',DRAW,draw),('retired_native_even_helpers',HELPER,code)]
    sprite_source=(ROOT/'asm/halfspace_sprite.s').read_text(encoding='utf-8').replace('SPRITE_DESCRIPTOR',str(0x08000000+entries['sprite_descriptor']))
    event_source=(ROOT/'asm/halfspace_event_wrap.s').read_text(encoding='utf-8')+'\n.balign 4,0\n'+sprite_source+'\n.balign 4,0\nentry_table: .word sprite_created,sprite_advance'
    event=assemble(event_source,EVENT_HELPER)
    entries.update({name:at-0x08000000 for name,at in zip(('sprite_created','sprite_advance'),struct.unpack('<2I',event[-8:]))})
    event=event[:-8]
    if EVENT_HELPER+len(event)>0x1434:raise ValueError('Shared post literal collision')
    event+=b'\xc0\x46'*((0x1434-EVENT_HELPER-len(event))//2)+struct.pack('<I',0x08025269)
    if EVENT_HELPER+len(event)>EVENT_LIMIT:raise ValueError('Event wrap owner overflow')
    writes.append(('retired_native_odd_event_wrap',EVENT_HELPER,event))
    writes.append(('event_pixel_wrap',0x9AA0C,assemble(f'bl {0x08000000+EVENT_HELPER}\nb 0x0809aa5e\nmov r8,r8',0x9AA0C)))
    writes.append(('sprite_created_hook',0x25164,assemble(f"bl {0x08000000+entries['sprite_created']}",0x25164)))
    writes.append(('sprite_pixel_advance',0x25208,assemble(f"push {{lr}}\nbl {0x08000000+entries['sprite_advance']}\npop {{r0}}\nmov lr,r0",0x25208)))
    writes.append(('sprite_reserved_glyph_guard',0xB9584,assemble(f"bl {0x08000000+entries['sprite_font']}",0xB9584)))
    writes.append(('sprite_narrow_background',0x25192,assemble(f"bl {0x08000000+entries['sprite_postprocess']}",0x25192)))
    bitmap=assemble((ROOT/'asm/halfspace_bitmap_convert.s').read_text(encoding='utf-8'),0x21FC)
    if len(bitmap)!=104:raise ValueError('Audited bitmap body extent changed')
    writes.append(('equivalent_bitmap_convert',0x21FC,bitmap))
    popup=assemble((ROOT/'asm/halfspace_popup_center.s').read_text(encoding='utf-8'),0x25D08)
    if len(popup)>160:raise ValueError('Native popup owner overflow')
    writes.append(('native_popup_pixel_center',0x25D08,popup))
    for at in (0x1616,0x16B0):writes.append(('draw_call',at,assemble(f"bl {0x08000000+entries['draw']}",at)))
    for at in (0x1620,0x16BA):writes.append(('advance_call',at,assemble(f"bl {0x08000000+entries['advance']}\nmov r8,r8",at)))
    writes.append(('wrap_entry',0x152C,b'\x00\x4b\x18\x47'+struct.pack('<I',0x08000001+entries['wrap'])))
    writes.append(('reset_entry',0x1710,b'\x00\x4b\x18\x47'+struct.pack('<I',0x08000001+entries['reset'])))
    writes.append(('clear_call',0x107E,assemble(f"bl {0x08000000+entries['clear']}",0x107E)))
    validate_runtime_spans(writes)
    result=bytearray(base); report=[]
    for name,at,payload in writes:
        result[at:at+len(payload)]=payload
        report.append(dict(writer=name,start=at,end=at+len(payload),before_sha256=sha(base[at:at+len(payload)]),after_sha256=sha(payload)))
    out=bytes(result)
    changed=[i for i,(a,b) in enumerate(zip(base,out)) if a!=b]
    assert all(any(w['start']<=i<w['end'] for w in report) for i in changed)
    patch=create_bps(japanese,out)
    assert apply_bps(japanese,patch)==out
    return out,patch,dict(status='DIAGNOSTIC_FULL_WINDOW_PROTOTYPE_ONLY',baseline_sha256=BASE,japanese_sha256=JP,sha256=sha(out),rom_bytes=len(out),writes=report,entries=entries,draw_bytes=len(draw),helper_bytes=len(code),retired_native_even_owner=dict(start=HELPER,end=LIMIT,before_sha256=sha(base[HELPER:LIMIT]),original_japanese_equal=True,thumb_bl_entry_callers=[],literal_entry_callers_before=hits,literal_entry_callers_after=[i for i in range(len(out)-3) if out.startswith(needle,i)],qualification='Bounded static reference proof; computed calls require independent QA'),native_text_changed=False,compressed_slots_changed=False,normal_glyph_advance_px=12,space_advance_px=6,compact_advance_px=8,limitations=['Nonselective prototype narrows full-window spaces without semantic classification' if not selective else 'Reserved8040 only; caller must encode and read back selective text slots','Natural runtime, saves, performance, and hardware are separate from this builder','Fullwindow byte6 and sprite padding23 consumer coverage requires independent QA'])


def main():
    p=argparse.ArgumentParser()
    for name in ('baseline','japanese','layout','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():raise ValueError('Fresh output directory required')
    image,patch,report=build(a.baseline.read_bytes(),a.japanese.read_bytes(),json.loads(a.layout.read_text(encoding='utf-8')))
    a.out.mkdir(parents=True)
    (a.out/'Xagros_Narikiri2_KOR_v1.1a_halfspace-PROTOTYPE.gba').write_bytes(image)
    (a.out/'Xagros_Narikiri2_KOR_v1.1a_halfspace-PROTOTYPE_FROM_JP.bps').write_bytes(patch)
    (a.out/'BUILD_RESULT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()
