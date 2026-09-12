"""Reproduce v0.9d from immutable Japanese/BETA2/BETA3 inputs and reviewed sources."""
import argparse
import json
from pathlib import Path
import struct

from build_graphics_test import repair, sha
from gba_rl import decompress
from narikiri2_item_ui_font import compress_lz77
from find_gba_lz77_asset import decompress_lz77_stream

ROOT = Path(__file__).resolve().parents[1]
TRADE_OFFSET = 0x37E584
TRADE_CAPACITY = 223
TARGET_SHA256 = '69c5a3e22e00bcacfbaaa7eb28f2efc7d06c8ef37a646ac7236bc78bf76d4012'


def trade_pixels():
    font = json.loads((ROOT/'config/title_trade_glyphs.json').read_text(encoding='utf-8'))
    if font['source_commit'] != '897f0e71224d9964a84b888f2596b2bfd7f98def':
        raise ValueError('Unexpected native font provenance')
    points = set()
    for i,ch in enumerate('교환'):
        rows = font['glyphs'][ch]['rows']
        if len(rows)!=8 or any(len(row)!=8 or set(row)-set('.#') for row in rows):
            raise ValueError('Trade glyph geometry is not native 8x8')
        points.update((16+i*8+x,4+y) for y,row in enumerate(rows) for x,pixel in enumerate(row) if pixel=='#')
    pixels=[[0]*48 for _ in range(16)]
    for x,y in points:
        for dx,dy in ((-1,0),(1,0),(0,-1),(0,1)):
            if (x+dx,y+dy) not in points:pixels[y+dy][x+dx]=9
    for x,y in points:pixels[y][x]=1
    return pixels


def trade_stream():
    pixels=trade_pixels();raw=bytearray()
    # Observed title OAM: three 16x16 pieces; storage order middle/right/left.
    for left in (16,32,0):
        for ty in range(2):
            for tx in range(2):
                for y in range(8):
                    for x in range(0,8,2):
                        xx=left+tx*8+x;yy=ty*8+y
                        raw.append(pixels[yy][xx]|pixels[yy][xx+1]<<4)
    packed=compress_lz77(bytes(raw),vram_safe=True)
    if len(raw)!=384 or len(packed)>TRADE_CAPACITY:
        raise ValueError('Trade resource capacity exceeded')
    if decompress_lz77_stream(packed,0,0x20000)[0]!=bytes(raw):
        raise ValueError('Trade LZ roundtrip mismatch')
    return packed,bytes(raw)


def build(base,japanese):
    previous,report=repair(base,japanese)
    if previous[0x37692C:0x376930]!=struct.pack('<I',TRADE_OFFSET-0x3768F8):
        raise ValueError('Trade relative resource binding changed')
    raw,used=decompress(previous,TRADE_OFFSET,allow_padding=True)
    if (len(raw),used)!=(384,TRADE_CAPACITY):raise ValueError('Trade source extent changed')
    packed,decoded=trade_stream();out=bytearray(previous)
    out[TRADE_OFFSET:TRADE_OFFSET+len(packed)]=packed
    if out[:TRADE_OFFSET]!=previous[:TRADE_OFFSET] or out[TRADE_OFFSET+len(packed):]!=previous[TRADE_OFFSET+len(packed):]:
        raise ValueError('Trade write escaped its owned region')
    report.update(version='v0.9d',target_sha256=sha(out),
                  different_bytes=sum(a!=b for a,b in zip(base,out)),
                  trade_decoded_sha256=sha(decoded),trade_packed_bytes=len(packed),
                  graphics_test_source_sha256=sha(previous))
    report['owned_regions'].append(dict(start=hex(TRADE_OFFSET),end_exclusive=hex(TRADE_OFFSET+len(packed)),
        purpose='Trade title uses the same native Dalmoori ink 1 / edge 9 / 8px cell as continue/new/suspend',decoded_bytes=384))
    if sha(out)!=TARGET_SHA256:raise ValueError('Unverified v0.9d target identity')
    return bytes(out),report


def build_product(beta2,beta3,japanese,workdir):
    from build_ffr_v09b import build as inherited_build
    from import_dalmoori_8x8 import generated_path,parse_generated_glyph,verify_checkout
    font=json.loads((ROOT/'config/title_trade_glyphs.json').read_text(encoding='utf-8'))
    checkout=ROOT/'third_party/_work/dalmoori-font';verify_checkout(checkout)
    for ch,row in font['glyphs'].items():
        source=generated_path(checkout,ch)
        if sha(source.read_bytes())!=row['source_file_sha256'] or list(parse_generated_glyph(source)[3])!=row['rows']:
            raise ValueError('Adopted trade glyph differs from pinned upstream native bitmap')
    base,_,inherited,_=inherited_build(beta2,beta3,japanese,workdir/'font')
    out,report=build(base,japanese)
    report.update(schema='narikiri2-v09d-product-v1',inherited_build=inherited,
                  development_inputs='Exact immutable BETA2/BETA3/Japanese; no prior patched ROM input')
    return out,report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--beta2-reference',type=Path,required=True)
    p.add_argument('--beta3',type=Path,required=True)
    p.add_argument('--japanese',type=Path,required=True)
    p.add_argument('--out-dir',type=Path,required=True)
    a=p.parse_args()
    a.out_dir.mkdir(parents=True,exist_ok=False)
    rom,report=build_product(a.beta2_reference.read_bytes(),a.beta3.read_bytes(),a.japanese.read_bytes(),a.out_dir)
    (a.out_dir/'Xagros_Narikiri2_KOR_v0.9d.gba').write_bytes(rom)
    (a.out_dir/'BUILD_MANIFEST.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
