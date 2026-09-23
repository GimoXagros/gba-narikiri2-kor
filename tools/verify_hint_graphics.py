"""Verify native hint ink through real map/menu consumers, including VBA-M."""
import argparse,json,struct,ctypes as C
from pathlib import Path
from PIL import Image,ImageDraw
from libretro_probe import Probe
from verify_boot_notice import InputProbe
from build_hint_graphics import HINTS,bitmap,sha
from gba_rl import decompress

def run(rom,core,save,out,fixtures=False):
    out.mkdir(parents=True,exist_ok=False);data=rom.read_bytes();checks=[]
    cases=[None]+(list(HINTS)+[44] if fixtures else [])
    for case in cases:
        current=bytearray(data);label='natural' if case is None else f'asset-{case}'
        if case is not None:
            # Test-only table substitution: load each 32x8 hint at the existing
            # clothes prefix position. Blank following piece prevents overlap.
            table=0x3A7ADC
            current[table+4+36*4:table+8+36*4]=data[table+4+case*4:table+8+case*4]
            current[table+4+39*4:table+8+39*4]=data[table+4+34*4:table+8+34*4]
            path=out/'loader_fixture.gba';path.write_bytes(current)
        else:path=rom
        folder=out/label;p=InputProbe(core,path,folder,save)
        p.lib.retro_set_controller_port_device.argtypes=[C.c_uint,C.c_uint];p.lib.retro_set_controller_port_device(0,1)
        def frames(n,keys=[]):p.execute(dict(op='frames',count=n,buttons=keys))
        def verify(raw,x,y,palette,name):
            vram=p.read_memory(0x06010000,0x8000);assert raw in vram,'Expected native hint missing from VRAM'
            if not (folder/(name+'.png')).exists():p.execute(dict(op='screenshot',name=name+'.png'))
            im=Image.open(folder/(name+'.png')).convert('RGB');pal=p.read_memory(0x05000200+palette*32,32);count=0
            for xx in range(len(raw)//4):
                for yy in range(8):
                    value=raw[(xx//8)*32+yy*4+xx%8//2]>>(4*(xx%2))&15
                    if not value:continue
                    c=struct.unpack_from('<H',pal,value*2)[0];expected=((c&31)*255//31,((c>>5)&31)*2*255//63,((c>>10)&31)*255//31)
                    actual=im.getpixel((x+xx,y+yy))
                    assert all(abs(a-b)<=5 for a,b in zip(actual,expected)),(name,xx,yy,actual,expected)
                    count+=1
            return count
        try:
            for n,b in [(60,[]),(6,['a']),(600,[]),(6,['start']),(90,[]),(6,['a']),(180,[])]:frames(n,b)
            if case is None:
                count=verify(bitmap('소문은',32,8,12),8,28,1,'town')
                count+=verify(bitmap('LR',16,8,12),40,28,1,'town')
                checks.append(dict(screen='town',pixels=count,status='PASS'))
            for key in ['select','down','down','a','a','a']:frames(6,[key]);frames(60)
            # Natural menu hint blinks every32frames. This route ends in visible phase.
            if case is None:
                count=verify(bitmap('LR로',32),156,104,0,'clothes')
                count+=verify(bitmap('정보',32),180,104,0,'clothes')
            else:count=verify(decompress(data,0x3AC014,allow_padding=True)[0] if case==44 else bitmap(HINTS[case],32),156,104,0,'hint')
            checks.append(dict(screen=label,pixels=count,status='PASS',fixture_only=case is not None))
        finally:p.lib.retro_unload_game();p.lib.retro_deinit()
    if fixtures:
        sheet=Image.new('RGB',(480,len(HINTS)*40),(30,30,30));d=ImageDraw.Draw(sheet)
        for n,case in enumerate(HINTS):
            im=Image.open(out/f'asset-{case}'/'hint.png');sheet.paste(im.crop((154,103,190,113)).resize((144,40),Image.Resampling.NEAREST),(120,n*40));d.text((8,n*40+12),str(case),fill='white')
        sheet.save(out/'all_hint_assets.png')
    (out/'REPORT.json').write_text(json.dumps(dict(product_sha256=sha(data),core_sha256=sha(core.read_bytes()),checks=checks,scope='Natural saved-game map/clothes routes; other assets tested by explicit loader substitution, not all gameplay routes.'),ensure_ascii=False,indent=2),'utf-8')
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('rom','core','save','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--fixtures',action='store_true');a=p.parse_args();run(a.rom,a.core,a.save,a.out,a.fixtures)
