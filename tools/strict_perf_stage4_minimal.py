"""Five performance writes; preserve the reviewed stage3 unit decoder exactly."""
from pathlib import Path
import argparse,hashlib,json,re,struct
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
from strict_perf_native_numeric_gaps import current_bounds,unpack_bounds24,derive_native_numeric_gaps
ROOT=Path(__file__).resolve().parents[1]
BASE='ac0ad35924ee76ade7ca4ff4d085ebb1cc4e96ff391f7f24f070bc29f5f03175'
LAYOUT='a93613327898e83876d0a5561d0dabf5bf1d71221cde47f88b1f664b1aeea179'
FINAL='9fd341b827a8ba282781d7f8f214f2ba8641365b541564d53e9ef5267511889b'
UNIT_START,UNIT_END=0x37E1F0,0x37E336
UNIT_SHA='b9af84d74757197b5f8531e50e1e9c03b9d03089efdddb09c32e559b23802460'
sha=lambda b:hashlib.sha256(b).hexdigest()
OWNERS=[('owned_alias_order',0xB9C00,0xB9D3C,'strict_perf_owned_alias_order.s'),
 ('exact_lookup_shifted',0xB9D3C,0xB9DE4,'strict_perf_lookup_shifted_key.s'),
 ('tile_idhome4_first_home_prefilter_balanced',0xC5BA8,0xC5E50,'strict_perf_tile_first_home_prefilter_balanced.s'),
 ('full_draw_lut16_strh',0xCAA10,0xCAB58,'strict_perf_full_draw_strh.s'),
 ('native_ram_numeric_gap_guard',0x3A8464,0x3A8520,'strict_perf_native_ram_gap_guard.s')]

def preserved_unit(image,part):
    if (part['new'],part['size'])!=(UNIT_START,UNIT_END-UNIT_START):
        raise ValueError('Preserved stage3 unit extent differs')
    if sha(image[UNIT_START:UNIT_END])!=UNIT_SHA:
        raise ValueError('Preserved stage3 unit bytes differ')
    return dict(start=UNIT_START,end=UNIT_END,size=UNIT_END-UNIT_START,sha256=UNIT_SHA)

def build(base,*,jp,adopted,link):
    if len(base)!=0x800000 or sha(base)!=BASE:raise ValueError('Exact stage3 ac0 input identity')
    if link['output_sha256']!=BASE:raise ValueError('Current stage3 LINK output identity')
    layout=link['layout']['segments']
    if len(layout)!=52 or sha(json.dumps(layout,sort_keys=True,separators=(',',':')).encode('ascii'))!=LAYOUT:
        raise ValueError('Current stage3 canonical52-segment layout identity')
    seg={s['name']:s for s in link['layout']['segments']}
    preserved=preserved_unit(base,seg['unit'])
    for name,owner_name in (('owned','owned_alias_order'),('lookup','exact_lookup_shifted'),('tile_cache','tile_idhome4_first_home_prefilter_balanced')):
        part=seg[name];owner=next(v for v in OWNERS if v[0]==owner_name)
        if (part['new'],part['new']+part['size'])!=owner[1:3]:raise ValueError('Current baseline owner differs')
    bounds=current_bounds(base,link);tables={n:unpack_bounds24(t) for n,t in bounds.items()}
    compact_starts=[p for p,n in tables['compact_bounds']];pages=sorted({p>>16 for p in compact_starts})
    if pages!=[0x082B,0x082C] or len(compact_starts)!=1043:raise ValueError('Complete compact page route proof')
    starts=[{p for p,n in tables[k+'_bounds']} for k in ('full','compact','extra')]
    if any(starts[i]&starts[j] for i in range(3) for j in range(i+1,3)):raise ValueError('Classifications overlap')
    aliases=list(struct.unpack_from('<7I',base,seg['aliases']['new']))
    if seg['aliases']['size']!=28 or not all(a<b for a,b in zip(aliases,aliases[1:])) or any(p not in starts[1] for p in aliases):raise ValueError('Complete sorted registered seven-alias proof')
    oldpool=struct.unpack('<23I',base[0xB9D3C-92:0xB9D3C])
    caps=dict(full=oldpool[8],compact=oldpool[13],extra=oldpool[22])
    if caps!=dict(full=283,compact=29,extra=45):raise ValueError('Original immutable caller capacities')
    symbols={'ALIAS_STARTS':0x08000000+seg['aliases']['new'],'UNIT_DECODER':0x08000000+seg['unit']['new']+1,
        'BOUNDS_LOOKUP':0x08000000+seg['lookup']['new']+1,'COMPACT_FIRST_PAGE':pages[0]}
    for kind in caps:
        symbols.update({kind.upper()+'_BOUNDS':0x08000000+seg[kind+'_bounds']['new'],
            kind.upper()+'_COUNT':len(tables[kind+'_bounds']),kind.upper()+'_CAPACITY':caps[kind],
            kind.upper()+'_BOOK':0x08000000+seg[kind+'_book']['new'],kind.upper()+'_BOOK_BYTES':seg[kind+'_book']['size']})
    proof=derive_native_numeric_gaps(jp,adopted,base,bounds,link)
    hull=(min(compact_starts),max(compact_starts))
    gaps=[g for g in proof['gaps'] if any(hull[0]<=int(v['pointer'],16)<=hull[1] for v in g['literals'])]
    if len(gaps)!=23 or any(g['low']>>16!=0x082C or g['high']>>16!=0x082C for g in gaps):raise ValueError('Complete native numeric gap proof')
    gap_table=b''.join(struct.pack('<HH',g['low']&65535,g['high']&65535) for g in gaps)
    symbols.update(GAP_COUNT=23,SOURCE_BASE=0x082C0000,GAP_TABLE=0x083A84C4)
    image=bytearray(base);writes=[];k=Ks(KS_ARCH_ARM,KS_MODE_THUMB)
    for name,start,end,file in OWNERS:
        path=ROOT/'asm'/file;source=path.read_text(encoding='utf-8')
        for label,value in symbols.items():source=re.sub(r'\b'+label+r'\b',str(value),source)
        def assemble(text):return bytes(k.asm(text,addr=0x08000000+start)[0])
        code=assemble(source);used=len(code)
        if name=='tile_idhome4_first_home_prefilter_balanced':
            if used!=680:raise ValueError('Exact first-home prefilter cache size')
            if code[-36:]!=base[end-36:end]:raise ValueError('Fixed original cache globals changed')
        elif name=='native_ram_numeric_gap_guard':
            if used!=96 or len(gap_table)!=92:raise ValueError('Guard96/table92 ownership')
            code+=gap_table
        elif name=='owned_alias_order':
            if code[:8]!=bytes.fromhex('f0b588b004000691'):raise ValueError('Exact fallback first8 replay')
            code=bytes.fromhex('004b1847')+struct.pack('<I',0x083A8465)+code[8:]
        else:
            expected={'exact_lookup_shifted':164,'full_draw_lut16_strh':288}[name]
            if used!=expected:raise ValueError('Exact reviewed code size')
            code+=bytes.fromhex('c046')*((end-start-used)//2)
        if len(code)!=end-start:raise ValueError('Owner extent changed')
        image[start:end]=code
        writes.append({'writer_id':'stage4_perf:'+name,'stage':4,'start':start,'end':end,'size':end-start,
            'before_sha256':sha(base[start:end]),'after_sha256':sha(code),'source_path':'asm/'+file,
            'source_sha256':sha(path.read_bytes()),'assembled_bytes':used,'changed_bytes':sum(a!=b for a,b in zip(base[start:end],code))})
    image=bytes(image)
    preserved_unit(image,seg['unit'])
    if sha(image)!=FINAL:raise ValueError('Exact reviewed stage4 output identity')
    changed=[i for i,(a,b) in enumerate(zip(base,image)) if a!=b]
    if any(not any(start<=i<end for _,start,end,_ in OWNERS) for i in changed):raise ValueError('Outside five performance owners changed')
    slots={p:n for values in tables.values() for p,n in values}
    for pointer,size in slots.items():
        at=pointer-0x08000000
        if base[at:at+size]!=image[at:at+size]:raise ValueError('Original compressed stream changed')
    files=['tools/strict_perf_stage4_minimal.py','tools/strict_perf_native_numeric_gaps.py']+['asm/'+v[3] for v in OWNERS]
    return image,{'status':'FIVE_OWNER_STAGE4_DIAGNOSTIC_NOT_PRODUCT','performance_gate_approved':False,'release_eligible':False,
        'stage3_input_sha256':BASE,'stage3_canonical_layout_sha256':LAYOUT,'stage4_output_sha256':FINAL,'rom_bytes':len(image),'writes':writes,
        'total_changed_bytes':len(changed),'preserved_stage3_unit':preserved,
        'original_compressed_slots_unchanged':len(slots),'complete_alias_starts':aliases,
        'complete_native_numeric_proof':proof,'selected_gap_pairs':gaps,'guard_code_table_split':[96,92],
        'public_source_files':[{'path':f,'sha256':sha((ROOT/f).read_bytes())} for f in files],
        'new_ram_or_metadata':False,'original_pointers_or_compressed_streams_changed':False,
        'qualification':'Reproducible diagnostic review build; CPU/local frozen validation, natural game/audio/hardware and release gates remain separate.'}
def main():
    p=argparse.ArgumentParser()
    for name in ('baseline','jp','adopted','link','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():raise ValueError('Fresh review evidence required')
    image,report=build(a.baseline.read_bytes(),jp=a.jp.read_bytes(),adopted=a.adopted.read_bytes(),link=json.loads(a.link.read_text(encoding='utf-8')))
    a.out.mkdir(parents=True);(a.out/'STAGE4_PERF_DIAGNOSTIC_NOT_PRODUCT.gba').write_bytes(image)
    (a.out/'STAGE4_WRITES.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('stage3_input_sha256','stage4_output_sha256','rom_bytes','total_changed_bytes','original_compressed_slots_unchanged')}))
if __name__=='__main__':main()
