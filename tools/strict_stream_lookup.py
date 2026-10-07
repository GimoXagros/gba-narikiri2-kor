"""Compact runtime bounds index, independent of the frozen stream encoding."""
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[1]


def pack_bounds(entries):
    """Pack (absolute original start, owned slot bytes), sorted by exact start."""
    rows=sorted(entries)
    if not rows or len({r[0] for r in rows})!=len(rows):
        raise ValueError('Empty or duplicate stream bound')
    words=[]
    for start,size in rows:
        if any(type(v)!=int for v in (start,size)) or not 1<=size<=511:
            raise ValueError('Input slot does not fit nine-bit bound')
        offset=start-0x08000000
        if not 0<=offset<offset+size<=0x800000:
            raise ValueError('Stream bound outside original ROM')
        words.append(offset|(size<<23))
    return struct.pack('<'+'I'*len(words),*words)


def assemble_lookup(address):
    from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
    from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
    if address&1:raise ValueError('Thumb entry alignment')
    code=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(
        (ROOT/'asm/strict_stream_lookup.s').read_text(),addr=address)[0])
    instructions=list(Cs(CS_ARCH_ARM,CS_MODE_THUMB).disasm(code,address))
    if sum(i.size for i in instructions)!=len(code) or any(i.size!=2 for i in instructions):
        raise ValueError('Lookup must use Thumb-1 only')
    return code
