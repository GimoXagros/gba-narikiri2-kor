"""Read-only active asset extents for the frozen strict-layout investigation.

Matched code or asset bytes establish a named owner, not complete reference
closure or permission to reuse surrounding padding. No ROM is emitted here.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import struct

from build_banked_font import assemble
from find_gba_lz77_asset import decompress_lz77_stream
from narikiri2_item_ui_font import compress_lz77
from verify_jp8mib_strict import source_identity

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():raise ValueError('Choose a new output folder')
    jp=(ROOT/'Japanese.gba').read_bytes()
    kr=(ROOT/'private_validation/listperf-20261002/root/credits-build-a/Xagros_Narikiri2_KOR_v1.0_listperf-pass01_credits_TEST.gba').read_bytes()
    source_identity(jp,kr)
    assets=[];unmatched=[]
    def add(name,start,size,evidence,consumer):
        data=kr[start:start+size]
        if len(data)!=size:raise ValueError('Asset outside baseline')
        assets.append(dict(name=name,start=f'{start:08X}',end=f'{start+size:08X}',bytes=size,
            sha256=hashlib.sha256(data).hexdigest(),evidence=evidence,consumer=consumer,
            placement='NOT_PLACED_INSIDE_8MIB'))
    for index,name in ((9,'korean_title'),(16,'copyright')):
        storage=0x3768F8+4+4*index
        start=0x3768F8+struct.unpack_from('<I',kr,storage)[0]
        raw,used=decompress_lz77_stream(kr,start,0x20000)
        add(name,start,used,f'actual relative pointer at {storage:08X}; bounded LZ read',f'title resource {index}')
    for start,name,storage in ((0xc18000,'ascii_dalmoori',0x2158),(0xc86000,'native_staff',None)):
        raw,used=decompress_lz77_stream(kr,start,0x20000)
        if storage and struct.unpack_from('<I',kr,storage)[0]!=0x08000000+start:
            raise ValueError('Font pointer mismatch')
        add(name,start,used,'actual LZ extent'+(f'; pointer {storage:08X}' if storage else '; ending wrapper literal'),'small font decode')
    count=len(json.loads((ROOT/'config/private_glyph_order.json').read_text(encoding='utf-8'))['glyphs'])
    specs=[('boot_notice',0xc90000,512),('ending_original_font',0xc86f00,128),
      ('banked_small',0xc00000,256),('banked_simple',0xc00100,256),('banked_full_name',0xc00200,256),
      ('banked_convert',0xc00300,256),('banked_decode',0xc00500,256),('banked_get_tile',0xc00600,256),
      ('banked_popup',0xc00c00,1024),('banked_name_import',0xc01000,512),('banked_name_commit',0xc01200,256),
      ('banked_name_init_first',0xc01400,128),('banked_name_init_second',0xc01480,128),
      ('banked_actor_name_store',0xc1e800,128),('banked_actor_name_resolve',0xc1e880,128),
      ('banked_actor_monster_init',0xc1e900,128),('banked_actor_party_init',0xc1e980,128),
      ('banked_actor_small_entry',0xc1ea00,128),('banked_actor_format_string',0xc1ea80,128),
      ('banked_battle_font_upload',0xc1eb00,128)]
    for name,start,limit in specs:
        body=assemble(ROOT/'asm'/(name+'.s'),start,count,limit)
        if kr[start:start+len(body)]!=body:
            unmatched.append(name)
            continue
        add(name,start,len(body),'exact reassembly matches baseline; reference closure still required','known build-chain entry')
    if 'boot_notice' in unmatched:raise ValueError('Cannot establish notice pixel consumer')
    pixels=kr[0xc91000:0xca3c00]
    add('notice_pixels',0xc91000,len(pixels),'matched boot_notice: C91000 source, 38400 halfwords','original copy loop')
    packed=compress_lz77(pixels,vram_safe=True)
    decoded,used=decompress_lz77_stream(packed,0,0x20000)
    if decoded!=pixels or not used<=len(packed)<used+4 or any(packed[used:]):
        raise ValueError('Notice compression roundtrip/padding')
    # This is non-display CpuSet data, explicitly excluded from the text audit.
    jp_sig=struct.unpack_from('<I',jp,0xa1e4)[0]-0x08000000
    ko_sig=struct.unpack_from('<I',kr,0xa1e4)[0]-0x08000000
    if jp_sig!=0x2bf4c8 or ko_sig!=0x9513e8 or jp_sig%4 or ko_sig%4:
        raise ValueError('Save signature source profile changed')
    if jp[jp_sig:jp_sig+8]!=kr[ko_sig:ko_sig+8] or jp[jp_sig:jp_sig+8]!=b'NARIKIRI':
        raise ValueError('Save signature payload changed')
    if jp[0xa1c8:0xa1e4]!=kr[0xa1c8:0xa1e4] or jp[0xa6024:0xa6028]!=kr[0xa6024:0xa6028]:
        raise ValueError('Signature copy consumer changed')
    signature=dict(status='IDENTICAL_ALIGNED_JP_SOURCE_AVAILABLE_NOT_APPLIED',pointer_storage='0000A1E4',
        current_source=f'{ko_sig:08X}',jp_source=f'{jp_sig:08X}',bytes=8,
        consumer='0800A1CA literal load, 0800A1D2 call to 080A6024 CpuSet wrapper',
        runtime_save_validation='NOT_RUN',legacy_save_guard='UNCHANGED')
    spans=sorted(assets,key=lambda x:int(x['start'],16))
    if any(int(a['end'],16)>int(b['start'],16) for a,b in zip(spans,spans[1:])):
        raise ValueError('Named asset overlap')
    args.out.mkdir(parents=True)
    with (args.out/'ACTIVE_ASSETS.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=assets[0]);w.writeheader();w.writerows(assets)
    (args.out/'notice_pixels_lz77.bin').write_bytes(packed)
    report=dict(status='READ_ONLY_MATCHED_ASSETS_NOT_RELOCATED',count=len(assets),
        sum_bytes=sum(x['bytes'] for x in assets),unmatched_sources=unmatched,
        notice_raw_bytes=len(pixels),notice_lossless_lz77_bytes=len(packed),
        notice_saving_bytes=len(pixels)-len(packed),notice_decoder_integration='NOT_IMPLEMENTED',
        signature=signature,scope='Named ranges only; no unowned extension byte declared dead/free')
    (args.out/'ASSET_REPORT.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()
