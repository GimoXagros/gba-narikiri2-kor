"""Exercise every place asset through the real map label loader using table fixtures."""
import argparse,json,struct
from pathlib import Path
from PIL import Image,ImageDraw
from libretro_probe import Probe
from build_place_names import NAMES,graphic,sha

def run(rom,core,save,out):
    out.mkdir(parents=True,exist_ok=False);data=rom.read_bytes()
    table=struct.unpack_from('<I',data,0xCAEC)[0]-0x08000000
    rows=[];sheet=Image.new('RGB',(640,22*40),(32,32,32));draw=ImageDraw.Draw(sheet)
    for row,text in enumerate(NAMES,3):
        fixture=bytearray(data);fixture[table+24:table+32]=data[table+8*row:table+8*row+8]
        path=out/'loader_fixture.gba';path.write_bytes(fixture)
        folder=out/f'{row:02d}'
        p=Probe(core,path,folder,save)
        try:
            for count,buttons in [(60,[]),(6,['a']),(600,[]),(6,['start']),(90,[]),(6,['a']),(180,[])]:
                p.execute({'op':'frames','count':count,'buttons':buttons})
            p.execute({'op':'screenshot','name':'place.png'})
            raw,width=graphic(text)
            vram=p.read_memory(0x06010000,0x8000)
            assert raw in vram,'Place asset not present in OBJ VRAM'
            screen=Image.open(folder/'place.png').convert('RGB')
            # Check the exact displayed lettering pixels through the current OAM.
            pal=p.read_memory(0x05000200,32)
            def color(v):
                c=struct.unpack_from('<H',pal,v*2)[0]
                return ((c&31)*255//31,((c>>5)&31)*2*255//63,((c>>10)&31)*255//31)
            checked=0
            for x in range(width):
                for y in range(16):
                    at=(x//32)*256+((y//8)*4+(x%32)//8)*32+y%8*4+x%8//2
                    value=raw[at]>>(x%2*4)&15
                    if value:
                        actual=screen.getpixel((8+x,8+y));expected=color(value)
                        assert all(abs(a-b)<=1 for a,b in zip(actual,expected)),(row,x,y,actual,expected)
                        checked+=1
            # Native rows doubled fit 40px per label; no screenshot resynthesis.
            strip=screen.crop((0,7,130,25)).resize((260,36),Image.Resampling.NEAREST)
            sheet.paste(strip,(42,(row-3)*40));draw.text((4,(row-3)*40+8),str(row),fill='white')
            rows.append({'row':row,'text':text,'status':'PASS','ink_pixels_checked':checked,'fixture_sha256':sha(fixture)})
        finally:p.lib.retro_unload_game();p.lib.retro_deinit()
    sheet.save(out/'all_places.png')
    (out/'REPORT.json').write_text(json.dumps({'product_sha256':sha(data),'rows':rows,
        'scope':'All 22 labels rendered by real town loader, church label row substituted per case. Does not assert natural travel to every dungeon.'},ensure_ascii=False,indent=2)+'\n','utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('rom','core','save','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.rom,a.core,a.save,a.out)
