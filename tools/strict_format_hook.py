"""Symbol-bound diagnostic formatter adapter; not a full runtime integration."""
from pathlib import Path
import re
import struct

ROOT=Path(__file__).resolve().parents[1]
FORMAT_ENTRY=0x2648
FORMAT_EXPECTED=bytes.fromhex('f0b582b0071c0c1c')


def assemble_format_hook(*, address, decoder, descriptors, count, book, book_bytes,
                         consumer='template', lookup=None, output_capacity=None):
    from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
    from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
    if consumer not in ('template','string_argument','dialogue','event_expand'):
        raise ValueError('Unproved formatter boundary')
    values=dict(STRICT_DECODER_ADDRESS=decoder,FORMAT_DESCRIPTORS=descriptors,
        FORMAT_DESCRIPTOR_COUNT=count,FORMAT_BOOK=book,FORMAT_BOOK_BYTES=book_bytes)
    if any(type(v)!=int or not 0<=v<2**32 for v in values.values()):
        raise ValueError('Invalid symbol')
    if address&3 or decoder&1 or descriptors&3 or book&1 or not count or book_bytes<28:
        raise ValueError('Invalid alignment or extent')
    if abs(decoder-(address+4))>=0x3ff000:
        raise ValueError('Decoder outside conservative Thumb BL reach')
    source=(ROOT/'asm/strict_format_hook.s').read_text(encoding='utf-8')
    data_bytes=28
    if lookup is not None:
        if type(lookup)!=int or lookup&1 or abs(lookup-(address+4))>=0x3ff000:
            raise ValueError('Lookup outside Thumb call contract')
        if type(output_capacity)!=int or not 1<=output_capacity<=0x1000:
            raise ValueError('Missing bounded native output capacity')
        start=source.index('    ldr r7, format_descriptors')
        end=source.index('format_native:')
        source=source[:start]+'''    movs r0, SOURCE_REGISTER
    ldr r1, format_descriptors
    ldr r2, format_descriptor_count
    bl FORMAT_LOOKUP_ADDRESS
    cmp r0, #0
    beq format_native
    movs r7, r0
    b format_compressed
'''+source[end:]
        source=source.replace('ldr r0, [r7, #8]','ldr r0, format_output_capacity')
        source=source.replace('ldr r1, [r7, #4]','movs r1, r7')
        source=source.replace('ldr r3, [r7, #8]','ldr r3, format_output_capacity')
        source+='\nformat_output_capacity: .word FORMAT_OUTPUT_CAPACITY\n'
        values.update(FORMAT_LOOKUP_ADDRESS=lookup,FORMAT_OUTPUT_CAPACITY=output_capacity)
        data_bytes+=4
    if consumer=='template':
        source=source.replace('SOURCE_REGISTER','r5').replace('RESTORE_DECODED_ARGS',
            'movs r0, r4\n    ldr r1, [sp, #16]\n    movs r2, r6')
        source=source.replace('ORIGINAL_PRELUDE',
            'push {r4-r7, lr}\n    sub sp, #8\n    adds r7, r0, #0\n    adds r4, r1, #0')
        source=source.replace('ORIGINAL_CONTINUATION','0x08002651')
    elif consumer=='event_expand':
        source=source.replace('SOURCE_REGISTER','r4').replace('RESTORE_DECODED_ARGS',
            'ldr r0, [sp, #16]\n    movs r1, r5\n    movs r2, r6')
        source=source.replace('ORIGINAL_PRELUDE',
            'push {r4-r7, lr}\n    mov r7, sl\n    mov r6, sb\n    mov r5, r8\n'
            '    push {r5-r7}\n    sub sp, #8\n    adds r5, r0, #0\n    movs r0, #58')
        source=source.replace('ORIGINAL_CONTINUATION','0x08098971')
    elif consumer=='dialogue':
        source=source.replace('SOURCE_REGISTER','r4').replace('RESTORE_DECODED_ARGS',
            'ldr r0, [sp, #16]\n    movs r1, r5\n    movs r2, r6')
        # Replay the overwritten entry and both remaining argument stores;
        # only then may r3 be used for the continuation address.
        source=source.replace('ORIGINAL_PRELUDE',
            'push {r4-r7, lr}\n    mov r7, sl\n    mov r6, sb\n    mov r5, r8\n'
            '    push {r5-r7}\n    sub sp, #72\n    str r0, [sp, #36]\n'
            '    str r1, [sp, #40]\n    str r2, [sp, #44]\n    str r3, [sp, #48]')
        source=source.replace('ORIGINAL_CONTINUATION','0x0809A451')
    else:
        # Preserve the adopted actor-name resolver before the original copy
        # and width calculation; the decoded native buffer is an ordinary
        # string to that resolver. Its caller owns the formatter output.
        source=source.replace('SOURCE_REGISTER','r4').replace('RESTORE_DECODED_ARGS',
            'ldr r0, [sp, #16]\n    movs r1, r5\n    movs r2, r6')
        source=source.replace('ORIGINAL_PRELUDE','')
        source=source.replace('ORIGINAL_CONTINUATION','0x08C1EA81')
    for key,value in values.items():
        source=re.sub(r'\b'+key+r'\b',str(value),source)
    payload=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(source,addr=address)[0])
    # The final seven words are data. Decode precisely the executable prefix,
    # allowing ARMv4T Thumb BL pairs, but no Thumb-2 or interworking BLX.
    instructions=list(Cs(CS_ARCH_ARM,CS_MODE_THUMB).disasm(payload[:-data_bytes],address))
    if sum(i.size for i in instructions)!=len(payload)-data_bytes:
        raise ValueError('Undecoded code bytes')
    if any((i.size!=2 and i.mnemonic!='bl') or i.mnemonic in
           ('blx','it','itt','cbz','cbnz','movw','movt') for i in instructions):
        raise ValueError('Not ARM7TDMI Thumb')
    for i in instructions:
        if i.mnemonic=='bl':
            destination=int(i.op_str.lstrip('#'),0)
            if not (address<=destination<address+len(payload)-data_bytes or destination in (decoder,lookup)):
                raise ValueError('Unresolved call target')
    return payload


def dialogue_veneer(address, target):
    """ARMv4T 16-byte veneer preserving four input arguments and LR."""
    from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
    if address&3 or target&1:
        raise ValueError('Veneer alignment')
    payload=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(
        f'push {{r3}}; ldr r3, target; mov ip, r3; pop {{r3}}; bx ip; '
        f'.balign 4,0; target: .word {target|1}',addr=address)[0])
    if len(payload)!=16:raise ValueError('Unexpected veneer size')
    return payload


def descriptor_blob(entries):
    """Explicit original start, input bound, output bound; no external template."""
    if not entries or len({e[0] for e in entries})!=len(entries):
        raise ValueError('Empty or ambiguous descriptor set')
    result=bytearray()
    for start,slot,capacity in sorted(entries):
        if not 0x08000000<=start<start+slot<=0x08800000 or not 1<=capacity<=0x1000:
            raise ValueError('Descriptor outside original text/validated output envelope')
        result.extend(struct.pack('<III',start,slot,capacity))
    return bytes(result)
