"""Store stable compact identity in the existing adopted actor-name record.

The temporary native decoding is inspected only during this call. Hangul
records retain the original ROM input pointer, never the stack buffer address.
Unregistered native input keeps the adopted store semantics.
"""
from strict_compact_font import validate_thumb


def assemble(address,*,decoder,native_store,fail_stop):
    from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
    if address&3 or any(not p&1 for p in (decoder,native_store,fail_stop)):
        raise ValueError('Actor store ABI alignment')
    source=f'''
    push {{r4-r6,lr}}
    sub sp,#32
    movs r4,r0
    movs r5,r1
    movs r0,r1
    mov r1,sp
    movs r2,#32
    ldr r3,decoder_ptr
    bl call_r3
    cmp r0,#0
    beq failed
    cmp r2,#0
    beq native
    movs r6,r0
    movs r1,r0
scan:
    ldrb r3,[r1]
    cmp r3,#127
    beq indirect
    cmp r3,#0
    beq ascii
    adds r1,#1
    b scan
indirect:
    ldr r0,signature
    str r0,[r4]
    str r5,[r4,#4]
    movs r0,#0
    strh r0,[r4,#8]
    movs r0,r4
    b done
ascii:
    cmp r2,#10
    bhi failed
    movs r0,r4
    movs r1,r6
    ldr r3,copy_ptr
    bl call_r3
    b done
native:
    movs r0,r4
    movs r1,r5
    ldr r3,native_ptr
    bl call_r3
done:
    add sp,#32
    pop {{r4-r6}}
    pop {{r3}}
    bx r3
failed:
    ldr r3,stop_ptr
call_r3:
    bx r3
    .balign 4,0
decoder_ptr: .word {decoder}
signature: .word 0x444e007f
copy_ptr: .word 0x080a6b91
native_ptr: .word {native_store}
stop_ptr: .word {fail_stop}
'''
    code=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(source,addr=address)[0])
    validate_thumb(code,5)
    return code
