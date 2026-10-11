"""Independent address contracts for candidate stage-4 fixed-owner code.

The baseline is separately frozen, not reconstructed from an unchecked manifest.
The CFG inspector follows both sides of conditional branches but does not infer
indirect reachability or instruction semantics. CPU differential tests remain
mandatory. Data addresses below are derived from the baseline layout, not the
performance assembler or its emitted relocation report.
"""
import argparse
from collections import Counter
import hashlib
import json
import struct
import sys
from pathlib import Path
from strict_perf_flow_audit import inventory, OWNERS, BASE, require

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'tools'))
from strict_stream_lookup24 import unpack_bounds24

BASE_SHA='ac0ad35924ee76ade7ca4ff4d085ebb1cc4e96ff391f7f24f070bc29f5f03175'
LAYOUT_SHA='a93613327898e83876d0a5561d0dabf5bf1d71221cde47f88b1f664b1aeea179'
sha=lambda data:hashlib.sha256(data).hexdigest()

def tile_global_block(data,row):
    """Verify the optional three-word RAM read, including its real consumer.

    The compact prologue replaces three independent PC loads with one LDM.
    Inspect the physical setup even if a corrupt branch makes it unreachable.
    This proves this explicit access span, not general LDM data flow.
    """
    start=OWNERS['tile'][0]
    setup,consumer=start+6,start+8
    half=struct.unpack_from('<H',data,consumer)[0]
    if half & 0xF800 != 0xC800:
        return None
    require(data[start:setup]==struct.pack('<3H',0xB5F0,0xB085,0x1C04),
            'Tile global block entry setup differs')
    load=struct.unpack_from('<H',data,setup)[0]
    require(load & 0xFF00 == 0x4800 and half==0xC80E,
            'Tile global block must load r0 then exactly r1/r2/r3')
    pool=((setup+4)&~3)+(load&255)*4
    end=OWNERS['tile'][1]
    require(start<=pool<=end-4,'Tile global pointer literal outside owner')
    pointer=struct.unpack_from('<I',data,pool)[0]
    require(pointer==0x0300004C,'Tile global block source differs')
    sites={int(i['address'],16)-BASE for i in row['instructions']}
    require({start,start+2,start+4,setup,consumer}<=sites,
            'Tile global block setup is not reachable')
    require(all(not start<int(b['target'],16)-BASE<=consumer for b in row['direct_branches']),
            'Branch bypasses tile global block setup')
    matches=[p for p in row['literals'] if int(p['storage'],16)-BASE==pool]
    require(len(matches)==1 and int(matches[0]['value'],16)==pointer
            and hex(BASE+setup) in matches[0]['sites'],'Tile global pointer inventory differs')
    return dict(setup=hex(BASE+setup),consumer=hex(BASE+consumer),
                source=hex(pointer),end_exclusive=hex(pointer+12),span_bytes=12,
                destinations=['r1','r2','r3'],writeback='r0',
                fields=['map_global','font_base_global','tilebase_global'])

def address_contracts(data,baseline,link):
    require(len(data)==len(baseline)==0x800000,'8MiB exact size')
    require(sha(baseline)==BASE_SHA and link['output_sha256']==BASE_SHA,'Stage3 identity')
    canonical_layout=json.dumps(link['layout']['segments'],sort_keys=True,separators=(',',':')).encode('ascii')
    require(len(link['layout']['segments'])==52 and sha(canonical_layout)==LAYOUT_SHA,
            'Frozen stage3 layout metadata differs')
    parts={p['name']:p for p in link['layout']['segments']}
    for name in ('owned','lookup','unit'):
        require((parts[name]['new'],parts[name]['new']+parts[name]['size'])==OWNERS[name][:2],('Owner moved',name))
    require((parts['tile_cache']['new'],parts['tile_cache']['new']+parts['tile_cache']['size'])==OWNERS['tile'][:2],'Tile owner moved')
    allowed=bytearray(len(data))
    for start,end,_ in OWNERS.values():
        require(not any(allowed[start:end]),'Owner overlap')
        allowed[start:end]=b'\1'*(end-start)
    require(all(a==b or ok for a,b,ok in zip(data,baseline,allowed)),'Outside six owners changed')
    rows=inventory(data)
    by_name={r['name']:r for r in rows}
    def ptr(name):return BASE+parts[name]['new']
    def literals(name):return [int(r['value'],16) for r in by_name[name]['literals']]
    expected={
      'owned':[0x083A8465,0x0A2BCFE0,0x0C2BCFE0,0x082BCFE0,
               ptr('aliases'),ptr('full_bounds'),8203,ptr('compact_bounds'),1043,
               ptr('unit')|1,ptr('lookup')|1,ptr('extra_bounds'),185,0x082B],
      'lookup':[0x32534253],
      'tile':[ptr('clear_font'),0x03000050,0x0600C000,0x0300004C,0x0600F800,
              0x03000054,0x0300145A,0x03000058,0x03000010,0x178],
      'unit':[],
      'gap':[0x082C0000,0x083A84C4,0x080B9C09],
    }
    tile_block=tile_global_block(data,by_name['tile'])
    if tile_block is not None:
        expected['tile'].remove(0x03000050)
        expected['tile'].remove(0x03000054)
    for name,values in expected.items():
        require(Counter(literals(name))==Counter(values),(name,'Unexpected PC-relative literal'))
    # ADR/LDM profile triples contain non-PC-loaded data addresses too.
    profiles=[(283,ptr('full_book'),parts['full_book']['size']),
              (29,ptr('compact_book'),parts['compact_book']['size']),
              (45,ptr('extra_book'),parts['extra_book']['size'])]
    actual_profiles=[]
    for row in by_name['owned']['adr_data']:
        words=tuple(int(x,16) for x in row['words'])
        actual_profiles.append((29,)+words if row['span_bytes']==8 else words)
    require(Counter(actual_profiles)==Counter(profiles),'Dictionary/capacity profile differs')
    require(all(not r['adr_data'] for r in rows if r['name']!='owned'),'Unexpected ADR data access')
    # Independently derive the 1bpp-to-four-nibbles table from pixel bits.
    lut=struct.pack('<16H',*[sum(15<<(4*i) for i in range(4) if bits&(1<<i)) for bits in range(16)])
    start,end,_=OWNERS['full_draw']
    hits=[pos for pos in range(start,end-31,2) if data[pos:pos+32]==lut]
    require(len(hits)==1,'Unique full draw lookup table required')
    require(Counter(literals('full_draw'))==Counter([0x0300145A,BASE+hits[0],0x3A0,0x080011C9,0x08001351]),'Full draw literal target differs')
    for row in by_name['full_draw']['instructions']:
        at=int(row['address'],16)-BASE
        require(not hits[0]<=at<hits[0]+32,'Lookup table executed as code')
    # Verify all three runtime tables are unchanged complete SBS2 tables.
    starts=[]
    data_ranges=[]
    for name in ('full_bounds','compact_bounds','extra_bounds','full_book','compact_book','extra_book','aliases','clear_font'):
        p=parts[name]; at,size=p['new'],p['size']
        require(0<=at<at+size<=len(data),(name,'Data outside cartridge'))
        require(data[at:at+size]==baseline[at:at+size],(name,'Data changed'))
        data_ranges.append(dict(name=name,start=hex(BASE+at),end_exclusive=hex(BASE+at+size),size=size))
        if name.endswith('_bounds'):
            entries=unpack_bounds24(data[at:at+size]);starts.extend(entries)
            require(len(entries)=={'full_bounds':8203,'compact_bounds':1043,'extra_bounds':185}[name],(name,'Entry count'))
    require(len(starts)==9431,'Complete runtime start count')
    aliases=parts['aliases']
    require(aliases['size']==28,'Complete seven-alias extent required')
    alias_starts=struct.unpack_from('<7I',data,aliases['new'])
    require(all(a<b for a,b in zip(alias_starts,alias_starts[1:])), 'Alias early-exit requires strict order')
    require(all(p in {address for address,length in starts} for p in alias_starts),'Alias outside registered starts')
    pairs=[struct.unpack_from('<HH',data,0x3A84C4+i*4) for i in range(23)]
    previous=-1
    for lower,upper in pairs:
        require(previous<=lower<upper<=0x10000,'Unsorted/overlapping numeric gap')
        previous=upper
        require(all(not 0x082C0000+lower<=p<0x082C0000+upper for p,n in starts),'Numeric bypass covers registered start')
    require(0x3A84C4+23*4==0x3A8520,'Gap data overlaps profile comparator')
    # Frozen native fallback entry instructions are outside the changed owners.
    for at in (0x11C8,0x1350):
        require(data[at:at+16]==baseline[at:at+16],'Native compositor entry differs')
    return {'status':'PASS_BOUNDED_STAGE4_ADDRESS_CONTRACTS',
      'baseline_sha256':BASE_SHA,'candidate_sha256':sha(data),'rom_bytes':len(data),
      'baseline_52_segment_layout_sha256':LAYOUT_SHA,
      'changed_owner_bytes':sum(end-start for start,end,_ in OWNERS.values()),
      'outside_owner_changed_bytes':0,
      'direct_reachable_instructions':sum(r['instruction_count'] for r in rows),
      'direct_branches':sum(len(r['direct_branches']) for r in rows),
      'pc_literal_sites':sum(len(x['sites']) for r in rows for x in r['literals']),
      'profile_count':3,'profile_spans':[r['span_bytes'] for r in by_name['owned']['adr_data']],
      'tile_global_block':tile_block,
      'complete_sorted_alias_count':len(alias_starts),
      'runtime_starts_checked':len(starts),'numeric_gap_pairs':len(pairs),
      'immutable_data_ranges':data_ranges,'owners':rows,
      'qualification':'Static direct-flow and explicit code/data address contracts only. Does not prove register-derived indirect targets, dynamic bus accesses, whole-game reachability, CPU semantics, timing or hardware. Stage3 reference proof and stage4 CPU/render/runtime tests are separately required.'}

def main():
    p=argparse.ArgumentParser()
    for name in ('baseline','link','rom','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--sha256',required=True)
    a=p.parse_args()
    data=a.rom.read_bytes(); require(sha(data)==a.sha256,'Candidate identity')
    baseline=a.baseline.read_bytes();link=json.loads(a.link.read_text(encoding='utf-8'))
    report=address_contracts(data,baseline,link)
    # Corrupt copies in RAM only: these must be rejected by address checks,
    # independent of the CLI whole-image identity guard.
    bad=[]
    for name,at,value in [('outside_8m_table',0xB9CF4,0x08800000),
                          ('unit_thumb_bit',0xB9D1C,0x0837E1F0),
                          ('overlap_gap_table',0x3A84BC,0x083A8520)]:
        changed=bytearray(data);struct.pack_into('<I',changed,at,value)
        try:address_contracts(bytes(changed),baseline,link)
        except ValueError:bad.append(name)
        else:raise ValueError(('Failed to reject corrupt address',name))
    changed=bytearray(data);struct.pack_into('<H',changed,0xB9C08,0xE3FE)
    try:address_contracts(bytes(changed),baseline,link)
    except ValueError:bad.append('direct_branch_outside_owner')
    else:raise ValueError('Failed to reject branch corruption')
    report['independent_corrupt_copy_rejections']=bad
    altered_link=json.loads(json.dumps(link))
    altered_link['layout']['segments'][0]['size']+=4
    try:address_contracts(data,baseline,altered_link)
    except ValueError:bad.append('baseline_layout_metadata_changed')
    else:raise ValueError('Failed to reject modified baseline layout')
    if any(r['span_bytes']==8 for r in report['owners'][0]['adr_data']):
        for name,at,value in [('compact_capacity_changed',0xB9C78,0x201C),
                              ('compact_ldm_consumer',0xB9C7C,0xCB61),
                              ('compact_adr_end_crossing',0xB9C7A,0xA32F)]:
            changed=bytearray(data);struct.pack_into('<H',changed,at,value)
            try:address_contracts(bytes(changed),baseline,link)
            except ValueError:bad.append(name)
            else:raise ValueError(('Failed to reject compact profile corruption',name))
    if report['tile_global_block'] is not None:
        for name,at,value in [('tile_global_extra_word',0xC5BB0,0xC81E),
                              ('tile_global_wrong_base',0xC5BB0,0xC90E),
                              ('tile_global_setup_bypass',0xC5BA8,0xE002)]:
            changed=bytearray(data);struct.pack_into('<H',changed,at,value)
            try:address_contracts(bytes(changed),baseline,link)
            except ValueError:bad.append(name)
            else:raise ValueError(('Failed to reject tile block corruption',name))
    a.out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('owners','immutable_data_ranges')}))
if __name__=='__main__':main()
