import sys,json,struct
from pathlib import Path
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tools'))
from libretro_probe import Probe
import argparse
parser=argparse.ArgumentParser(description='Capture all 231 arte descriptions through the ordinary skill menu with isolated known-arte RAM fixtures.')
for name in ('rom','core','save','output'): parser.add_argument('--'+name,type=Path,required=True)
a=parser.parse_args()
rom=a.rom;base=a.output;save=a.save
if base.exists():raise FileExistsError('Choose a fresh private evidence directory')
results=[]
for start in range(1,232,10):
 ids=list(range(start,min(start+10,232)));h=Probe(a.core,rom,base/f'group-{start:03d}',save)
 def f(n,k=()):h.execute(dict(op='frames',count=n,buttons=list(k)))
 def p(k):f(6,[k]);f(90)
 try:
  f(600);f(6,['start']);f(180);f(6,['a']);f(240)
  address=0x200325c;old=h.read_memory(address,56);n=bytearray(old)
  n[0]=10;n[1]=15;n[0x1b:0x25]=bytes(ids)+bytes(10-len(ids));n[0x25:0x29]=bytes([ids[0],0,0,0]);n[0x2c:0x30]=struct.pack('<I',(1<<len(ids))-1)
  h.execute(dict(op='write_ram',address=hex(address),expected_hex=old.hex(),final_hex=n.hex(),test_fixture_only=True,reason='Isolated known-arte slots exercise description capacity through the ordinary skill menu; not natural learning, combat legality or save evidence'))
  for k in ['select','a','a','a']:p(k)
  for i,rid in enumerate(ids):
   if i:p('down')
   s=h.execute(dict(op='screenshot',name=f'arte_{rid:03d}.png'));results.append(dict(id=rid,**s))
 finally:h.lib.retro_unload_game();h.lib.retro_deinit()
 print(start,flush=True)
(base/'RESULTS.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
for page in range((len(results)+23)//24):
 batch=results[page*24:page*24+24];c=Image.new('RGB',(720,70*((len(batch)+2)//3)),'white');d=ImageDraw.Draw(c)
 for i,r in enumerate(batch):
  x=i%3*240;y=i//3*70;c.paste(Image.open(r['path']).crop((0,112,240,160)),(x,y+20));d.text((x+2,y+2),str(r['id']),fill='black')
 c.resize((1440,c.height*2),Image.Resampling.NEAREST).save(base/f'contact_{page}.png')
