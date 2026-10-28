"""Read exact v1.1a slots and plan conservative interior word-space changes."""
import argparse,csv,hashlib,json,struct
from collections import Counter
from pathlib import Path
from strict_packed_tree import unpack_tree,pack_tree
from strict_unit_codec import code_table,decode_parts,encode_parts,units,fit_parts_book
from strict_default_names import unpack_name
from narikiri2_text_spec import decode_game_text

sha=lambda b:hashlib.sha256(b).hexdigest()
BASE='8823db1cb72f1328136ccfd8fff1fbdca0c8489cbc7ccf90f7e4ecdbb1c37776'
FULL_NAME_STORAGES={0x2B580C+i*64 for i in range(201)}|{0x374A38+i*20+4 for i in range(232)}|{0x9784,0x978C}


def control_spans(tokens):
    # Actual event jump table9A524 and formatter2648 handlers. @ directives
    # consume their letter only; following digits are visible text, not args.
    visible_events=set(b'BCDEFGIMNRTcdefinrt')
    controls={};resets=set();i=0
    while i<len(tokens):
        if tokens[i] not in (b'%',b'@'):
            i+=1;continue
        begin=i;kind=tokens[i];i+=1
        if kind==b'%':
            while i<len(tokens) and len(tokens[i])==1 and tokens[i] in [bytes([c]) for c in b'-0123456789']:i+=1
            if i<len(tokens) and len(tokens[i])==1:
                spec=tokens[i]
                i+=1
                role='visible' if spec in (b's',b'd') else 'clear' if spec==b'l' else 'neutral' if spec in (b'k',b't',b'h') else 'unknown'
            else:role='unknown'
        elif i<len(tokens) and len(tokens[i])==1:
            code=tokens[i][0]
            role='visible' if code in visible_events else 'clear' if code in b'LP' else 'line' if code==ord('K') else 'neutral' if code==ord('S') else 'unknown'
            i+=1
        else:role='unknown'
        if role in ('clear','line'):resets.add(i-1)
        for n in range(begin,i):controls[n]=(begin,i,role)
    return controls,resets


def classify(tokens,index,controls=None,resets=None,*,visible_substitutions=True):
    if controls is None:controls,resets=control_spans(tokens)
    def space(unit):return unit in (b' ',b'\x81\x40')
    # Preserve every run and edge as a layout exception. An interior singleton
    # between visible glyphs is the only automatic word-separator rule.
    if index==0 or tokens[index-1]==b'\n':return 'INDENT'
    if index+1==len(tokens) or tokens[index+1]==b'\n':return 'TRAILING_ERASE'
    if space(tokens[index-1]) or space(tokens[index+1]):return 'COLUMN_ALIGNMENT'
    if not visible_substitutions and (index in controls or index-1 in controls or index+1 in controls):return 'CONTROL_ARGUMENT'
    if index in controls:return 'CONTROL_ARGUMENT'
    def neighbour(at,direction):
        while 0<=at<len(tokens):
            if at in controls:
                start,end,role=controls[at]
                if role=='neutral':at=start-1 if direction<0 else end;continue
                return 'visible' if role=='visible' else 'boundary' if role in ('clear','line') else 'unknown'
            token=tokens[at]
            if token in (b'\n',b'\x10'):return 'boundary'
            if token in (b'\x11',b'\x12'):at+=direction;continue
            if len(token)==1 and token[0]<32:return 'unknown'
            return 'visible'
        return 'boundary'
    left,right=neighbour(index-1,-1),neighbour(index+1,1)
    if left=='boundary':return 'INDENT'
    if right=='boundary':return 'TRAILING_ERASE'
    return 'WORD_SEPARATOR' if left==right=='visible' else 'CONTROL_ARGUMENT'


def swapped_space_book(book):
    out=bytearray(book);found=[]
    for index in range(struct.unpack_from('<H',book)[0]):
        at=4+index*8;a=struct.unpack_from('<H',book,at)[0]
        if not a&0x8000:continue
        token=book[at+4:at+4+(a&0x7fff)]
        replacement={b'\x81\x40':b'\x80\x40',b' ':b'\x81\x40'}.get(token)
        if replacement is None:continue
        out[at:at+8]=struct.pack('<HH',0x8000|len(replacement),0)+replacement.ljust(4,b'\0');found.append(token)
    if set(found)!={b' ',b'\x81\x40'}:raise ValueError('Space leaves missing')
    code_table(bytes(out))
    return bytes(out)


def audit(image,corpus,layout,components):
    if len(image)!=0x800000 or sha(image)!=BASE or len(corpus['rows'])!=10371:raise ValueError('Exact v1.1a corpus required')
    seg={s['name']:s for s in layout['segments']}
    books={kind:unpack_tree(image[seg[name]['new']:seg[name]['new']+seg[name]['size']]) for kind,name in [('full_text','full_book'),('compact','compact_book'),('extra','extra_book')]}
    extra={r['storage']:r for r in components['extra_ui']['rows']}
    swap=swapped_space_book(books['full_text'])
    records=[];plans=[];counts=Counter();native_by_binding={}
    for row in corpus['rows']:
        storage=int(row['pointer_storage'],16);start=int(row['current_start'],16);cap=int(row['original_slot_bytes'])
        if start!=int(row['original_start'],16) or int.from_bytes(image[storage:storage+4],'little')!=0x08000000+start:raise ValueError('Pointer/start binding mismatch')
        if row['category']=='fixed_name':
            raw=unpack_name(image[start:start+cap],(row['native_bytes']-1)//3)
        else:
            kind='full_text' if row['category']=='full_text' else 'compact'
            if storage in extra and not extra[storage]['existing_binding']:kind='extra'
            selection=int(row['variant_selection'])
            raw,original_encoded=decode_parts(image[start:start+cap],books[kind],283 if kind=='full_text' else 288,1 if selection==1 else 4,selection,allow_suffix=True)
        if sha(raw)!=row['native_sha256']:raise ValueError('Native hash mismatch '+row['binding_id'])
        native_by_binding[row['binding_id']]=raw
        tokens=units(raw[:-1],'full_text' if row['category']=='full_text' else 'compact')
        if b'\x80\x40' in raw:raise ValueError('Reserved8040 token already occurs: '+row['binding_id'])
        controls,resets=control_spans(tokens)
        rewritten=[];changed=0
        for n,token in enumerate(tokens):
            if token not in (b' ',b'\x81\x40'):
                rewritten.append(token);continue
            category='USER_NAME' if storage in (0x9784,0x978C) else classify(tokens,n,controls,resets) if row['category']=='full_text' else 'FIXED_FIELD_PADDING' if row['category']=='fixed_name' else 'UNKNOWN'
            desired=6 if category=='WORD_SEPARATOR' else 12 if row['category']=='full_text' else 8
            replacement=(b'\x80\x40' if category=='WORD_SEPARATOR' else b'\x81\x40') if row['category']=='full_text' and kind=='full_text' else token
            changed+=replacement!=token;rewritten.append(replacement)
            counts[category]+=1
            consumer='FULL_080015B8;SPRITE_080250E0_080021F4_CPU_PENDING' if storage in FULL_NAME_STORAGES else '080015B8' if row['category']=='full_text' else '08001AC8_OR_OTHER_COMPACT_PENDING'
            records.append(dict(binding_id=row['binding_id'],use_site=f"{row['category']}:{n}",category=category,consumer_id=consumer,source_hash=sha(raw),unicode_space_type='U+3000' if token==b'\x81\x40' else 'U+0020',native_space_hex=token.hex(),compression_mode='packed_tree_v2',normal_glyph_advance_px=12 if row['category']=='full_text' else 8,current_space_advance_px=12 if row['category']=='full_text' else 8,space_purpose=category,desired_advance_px=desired,evidence='native_slot_decode;interior_singleton_rule' if category=='WORD_SEPARATOR' else 'native_slot_decode;conservative_exception',status='PLANNED_NOT_RUNTIME_VERIFIED' if category=='WORD_SEPARATOR' else 'PRESERVED_EXCEPTION' if category!='UNKNOWN' else 'UNKNOWN_NOT_CHANGED'))
        if row['category']=='full_text':
            payload=b''.join(rewritten)
            if kind!='full_text':
                if payload!=raw[:-1]:raise ValueError('Unsupported extra-book native conversion')
                plans.append(dict(binding_id=row['binding_id'],compression_kind=kind,start=start,capacity=cap,before_sha256=sha(raw),native_hex=payload.hex(),changed_spaces=0,fixed_book_encoded_bytes=original_encoded,swapped_book_encoded_bytes=original_encoded,fixed_overflow=False,swapped_overflow=False))
                continue
            ascii_payload=payload.replace(b'\x80\x40',b' ')
            encoded=encode_parts([ascii_payload],'full_text',books['full_text']);swapped=encode_parts([payload],'full_text',swap)
            decoded,used=decode_parts(swapped,swap,283,1,1)
            if decoded!=payload+b'\0' or used!=len(swapped):raise ValueError('Halfspace native roundtrip')
            if payload.replace(b'\x80\x40',b'\x81\x40')!=raw[:-1].replace(b' ',b'\x81\x40'):raise ValueError('Nonspace native changes')
            plans.append(dict(binding_id=row['binding_id'],compression_kind=kind,start=start,capacity=cap,before_sha256=sha(raw),native_hex=payload.hex(),changed_spaces=changed,fixed_book_encoded_bytes=len(encoded),swapped_book_encoded_bytes=len(swapped),fixed_overflow=len(encoded)>cap,swapped_overflow=len(swapped)>cap))
    refit=None
    if any(p['swapped_overflow'] for p in plans):
        full=[p for p in plans if p['compression_kind']=='full_text']
        swap,refit=fit_parts_book([[bytes.fromhex(p['native_hex'])] for p in full],'full_text',[p['capacity'] for p in full],64)
        refit={k:v for k,v in refit.items() if k not in ('training_weights','encoded_sizes')}
    for p in plans:
        size=len(encode_parts([bytes.fromhex(p['native_hex'])],'full_text',swap)) if p['compression_kind']=='full_text' else p['fixed_book_encoded_bytes']
        p.update(final_book_encoded_bytes=size,final_overflow=size>p['capacity'])
    return records,plans,dict(bindings_checked=len(corpus['rows']),full_bindings=len(plans),space_occurrences=len(records),categories=dict(counts),planned_native_conversions=sum(p['changed_spaces'] for p in plans),fixed_book_overflows=sum(p['fixed_overflow'] for p in plans),swapped_book_overflows=sum(p['swapped_overflow'] for p in plans),final_book_overflows=sum(p['final_overflow'] for p in plans),dictionary_refit=refit),swap


def main():
    p=argparse.ArgumentParser()
    for name in ('baseline','corpus','layout','components','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    records,plans,report,swap=audit(a.baseline.read_bytes(),json.loads(a.corpus.read_text(encoding='utf-8')),json.loads(a.layout.read_text(encoding='utf-8')),json.loads(a.components.read_text(encoding='utf-8')))
    with (a.out/'SPACE_AUDIT.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    (a.out/'SPACE_PLAN.json').write_text(json.dumps(plans,indent=2),encoding='utf-8')
    (a.out/'SPACE_POLICY.json').write_text(json.dumps(dict(report,policy='Only singleton interior full-text spaces become8040; full-width exceptions8140, compact/name bytes unchanged',baseline_sha256=BASE,space_data='PLANNED_ONLY',space_render='PROTOTYPE_ONLY',reserved_token_collision_bindings=0),indent=2),encoding='utf-8')
    (a.out/'SWAPPED_FULL_BOOK.bin').write_bytes(pack_tree(swap))
    print(json.dumps(report))


if __name__=='__main__':main()
