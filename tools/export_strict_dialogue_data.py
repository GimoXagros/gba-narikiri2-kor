"""Read final in-place streams for private bilingual exports; never a release gate."""
import argparse,csv,hashlib,io,json,os,struct,tempfile
from pathlib import Path
from strict_text_bindings import JP_SHA256,BASELINE_SHA256,require_image
from strict_packed_tree import unpack_tree
from strict_unit_codec import decode_parts
from strict_default_names import unpack_name
from extract_dialogue_book_data import compact_korean
from narikiri2_text_spec import decode_game_text
from v09c_io import atomic_write_new

ROOT=Path(__file__).resolve().parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
def csv_rows(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def csv_bytes(rows):
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
    writer.writeheader();writer.writerows(rows)
    result=stream.getvalue().encode('utf-8')
    if list(csv.DictReader(io.StringIO(result.decode('utf-8'),newline='')))!=[
        {k:str(v) for k,v in row.items()} for row in rows]:raise ValueError('CSV roundtrip')
    return result
def word(data,at):return struct.unpack_from('<I',data,at)[0]


def publish_export(out, files):
    """Stage the complete export and preserve foreign files on failure.

    Ordinary failures roll back owned outputs so the same path can be retried.
    A process/power interruption is not an atomic multi-file transaction.
    """
    out=Path(out)
    if out.exists() or out.is_symlink():raise FileExistsError('Fresh export directory required')
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.dialogue-export-',dir=out.parent) as directory:
        staged=[]
        for name,data in files:
            if Path(name).name!=name:raise ValueError('Export filename must be a basename')
            path=Path(directory)/name
            atomic_write_new(path,data)
            stat=path.stat();staged.append((path,out/name,data,(stat.st_dev,stat.st_ino)))
        out.mkdir()  # Exclusive: do not acquire an existing output directory.
        stat=out.stat();directory_id=(stat.st_dev,stat.st_ino)
        published=[]
        try:
            for source,destination,data,identity in staged:
                if os.name=='nt':os.rename(source,destination)
                else:os.link(source,destination)
                published.append((destination,identity))
                if destination.read_bytes()!=data:raise OSError('Export read-back mismatch')
        except BaseException:
            for path,identity in reversed(published):
                if path.exists() and not path.is_symlink():
                    stat=path.stat()
                    if (stat.st_dev,stat.st_ino)==identity:path.unlink()
            if out.exists() and not out.is_symlink():
                stat=out.stat()
                if (stat.st_dev,stat.st_ino)==directory_id:
                    try:out.rmdir()
                    except OSError:pass  # A foreign output remains; preserve it.
            raise


def cstring(data,start):
    end=data.find(b'\0',start,min(start+4096,len(data)))
    if end<0:raise ValueError('Unterminated source string')
    return data[start:end]

def keyboard_display(raw,glyphs):
    """Keep keyboard glyph codes explicit; their visual mapping is not prose."""
    parts=[];begin=0
    for index,value in enumerate(raw):
        if 0xA1<=value<=0xDF:
            if index>begin:parts.append(compact_korean(raw[begin:index],glyphs))
            parts.append(f'⟦FONT:{value:02X}⟧');begin=index+1
    if begin<len(raw):parts.append(compact_korean(raw[begin:],glyphs))
    return ''.join(parts)


def export(japanese,adopted,rom,link,components,text_build,previous,out):
    paths={k:Path(v) for k,v in locals().copy().items()}
    out=paths['out']
    if out.exists():raise FileExistsError('Fresh export directory required')
    jp=paths['japanese'].read_bytes();ko=paths['adopted'].read_bytes();image=paths['rom'].read_bytes()
    require_image(jp,JP_SHA256,0x800000,'Japanese source')
    require_image(ko,BASELINE_SHA256,13270790,'Adopted Korean source')
    linked=json.loads(paths['link'].read_text(encoding='utf-8'))
    if len(image)!=0x800000 or sha(image)!=linked['output_sha256']:raise ValueError('Linked ROM identity')
    build=json.loads(paths['components'].read_text(encoding='utf-8'))
    segments={s['name']:s for s in linked['layout']['segments']}
    books={}
    for kind,name in (('full_text','full_book'),('compact','compact_book'),('extra','extra_book')):
        s=segments[name];books[kind]=unpack_tree(image[s['new']:s['new']+s['size']])
    bindings=csv_rows(paths['text_build']/'TEXT_BINDINGS.csv')
    fits={r['binding_id']:r for r in csv_rows(paths['text_build']/'SLOT_FIT_REPORT.csv')}
    old={r['binding_id']:r for r in csv_rows(paths['previous'])}
    if len(bindings)!=10172 or len(fits)!=10172 or len(old)!=10172:raise ValueError('Historical denominator')
    glyphs=json.loads((ROOT/'config/private_glyph_order.json').read_text(encoding='utf-8'))['glyphs']
    rows=[];maps=[];natives={}
    def add(identity,kind,storage,start,capacity,native,encoded,parts,selection,original,review='ADDITIONAL_BINDING'):
        if not 0<encoded<=capacity or not 0<=start<start+capacity<=len(image):
            raise ValueError(identity+': slot extent')
        if image[storage:storage+4]!=jp[storage:storage+4] or word(image,storage)!=0x08000000+start:
            raise ValueError(identity+': pointer differs')
        if not native.endswith(b'\0') or b'\0' in native[:-1]:raise ValueError(identity+': native terminator')
        raw=native[:-1];oldstart=word(ko,storage)-0x08000000
        if cstring(ko,oldstart)!=raw:raise ValueError(identity+': adopted native bytes differ')
        text=(decode_game_text(image,raw) if kind=='full_text' else
              keyboard_display(raw,glyphs) if kind=='keyboard_glyph_row' else compact_korean(raw,glyphs))
        rows.append(dict(binding_id=identity,category=kind,Japanese_source=original,
            Korean_actual_output=text,review_status=review,pointer_storage=f'{storage:08X}',
            original_start=f'{start:08X}',current_start=f'{start:08X}',variant_selection=selection,
            original_slot_bytes=capacity,encoded_bytes=encoded,native_bytes=len(native),
            native_sha256=sha(native),validation='FINAL_ROM_DECODE_MATCHES_ADOPTED;GAME_COVERAGE_SEPARATE'))
        maps.append(dict(binding_id=identity,pointer_storage=f'{storage:08X}',
            pointer_width=4,pointer_kind='GBA_ROM_ABSOLUTE_LE32',original_pointer=f'{word(jp,storage):08X}',
            current_pointer=f'{word(image,storage):08X}',original_start=f'{start:08X}',current_start=f'{start:08X}',
            encoding='FIXED_NAME_9BIT' if kind=='fixed_name' else 'unit_inline_native_v1_packed_tree_v2',
            slot_capacity=capacity,encoded_bytes=encoded,native_output_bytes=len(native),
            inline_parts=parts,variant_selection=selection,native_sha256=sha(native),
            pointer_equal=True,start_equal=True,slot_overflow=0,native_equal=True,
            runtime_coverage='SEPARATE_GAME_ROUTE_EVIDENCE'))
    for binding in bindings:
        identity=binding['binding_id'];fit=fits[identity];prior=old[identity]
        kind=binding['category'];start=int(binding['jp_text_start']);size=int(fit['encoded_length'])
        parts,selection=int(fit['inline_part_count']),int(fit['inline_selection'])
        native,used=decode_parts(image[start:start+size],books[kind],int(fit['native_output_length']),parts,selection)
        if used!=size or sha(native)!=fit['native_output_sha256']:raise ValueError(identity+': final stream differs')
        original=cstring(jp,start).decode('cp932')
        if kind=='compact':original=original.replace('\x12','⟦모드전환⟧')
        add(identity,kind,int(binding['jp_pointer_storage']),start,int(binding['slot_capacity']),
            native,size,parts,selection,original,prior['review_status'])
        # The old book is context evidence; the final decoded bytes are text truth.
        natives[identity]=native
    for item in build['extra_ui']['rows']:
        start,storage=item['start'],item['storage']
        if item['existing_binding']:
            size=int(fits[item['existing_binding']]['encoded_length'])
            native=natives[item['existing_binding']]
        else:
            native,size=decode_parts(image[start:start+item['slot_capacity']],books['extra'],
                len(bytes.fromhex(item['native_hex']))+1,1,1,allow_suffix=True)
            if item.get('encoded_length',size)!=size:raise ValueError('Additional stream length')
        if native!=bytes.fromhex(item['native_hex'])+b'\0':raise ValueError('Additional native value')
        kind=('full_text' if storage in (0x2B580C,0x37548C) else
              'keyboard_glyph_row' if storage in (0x3A7A70,0x3A7A88) else 'compact')
        add(f'EXTRA_UI:{storage:08X}',kind,storage,start,item['slot_capacity'],native,size,1,1,
            cstring(jp,start).decode('cp932').replace('\x12','⟦모드전환⟧'))
    for storage,count in ((0x9780,3),(0x9788,2)):
        start=word(jp,storage)-0x08000000
        add(f'FIXED_NAME:{storage:08X}','fixed_name',storage,start,4,
            unpack_name(image[start:start+4],count),4,1,1,cstring(jp,start).decode('cp932'))
    if len(rows)!=10371 or len({r['binding_id'] for r in rows})!=10371:raise ValueError('Complete denominator')
    master=csv_bytes(rows);pointer=csv_bytes(maps)
    manifest=dict(rom_sha256=sha(image),rom_bytes=len(image),japanese_sha256=sha(jp),
        adopted_sha256=sha(ko),historical_bindings=10172,additional_ui_bindings=197,
        additional_fixed_names=2,total_bindings=len(rows),pointer_mismatches=0,stream_start_mismatches=0,
        native_mismatches=0,slot_overflows=0,release_eligible=False,
        csv_profile='Machine-readable lossless UTF-8. Import text columns as text; XLSX is the spreadsheet-safe view.',
        review_scope='Prior review labels preserved. This export performs no new translation or scene review.',
        keyboard_rows='Two keyboard rows preserve unresolved visual glyph codes as FONT:XX; no Unicode appearance claim.',
        files={'NARIKIRI2_v1.1_JP_KO_MASTER_UTF8.csv':dict(size=len(master),sha256=sha(master)),
               'NARIKIRI2_v1.1_POINTER_RUNTIME_MAP.csv':dict(size=len(pointer),sha256=sha(pointer))})
    publish_export(out,(('NARIKIRI2_v1.1_JP_KO_MASTER_UTF8.csv',master),('NARIKIRI2_v1.1_POINTER_RUNTIME_MAP.csv',pointer),
        ('workbook-data.json',json.dumps(dict(manifest=manifest,rows=rows),ensure_ascii=False).encode('utf-8')),
        ('NARIKIRI2_v1.1_SCRIPT_EXPORT_MANIFEST.json',(json.dumps(manifest,indent=2)+'\n').encode('utf-8'))))
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('japanese','adopted','rom','link','components','text-build','previous','out'):
        p.add_argument('--'+key,type=Path,required=True)
    print(json.dumps(export(**vars(p.parse_args())),indent=2))
