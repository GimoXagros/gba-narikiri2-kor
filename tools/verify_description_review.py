"""Capture all selected item and monster descriptions using isolated save flags."""
import argparse,json,struct,ctypes as C
from pathlib import Path
from PIL import Image,ImageDraw
from verify_boot_notice import InputProbe
from build_description_review import sha
from build_hint_graphics import ROOT
from extract_dialogue_book_data import source_text
from narikiri2_text_spec import decode_game_text

def run(rom,core,save,out,kind):
    out.mkdir(parents=True,exist_ok=False)
    p=InputProbe(core,rom,out/'screens',save);p.lib.retro_set_controller_port_device.argtypes=[C.c_uint,C.c_uint];p.lib.retro_set_controller_port_device(0,1)
    data=rom.read_bytes();rows=json.loads((ROOT/'private_validation/description-review-20260923/review_full_private.json').read_text('utf-8'));rows={r['id']:r for r in rows if r['kind']==kind};results=[]
    for r in rows.values():
        r['final']=decode_game_text(data,source_text(data,r['storage'])[1]).replace('\u3000',' ')
        assert len(r['final'].split('\n'))<=2 and max(map(len,r['final'].split('\n')))<=18
    def f(n,keys=[]):p.execute(dict(op='frames',count=n,buttons=keys))
    def key(k,wait=60):f(6,[k]);f(wait)
    def write(a,old,new,reason):p.execute(dict(op='write_ram',address=hex(a),expected_hex=old.hex(),final_hex=bytes(new).hex(),test_fixture_only=True,reason=reason))
    glyphs=json.loads((ROOT/'config/private_glyph_order.json').read_text('utf-8'))['glyphs']
    font={ch:{data[off+i*32:off+(i+1)*32] for off in (0xC02000,0xC06000)} for i,ch in enumerate(glyphs)}
    def locate(text):
        v=p.read_memory(0x0600C000,0x4000);tiles=struct.unpack_from('<1024H',v,0x3800)
        def match(t,ch):
            t &= 1023
            return v[t*32:t*32+32] in font[ch] if ch in font else t==ord(ch)-16
        return [[x,y] for y in range(20) for x in range(32-len(text)) if all(match(tiles[y*32+x+i],ch) for i,ch in enumerate(text))]
    try:
        for n,k in [(60,[]),(6,['a']),(600,[]),(6,['start']),(90,[]),(6,['a']),(180,[])]:f(n,k)
        if kind=='monster':
            base=int.from_bytes(p.read_memory(0x02003ff0,4),'little');old=p.read_memory(base,160);new=bytearray(old)
            for start,count in [(0x22a,165),(0x2cf,165)]:
                for bit in range(start,start+count):new[bit//8]|=1<<(bit%8)
            write(base,old,new,'Isolated monster discovery flags; no exported save or natural unlock claim')
            key('select',90)
            for _ in range(8):key('down')
            key('a',90);key('a',90)
            order=[data[0x2c614c+i*4] for i in range(142)]
        else:
            base=int.from_bytes(p.read_memory(0x02003ff8,4),'little');old=p.read_memory(base+0xa2c,79);new=bytearray(b'\x11'*79);new[0]&=0xf0;new[78]&=0x0f
            write(base+0xa2c,old,new,'Isolated inventory grants one of each item; no exported gameplay save')
            for k in ['select','down','a','down','a']:key(k,60)
            order=list(range(1,157))
        for pos,rid in enumerate(order):
            if pos:key('down',30)
            f(60)
            positions=locate(rows[rid]['name'])
            if not positions:raise ValueError(f"Expected name absent: {kind} {rid} {rows[rid]['name']}")
            name=f'{pos+1:03d}_{rid:03d}.png';p.execute(dict(op='screenshot',name=name))
            results.append(dict(order=pos+1,id=rid,name=rows[rid]['name'],text=rows[rid]['final'],name_pixel_positions=positions,screenshot=name,widths=[len(s)*12 for s in rows[rid]['final'].split('\n')]))
        key('b');key('b');p.execute(dict(op='screenshot',name='return.png'))
    finally:p.lib.retro_unload_game();p.lib.retro_deinit()
    for start in range(0,len(results),24):
        batch=results[start:start+24];im=Image.new('RGB',(720,((len(batch)+2)//3)*68),(240,240,240));draw=ImageDraw.Draw(im)
        for i,r in enumerate(batch):
            x=i%3*240;y=i//3*68;draw.text((x+4,y+2),str(r['order'])+' / ID '+str(r['id']),fill='black')
            im.paste(Image.open(out/'screens'/r['screenshot']).crop((0,112,240,160)),(x,y+18))
        im.resize((1440,im.height*2),Image.Resampling.NEAREST).save(out/f'contact_{start//24:02d}.png')
    (out/'REPORT.json').write_text(json.dumps(dict(rom_sha256=sha(data),core_sha256=sha(core.read_bytes()),kind=kind,records=results,scope='All entries traversed with isolated inventory/discovery flags; screenshots and source-bound 18x2 checks, not natural acquisition.'),ensure_ascii=False,indent=2),'utf-8')
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('rom','core','save','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--kind',choices=['item','monster'],required=True);a=p.parse_args();run(a.rom,a.core,a.save,a.out,a.kind)
