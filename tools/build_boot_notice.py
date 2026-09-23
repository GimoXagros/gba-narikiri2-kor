"""Append-only first-screen notice. No existing game data is moved."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from PIL import Image
from build_banked_font import assemble
from bps import create_bps, apply_bps

ROOT=Path(__file__).resolve().parents[1]
BASE_SHA='6ce5726f7621af335c7042f4f6481ed98c3b6dc53046e7a9412f22ae984f3070'
JP_SHA='a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7'
def sha(data):return hashlib.sha256(data).hexdigest()

def build(base, screen):
    if sha(base)!=BASE_SHA or len(base)!=0xC90000:
        raise ValueError('Exact prior title/credits test build required')
    if base[0x100:0x104]!=struct.pack('<I',0x08007401):
        raise ValueError('Original main pointer changed')
    if screen.size!=(240,160):raise ValueError('Native screen geometry required')
    # Explicit hardware RGB555 quantization; no rescaling or text redrawing.
    pixels=b''.join(struct.pack('<H',(r>>3)|((g>>3)<<5)|((b>>3)<<10))
                    for r,g,b in screen.convert('RGB').getdata())
    code=assemble(ROOT/'asm/boot_notice.s',0xC90000,0,0x1000)
    result=bytearray(base+b'\xff'*0x14000)
    result[0xC90000:0xC90000+len(code)]=code
    result[0xC91000:0xC91000+len(pixels)]=pixels
    result[0x100:0x104]=struct.pack('<I',0x08C90001)
    assert result[:0x100]==base[:0x100] and result[0x104:len(base)]==base[0x104:]
    report={'base_sha256':sha(base),'target_sha256':sha(result),
            'existing_data_moved':False,'only_existing_write':{'offset':'0x100','length':4,
            'before':'01740008','after':'0100c908'},'code_offset':'0xC90000',
            'pixels_offset':'0xC91000','pixels_sha256':sha(pixels),
            'input':'release held buttons, press any GBA button, release to continue',
            'scope':'Local test build; original startup resumes at 0x08007401'}
    return bytes(result),report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True)
    p.add_argument('--screen',type=Path,required=True);p.add_argument('--japanese',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out,report=build(a.base.read_bytes(),Image.open(a.screen))
    jp=a.japanese.read_bytes()
    if sha(jp)!=JP_SHA:raise ValueError('Japanese source differs')
    patch=create_bps(jp,out,b'Xagros Narikiri2 first notice test')
    assert apply_bps(jp,patch)==out
    a.out.mkdir(parents=True,exist_ok=False)
    (a.out/'Xagros_Narikiri2_KOR_notice_test.gba').write_bytes(out)
    (a.out/'Xagros_Narikiri2_KOR_notice_test_JP.bps').write_bytes(patch)
    (a.out/'BUILD_MANIFEST.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
