"""In-place restoration of proven relative UI resource-table bindings."""
import struct
from find_gba_lz77_asset import decompress_lz77_stream
from gba_rl import decompress as decompress_rl
from narikiri2_item_ui_font import compress_lz77
from strict_layout_core import Write, sha

TABLES = ((0x3768F8, 20), (0x380F08, 135), (0x3A7ADC, 87))
EXTERNALLY_OWNED = {(0x3768F8,9), (0x3768F8,16), (0x380F08,6), (0x380F08,7)}


def read_resource(image, start):
    if not 0 <= start <= len(image)-4:
        raise ValueError('Resource address outside source')
    tag = image[start] & 0xF0
    if tag == 0x30:
        return decompress_rl(image, start, allow_padding=True)
    if tag == 0x10:
        result = decompress_lz77_stream(image, start, 0x20000)
        if result is None:raise ValueError('Invalid resource LZ stream')
        return result
    raise ValueError('Unsupported resource compression type')


def plan(japanese, adopted):
    writes, records = [], []
    for table, count in TABLES:
        if struct.unpack_from('<I', japanese, table)[0] != count:
            raise ValueError('Original resource table count')
        if adopted[table:table+4] != japanese[table:table+4]:
            raise ValueError('Adopted resource table count')
        starts = [table+struct.unpack_from('<I',japanese,table+4+i*4)[0] for i in range(count)]
        for i, start in enumerate(starts):
            at = table+4+i*4
            adopted_start = table+struct.unpack_from('<I',adopted,at)[0]
            if adopted_start == start or (table,i) in EXTERNALLY_OWNED:continue
            original, cap = read_resource(japanese,start)
            native, used = read_resource(adopted,adopted_start)
            if len(native) != len(original):raise ValueError('In-place resource geometry changed')
            packed = compress_lz77(native,vram_safe=True)
            if len(packed)>cap or (i+1<count and start+cap>starts[i+1]):
                raise ValueError('In-place resource exceeds proved consumed extent')
            if read_resource(packed,0)[0]!=native:raise ValueError('Resource roundtrip differs')
            for label,offset,data in [('stream',start,packed),('relative',at,japanese[at:at+4])]:
                writes.append(Write(f'asset:relative_{table:06x}_{i}_{label}',offset,
                    japanese[offset:offset+len(data)],data,
                    'same adopted native resource in original consumed slot',
                    f'original relative resource table {table:06x} index {i}',
                    'frozen Japanese/adopted sources and lossless LZ roundtrip',
                    ('source_identity','original_relative_value','bounded_native_roundtrip')))
            records.append(dict(table=table,index=i,start=start,adopted_start=adopted_start,
                original_consumed=cap,adopted_consumed=used,packed_bytes=len(packed),
                native_bytes=len(native),native_sha256=sha(native)))
    return writes,records
