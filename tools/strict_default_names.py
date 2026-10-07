"""Two discovered fixed-name slots, not part of the original 10,172 bindings.

Their full native text is stored at the original four-byte JP slot as existing
9-bit glyph IDs. No text pointer/indirect body table, new glyph, or SAV encoding.
"""
from pathlib import Path
from strict_compact_font import validate_thumb
ROOT=Path(__file__).resolve().parents[1]


def pack_name(raw):
    if not raw or len(raw)%3 or not 1<=len(raw)//3<=3:
        raise ValueError('Fixed initializer count outside 1..3 glyphs')
    indices=[]
    for i in range(0,len(raw),3):
        marker,bank,cell=raw[i:i+3]
        index=(bank-1)*31+cell-1
        if marker!=127 or not 1<=bank<=31 or not 1<=cell<=31 or not 0<=index<512:
            raise ValueError('Not an adopted compact glyph ID')
        indices.append(index)
    result=sum(v<<(9*i) for i,v in enumerate(indices)).to_bytes(4,'little')
    if unpack_name(result,len(indices))!=raw+b'\0':raise ValueError('Name roundtrip')
    return result


def unpack_name(data,count):
    if len(data)!=4 or count not in (1,2,3):raise ValueError('Name slot/count')
    value=int.from_bytes(data,'little')
    if value>>(9*count):raise ValueError('Nonzero name padding')
    out=bytearray()
    for i in range(count):
        glyph=(value>>(9*i))&511
        out.extend((127,glyph//31+1,glyph%31+1))
    return bytes(out)+b'\0'


def assemble_decoder(address):
    from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
    if address&1:raise ValueError('Thumb alignment')
    code=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(
        (ROOT/'asm/strict_default_name9.s').read_text(),addr=address)[0])
    from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
    insns=list(Cs(CS_ARCH_ARM,CS_MODE_THUMB).disasm(code,address))
    if sum(i.size for i in insns)!=len(code) or any(i.size!=2 for i in insns):
        raise ValueError('Fixed-name decoder must be Thumb1')
    return code


def assemble_initializer(address,*,fixed_decoder,stream_decoder,count,second,fail_stop):
    """Reconstruct compact+full default-name fields then skip native raw memcpy.

    First starts at adopted C01400 (original9720); second at C01480 (9734).
    Only r0..r3 are volatile; r4 still points to original game-data root.
    """
    from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
    if address&3 or count not in (2,3) or any(not p&1 for p in (fixed_decoder,stream_decoder,fail_stop)):
        raise ValueError('Name initializer ABI')
    code=('' if second else '    ldr r0,[r4]\n')+f'''
    push {{r4-r6,lr}}
    movs r4,r0
    movs r1,r0
'''+('    adds r1,#60\n' if second else '')+f'''
    ldr r0,compact_pointer
    ldr r0,[r0]
    movs r2,#{count}
    movs r3,#19
    ldr r6,fixed_ptr
    bl call_r6
    cmp r0,#{count*3+1}
    bne failed
    ldr r0,full_pointer
    ldr r0,[r0]
    movs r1,r4
    adds r1,#{79 if second else 19}
    movs r2,#7
    ldr r6,stream_ptr
    bl call_r6
    cmp r0,#0
    beq failed
    cmp r2,#{5 if second else 7}
    bne failed
'''+('''    movs r1,#0
    strb r1,[r0,#5]
    strb r1,[r0,#6]
''' if second else '')+f'''
    pop {{r4-r6}}
    pop {{r3}}
    mov lr,r3
    ldr r3,resume_ptr
    bx r3
failed:
    ldr r6,stop_ptr
call_r6:
    bx r6
    .balign 4,0
compact_pointer: .word {0x08009788 if second else 0x08009780}
full_pointer: .word {0x0800978c if second else 0x08009784}
fixed_ptr: .word {fixed_decoder}
stream_ptr: .word {stream_decoder}
resume_ptr: .word {0x08009745 if second else 0x08009733}
stop_ptr: .word {fail_stop}
'''
    result=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(code,addr=address)[0])
    validate_thumb(result,6)
    return result
