"""Exact-start classifier with two explicit output ownership profiles.

Default: r0=input; result r0=native, r1=heap owner, r2=decoded bytes.
caller_buffer=True: r0=input, r1=destination, r2=capacity; successful decoded
result r0=r1=destination, r2=decoded bytes. It allocates/frees no heap. The r1
echo is not a heap owner in this profile. Native pass-through returns r1=r2=0.
The linked 8 MiB diagnostic uses caller_buffer=True.

This is an integration component, not a claim that every consumer is hooked.
Decoded data is never persisted or freed before the synchronous consumer returns.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def assemble(address, *, caller_buffer=False, **symbols):
    from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
    from strict_compact_font import validate_thumb
    required={'ALIAS_STARTS','FULL_BOUNDS','FULL_COUNT','FULL_BOOK',
              'FULL_BOOK_BYTES','FULL_CAPACITY','COMPACT_BOUNDS','COMPACT_COUNT',
              'COMPACT_BOOK','COMPACT_BOOK_BYTES','COMPACT_CAPACITY',
              'UNIT_DECODER','BOUNDS_LOOKUP'}
    extra={'EXTRA_BOUNDS','EXTRA_COUNT','EXTRA_BOOK','EXTRA_BOOK_BYTES','EXTRA_CAPACITY'}
    has_extra=bool(set(symbols)&extra)
    if has_extra:required |= extra
    if set(symbols)!=required or address&3:
        raise ValueError('Missing or unexpected owned-decoder symbols')
    for name,value in symbols.items():
        if type(value)!=int or not 0<value<2**32:
            raise ValueError('Invalid symbol '+name)
        if name in ('UNIT_DECODER','BOUNDS_LOOKUP') and not value&1:
            raise ValueError('Thumb function bit '+name)
        if name in ('ALIAS_STARTS','FULL_BOUNDS','COMPACT_BOUNDS','EXTRA_BOUNDS') and value&3:
            raise ValueError('Word alignment '+name)
        if name in ('FULL_BOOK','COMPACT_BOOK','EXTRA_BOOK') and value&1:
            raise ValueError('Halfword alignment '+name)
    source=(ROOT/'asm/strict_owned_decode.s').read_text()
    if has_extra:
        marker='    cmp r0,#0\n    beq native\n    movs r7,r0'
        if source.count(marker)!=1:raise ValueError('Extra-book classification anchor')
        source=source.replace(marker,marker.replace('beq native','beq extra'))
        source=source.replace('allocate:\n', '''    b allocate
extra:
    movs r0,r4
    ldr r1,extra_bounds
    ldr r2,extra_count
    bl lookup_call
    cmp r0,#0
    beq native
    movs r7,r0
    ldr r5,extra_book
    ldr r6,extra_book_bytes
    ldr r0,extra_capacity
allocate:
''')
        source+='''\nextra_bounds: .word EXTRA_BOUNDS
extra_count: .word EXTRA_COUNT
extra_book: .word EXTRA_BOOK
extra_book_bytes: .word EXTRA_BOOK_BYTES
extra_capacity: .word EXTRA_CAPACITY
'''
    if caller_buffer:
        # The caller, rather than this helper, owns the output through the
        # complete synchronous consumer. No pointer to helper locals escapes.
        source=source.replace('sub sp,#24','sub sp,#32').replace('add sp,#24','add sp,#32')
        source=source.replace('    movs r4,r0\n','    movs r4,r0\n    str r1,[sp,#24]\n    str r2,[sp,#28]\n',1)
        old='''    str r0,[sp,#16]
    ldr r3,heap_alloc
    bl call_r3
    cmp r0,#0
    beq failed
    movs r2,r0'''
        new='''    ldr r2,[sp,#28]
    cmp r2,r0
    bhs capacity_ready
    movs r0,r2
capacity_ready:
    str r0,[sp,#16]
    ldr r2,[sp,#24]'''
        if source.count(old)!=1:raise ValueError('Caller-buffer derivation changed')
        source=source.replace(old,new)
        source=source.replace('''    ldr r0,[sp,#16]
    ldr r3,heap_free
    bl call_r3
failed:''','''failed:''')
    for name,value in symbols.items():
        source=re.sub(r'\b'+name+r'\b',str(value),source)
    code=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(source,addr=address)[0])
    validate_thumb(code,23 if has_extra else 18)
    return code


def assemble_name_initializer(address, *, decoder, second=False, fail_stop):
    """Decode the original default-name slot directly into its existing 19B field.

    This replaces only the adopted first/second initializer shim. The pointer
    literal in original ROM stays untouched; no temporary pointer is persisted.
    """
    from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
    from strict_compact_font import validate_thumb
    if address&3 or not decoder&1 or not fail_stop&1:
        raise ValueError('Initializer alignment')
    source=('' if second else '    ldr r0,[r4]\n')+'''
    push {r0,r2,r3,lr}
    movs r1,r0
'''+('    adds r1,#60\n' if second else '')+f'''
    ldr r0,source_pointer
    ldr r0,[r0]
    movs r2,#19
    ldr r3,decoder_ptr
    bl call_r3
    cmp r0,#0
    beq failed
    ldr r1,[r0]
    pop {{r0,r2,r3}}
    pop {{r3}}
    mov lr,r3
'''+('    adds r0,#79\n' if second else '')+f'''
    ldr r3,resume_ptr
    bx r3
failed:
    ldr r3,stop_ptr
call_r3:
    bx r3
    .balign 4,0
source_pointer: .word {0x08009788 if second else 0x08009780}
decoder_ptr: .word {decoder}
resume_ptr: .word {0x0800973d if second else 0x08009729}
stop_ptr: .word {fail_stop}
'''
    code=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(source,addr=address)[0])
    validate_thumb(code,4)
    return code


def assemble_sync_wrapper(address, *, decoder, source_register, consumer,
                          resolve=0, fail_stop, caller_buffer=False):
    """For proven functions with r0..r3 arguments and r0 return, no stack args.

    `consumer` is an unhooked original-entry trampoline or an existing adopted
    wrapper, not the patched entry. Inputs/results stay live across nested calls.
    The fail-stop is diagnostic until each product error path is established.
    """
    from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
    from strict_compact_font import validate_thumb
    if source_register not in range(4) or address&3:
        raise ValueError('Unsupported synchronous ABI')
    if any(not p&1 for p in (decoder,consumer,fail_stop)) or (resolve and not resolve&1):
        raise ValueError('Thumb target required')
    off=4*source_register
    source=f'''
    push {{r4,lr}}
    sub sp,#24
    str r0,[sp]
    str r1,[sp,#4]
    str r2,[sp,#8]
    str r3,[sp,#12]
    ldr r0,[sp,#{off}]
'''
    if resolve:
        source+='    ldr r3,resolver\n    bl call_r3\n'
    source+=f'''
    ldr r3,decoder_ptr
    bl call_r3
    cmp r0,#0
    beq failed
    str r0,[sp,#{off}]
    str r1,[sp,#16]
    ldr r0,[sp]
    ldr r1,[sp,#4]
    ldr r2,[sp,#8]
    ldr r3,[sp,#12]
    ldr r4,consumer_ptr
    bl call_r4
    str r0,[sp,#20]
    ldr r0,[sp,#16]
    cmp r0,#0
    beq done
    ldr r3,free_ptr
    bl call_r3
done:
    ldr r0,[sp,#20]
    add sp,#24
    pop {{r4}}
    pop {{r3}}
    bx r3
failed:
    ldr r3,stop_ptr
call_r3:
    bx r3
call_r4:
    bx r4
    .balign 4,0
decoder_ptr: .word {decoder}
consumer_ptr: .word {consumer}
free_ptr: .word 0x080035dd
stop_ptr: .word {fail_stop}
'''
    if resolve:source+=f'resolver: .word {resolve}\n'
    if caller_buffer:
        # 24 bytes of argument/result storage followed by exactly 288 bytes of
        # per-invocation native text. The entire frame remains until return.
        source=source.replace('sub sp,#24','sub sp,#312').replace('add sp,#24','add sp,#312')
        source=source.replace('    ldr r3,decoder_ptr\n',
            '    add r1,sp,#24\n    movs r2,#144\n    lsls r2,r2,#1\n    ldr r3,decoder_ptr\n')
        source=source.replace('''    ldr r0,[sp,#16]
    cmp r0,#0
    beq done
    ldr r3,free_ptr
    bl call_r3
''','')
    code=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(source,addr=address)[0])
    validate_thumb(code,5 if resolve else 4)
    return code
