"""Scroll actual encyclopedia screens with isolated discovery-bit fixtures."""
import argparse,csv,hashlib,json,struct
from pathlib import Path
from PIL import Image
from libretro_probe import Probe

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-dir',type=Path,required=True)
    p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--core',type=Path,required=True)
    p.add_argument('--save',type=Path,required=True)
    p.add_argument('--entry-route',type=Path,required=True)
    p.add_argument('--book',choices=('monster','costume','character'),required=True)
    p.add_argument('--details',action='store_true')
    p.add_argument('--limit',type=int)
    p.add_argument('--start',type=int,default=0)
    p.add_argument('--detail-pages',type=int,default=0)
    a=p.parse_args()
    m=json.loads((a.build_dir/'BUILD_MANIFEST.json').read_text(encoding='utf-8'))
    path=a.build_dir/'NARIKIRI2_BANKED_ENGINE_DIAGNOSTIC.gba'; rom=path.read_bytes()
    if hashlib.sha256(rom).hexdigest()!=m['target_rom_sha256']:raise ValueError('Artifact mismatch')
    with (a.build_dir/'names.csv').open(encoding='utf-8',newline='') as f:names={r['id']:r['text'] for r in csv.DictReader(f)}
    families={'monster':('MONSTER',[rom[0x2C614C+i*4] for i in range(142)]),
              'costume':('JOB',list(rom[0x2BC164:0x2BC164+200])),
              'character':('CHARACTER_BOOK',list(range(22)))}
    family,order=families[a.book]
    if len(set(order))!=len(order):raise ValueError('Duplicate book record mapping')
    h=Probe(a.core,path,a.run_dir,
            a.save)
    def frames(n,keys=()):h.execute(dict(op='frames',count=n,buttons=list(keys)))
    def press(k,wait=45):frames(6,(k,));frames(wait)
    def shot(name):h.execute(dict(op='screenshot',name=name+'.png'))
    font={ch:{rom[off+i*32:off+(i+1)*32] for off in (0xC02000,0xC06000)} for i,ch in enumerate(m['glyphs'])}
    def locate(text):
        v=h.read_memory(0x0600C000,0x4000)
        tiles=struct.unpack_from('<1024H',v,0x3800)
        def match(tile,ch):
            tile &=1023
            if ch in font:return v[tile*32:tile*32+32] in font[ch]
            return tile==ord(ch)-16
        positions=[]
        for y in range(20):
            for x in range(31-len(text)):
                if all(match(tiles[y*32+x+i],ch) for i,ch in enumerate(text)):
                    positions.append([x,y])
        return positions
    try:
        log=a.entry_route
        for row in map(json.loads,log.read_text(encoding='utf-8').splitlines()):
            if row['frame']>1614:break
            request=row.get('request',{})
            if request.get('op')=='frames':h.execute(request)
        base=int.from_bytes(h.read_memory(0x02003ff0,4),'little')
        if base&3 or not 0x02000000<=base<base+160<=0x02040000:raise ValueError('Flag base mismatch')
        before=h.read_memory(base,160); after=bytearray(before)
        for start,count in ((0x22A,165),(0x2CF,165),(0x374,201),(0x453,22)):
            for bit in range(start,start+count):after[bit//8]|=1<<(bit%8)
        h.execute(dict(op='write_ram',address=hex(base),expected_hex=before.hex(),final_hex=after.hex(),
            test_fixture_only=True,reason='Set only decoded monster discovery/inspection, costume discovery and character-book flags for renderer coverage; never exported as gameplay save'))
        for _ in range(('monster','costume','character').index(a.book)):press('down')
        press('a',120);shot('opened')
        observations=[];covered=set();artes=set()
        for step,rid in enumerate(order):
            if a.limit is not None and step>=a.start+a.limit:break
            if step:press('down')
            if step<a.start:continue
            expected=names[f'{family}_{rid:03d}'];positions=locate(expected)
            shot(f'row_{step:03d}')
            if not positions:raise ValueError(f'{a.book} step {step} record {rid}: expected name absent: {expected}')
            covered.add(rid);observations.append(dict(step=step,record_id=rid,text=expected,positions=positions))
            if a.details:
                bottom=Image.open(a.run_dir/f'row_{step:03d}.png').crop((0,114,240,160)).tobytes()
                press('a',120);shot(f'detail_{step:03d}')
                if a.book=='character':
                    for page in range(8):
                        press('a',120);shot(f'detail_{step:03d}_page_{page}')
                        image=Image.open(a.run_dir/f'detail_{step:03d}_page_{page}.png')
                        if image.crop((0,114,240,160)).tobytes()==bottom:break
                    else:raise ValueError('Character biography did not return to its selection prompt')
                else:
                    for page in range(a.detail_pages):
                        press('right',90);shot(f'detail_{step:03d}_right_{page}')
                        if a.book=='costume' and page%2==0:
                            for j in range(10):
                                skill=rom[0x2B580C+rid*64+0x14+j*4]
                                if skill:
                                    text=names[f'ARTE_{skill:03d}']
                                    if not locate(text):raise ValueError(f'Costume {rid}: skill {skill} text absent or overwritten: {text}')
                                    artes.add(skill)
                    press('b',120)
                shot(f'return_{step:03d}')
                if not locate(expected):raise ValueError('Detail return did not restore the expected list name')
        report=dict(status='PASS_ACTUAL_BOOK_LIST_PIXELS',rom_sha256=m['target_rom_sha256'],book=a.book,
            fixture_modified=True,natural_unlock_verified=False,records=len(covered),observations=observations,
            detail_screens_captured=len(covered) if a.details else 0,
            complete_book_coverage=len(covered)==len(order),
            actual_arte_names_verified=len(artes),arte_ids=sorted(artes),
            limitations=['Discovery flags set in isolated RAM only','List scroll coverage; detail, battle and other consumers are separate claims'])
        (a.run_dir/'BOOK_MATRIX.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k!='observations'},ensure_ascii=False))
    finally:h.lib.retro_unload_game();h.lib.retro_deinit()

if __name__=='__main__':main()
