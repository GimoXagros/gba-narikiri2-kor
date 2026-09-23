"""Frame-stepped title / full staff-roll verification, with a disclosed entry fixture."""
import argparse
import json
from pathlib import Path
import struct

from build_title_credits import APPEND, CREDITS_TARGET, TABLE, sha
from find_gba_lz77_asset import decompress_lz77_stream
from libretro_probe import Probe


def close(probe):
    probe.lib.retro_unload_game()
    probe.lib.retro_deinit()


def run(rom_path, core, out):
    out.mkdir(parents=True,exist_ok=False)
    rom=rom_path.read_bytes()
    report={'rom_sha256':sha(rom),'core_sha256':sha(core.read_bytes()),'checks':{}}
    title=Probe(core,rom_path,out/'title',None)
    try:
        title.execute({'op':'frames','count':600})
        title.execute({'op':'screenshot','name':'title.png'})
        vram=title.read_memory(0x06010000,0x8000)
        for index,loaded_at,size in ((9,0,17088),(16,0x4E00,3328)):
            offset=TABLE+struct.unpack_from('<I',rom,TABLE+4+index*4)[0]
            decoded,_=decompress_lz77_stream(rom,offset,0x20000)
            if len(decoded)!=size or decoded!=vram[loaded_at:loaded_at+size]:
                raise ValueError(f'Resource {index} is not consumed at expected OBJ VRAM')
            report['checks'][f'resource_{index}_runtime_load']='PASS'
        title.execute({'op':'frames','count':6,'buttons':['start']})
        title.execute({'op':'frames','count':90})
        title.execute({'op':'screenshot','name':'start_menu.png'})
        report['checks']['title_cold_boot_and_start_menu']='PASS; screenshots require visual review'
    finally:
        close(title)
    # One function-table entry invokes the real ending routine at boot. All
    # staff assets/code, pointers, timing and final save prompt remain product
    # bytes. This is consumer verification, not natural story completion.
    fixture=bytearray(rom)
    if fixture[0x3746D8:0x3746DC]!=bytes.fromhex('5daa0008'):
        raise ValueError('Original boot dispatch slot changed')
    fixture[0x3746D8:0x3746DC]=bytes.fromhex('d9520a08')
    path=out/'ending_entry_fixture.gba';path.write_bytes(fixture)
    report['ending_entry_fixture']={'rom_sha256':sha(fixture),'offset':'0x3746D8',
        'before':'5daa0008','after':'d9520a08',
        'purpose':'Invoke original ending routine via boot dispatch; no RAM intervention',
        'limitation':'Does not prove natural story completion or cleared-save compatibility'}
    ending=Probe(core,path,out/'ending',None)
    try:
        for _ in range(5):ending.execute({'op':'frames','count':1200})
        ending.execute({'op':'frames','count':600})
        ending.execute({'op':'screenshot','name':'namco_and_korean_credits.png'})
        vram=ending.read_memory(0x06000000,0x18000)
        native,_=decompress_lz77_stream(rom,0xC86000,0x10000)
        if vram[0xC000:0xE000]!=native:
            raise ValueError('Staff ASCII font does not match original in live VRAM')
        report['checks']['native_ascii_staff_font_in_vram']='PASS; all 8192 bytes'
        for text in ('YOICHI HARAGUCHI','KYUSHIRO TAKAGI','MASAYA NAKAMURA',
                     '-KOREAN TRANSLATION-','TEAM FFR','XAGROS','(SPECIAL THANKS)','AND YOU'):
            # The observed staff renderer emits ASCII - 0x10, palette bank 12.
            tiles=b''.join(struct.pack('<H',(ord(ch)-0x10)|0xC000) for ch in text)
            at=vram.find(tiles)
            if at<0:raise ValueError(f'Credit line not in live tilemap: {text}')
            report['checks']['live_staff_line_'+text]={'status':'PASS','vram':hex(0x06000000+at)}
        ending.execute({'op':'frames','count':240})
        ending.execute({'op':'screenshot','name':'korean_credits_scrolling.png'})
        ending.execute({'op':'frames','count':3600})
        ending.execute({'op':'screenshot','name':'clear_save_prompt.png'})
        report['checks']['ending_tail']='PASS; frame 10440 save prompt screenshot requires visual review'
    finally:
        close(ending)
    (out/'RUNTIME_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True)
    p.add_argument('--core',type=Path,required=True)
    p.add_argument('--out-dir',type=Path,required=True)
    a=p.parse_args();run(a.rom,a.core,a.out_dir)
