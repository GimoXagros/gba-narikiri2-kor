"""Decode the two original name fields before native profile persistence.

0800763C copies 092CC compact names at +0 and 091DC full names at +0x13
when the recruit slot is available. Both getters return original ROM starts,
which can now contain compressed bytes. Decode directly into the persistent
record, bounded by its actual next fields (19 and 13 bytes including NUL).
No pointer, string location, record layout or save format changes.
"""
from __future__ import annotations

import hashlib
import struct

from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
from strict_compact_font import validate_thumb
from strict_relative_assets import read_resource


JAPANESE_SHA256 = 'a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7'
INPUT_SHA256 = 'd5c375379369916bd1a5309678be2e9e28c5b0fff6955ebddb73537c64c187f5'
HELPER = 0x3A83AC
OWNER_END = 0x3A8555
OWNER_SHA256 = '9add4f5a2000c2142cc8a8c3081555dc923e7ce88e256f4986a3e00cee1ce19b'
CALLS = ((0x76AA, 0, bytes.fromhex('9ff071fa')),
         (0x76BC, 4, bytes.fromhex('9ff068fa')))


def assemble() -> tuple[bytes, list[bytes]]:
    source = '''
compact_entry:
    movs r2,#19
    b common
full_entry:
    movs r2,#13
common:
    push {r4,r5,r6,lr}
    movs r4,r0
    movs r5,r2
    movs r0,r1
    movs r1,r4
    ldr r3,owned
    bl call_r3
    cmp r0,#0
    beq failed
    cmp r1,#0
    bne done
    movs r1,r0
    movs r6,r4
native_copy:
    cmp r5,#0
    beq failed
    ldrb r2,[r1]
    strb r2,[r6]
    cmp r2,#0
    beq done
    adds r1,#1
    adds r6,#1
    subs r5,#1
    b native_copy
done:
    movs r0,r4
    pop {r4,r5,r6,pc}
failed:
    ldr r3,stop
call_r3:
    bx r3
    .balign 4,0
owned: .word 0x080B9C01
stop: .word 0x080B9DE5
'''
    ks=Ks(KS_ARCH_ARM,KS_MODE_THUMB)
    helper=bytes(ks.asm(source,addr=0x08000000+HELPER)[0])
    validate_thumb(helper,2)
    if len(helper)>OWNER_END-HELPER:
        raise ValueError('Name copy helper exceeds retired shop resource')
    calls=[bytes(ks.asm(f'bl #0x{0x08000000+HELPER+entry:08x}',addr=0x08000000+site)[0])
           for site,entry,_ in CALLS]
    if any(len(c)!=4 for c in calls):raise ValueError('Unexpected Thumb BL width')
    return helper,calls


def diagnostic_patch(japanese: bytes, candidate: bytes) -> tuple[bytes, dict]:
    sha=lambda data:hashlib.sha256(data).hexdigest()
    if len(japanese)!=0x800000 or sha(japanese)!=JAPANESE_SHA256:
        raise ValueError('Exact 8 MiB Japanese source required')
    if len(candidate)!=0x800000 or sha(candidate)!=INPUT_SHA256:
        raise ValueError('Exact 8 MiB description-length candidate required')
    if sha(candidate[HELPER:OWNER_END])!=OWNER_SHA256:
        raise ValueError('Retired shop owner identity changed')
    table=0x3A7ADC
    if candidate[table:table+12]!=japanese[table:table+12]:
        raise ValueError('Original shop resource-table binding changed')
    start=table+struct.unpack_from('<I',candidate,table+4)[0]
    next_start=table+struct.unpack_from('<I',candidate,table+8)[0]
    native,used=read_resource(candidate,start)
    original,old_used=read_resource(japanese,start)
    if (start!=0x3A7C3C or len(native)!=4096 or len(original)!=4096
            or start+used!=0x3A83A9 or start+old_used!=OWNER_END
            or not start+used<=HELPER<OWNER_END<=next_start):
        raise ValueError('Shop suffix is not beyond the consumed resource')
    helper,calls=assemble()
    out=bytearray(candidate);writes=[]
    for at,expected,after in [(HELPER,candidate[HELPER:HELPER+len(helper)],helper),
            *[(site,original,call) for (site,_,original),call in zip(CALLS,calls)]]:
        if candidate[at:at+len(expected)]!=expected:
            raise ValueError('Original name-copy call changed')
        out[at:at+len(after)]=after
        writes.append({'offset':at,'bytes':len(after),'before_sha256':sha(expected),'after_sha256':sha(after)})
    if read_resource(out,start)!=(native,used):raise ValueError('Live shop graphic changed')
    return bytes(out),{'status':'DIAGNOSTIC_ONLY_BOUNDED_PROFILE_NAME_COPY',
        'input_sha256':INPUT_SHA256,'output_sha256':sha(out),'size':len(out),
        'writes':writes,'field_capacities':[19,13],'persistent_extra_ram':0,
        'owner':{'start':HELPER,'end':OWNER_END,'active_resource_end':start+used},
        'scope':'Two native profile strcpy callsites; caller reachability and game regression remain separate'}
