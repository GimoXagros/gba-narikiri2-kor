"""Japanese-source Korean title and appended ending credits, after frozen v0.9d.

No source artwork is bundled. The adopted Korean logo and frozen 8px copyright glyphs are used without
fallback. Sprite allocation/shape/order and all original credit rows are retained.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

from gba_rl import decompress
from narikiri2_item_ui_font import compress_lz77
from find_gba_lz77_asset import decompress_lz77_stream
from build_v09d import TARGET_SHA256, build_product as previous_product
from build_graphics_test import JP_SHA
from bps import create_bps, apply_bps

ROOT = Path(__file__).resolve().parents[1]
TABLE = 0x3768F8
APPEND = 0xC80000
LOGO_TARGET, COPYRIGHT_TARGET, CREDITS_TARGET = APPEND, APPEND+0x4000, APPEND+0x5000
# Resource 9 tile ranges / screen layout, confirmed by Japanese title OAM.
# Each tuple: x,y,width,height,first 4bpp tile,palette bank.
LOGO_SPRITES = [
    (168,9,32,32,518,0), (104,8,64,32,486,0), (41,8,64,32,454,0),
    (184,28,32,64,422,2), (152,28,32,64,390,2), (120,28,32,64,358,2),
    (88,28,32,64,326,2), (24,28,32,64,294,2), (56,28,32,64,262,2),
    (176,84,16,8,260,1), (96,92,32,8,256,1), (64,-4,64,32,224,1),
    (128,-4,64,32,192,1), (24,28,32,64,160,1), (56,28,32,64,128,1),
    (88,28,32,64,96,1), (120,28,32,64,64,1), (152,28,32,64,32,1),
    (184,20,32,64,0,1),
]
COPYRIGHT_SPRITES = [(200,144,32,16,96,3), (136,128,64,32,64,3),
                     (72,128,64,32,32,3), (8,128,64,32,0,3)]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unpack(raw, sprites):
    layers = {bank: [[0]*240 for _ in range(160)] for *_, bank in sprites}
    for left, top, width, height, first, bank in reversed(sprites):
        for y in range(height):
            for x in range(width):
                at = (first + (y//8)*(width//8)+x//8)*32 + (y%8)*4 + (x%8)//2
                value = (raw[at] >> (4*(x%2))) & 15
                if value and 0 <= top+y < 160 and 0 <= left+x < 240:
                    layers[bank][top+y][left+x] = value
    return layers


def pack_into(raw, sprites, layers, allowed):
    result = bytearray(raw)
    for left, top, width, height, first, bank in sprites:
        for y in range(height):
            for x in range(width):
                xx, yy = left+x, top+y
                if not (0 <= yy < 160 and 0 <= xx < 240 and allowed(bank,xx,yy)):
                    continue
                at = (first + (y//8)*(width//8)+x//8)*32 + (y%8)*4 + (x%8)//2
                shift = 4*(x%2)
                result[at] = (result[at] & ~(15 << shift)) | (layers[bank][yy][xx] << shift)
    return bytes(result)


def copyright_points(text):
    font = json.loads((ROOT/'config/title_copyright_glyphs.json').read_text(encoding='utf-8'))
    points, left = set(), 0
    for ch in text:
        if ch == ' ':
            left += 4
            continue
        if ch not in font['glyphs']:
            raise ValueError(f'Missing copyright glyph: {ch!r}')
        glyph=font['glyphs'][ch]
        rows=glyph['rows']
        if len(rows)!=8 or any(len(row)!=glyph['advance'] or set(row)-set('.#') for row in rows):
            raise ValueError('Copyright glyph geometry changed')
        points.update((left+x,y) for y,row in enumerate(rows) for x,value in enumerate(row) if value=='#')
        left += glyph['advance']
    return points, left


def expanded(points, radius):
    return {(x+dx,y+dy) for x,y in points for dx in range(-radius,radius+1)
            for dy in range(-radius,radius+1) if abs(dx)+abs(dy)<=radius}


def paint(layer, points, value):
    for x,y in points:
        if not (0 <= x < 240 and 0 <= y < 160):
            raise ValueError('Title glyph clipping')
        layer[y][x] = value(x,y) if callable(value) else value


def refine_numeral(layers, japanese_layers):
    """Restore native 2 shading, remove stray pixels and separate the small ®."""
    ink,backdrop=layers[2],layers[1]
    # The Japanese numeral is isolated from its Japanese lettering and old R.
    # Both planes have real sprite coverage through x215, y83; bank 2 continues
    # to y91. The registered mark occupies its original gap beside ㄴ and 2.
    for y in range(26,92):
        for x in range(190,216):
            backdrop[y][x]=0
            if y>=28:ink[y][x]=0
    for y in range(75,92):
        for x in range(185,193):
            ink[y][x]=0
            backdrop[y][x]=0
    for y in range(29,84):
        left=192 if 51<=y<=59 else 191 if y>=75 else 190
        for x in range(left,216):ink[y][x]=japanese_layers[2][y][x]
    # The user supplied the Japanese detail as the adopted outline reference.
    # Restore its original pale rim, including its small antialias transitions.
    for y in range(26,84):
        for x in range(190,216):backdrop[y][x]=japanese_layers[1][y][x]
    # Copy the native registered mark's disk, excluding the neighboring Japanese
    # letter. Retain its original position and light R on a dark-blue interior.
    bounds=((186,190),(185,191),(184,191),(184,191),(184,191),
            (184,191),(184,191),(185,191),(186,190))
    for dy,(left,right) in enumerate(bounds):
        for x in range(left,right):ink[75+dy][x]=japanese_layers[2][75+dy][x]
    return layers


def logo_raw(japanese, korean_reference):
    original,used=decompress(japanese,0x37C09C)
    korean,consumed=decompress(korean_reference,0x37C09C)
    if (len(original),used,len(korean),consumed)!=(17088,8913,17088,8253):
        raise ValueError('Japanese/Korean logo reference extent changed')
    # User supplied this established Korean title as the style reference. Keep
    # its authored letter shapes, gold shading, blue extrusion, ribbon and
    # do not substitute enlarged monospaced dialogue glyphs.
    # Palette and sprite allocation are the original Japanese layout.
    for lo,hi in ((0x37694C,0x376A0C),(0x37B934,0x37B9F4)):
        if japanese[lo:hi]!=korean_reference[lo:hi]:
            raise ValueError('Shared title palette changed')
    layers=unpack(korean,LOGO_SPRITES)
    old=layers[2]
    # Correct the old final syllable 젼 to 전 by removing the upper short arm
    # of ㅕ; keep ㅈ's top bar and the lower arm/vertical stem of ㅓ.
    face={(x,y):old[y][x] for y in range(36,81) for x in range(24,188)
          if old[y][x] in (10,11,12,13,15)}
    for y in range(48,52):
        for x in range(174 if y==48 else 172,178):face.pop((x,y),None)
    transformed={}
    for (x,y),value in face.items():
        xx=x-2 if x<132 else 137+(x-133)*47//51
        transformed[(xx,y)]=value
    # Rebuild the outline around the source lettering after opening a word gap.
    # Same native palette: pale edge, cyan bevel, dark-blue lower extrusion.
    points=set(transformed)
    def cutoff(y):return 185 if y>=75 else 192 if 51<=y<=59 else 190
    for y in range(28,92):old[y][24:cutoff(y)]=[0]*(cutoff(y)-24)
    paint(old,expanded(points,3),14)
    paint(old,{(x,y+3) for x,y in expanded(points,2)},9)
    paint(old,expanded(points,2),5)
    paint(old,expanded(points,1),6)
    for point,value in transformed.items():paint(old,{point},value)
    # Bank 1 contains both the emblem and the old lettering's broad white halo.
    # Only palette 6/7 outside the emblem's two-pixel pale rim is removable.
    # White emblem interiors (5) and cyan detail (8..15) identify its support;
    # their original pixels plus the rim remain an immutable backdrop.
    backdrop=layers[1]
    emblem={(x,y) for y in range(160) for x in range(240)
            if backdrop[y][x]==5 or backdrop[y][x]>=8}
    protected=expanded(emblem,2)
    editable=lambda x,y:24<=x<cutoff(y) and 28<=y<92 and (x,y) not in protected
    for y in range(28,92):
        for x in range(24,cutoff(y)):
            if editable(x,y) and backdrop[y][x] in (6,7):backdrop[y][x]=0
    silhouette={(x,y) for y in range(28,92) for x in range(24,cutoff(y)) if old[y][x]}
    for x,y in expanded(silhouette,2):
        if editable(x,y) and backdrop[y][x]==0:backdrop[y][x]=6
    final=pack_into(korean,LOGO_SPRITES,layers,
        lambda bank,x,y:bank in (1,2) and 24<=x<cutoff(y) and 28<=y<92)
    # Ribbon tiles remain byte-identical. The emblem's original colored pixels
    # and pale rim are protected while its shared white lettering halo changes.
    for x,y,w,h,tile,bank in LOGO_SPRITES:
        if bank==0 and final[tile*32:tile*32+w*h//2]!=korean[tile*32:tile*32+w*h//2]:
            raise ValueError('Ribbon changed outside lettering scope')
    source_backdrop=unpack(korean,LOGO_SPRITES)[1]
    for y in range(160):
        for x in range(240):
            if source_backdrop[y][x]!=backdrop[y][x] and (
                not editable(x,y) or source_backdrop[y][x] not in (0,6,7)):
                raise ValueError('Protected emblem/numeral pixel changed')
    layers=refine_numeral(unpack(final,LOGO_SPRITES),unpack(original,LOGO_SPRITES))
    final=pack_into(final,LOGO_SPRITES,layers,lambda bank,x,y:
        bank in (1,2) and ((190<=x<216 and 26<=y<92) or (184<=x<193 and 75<=y<92)))
    return final,unpack(final,LOGO_SPRITES)


def copyright_raw(japanese):
    raw,used=decompress(japanese,0x37EBE8)
    if (len(raw),used)!=(3328,2040):raise ValueError('Copyright source extent changed')
    layers=unpack(raw,COPYRIGHT_SPRITES)
    for y in range(128,149):layers[3][y]=[0]*240
    points,width=copyright_points('© 이노마타 무츠미  © 후지시마 코스케')
    # The three upper copyright sprites span x8..199; the final 32px sprite
    # exists only on the lower English row. Fit the Korean line to this extent.
    points={(x+(240-width)//2,y+137) for x,y in points}
    if any(not(8<=x<200 and 128<=y<149) for x,y in expanded(points,1)):
        raise ValueError('Copyright text exceeds real sprite coverage')
    paint(layers[3],expanded(points,1),9)
    paint(layers[3],points,1)
    final=pack_into(raw,COPYRIGHT_SPRITES,layers,lambda bank,x,y:128<=y<149)
    # Bottom English company/year copyright row is byte-for-byte preserved.
    after=unpack(final,COPYRIGHT_SPRITES)[3]
    original=unpack(raw,COPYRIGHT_SPRITES)[3]
    assert after[149:160]==original[149:160]
    return final,layers


def build(base,japanese):
    if sha(base)!=TARGET_SHA256 or sha(japanese)!=JP_SHA:
        raise ValueError('Exact v0.9d and Japanese source ROMs are required')
    if len(base)!=APPEND:raise ValueError('Append ownership starts at original EOF')
    image=base+b'\xff'*0x10000
    writes=[]
    def write(name,offset,payload,expected):
        if image[offset:offset+len(payload)]!=expected or len(expected)!=len(payload):
            raise ValueError(f'Expected source changed: {name}')
        writes.append((offset,payload,name))
    assets=[]
    for index,offset,target,raw in ((9,0x37C09C,LOGO_TARGET,logo_raw(japanese,base)[0]),
                                    (16,0x37EBE8,COPYRIGHT_TARGET,copyright_raw(japanese)[0])):
        packed=compress_lz77(raw,vram_safe=True)
        if len(packed)> (0x4000 if index==9 else 0x1000):raise ValueError('Asset allocation overflow')
        if decompress_lz77_stream(packed,0,0x20000)[0]!=raw:raise ValueError('Compression roundtrip')
        write(f'title_resource_{index}',target,packed,b'\xff'*len(packed))
        write(f'title_resource_{index}_pointer',TABLE+4+4*index,struct.pack('<I',target-TABLE),struct.pack('<I',offset-TABLE))
        assets.append({'resource':index,'target':hex(target),'decoded_sha256':sha(raw),'packed_size':len(packed)})
    # The original 191 credit rows and zero terminator are consumer-defined.
    original=base[0x7F9608:0x7F9908]
    if original!=japanese[0x7F9608:0x7F9908] or original[-4:]!=bytes(4):
        raise ValueError('Original staff table changed')
    if base[0xA5316:0xA5318]!=bytes.fromhex('3521'):
        raise ValueError('Final scroll phase instruction changed')
    strings=['KOREAN TRANSLATION','TEAM FFR','XAGROS']
    strings_start=CREDITS_TARGET+len(original)+5*4
    strings_bytes=bytearray();pointers=[]
    for s in strings:
        if not 0<len(s)<=30 or not s.isascii():raise ValueError('Credits line does not fit renderer')
        pointers.append(0x08000000+strings_start+len(strings_bytes))
        strings_bytes.extend(s.encode('ascii')+b'\0')
    table=original[:-4]+struct.pack('<5I',0x08373FC0,0x08373FC0,*pointers)+bytes(4)
    payload=table+strings_bytes
    assert CREDITS_TARGET+len(table)==strings_start
    write('extended_staff_table',CREDITS_TARGET,payload,b'\xff'*len(payload))
    write('staff_table_pointer',0xA56E8,struct.pack('<I',0x08000000+CREDITS_TARGET),struct.pack('<I',0x087F9608))
    # Five appended rows get five extra scroll rows, retaining original tail gap.
    write('last_scroll_rows_53_to_58',0xA5316,bytes.fromhex('3a21'),bytes.fromhex('3521'))
    out=bytearray(image);end=0
    for off,data,name in sorted(writes):
        if off<end:raise ValueError('Overlapping writers: '+name)
        out[off:off+len(data)]=data;end=off+len(data)
    owned=set(i for off,data,_ in writes for i in range(off,off+len(data)))
    if any(a!=b and i not in owned for i,(a,b) in enumerate(zip(image,out))):raise ValueError('Unowned write')
    manifest={'base_sha256':sha(base),'japanese_sha256':sha(japanese),'target_sha256':sha(out),
              'title':'테일즈 오브 더 월드 나리키리 던전®2',
              'copyright':'© 이노마타 무츠미  © 후지시마 코스케','appended_credits':strings,
              'original_credit_rows':191,'added_credit_rows':5,'final_scroll_rows':58,
              'assets':assets,'writes':[{'offset':hex(o),'length':len(p),'purpose':n} for o,p,n in sorted(writes)],
              'logo_policy':'preserve ribbon/emblem; correct Korean lettering/halo; restore Japanese numeral shading/rim and native registered mark at original position',
              'copyright_font':'Dalmoori native 8px; space after both copyright symbols',
              'runtime_status':'PENDING','scope':'title and ending credits local test build'}
    return bytes(out),manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,help='Exact frozen v0.9d for incremental local iteration')
    p.add_argument('--beta2-reference',type=Path)
    p.add_argument('--beta3',type=Path)
    p.add_argument('--japanese',type=Path,required=True)
    p.add_argument('--out-dir',type=Path,required=True)
    a=p.parse_args();a.out_dir.mkdir(parents=True,exist_ok=False)
    jp=a.japanese.read_bytes()
    if a.baseline:
        base=a.baseline.read_bytes();inherited=None
    elif a.beta2_reference and a.beta3:
        base,inherited=previous_product(a.beta2_reference.read_bytes(),a.beta3.read_bytes(),jp,a.out_dir/'inherited')
    else:
        p.error('Provide --baseline or both --beta2-reference and --beta3')
    rom,report=build(base,jp)
    if inherited is not None:report['inherited_build']=inherited
    patch=create_bps(jp,rom,b'Xagros Korean title and ending credits test; original Japanese source')
    if apply_bps(jp,patch)!=rom:raise ValueError('JP BPS roundtrip failure')
    (a.out_dir/'Xagros_Narikiri2_KOR_title_credits_test.gba').write_bytes(rom)
    (a.out_dir/'Xagros_Narikiri2_KOR_title_credits_test_JP.bps').write_bytes(patch)
    report['bps_sha256']=sha(patch)
    (a.out_dir/'BUILD_MANIFEST.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))


if __name__=='__main__':main()
