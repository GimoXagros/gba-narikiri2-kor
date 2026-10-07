"""Exact two-palette compact-font packing; no glyph design or text changes."""
from pathlib import Path
import re,struct
ROOT=Path(__file__).resolve().parents[1]


def validate_thumb(code,data_words):
    from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
    prefix=code[:-4*data_words]
    insns=list(Cs(CS_ARCH_ARM,CS_MODE_THUMB).disasm(prefix,0))
    if sum(i.size for i in insns)!=len(prefix) or any(i.size!=2 and i.mnemonic!='bl' for i in insns):
        raise ValueError('Unsupported Thumb instruction')


def pack_font(clear,solid):
    if not clear or len(clear)%32 or len(clear)!=len(solid):
        raise ValueError('Compact font bank extent')
    bits=[];byte=0;shift=0
    for a,b in zip(clear,solid):
        for x,y in ((a&15,b&15),(a>>4,b>>4)):
            if (x,y) not in ((0,11),(15,15)):
                raise ValueError('Font palette pair is not reversible')
            byte|=(x==15)<<shift;shift+=1
            if shift==8:bits.append(byte);byte=shift=0
    tables=b''.join(struct.pack('<H',sum((15 if value&(1<<i) else background)<<(4*i) for i in range(4)))
                    for background in (0,11) for value in range(16))
    return bytes(bits),tables


def assemble(name,address,**symbols):
    from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
    if address&3:raise ValueError('Code literal alignment')
    source=(ROOT/'asm'/name).read_text()
    for key,value in symbols.items():
        if type(value)!=int or not 0<=value<2**32:raise ValueError('Invalid assembly symbol')
        source=re.sub(r'\b'+key+r'\b',str(value),source)
    code=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(source,addr=address)[0])
    validate_thumb(code,3 if name=='strict_compact_font_unpack.s' else 4)
    return code


def assemble_inspector(address,unpacker):
    """Preserve affine renderer; unpack into a new 32-byte local tile first."""
    from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
    source=(ROOT/'asm/banked_inspect_text.s').read_text()
    old='''    lsls r0, r0, #5
    ldr r1, font
    adds r0, r0, r1'''
    new='''    add r1, sp, #12
    movs r2, #0
    ldr r3, font_unpacker
    bl call_r3
    cmp r0, #0
    beq fatal'''
    if source.count(old)!=1:raise ValueError('Affine renderer source contract')
    source=source.replace(old,new).replace('sub sp, #12','sub sp, #44').replace('add sp, #12','add sp, #44')
    source=source.replace('font: .word 0x08c02000',f'font_unpacker: .word {unpacker|1}')
    code=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(source,addr=address)[0])
    validate_thumb(code,7)
    return code
