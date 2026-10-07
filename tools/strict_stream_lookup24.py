"""SBS2 exact start/bound metadata, independent of compressed text format."""
from pathlib import Path
import struct
from strict_stream_lookup import pack_bounds
ROOT=Path(__file__).resolve().parents[1]
MAGIC=0x32534253


def pack_bounds24(entries):
    rows=sorted(entries)
    pack_bounds(rows)  # Same address, duplicate and exact nine-bit size contract.
    if len(rows)>65535:raise ValueError('Directory index width')
    groups={}
    for start,size in rows:
        groups.setdefault(start&~32767,[]).append((start&32767)|(size<<15))
    directory=bytearray();data=bytearray();index=0
    for page,words in groups.items():
        directory.extend(struct.pack('<IHH',page,len(words),index))
        data.extend(b''.join(word.to_bytes(3,'little') for word in words))
        index+=len(words)
    blob=struct.pack('<IHHI',MAGIC,len(groups),len(rows),12+len(directory))+directory+data
    if unpack_bounds24(blob)!=rows:raise ValueError('Metadata roundtrip')
    return bytes(blob)


def unpack_bounds24(blob):
    if len(blob)<12:raise ValueError('Truncated bounds header')
    magic,pages,total,offset=struct.unpack_from('<IHHI',blob)
    if magic!=MAGIC or not pages or not total or offset!=12+8*pages or len(blob)!=offset+3*total:
        raise ValueError('Bounds version/extent')
    rows=[];lastpage=0
    for i in range(pages):
        page,count,first=struct.unpack_from('<IHH',blob,12+8*i)
        if page&32767 or page<=lastpage or not count or first!=len(rows) or first+count>total:
            raise ValueError('Invalid page directory')
        lastpage=page
        for index in range(first,first+count):
            at=offset+3*index;word=int.from_bytes(blob[at:at+3],'little')
            rows.append((page+(word&32767),word>>15))
    if len(rows)!=total or rows!=sorted(rows):raise ValueError('Bounds order/count')
    pack_bounds(rows)
    return rows


def assemble_lookup24(address):
    from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
    from strict_compact_font import validate_thumb
    if address&3:raise ValueError('Word-aligned Thumb code')
    code=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(
        (ROOT/'asm/strict_stream_lookup24.s').read_text(),addr=address)[0])
    validate_thumb(code,1)
    return code
