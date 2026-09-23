"""Rebuild all 22 map place labels with matching sprite geometry, append only."""
import csv,json,struct,hashlib,argparse
from pathlib import Path
from build_banked_font import encode
from import_dalmoori_8x8 import generated_path,parse_generated_glyph,verify_checkout
from narikiri2_item_ui_font import compress_lz77
from find_gba_lz77_asset import decompress_lz77_stream
from bps import create_bps,apply_bps
ROOT=Path(__file__).resolve().parents[1]
BASE_SHA='d3c4b127cde5b3f0d29970369a6f54c02560e4e591dfc42deffbabc0c0fe2209'
NAMES=['레그니아 교회','훈다르크 상점','스테비아 의상실','포르포르 공방','펍・로즈',
       '카페・벡','장로 라이엘의 집','아나스이 거리','레그니아 거리','뒷골목','중앙 광장','문',
       '칠흑의 갱도','만년빙동','시련의 탑','물의 고성','부유 사도','사냥꾼의 숲',
       '환상의 성','거목의 신전','용의 미궁','레그니아 마을']
def sha(b):return hashlib.sha256(b).hexdigest()

def graphic(text):
    font=ROOT/'third_party/_work/dalmoori-font'
    ink=set();left=2
    for ch in text:
        if ch==' ':left+=4;continue
        if ch=='・':
            ink.update((left+x,5+y) for x in (1,2) for y in (0,1));left+=5;continue
        _,_,_,rows=parse_generated_glyph(generated_path(font,ch))
        for y,row in enumerate(rows):
            for x,c in enumerate(row):
                if c=='#':ink.add((left+x,3+y))
        left+=len(rows[0])+1
    width=((left+2+31)//32)*32
    if width>96:raise ValueError('Place label exceeds bounded map area')
    pixels=[[0]*width for _ in range(16)]
    for x,y in ink:
        for dx in (-1,0,1):
            for dy in (-1,0,1):pixels[y+dy][x+dx]=8
    for x,y in ink:pixels[y][x]=15
    for x in range(1,left):pixels[14][x]=8
    raw=bytearray()
    for start in range(0,width,32):
        for ty in range(2):
            for tx in range(4):
                for y in range(8):
                    for x in range(0,8,2):
                        xx=start+8*tx+x;yy=8*ty+y
                        raw.append(pixels[yy][xx]|pixels[yy][xx+1]<<4)
    return bytes(raw),width

def build(base):
    if sha(base)!=BASE_SHA:raise ValueError('Exact notice build required')
    verify_checkout(ROOT/'third_party/_work/dalmoori-font')
    result=bytearray(base);writes=[]
    def append(data):
        result.extend(b'\xff'*((-len(result))%4));off=len(result);result.extend(data);return off
    def write(off,data):
        writes.append({'offset':hex(off),'before':base[off:off+len(data)].hex(),'after':data.hex()})
        result[off:off+len(data)]=data
    if struct.unpack_from('<I',base,0xCAEC)[0]!=0x082C23B8 or struct.unpack_from('<I',base,0xCAF0)[0]!=0x08380F08:
        raise ValueError('Map-label consumer source changed')
    assets=bytearray(base[0x380F08:0x380F08+4+135*4])
    asset_at=append(assets)
    labels=bytearray(base[0x2C23B8:0x2C23B8+25*8]);label_at=append(labels)
    # Every original relative asset entry needs rebasing when its table moves.
    for i in range(135):
        target=0x380F08+struct.unpack_from('<I',assets,4+i*4)[0]
        struct.pack_into('<I',assets,4+i*4,(target-asset_at)&0xffffffff)
    rows=[]
    for row,text in enumerate(NAMES,3):
        raw,width=graphic(text);packed=compress_lz77(raw,vram_safe=True)
        assert decompress_lz77_stream(packed,0,0x20000)[0]==raw
        at=append(packed);resource=row+6
        struct.pack_into('<I',assets,4+resource*4,at-asset_at)
        # Native frame record: signed x/y, shape 6 (32x16), tile offset, flags.
        layout=struct.pack('<I',width//32)+b''.join(struct.pack('<bbHHH',x,0,6,x//4,0) for x in range(0,width,32))
        layout_at=append(layout);frame_at=append(struct.pack('<II',1,0x08000000+layout_at))
        struct.pack_into('<I4b',labels,row*8,0x08000000+frame_at,resource,-1,-1,-1)
        rows.append({'row':row,'text':text,'width':width,'resource':resource,'decoded_sha256':sha(raw)})
    result[asset_at:asset_at+len(assets)]=assets;result[label_at:label_at+len(labels)]=labels
    write(0xCAEC,struct.pack('<I',0x08000000+label_at));write(0xCAF0,struct.pack('<I',0x08000000+asset_at))
    # Latest user spelling supersedes earlier NPC transliteration, too.
    glyphs=json.loads((ROOT/'config/private_glyph_order.json').read_text('utf-8'))['glyphs']
    from extract_dialogue_book_data import compact_korean,source_text
    changed=[]
    with (ROOT/'analysis/v0.9c/pointer_audit.csv').open(encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if row['kind']!='compact' and not row['id'].startswith('UI_'):continue
            storage=int(row['storage'],16);_,raw=source_text(base,storage)
            try:old=compact_korean(raw,glyphs)
            except ValueError:continue
            if '훈다크르' not in old:continue
            new=old.replace('훈다크르','훈다르크');data=encode(new,{c:i for i,c in enumerate(glyphs)})+b'\0'
            at=append(data);write(storage,struct.pack('<I',0x08000000+at));changed.append({'storage':hex(storage),'before':old,'after':new})
    # Same-length full-dialogue spelling correction, at declared text boundaries.
    from narikiri2_text_spec import encode_korean_fixed_slot
    old_bytes=encode_korean_fixed_slot('훈다크르');new_bytes=encode_korean_fixed_slot('훈다르크')
    seen=set();dialogue=[]
    with (ROOT/'analysis/v0.9c/pointer_audit.csv').open(encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if row['kind']!='full_text':continue
            at,raw=source_text(base,int(row['storage'],16))
            if at in seen:continue
            seen.add(at)
            cursor=0
            while (pos:=raw.find(old_bytes,cursor))>=0:
                write(at+pos,new_bytes);dialogue.append({'id':row['id'],'offset':hex(at+pos)})
                cursor=pos+len(old_bytes)
    allowed={int(w['offset'],16)+i for w in writes for i in range(len(bytes.fromhex(w['after'])))}
    assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(base,result)))
    return bytes(result),{'base_sha256':sha(base),'target_sha256':sha(result),'places':rows,'npc_changes':changed,'dialogue_spelling':dialogue,
                         'writes':writes,'label_table':hex(label_at),'asset_table':hex(asset_at),'old_data_moved':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--japanese',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rom,report=build(a.base.read_bytes());jp=a.japanese.read_bytes()
    if sha(jp)!='a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7':
        raise ValueError('Exact Japanese source ROM required')
    patch=create_bps(jp,rom)
    assert apply_bps(jp,patch)==rom
    a.out.mkdir(parents=True,exist_ok=False)
    (a.out/'Xagros_Narikiri2_KOR_places_test.gba').write_bytes(rom)
    (a.out/'Xagros_Narikiri2_KOR_places_test_JP.bps').write_bytes(patch)
    (a.out/'BUILD_MANIFEST.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
