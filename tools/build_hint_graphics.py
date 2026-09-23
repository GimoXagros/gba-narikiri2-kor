"""Replace cropped inherited 8px hint bitmaps without changing allocations."""
import argparse,json,struct,hashlib
from pathlib import Path
from import_dalmoori_8x8 import generated_path,parse_generated_glyph,verify_checkout
from narikiri2_item_ui_font import compress_lz77
from find_gba_lz77_asset import decompress_lz77_stream
from gba_rl import decompress
from bps import create_bps,apply_bps
ROOT=Path(__file__).resolve().parents[1]
BASE_SHA='61d5b6866afefc1169211eea33e3fed85898d01c94ebd8d8ad97bce939392c3d'
# Keep the existing phrase pieces and sprite placements. Blank suffix pieces
# 34/40 and non-text controls are intentionally left as they are.
HINTS={32:'특기',33:'는 설정',35:'을 보다',36:'LR로',37:'캐릭',38:'전환',39:'정보',41:'↔로',42:'PAGE',43:'보기',45:'나누기',59:'가격',60:'소지량',70:'반전',71:'교신중',73:'SELECT',74:'로 자동'}
def sha(b):return hashlib.sha256(b).hexdigest()
def bitmap(text,width,ink=15,edge=4):
    points=set();left=1
    for ch in text:
        if ch==' ':left+=3;continue
        if ch=='↔':
            rows=('........','..#..#..','.#....#.','########','.#....#.','..#..#..','........','........')
        else:
            _,_,_,rows=parse_generated_glyph(generated_path(ROOT/'third_party/_work/dalmoori-font',ch))
        assert len(rows)==8
        for y,row in enumerate(rows):
            for x,c in enumerate(row):
                if c=='#':points.add((left+x,y))
        left+=len(rows[0])+1
    assert points and max(x for x,y in points)<width-1,(text,width,left)
    pix=[[0]*width for _ in range(8)]
    for x,y in points:
        for dx,dy in ((-1,0),(1,0),(0,-1),(0,1)):
            xx,yy=x+dx,y+dy
            if 0<=xx<width and 0<=yy<8:pix[yy][xx]=edge
    for x,y in points:pix[y][x]=ink
    raw=bytes(pix[y][tx+x]|pix[y][tx+x+1]<<4 for tx in range(0,width,8) for y in range(8) for x in range(0,8,2))
    # Every source ink pixel is retained; no crop/resize of a larger font.
    decoded={(x,y) for y in range(8) for x in range(width) if (raw[(x//8)*32+y*4+x%8//2]>>(4*(x%2))&15)==ink}
    assert decoded==points
    return raw

def build(base):
    assert sha(base)==BASE_SHA,'Exact latest place-name build required'
    verify_checkout(ROOT/'third_party/_work/dalmoori-font')
    result=bytearray(base);writes=[];rows=[]
    def append(data):
        result.extend(b'\xff'*((-len(result))%4));at=len(result);result.extend(data);return at
    def replace(table,index,text,width):
        entry=table+4+index*4;old=(table+struct.unpack_from('<I',base,entry)[0])&0xffffffff
        original,_=decompress(base,old,allow_padding=True) if base[old]==0x30 else decompress_lz77_stream(base,old,0x20000)
        raw=bitmap(text,width,8,12) if table!=0x3A7ADC else bitmap(text,width);assert len(raw)==len(original)
        packed=compress_lz77(raw,vram_safe=True);assert decompress_lz77_stream(packed,0,0x20000)[0]==raw
        at=append(packed);data=struct.pack('<I',(at-table)&0xffffffff)
        assert entry not in [w['offset'] for w in writes]
        writes.append(dict(offset=entry,before=base[entry:entry+4].hex(),after=data.hex()))
        result[entry:entry+4]=data
        rows.append(dict(table=hex(table),index=index,text=text,width=width,height=8,old_offset=hex(old),new_offset=hex(at),raw_sha256=sha(raw),ink_pixels=sum(v==(8 if table!=0x3A7ADC else 15) for b in raw for v in (b&15,b>>4))))
    # The map label loader has a private table since the place-name fix;
    # update its active entries, plus the original table used by other callers.
    map_table=struct.unpack_from('<I',base,0xCAF0)[0]-0x08000000
    for table in [0x380F08,map_table]:
        replace(table,6,'소문은',32);replace(table,7,'LR',16)
    for index,text in HINTS.items():replace(0x3A7ADC,index,text,32)
    # CP bitmap is intact, but the inherited stream header is 04, not RL30.
    assert base[0x3AC014]==4 and base[0x3AC015:0x3AC018]==bytes.fromhex('400000')
    result[0x3AC014]=0x30
    cp,_=decompress(result,0x3AC014,allow_padding=True)
    assert len(cp)==64
    writes.append(dict(offset=0x3AC014,before='04',after='30'))
    allowed={w['offset']+i for w in writes for i in range(len(bytes.fromhex(w['after'])))}
    assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(base,result)))
    return bytes(result),dict(base_sha256=sha(base),target_sha256=sha(result),writes=writes,assets=rows,old_data_moved=False,allocation_sizes_unchanged=True,source_ink_preserved=True)
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('base','japanese','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();rom,report=build(a.base.read_bytes());jp=a.japanese.read_bytes()
    assert sha(jp)=='a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7'
    patch=create_bps(jp,rom);assert apply_bps(jp,patch)==rom
    a.out.mkdir(parents=True,exist_ok=False)
    (a.out/'Xagros_Narikiri2_KOR_hints_test.gba').write_bytes(rom)
    (a.out/'Xagros_Narikiri2_KOR_hints_test_JP.bps').write_bytes(patch)
    (a.out/'BUILD_MANIFEST.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
