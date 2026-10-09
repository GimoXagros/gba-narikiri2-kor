"""Decode original honorific starts before native synchronous name concatenation.

09228 formats the name through the decoded formatter but its two native strcat
calls otherwise copy compressed suffix bytes into RAM. Preserve those original
suffix pointers and use a caller-owned temporary buffer until strcat returns.
"""
from __future__ import annotations

import hashlib
import struct
from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
from strict_compact_font import validate_thumb
from strict_relative_assets import read_resource
from strict_profile_name_copy import JAPANESE_SHA256

INPUT_SHA256='360bc541cbf7bb23b2d8282313c3d99c1ed128a27773b8cc92e2d21953044663'
HELPER=0x3A83F4
OWNER_END=0x3A8555
OWNER_SHA256='cc705cbb9ad335f0105b705b3db938bbe233dacb876160d15585977ee41366f9'
CALLS=((0x92A4,bytes.fromhex('9df022fc')),(0x92BC,bytes.fromhex('9df016fc')))


def assemble_consumer(address,native_consumer,call_sites):
    source='''
    push {r4,lr}
    sub sp,#288
    movs r4,r0
    movs r0,r1
    mov r1,sp
    movs r2,#144
    lsls r2,r2,#1
    ldr r3,owned
    bl call_r3
    cmp r0,#0
    beq failed
    movs r1,r0
    movs r0,r4
    ldr r3,native_cat
    bl call_r3
    add sp,#288
    pop {r4,pc}
failed:
    ldr r3,stop
call_r3:
    bx r3
    .balign 4,0
owned: .word 0x080B9C01
native_cat: .word 0x080A6AED
stop: .word 0x080B9DE5
'''
    ks=Ks(KS_ARCH_ARM,KS_MODE_THUMB)
    source=source.replace('0x080A6AED',hex(native_consumer))
    helper=bytes(ks.asm(source,addr=0x08000000+address)[0])
    validate_thumb(helper,3)
    calls=[bytes(ks.asm(f'bl #0x{0x08000000+address:x}',addr=0x08000000+at)[0]) for at in call_sites]
    if any(len(call)!=4 for call in calls):raise ValueError('Unexpected Thumb BL width')
    return helper,calls


def assemble():
    helper,calls=assemble_consumer(HELPER,0x080A6AED,[at for at,_ in CALLS])
    if len(helper)>OWNER_END-HELPER:raise ValueError('Honorific helper exceeds resource owner')
    return helper,calls


def diagnostic_patch(japanese,candidate):
    sha=lambda b:hashlib.sha256(b).hexdigest()
    if len(japanese)!=0x800000 or sha(japanese)!=JAPANESE_SHA256:
        raise ValueError('Exact 8 MiB Japanese source required')
    if len(candidate)!=0x800000 or sha(candidate)!=INPUT_SHA256:
        raise ValueError('Exact profile-copy diagnostic required')
    if sha(candidate[HELPER:OWNER_END])!=OWNER_SHA256:
        raise ValueError('Retired shop suffix identity changed')
    table=0x3A7ADC
    if candidate[table:table+12]!=japanese[table:table+12]:
        raise ValueError('Shop table binding changed')
    start=table+struct.unpack_from('<I',candidate,table+4)[0]
    next_start=table+struct.unpack_from('<I',candidate,table+8)[0]
    native,used=read_resource(candidate,start)
    original,old_used=read_resource(japanese,start)
    if (start!=0x3A7C3C or len(native)!=4096 or len(original)!=4096
            or start+used!=0x3A83A9 or start+old_used!=OWNER_END
            or not start+used<=HELPER<OWNER_END<=next_start):
        raise ValueError('Honorific owner overlaps consumed shop resource')
    helper,calls=assemble();out=bytearray(candidate);writes=[]
    for at,expected,after in [(HELPER,candidate[HELPER:HELPER+len(helper)],helper),
            *[(at,before,after) for (at,before),after in zip(CALLS,calls)]]:
        if candidate[at:at+len(expected)]!=expected:raise ValueError('Original honorific call differs')
        out[at:at+len(after)]=after
        writes.append(dict(offset=at,bytes=len(after),before_sha256=sha(expected),after_sha256=sha(after)))
    if read_resource(out,start)!=(native,used):raise ValueError('Live shop graphic changed')
    return bytes(out),dict(status='DIAGNOSTIC_ONLY_DECODED_HONORIFIC_APPEND',
        input_sha256=INPUT_SHA256,output_sha256=sha(out),size=len(out),writes=writes,
        stack_temporary_bytes=288,persistent_extra_ram=0,
        owner=dict(start=HELPER,end=OWNER_END,active_resource_end=start+used),
        scope='Two original suffix strcat callsites; native destination contract is unchanged')
