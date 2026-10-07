"""Restore adopted map labels inside audited original graphic resource owners.

These are sprite resources, not text streams.  No text pointer is relocated.
"""
import struct
from strict_layout_core import Write, sha
from strict_relative_assets import read_resource
from narikiri2_item_ui_font import compress_lz77


def word(image, at):
    return struct.unpack_from('<I', image, at)[0]


def plan(japanese, adopted):
    original_table, original_labels = 0x380F08, 0x2C23B8
    table, labels = word(adopted, 0xCAF0)-0x08000000, word(adopted, 0xCAEC)-0x08000000
    if table != 0xCA4000 or labels != 0xCA4220:
        raise ValueError('Frozen map source tables changed')
    if word(japanese, original_table) != 135 or word(adopted, table) != 135:
        raise ValueError('Map table count changed')
    starts = [original_table+word(japanese, original_table+4+4*i) for i in range(135)]
    resources = []
    for i in range(135):
        source = (table+word(adopted, table+4+4*i))&0xFFFFFFFF
        prior_source = original_table+word(adopted, original_table+4+4*i)
        if not 9 <= i <= 30:
            if source != prior_source and i not in (6,7):
                raise ValueError('Unclassified map resource change')
            continue
        native, _ = read_resource(adopted, source)
        packed = compress_lz77(native, vram_safe=True)
        if read_resource(packed, 0)[0] != native:
            raise ValueError('Map graphic roundtrip changed')
        resources.append((i, native, packed))
    for i in range(9, 31):
        _, consumed = read_resource(japanese, starts[i])
        gap = starts[i+1]-(starts[i]+consumed)
        if gap not in range(4):
            raise ValueError('Map family has unowned interior gap')
    # Reject unrelated absolute references into the resource pool.  The proven
    # map table uses relative offsets and is the sole observed ROM owner.
    pool_start, pool_end = starts[9], starts[31]
    pointer_shapes = []
    for at in range(0, len(japanese)-3, 4):
        ptr = word(japanese, at)-0x08000000
        if pool_start <= ptr < pool_end:
            # A voice table points to this WaveData header.  The pointer-
            # shaped word is inside its 4,009 signed PCM sample bytes.
            if (at!=0x131354 or ptr!=0x3824EA or
                japanese[0x13075C:0x13076C]!=struct.pack('<4I',0,0x7D0000,0,0xFA9) or
                word(japanese,0xCC654)!=0x0813075C or
                adopted[0xCC654:0xCC658]!=japanese[0xCC654:0xCC658] or
                japanese[0x13075C:0x131715]!=adopted[0x13075C:0x131715]):
                raise ValueError(f'Unclassified absolute map-pool reference {at:x}')
            pointer_shapes.append(dict(storage=at,value=ptr+0x08000000,
                classification='referenced_pcm_sample_unchanged',
                header=0x13075C,reference=0xCC654,data=[0x13076C,0x131715]))
    arenas = [[pool_start, pool_end]]
    for i in (10,13,14,15):
        old = 0x3768F8+word(japanese, 0x3768FC+i*4)
        source = 0x3768F8+word(adopted, 0x3768FC+i*4)
        _, cap = read_resource(japanese, old)
        native, _ = read_resource(adopted, source)
        size = len(compress_lz77(native, vram_safe=True))
        arenas.append([(old+size+3)&~3, old+cap])
    initial_arenas = [a[:] for a in arenas]
    def allocate(size):
        for arena in arenas:
            start = (arena[0]+3)&~3
            if start+size <= arena[1]:
                arena[0] = start+size
                return start
        raise ValueError(f'Map owner allocation overflow: {size}')
    writes, records = [], []
    def put(name, at, data):
        writes.append(Write('asset:map_'+name,at,japanese[at:at+len(data)],data,
            'same adopted map sprites in audited resource owners',
            'original map resource family or bounded retired title resource suffix',
            'exact source guards and decompressed native resource comparison',
            ('source_identity','owned_extent','native_roundtrip')))
    for i, native, packed in sorted(resources, key=lambda r:(-len(r[2]),r[0])):
        dest = allocate(len(packed))
        put(f'resource_{i}',dest,packed)
        put(f'relative_{i}',original_table+4+4*i,struct.pack('<I',(dest-original_table)&0xFFFFFFFF))
        records.append(dict(index=i,start=dest,packed_bytes=len(packed),
            native_bytes=len(native),native_sha256=sha(native)))
    for i in (6,7):
        source = (table+word(adopted, table+4+4*i))&0xFFFFFFFF
        native, _ = read_resource(adopted,source)
        original, cap = read_resource(japanese,starts[i])
        packed = compress_lz77(native,vram_safe=True)
        if len(native)!=len(original) or len(packed)>cap:
            raise ValueError('Active map hint exceeds original geometry/slot')
        put(f'active_hint_{i}',starts[i],packed)
        at=original_table+4+4*i
        put(f'active_hint_relative_{i}',at,japanese[at:at+4])
    if adopted[labels:labels+24] != japanese[original_labels:original_labels+24]:
        raise ValueError('First three native map labels changed')
    layouts = []
    for row in range(3,25):
        old_row = original_labels+8*row
        new_row = labels+8*row
        old_frame = word(japanese,old_row)-0x08000000
        new_frame = word(adopted,new_row)-0x08000000
        if word(japanese,old_frame)!=1 or word(adopted,new_frame)!=1:
            raise ValueError('Map label frame count changed')
        old_layout = word(japanese,old_frame+4)-0x08000000
        new_layout = word(adopted,new_frame+4)-0x08000000
        old_size = 4+8*word(japanese,old_layout)
        new_size = 4+8*word(adopted,new_layout)
        if not 4 <= old_size <= 36 or not 4 <= new_size <= 36:
            raise ValueError('Map sprite layout count')
        destination = old_layout if new_size <= old_size else allocate(new_size)
        put(f'label_{row}',old_row,struct.pack('<I',old_frame+0x08000000)+adopted[new_row+4:new_row+8])
        put(f'frame_{row}',old_frame,adopted[new_frame:new_frame+4]+struct.pack('<I',destination+0x08000000))
        put(f'layout_{row}',destination,adopted[new_layout:new_layout+new_size])
        layouts.append(dict(row=row,frame=old_frame,layout=destination,size=new_size))
    for at in (0xCAEC,0xCAF0):
        put(f'caller_{at:x}',at,japanese[at:at+4])
    ordered = sorted(writes,key=lambda w:w.start)
    if any(a.end>b.start for a,b in zip(ordered,ordered[1:])):
        raise ValueError('Map write ownership overlaps')
    return writes,dict(resources=records,layouts=layouts,arenas=initial_arenas,
        remaining=arenas,packed_bytes=sum(len(r[2]) for r in resources),
        pointer_shapes=pointer_shapes)
