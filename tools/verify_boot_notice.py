"""Verify exact notice pixels, held input, all GBA buttons and title resources."""
import argparse
import ctypes as C
import json
import struct
from pathlib import Path
from PIL import Image
from libretro_probe import Probe
from build_boot_notice import sha
from build_title_credits import TABLE
from find_gba_lz77_asset import decompress_lz77_stream

class InputProbe(Probe):
    def __init__(self,*args):
        self.log_callback=C.CFUNCTYPE(None,C.c_int,C.c_char_p)(lambda *_:None)
        super().__init__(*args)
    def environment(self,command,data):
        if command & 0xffff == 27:
            C.cast(data,C.POINTER(C.c_void_p))[0]=C.cast(self.log_callback,C.c_void_p).value
            return True
        return super().environment(command,data)

def run(rom,core,screen,out,save=None):
    out.mkdir(parents=True,exist_ok=False)
    expected=Image.open(screen).convert('RGB').tobytes()
    data=rom.read_bytes();checks={}
    for key in ('a','b','start','select','up','down','left','right','l','r'):
        p=InputProbe(core,rom,out/key,save)
        p.lib.retro_set_controller_port_device.argtypes=[C.c_uint,C.c_uint]
        p.lib.retro_set_controller_port_device(0,1)
        try:
            p.execute({'op':'frames','count':120,'buttons':[key]})
            p.execute({'op':'screenshot','name':'held_at_boot.png'})
            assert Image.open(out/key/'held_at_boot.png').convert('RGB').tobytes()==expected
            p.execute({'op':'frames','count':120})
            p.execute({'op':'screenshot','name':'released.png'})
            assert Image.open(out/key/'released.png').convert('RGB').tobytes()==expected
            p.execute({'op':'frames','count':6,'buttons':[key]})
            p.execute({'op':'frames','count':600})
            p.execute({'op':'screenshot','name':'title.png'})
            vram=p.read_memory(0x06010000,0x8000)
            for index,start in ((9,0),(16,0x4e00)):
                offset=TABLE+struct.unpack_from('<I',data,TABLE+4+index*4)[0]
                raw,_=decompress_lz77_stream(data,offset,0x20000)
                assert vram[start:start+len(raw)]==raw
            checks[key]='PASS: held input guarded; fresh press/release reaches original title assets'
            if key=='a' and save:
                p.execute({'op':'frames','count':6,'buttons':['start']})
                p.execute({'op':'frames','count':90})
                p.execute({'op':'screenshot','name':'continue_menu.png'})
                p.execute({'op':'frames','count':6,'buttons':['a']})
                p.execute({'op':'frames','count':180})
                p.execute({'op':'screenshot','name':'loaded_save.png'})
        finally:
            p.lib.retro_unload_game();p.lib.retro_deinit()
    report={'rom_sha256':sha(data),'core_sha256':sha(core.read_bytes()),'checks':checks,
            'save_input_sha256':sha(save.read_bytes()) if save else None,
            'scope':'Headless core verification; save screenshot requires visual review'}
    (out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('rom','core','screen','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--save',type=Path);a=p.parse_args()
    run(a.rom,a.core,a.screen,a.out,a.save)
