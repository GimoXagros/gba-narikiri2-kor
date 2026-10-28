"""Build the private exception-aware full-window half-space candidate."""
import argparse,csv,hashlib,json
from pathlib import Path
from audit_halfspace import audit,sha
from build_halfspace_prototype import build,REVIEWED_RUNTIME_SPANS
from strict_packed_tree import pack_tree
from strict_unit_codec import decode_parts,encode_parts
from bps import create_bps,apply_bps
from build_v11a import validate_writes


def candidate(base,japanese,corpus,link,components):
    layout=link['layout']
    records,plans,summary,book=audit(base,corpus,layout,components)
    if summary['final_book_overflows']:raise ValueError('Halfspace slot overflow')
    runtime,_,report=build(base,japanese,layout,selective=True)
    result=bytearray(runtime);seg=next(s for s in layout['segments'] if s['name']=='full_book')
    packed=pack_tree(book)
    if len(packed)!=seg['size']:raise ValueError('Full dictionary extent changed')
    result[seg['new']:seg['new']+seg['size']]=packed
    writes={};changed_bindings=[]
    for row in plans:
        if row['compression_kind']!='full_text':continue
        payload=bytes.fromhex(row['native_hex']);encoded=encode_parts([payload],'full_text',book)
        start=row['start'];cap=row['capacity']
        if len(encoded)>cap or len(payload)+1>283:raise ValueError('Slot/output capacity')
        if start in writes and writes[start]!=encoded:raise ValueError('Conflicting shared start')
        writes[start]=encoded
        if base[start:start+len(encoded)]!=encoded:changed_bindings.append(row['binding_id'])
        result[start:start+len(encoded)]=encoded
    out=bytes(result)
    protected=[(s['new'],s['new']+s['size']) for s in layout['segments'] if s['name']!='full_book']
    protected += [(int(r['pointer_storage'],16),int(r['pointer_storage'],16)+4) for r in corpus['rows']]
    full_ids={p['binding_id'] for p in plans if p['compression_kind']=='full_text'}
    protected += [(int(r['current_start'],16),int(r['current_start'],16)+int(r['original_slot_bytes'])) for r in corpus['rows'] if r['binding_id'] not in full_ids]
    protected.append((0xCA254,0xCA3F4))
    planned={w['start']:out[w['start']:w['end']] for w in report['writes']}
    for start,data in [*writes.items(),(seg['new'],packed)]:
        if start in planned:raise ValueError('Conflicting runtime/text writer')
        planned[start]=data
    validate_writes(planned,protected,len(out))
    for row in plans:
        if row['compression_kind']!='full_text':
            start=row['start'];cap=row['capacity']
            if out[start:start+cap]!=base[start:start+cap]:raise ValueError('Extra-book full-name stream changed')
            continue
        start=row['start'];raw,used=decode_parts(out[start:start+row['capacity']],book,283,1,1,allow_suffix=True)
        if raw!=bytes.fromhex(row['native_hex'])+b'\0' or used>row['capacity']:raise ValueError('Final stream readback')
    for row in corpus['rows']:
        storage=int(row['pointer_storage'],16)
        if out[storage:storage+4]!=base[storage:storage+4]:raise ValueError('Original pointer changed')
    for protected in layout['segments']:
        if protected['name']=='full_book':continue
        a=protected['new'];b=a+protected['size']
        if out[a:b]!=base[a:b]:raise ValueError('Protected component changed '+protected['name'])
    allowed=bytearray(len(base))
    for lo,hi in [(w['start'],w['end']) for w in report['writes']]+[(seg['new'],seg['new']+seg['size'])]+[(a,a+len(b)) for a,b in writes.items()]:
        allowed[lo:hi]=b'\1'*(hi-lo)
    if any(a!=b and not allowed[i] for i,(a,b) in enumerate(zip(base,out))):raise ValueError('Unplanned write')
    # The accepted-runtime audit uses fixed reviewed native extents, never a
    # candidate's self-declared runtime lengths as its permission source.
    accepted_allowed=bytearray(len(base))
    for lo,hi in [*REVIEWED_RUNTIME_SPANS,(seg['new'],seg['new']+seg['size']),*[(a,a+len(b)) for a,b in writes.items()]]:
        accepted_allowed[lo:hi]=b'\1'*(hi-lo)
    accepted_count=0
    def check_accepted(value):
        nonlocal accepted_count
        if isinstance(value,dict):
            for key,child in value.items():
                if key=='writes' and isinstance(child,list):
                    for writer in child:
                        if not isinstance(writer,dict):continue
                        if 'start' in writer and 'end' in writer:lo,hi=writer['start'],writer['end']
                        elif 'offset' in writer and ('bytes' in writer or 'size' in writer):
                            lo=writer['offset'];lo=int(lo,0) if isinstance(lo,str) else lo;hi=lo+writer.get('bytes',writer.get('size'))
                        else:raise ValueError('Unparsed accepted LINK writer')
                        if not 0<=lo<=hi<=len(base):raise ValueError('Accepted writer outside ROM')
                        if any(base[i]!=out[i] and not accepted_allowed[i] for i in range(lo,hi)):raise ValueError('Accepted runtime writer changed')
                        accepted_count+=1
                check_accepted(child)
        elif isinstance(value,list):
            for child in value:check_accepted(child)
    check_accepted(link)
    if accepted_count!=41717:raise ValueError('Accepted nested writer denominator changed')
    patch=create_bps(japanese,out)
    if apply_bps(japanese,patch)!=out:raise ValueError('Cumulative patch mismatch')
    report.update(status='LOCAL_FULL_WINDOW_HALFSPACE_CANDIDATE_NOT_RELEASE',sha256=sha(out),patch_sha256=sha(patch),space_summary=summary,native_text_changed=True,compressed_slots_changed=True,full_dictionary=dict(start=seg['new'],end=seg['new']+seg['size'],before_sha256=sha(base[seg['new']:seg['new']+seg['size']]),after_sha256=sha(packed),reason='Swap space leaves; refit only if required to fit every original slot'),text_pointer_bindings_preserved=10371,full_bindings_readback=8947,other_bindings_unchanged=1424,protected_segments_preserved=51,later_integrated_runtime_bytes_preserved=416,changed_encoded_bindings=len(changed_bindings),changed_encoded_starts=sum(base[a:a+len(b)]!=b for a,b in writes.items()),raw_unicode_before=dict(U0020=sum(r['Korean_actual_output'].count(' ') for r in corpus['rows']),U3000=sum(r['Korean_actual_output'].count('\u3000') for r in corpus['rows'])),reserved_native_token='8040',reserved_native_token_existing_collisions=0,space_native_policy='Full ordinary wordspaces8040=6px; layout8140=12px; saved/user names and compact streams unchanged',limitations=['Interior singleton classification is provisional until independent QA','Compact spaces remain8px;683UNKNOWN occurrences unchanged','Native dialogue reflow uses pixel width while retaining the original72-count page clock and manual LF','Natural runtime/saves/performance/hardware NOT_RUN by builder','Fullwindow byte6 and immutable sprite descriptor alias require independent consumer coverage; CPU checks are not natural menu traces'])
    report['accepted_nested_writers_checked']=accepted_count
    report['full_name_bindings']=435
    report['full_name_wordspace_bindings']=106
    report['sprite_width_metadata']='immutable descriptor identity; affine byte23 and generic allocator unchanged'
    report['sprite_priority_metadata_unchanged']=True
    report['compact_allocations_excluded']=[dict(start=0x1438,end=0x14e0),dict(start=0x2264,end=0x23b8)]
    report['event_page_clock_preserved']=72
    report['bitmap_converter_bytes']=104
    report['popup_centering']=dict(native_owner_start=0x25d08,native_owner_end=0x25da8,grid_px=6,tie_policy='floor leading halfunits, left bias3px',text_field_capacity=32,no_halfspace_rounding='native12px unchanged for valid inputs',oversized_source='empty reject above31B',padding_overflow='omit padding; preserve source')
    return out,patch,report,records,plans


def main():
    p=argparse.ArgumentParser()
    for name in ('baseline','japanese','corpus','link','components','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():raise ValueError('Fresh output required')
    for path,digest in ((a.corpus,'b1ccdd128a6b75917f0b7f010c6a1e2d032c01c7cf9844320a2e5f4aea8e4ad1'),(a.components,'5d45d6a100b95cff594c66c1308ac983198994de5a0c33f922f99cb81e3b9468'),(a.link,'82b143f8f7328a45a3a9af41d8284d6362dcda5003be6851a93095e0ce2260ee')):
        if sha(path.read_bytes())!=digest:raise ValueError('Frozen private input hash mismatch: '+str(path))
    image,patch,report,records,plans=candidate(a.baseline.read_bytes(),a.japanese.read_bytes(),json.loads(a.corpus.read_text(encoding='utf-8')),json.loads(a.link.read_text(encoding='utf-8')),json.loads(a.components.read_text(encoding='utf-8')))
    a.out.mkdir(parents=True)
    (a.out/'Xagros_Narikiri2_KOR_v1.1a_halfspace-test01.gba').write_bytes(image)
    (a.out/'Xagros_Narikiri2_KOR_v1.1a_halfspace-test01_FROM_JP.bps').write_bytes(patch)
    (a.out/'BUILD_RESULT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (a.out/'SPACE_PLAN.json').write_text(json.dumps(plans,indent=2)+'\n',encoding='utf-8')
    with (a.out/'SPACE_AUDIT.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    print(json.dumps(report))


if __name__=='__main__':main()
