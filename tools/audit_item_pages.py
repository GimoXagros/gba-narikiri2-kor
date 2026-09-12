#!/usr/bin/env python3
"""Exact-artifact mGBA item-page pixel audit using an explicit inventory fixture."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import struct
import unicodedata

from libretro_probe import Probe
from transcribe_compact_font import READINGS
from find_gba_lz77_asset import decompress_lz77_stream


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-dir',type=Path,required=True)
    p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--core',type=Path,required=True)
    p.add_argument('--save',type=Path,required=True)
    p.add_argument('--require-unlocked-save',action='store_true',help='Require existing items; do not modify RAM')
    args=p.parse_args()
    manifest=json.loads((args.build_dir/'BUILD_MANIFEST.json').read_text(encoding='utf-8'))
    rom_path=args.build_dir/'NARIKIRI2_BANKED_ENGINE_DIAGNOSTIC.gba'
    rom=rom_path.read_bytes()
    if hashlib.sha256(rom).hexdigest()!=manifest['target_rom_sha256']:raise ValueError('ROM mismatch')
    font_pointer=struct.unpack_from('<I',rom,0x2158)[0]-0x08000000
    expected_base_font=decompress_lz77_stream(rom,font_pointer,0x10000)[0]
    with (args.build_dir/'names.csv').open(encoding='utf-8-sig',newline='') as f:
        names={int(r['id'].split('_')[1]):r['text'] for r in csv.DictReader(f) if r['category']=='ITEM'}
    font={}
    for offset in (0xC02000,0xC06000):
        for i,char in enumerate(manifest['glyphs']):
            bitmap=rom[offset+i*32:offset+(i+1)*32]
            font.setdefault(bitmap,set()).add(char)
    host=Probe(args.core,rom_path,args.run_dir,args.save)
    def frames(n,keys=()):host.execute(dict(op='frames',count=n,buttons=list(keys)))
    def press(key,wait=40):frames(6,(key,));frames(wait)
    def shot(name):host.execute(dict(op='screenshot',name=name+'.png'))
    observations=[]
    try:
        frames(600);press('start',60);press('a',150)
        shot('00_loaded')
        base=int.from_bytes(host.read_memory(0x02003ff8,4),'little')
        if base&3 or not 0x02000000<=base<base+0xA7B<=0x02040000:raise ValueError('Game-data root mismatch')
        before=host.read_memory(base+0xa2c,79)
        after=bytearray(b'\x11'*79);after[0]&=0xf0;after[78]&=0x0f
        if args.require_unlocked_save:
            if before!=after:raise ValueError('Save must contain one of each real item')
        else:
            host.execute(dict(op='write_ram',address=hex(base+0xa2c),expected_hex=before.hex(),
                final_hex=after.hex(),test_fixture_only=True,
                reason='Grant one of each real item, IDs 1..156, to an isolated renderer coverage fixture; not save or natural-play evidence'))
        press('select',90);press('down',20);press('a',90);press('down',40)
        shot('01_all_items')
        press('a',40)
        for step in range(157):
            if step:press('down',20)
            vram=host.read_memory(0x0600c000,0x4000)
            if vram[:0x2000]!=expected_base_font:
                shot(f'FAIL_background_{step:03d}')
                raise ValueError(f'Page {step}: base-font VRAM differs, including transparent background pixels')
            shadow=host.read_memory(0x03000058,0x500)
            visible=struct.unpack_from('<1024H',vram,0x3800)
            live={t&1023 for t in visible+struct.unpack('<640H',shadow) if 0x178<=t&1023<0x1c0}
            unmatched=[hex(t) for t in live if vram[t*32:t*32+32] not in font]
            first=1 if step==156 else max(1,step-4)
            expected=[names[i] for i in range(first,min(first+6,157))]
            for y,word in zip(range(2,14,2),expected):
                for x,char in enumerate(word,12):
                    tile=visible[y*32+x]&1023
                    actual=font.get(vram[tile*32:tile*32+32],set()) if tile>=0x178 else {
                        unicodedata.normalize('NFC',READINGS.get(tile,''))}
                    if char not in actual:
                        shot(f'FAIL_step_{step:03d}')
                        raise ValueError(f'Page {step}, tile ({x},{y}): expected {char!r}, got {actual}')
            if unmatched:raise ValueError(f'Non-Dalmoori referenced private tile at step {step}: {unmatched}')
            observations.append(dict(step=step,first_item=first,visible_item_ids=list(range(first,min(first+6,157))),
                                     live_private_tiles=len(live),pixel_identity='PASS'))
            if True:shot(f'items_step_{step:03d}')
        press('b');press('b');shot('02_returned_to_menu')
        result=dict(status='PASS',rom_sha256=manifest['target_rom_sha256'],core_sha256=host.dll_hash,
            core_version=host.core_version,fixture_modified=not args.require_unlocked_save,natural_play_verified=False,
            persistent_save_items_required=args.require_unlocked_save,
            save_compatibility_verified=False,item_ids_covered=156,screen_samples=len(observations),
            max_live_private_tiles=max(r['live_private_tiles'] for r in observations),
            base_font_including_transparency='8192 bytes exact on every screen',
            observations=observations,limitations=['One inventory route, one save fixture and one mGBA core',
                'Other menus, name entry, battle, saving and hardware remain separate checks'])
        (args.run_dir/'ITEM_MATRIX.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='observations'},ensure_ascii=False,indent=2))
    finally:
        host.lib.retro_unload_game();host.lib.retro_deinit()


if __name__=='__main__':main()
