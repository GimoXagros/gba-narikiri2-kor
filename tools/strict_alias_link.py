"""Link proved alias adapters against the common v2 decoder and native hooks."""
from pathlib import Path
import struct
from strict_compact_font import validate_thumb
ROOT=Path(__file__).resolve().parents[1]


def assemble_job(address,*,descriptors,book,book_bytes,unit_decoder):
    from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
    if address&3 or not unit_decoder&1 or descriptors&3 or book&1 or book_bytes<4:
        raise ValueError('Alias link ABI')
    source=(ROOT/'asm/strict_runtime_select_job.s').read_text()
    source=source.replace('.word 0xDE5C0001',f'.word {descriptors}').replace('.word 0xDE5C0002',f'.word {book}')
    if source.count('.word 7388')!=1:raise ValueError('Frozen book-size literal changed')
    source=source.replace('.word 7388',f'.word {book_bytes}')
    source+=f'\nstrict_unit_bundle_decode: ldr r4,common_unit; bx r4; .balign 4,0; common_unit: .word {unit_decoder}\n'
    # r4 is a saved source cursor across the decode call. A local veneer must
    # preserve it just as the decoder does.
    source=source.replace('strict_unit_bundle_decode: ldr r4,common_unit; bx r4;',
        'strict_unit_bundle_decode: push {r4}; ldr r4,common_unit; mov ip,r4; pop {r4}; bx ip;')
    ks=Ks(KS_ARCH_ARM,KS_MODE_THUMB)
    code=bytes(ks.asm(source,addr=address)[0])
    prefix=source.split('strict_runtime_select_job_menu:')[0]
    entry=len(ks.asm(prefix+'\nstrict_unit_bundle_decode: bx lr\n',addr=address)[0])-2
    if code[entry:entry+2]!=b'\xf0\xb5':raise ValueError('Alias wrapper entry changed')
    return code,entry


def assemble_arte_accessor(address,*,fail_stop):
    """Original index and mode select an opaque tag, without global context.

    Replaces eight bytes at 08008C54 using a direct veneer; unlike the earlier
    diagnostic push/BL patch there is no extra LR word on the caller's stack.
    """
    from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
    if address&3 or not fail_stop&1:raise ValueError('ARTE link ABI')
    source=f'''
    push {{r4,r5,lr}}
    cmp r0,#232
    bhs failed
    movs r4,r0
    movs r5,r1
    bl original
    cmp r5,#0
    bne done
    subs r4,#158
    cmp r4,#1
    bhi done
    ldr r1,original_source
    cmp r0,r1
    bne failed
    ldr r0,left_tag
    cmp r4,#0
    beq done
    ldr r0,right_tag
done:
    pop {{r4,r5}}
    pop {{r1}}
    bx r1
failed:
    ldr r3,stop_ptr
    bx r3
original:
    lsls r2,r0,#2
    adds r2,r2,r0
    lsls r2,r2,#2
    ldr r3,table_ptr
    cmp r1,#0
    beq compact
    adds r3,#4
compact:
    ldr r0,[r3,r2]
    bx lr
    .balign 4,0
original_source: .word 0x082bcfe0
left_tag: .word 0x0a2bcfe0
right_tag: .word 0x0c2bcfe0
stop_ptr: .word {fail_stop}
table_ptr: .word 0x08374a38
'''
    code=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(source,addr=address)[0])
    if len(code)!=88:raise ValueError('Frozen ARTE accessor footprint changed')
    validate_thumb(code,5)
    return code
