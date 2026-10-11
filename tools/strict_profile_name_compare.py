"""Compare original default-name pointers in native encoding against RAM names.

1A178 distinguishes existing defaults from user-entered names. Its original
strcmp input from 091DC can be compressed; decoding must precede comparison,
otherwise every default name is incorrectly treated as a custom name.
"""
import hashlib
import struct
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
from strict_compact_font import validate_thumb
from strict_profile_name_copy import JAPANESE_SHA256
from strict_relative_assets import read_resource

INPUT_SHA256='a4865cec1b831ab85b6701e1ceab45dca132f6651443c2e2aa78429b97349327'
HELPER=0x3A8520
OWNER_END=0x3A8555
OWNER_SHA256='353fd628b7f6e7d426e5d6a27d1bc3ac22fa7f812e7594cf2ec5ca1175785b50'
CALL=0x1A18C


def assemble():
    source='''
    push {r4,lr}
    sub sp,#288
    movs r4,r1
    mov r1,sp
    movs r2,#144
    lsls r2,r2,#1
    ldr r3,owned
    bl call_r3
    cmp r0,#0
    beq failed
    movs r1,r4
    ldr r3,native_cmp
    bl call_r3
    add sp,#288
    pop {r4,pc}
failed:
    ldr r3,stop
call_r3:
    bx r3
    .balign 4,0
owned: .word 0x080B9C01
native_cmp: .word 0x080A6B35
stop: .word 0x080B9DE5
'''
    ks=Ks(KS_ARCH_ARM,KS_MODE_THUMB)
    helper=bytes(ks.asm(source,addr=0x08000000+HELPER)[0]);validate_thumb(helper,3)
    if len(helper)>OWNER_END-HELPER:raise ValueError('Name compare helper exceeds resource owner')
    call=bytes(ks.asm(f'bl #0x{0x08000000+HELPER:x}',addr=0x08000000+CALL)[0])
    if len(call)!=4:raise ValueError('Unexpected Thumb BL width')
    return helper,call


def diagnostic_patch(japanese,candidate):
    sha=lambda b:hashlib.sha256(b).hexdigest()
    if len(japanese)!=0x800000 or sha(japanese)!=JAPANESE_SHA256:
        raise ValueError('Exact 8 MiB Japanese source required')
    if len(candidate)!=0x800000 or sha(candidate)!=INPUT_SHA256:
        raise ValueError('Exact popup-copy diagnostic required')
    if sha(candidate[HELPER:OWNER_END])!=OWNER_SHA256:
        raise ValueError('Retired shop suffix identity changed')
    table=0x3A7ADC
    if candidate[table:table+12]!=japanese[table:table+12]:raise ValueError('Shop table binding changed')
    start=table+struct.unpack_from('<I',candidate,table+4)[0]
    next_start=table+struct.unpack_from('<I',candidate,table+8)[0]
    native,used=read_resource(candidate,start)
    original,old_used=read_resource(japanese,start)
    if (start!=0x3A7C3C or len(native)!=4096 or len(original)!=4096
            or start+used!=0x3A83A9 or start+old_used!=OWNER_END
            or not start+used<=HELPER<OWNER_END<=next_start):
        raise ValueError('Compare owner overlaps consumed shop resource')
    helper,call=assemble();out=bytearray(candidate);writes=[]
    for at,expected,after in [(HELPER,candidate[HELPER:HELPER+len(helper)],helper),
            (CALL,japanese[CALL:CALL+4],call)]:
        if candidate[at:at+len(expected)]!=expected:raise ValueError('Original name-compare call differs')
        out[at:at+len(after)]=after
        writes.append(dict(offset=at,bytes=len(after),before_sha256=sha(expected),after_sha256=sha(after)))
    if read_resource(out,start)!=(native,used):raise ValueError('Live shop graphic changed')
    return bytes(out),dict(status='DIAGNOSTIC_ONLY_NATIVE_PROFILE_NAME_COMPARISON',
        input_sha256=INPUT_SHA256,output_sha256=sha(out),size=len(out),writes=writes,
        stack_temporary_bytes=288,persistent_extra_ram=0,
        owner=dict(start=HELPER,end=OWNER_END,active_resource_end=start+used),
        scope='Original strcmp comparison and signed return preserved; original name/profile pointers unchanged')
