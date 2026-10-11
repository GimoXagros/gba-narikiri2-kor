"""Dictionary ABI v2: four-byte nodes, unchanged v1 stream bits and glyphs.

This is a versioned representation change, not accepted by the v1 decoder.
Header: uint16 node count; uint16 version=2. Internal nodes retain two uint16
indices (<0x8000). Leaf: bit31=1, bits24..30=length (0..3), low24 native bytes.
No source string, selector, text start or pointer changes during conversion.
"""
from pathlib import Path
import struct
from strict_unit_codec import code_table
ROOT=Path(__file__).resolve().parents[1]
FORMAT_VERSION='unit_inline_native_v1_packed_tree_v2'


def assemble_decoder(address):
    """Assemble the checked source without importing a CPU test harness."""
    from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
    source=(ROOT/'asm/strict_unit_bundle_decode_v2.s').read_text()
    if source!=decoder_source():raise ValueError('Packed decoder source derivation changed')
    if address&1 or not 0<=address<=0xFFFFFFFE:raise ValueError('Thumb assembly address')
    return bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(source,addr=address)[0])


def pack_tree(original):
    code_table(original)
    count=struct.unpack_from('<H',original)[0]
    words=[]
    for i in range(count):
        a,b=struct.unpack_from('<HH',original,4+i*8)
        payload=original[8+i*8:11+i*8]
        if a&0x8000:
            word=0x80000000|((a&0x7fff)<<24)|int.from_bytes(payload,'little')
        else:
            word=a|(b<<16)
        words.append(word)
    packed=struct.pack('<HH',count,2)+struct.pack('<'+'I'*count,*words)
    if unpack_tree(packed)!=original:raise ValueError('Dictionary conversion is not reversible')
    return packed


def unpack_tree(packed):
    if len(packed)<16:raise ValueError('Truncated packed tree')
    count,version=struct.unpack_from('<HH',packed)
    if version!=2 or not 3<=count<0x8000 or len(packed)!=4+count*4:
        raise ValueError('Packed tree version/extent')
    nodes=[]
    for i in range(count):
        word=struct.unpack_from('<I',packed,4+i*4)[0]
        if word&0x80000000:
            size=(word>>24)&0x7f
            raw=(word&0xffffff).to_bytes(3,'little')
            if size>3 or any(raw[size:]) or 0 in raw[:size]:raise ValueError('Packed leaf')
            nodes.append(struct.pack('<HH',0x8000|size,0)+raw+b'\0')
        else:
            a,b=word&0xffff,word>>16
            if a>=count or b>=count:raise ValueError('Packed edge')
            nodes.append(struct.pack('<HHI',a,b,0))
    result=struct.pack('<HH',count,0)+b''.join(nodes)
    code_table(result)  # Depth, cycles, duplicate leaves, EOS, reachability.
    return result


def decoder_source():
    """Guarded, reviewable mechanical derivation from unchanged v1 decoder."""
    source=(ROOT/'asm/strict_unit_bundle_decode.s').read_text()
    replacements=[
        ('experimental bounded glyph-prefix decoder.','packed-tree-v2 bounded glyph-prefix decoder.',1),
        ('No game hook yet.','The stream bit format is unchanged; dictionary header version is 2.',1),
        ('cmp r5, #28','cmp r5, #16',1),
        ('lsls r7, r6, #3','lsls r7, r6, #2',1),
        ('ldrh r7, [r4, #2]\n    cmp r7, #0','ldrh r7, [r4, #2]\n    cmp r7, #2',1),
        ('lsls r7, r7, #3','lsls r7, r7, #2',1),
        ('ldrh r0, [r7]\n    lsrs r0, r0, #15','ldrh r0, [r7, #2]\n    lsrs r0, r0, #15',1),
        ('ldrh r0, [r7]\n    lsls r0, r0, #17\n    lsrs r0, r0, #17',
         'ldrb r0, [r7, #3]\n    lsls r0, r0, #25\n    lsrs r0, r0, #25',1),
        ('    movs r1, r0\n    adds r7, #4\n','    movs r1, r0\n',2),
    ]
    for old,new,count in replacements:
        if source.count(old)!=count:raise ValueError('V1 decoder derivation contract changed: '+old)
        source=source.replace(old,new)
    return source


if __name__=='__main__':
    output=ROOT/'asm/strict_unit_bundle_decode_v2.s'
    if output.exists():raise SystemExit('Refusing to overwrite generated ASM')
    output.write_text(decoder_source(),encoding='utf-8')
