"""Rebuild frozen runtime components from explicitly supplied, guarded inputs. NOT product.

Remaining direct table/copy/name/menu consumers deliberately remain open and
may fail. The image is only for offscreen discovery, never user delivery.
"""
import argparse,csv,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
from strict_boot_notice_1bpp import plan_notice_1bpp
from strict_owned_decode import assemble,assemble_sync_wrapper,assemble_name_initializer
from strict_stream_lookup import pack_bounds,assemble_lookup
from strict_packed_tree import pack_tree,assemble_decoder as assemble_unit_decoder
from strict_format_hook import dialogue_veneer
from strict_layout_core import Write,sha
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('japanese','adopted','text-build','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():raise ValueError('Fresh output folder required')
    jp,base=a.japanese.read_bytes(),a.adopted.read_bytes()
    from strict_text_bindings import require_image,JP_SHA256,BASELINE_SHA256
    require_image(jp,JP_SHA256,0x800000,'Japanese source')
    require_image(base,BASELINE_SHA256,13270790,'Adopted source')
    build=a.text_build
    frozen={
        'TEXT_SLOT_IMAGE_NOT_PLAYABLE.bin':'ba9a42690ce2899d9465a41cb326f31f4af6f4cc8047fcb4840f22e0ed3e5006',
        'TEXT_BINDINGS.csv':'c7912281d068454160724624a69f53817b98f77acfd50868700f9c5e2b61adc0',
        'SLOT_FIT_REPORT.csv':'036aef59d36c7c23d318b446b0f6448fd65bf7128ff76b8e1172ccc2f539ddd3',
        'EXPERIMENT_CODEBOOK_compact.bin':'25553331cee20c17c778ac6d63f790c7057b9274b35a8d8ccbb939644bef66d3',
        'EXPERIMENT_CODEBOOK_full_text.bin':'767011c4be9dd25311f73a9a57d8e131a5f5d8f40ffffbf8ef45ee92239f6574',
    }
    for name,expected in frozen.items():
        if sha((build/name).read_bytes())!=expected:raise ValueError('Frozen text input changed: '+name)
    image=(build/'TEXT_SLOT_IMAGE_NOT_PLAYABLE.bin').read_bytes()
    # One reviewed profile. Experimental ablations remain in private discovery tools.
    a.caller_buffer=a.default_names=a.actor_store=a.aliases=True
    a.event_allocation=a.extra_ui=a.bounds24=True
    with (build/'TEXT_BINDINGS.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    with (build/'SLOT_FIT_REPORT.csv').open(encoding='utf-8-sig',newline='') as f:fits=list(csv.DictReader(f))
    writes,notice=plan_notice_1bpp(base,jp)
    def add(name,start,data,why):
        writes.append(Write('owned_probe:'+name,start,base[start:start+len(data)],data,why,
            'diagnostic exact-boundary adapters; remaining consumers OPEN','frozen Japanese and adopted inputs',('exact_source','bounded_owner')))
    starts={};pointers={};bounds={'full_text':{},'compact':{}}
    for row in rows:
        start=int(row['jp_text_start']);size=int(row['encoded_length']);storage=int(row['jp_pointer_storage'])
        data=image[start:start+size]
        if start in starts and starts[start]!=data:raise ValueError('Conflicting stream')
        starts[start]=data;pointers[storage]=jp[storage:storage+4]
        bounds[row['category']][0x08000000+start]=int(row['slot_capacity'])
    for start,data in starts.items():add(f'stream_{start:06x}',start,data,'unchanged frozen compressed bytes at original JP start')
    for start,data in pointers.items():add(f'pointer_{start:06x}',start,data,'restore exact JP pointer storage/value')
    caps={k:max(int(r['native_output_length']) for r in fits if r['category']==k) for k in bounds}
    aliases=sorted({0x08000000+int(r['jp_text_start']) for r in fits if r['inline_part_count']=='4'})
    if len(aliases)!=7:raise ValueError('Alias denominator')
    books={k:pack_tree((build/f'EXPERIMENT_CODEBOOK_{k}.bin').read_bytes()) for k in bounds}
    symbols=dict(ALIAS_STARTS=0x08ca0000,FULL_BOUNDS=0x08c96800,FULL_COUNT=len(bounds['full_text']),
        FULL_BOOK=0x08c93000,FULL_BOOK_BYTES=len(books['full_text']),FULL_CAPACITY=caps['full_text'],
        COMPACT_BOUNDS=0x08c9ea00,COMPACT_COUNT=len(bounds['compact']),
        COMPACT_BOOK=0x08c95600,COMPACT_BOOK_BYTES=len(books['compact']),COMPACT_CAPACITY=caps['compact'],
        UNIT_DECODER=0x08c91801,BOUNDS_LOOKUP=0x08c91a01)
    extra_report=None
    if a.extra_ui:
        from strict_extra_ui import plan as plan_extra_ui
        extra_writes,extra_book,extra_bounds,extra_report=plan_extra_ui(jp,base,
            json.loads((ROOT/'config/ui_source_bindings.json').read_text()),rows,image,
            (build/'EXPERIMENT_CODEBOOK_compact.bin').read_bytes())
        for name,start,data in extra_writes:add(name,start,data,'additional source-bound UI text; original pointers and slot extents')
        # Audited diagnostic arena gap after full bounds and before compact bounds.
        if 0xc9c900+len(extra_book)>0xc9d300 or 0xc9d300+len(extra_bounds)>0xc9ea00:
            raise ValueError('Extra UI diagnostic extent')
        add('extra_book',0xc9c900,extra_book,'additional single glyph/byte tree, never whole templates')
        add('extra_bounds',0xc9d300,extra_bounds,'exact additional original stream starts and bounds')
        symbols.update(EXTRA_BOOK=0x08c9c900,EXTRA_BOOK_BYTES=len(extra_book),
            EXTRA_BOUNDS=0x08c9d300,EXTRA_COUNT=extra_report['new_streams'],EXTRA_CAPACITY=extra_report['max_output'])
    if a.bounds24:
        from strict_stream_lookup24 import pack_bounds24,assemble_lookup24
        bounds_packer,lookup_assembler=pack_bounds24,assemble_lookup24
    else:bounds_packer,lookup_assembler=pack_bounds,assemble_lookup
    for name,start,data in (
        ('owned',0xc91600,assemble(0x08c91600,caller_buffer=a.caller_buffer,**symbols)),
        ('unit',0xc91800,assemble_unit_decoder(0x08c91800)),('lookup',0xc91a00,lookup_assembler(0x08c91a00)),
        ('failstop',0xc91b00,b'\xfe\xe7'),('aliases',0xca0000,struct.pack('<7I',*aliases)),
        ('full_bounds',0xc96800,bounds_packer(list(bounds['full_text'].items()))),
        ('compact_bounds',0xc9ea00,bounds_packer(list(bounds['compact'].items()))),
        ('full_book',0xc93000,books['full_text']),('compact_book',0xc95600,books['compact'])):
        add(name,start,data,'owned notice suffix after lossless 1bpp notice conversion')
    ks=Ks(KS_ARCH_ARM,KS_MODE_THUMB)
    hooks=[]
    def wrap(name,entry,at,source,consumer=None,prelude=None,expected=None,resolve=0):
        if expected and base[entry:entry+len(expected)]!=expected:raise ValueError(name+' entry differs')
        if prelude is not None:
            # All listed preludes have no PC-relative access and no stack arguments.
            tramp=at+0x80
            code=bytes(ks.asm(prelude+'\n ldr r3,return_ptr\n bx r3\n .balign 4,0\n return_ptr: .word '+str(0x08000000+entry+8+1),addr=0x08000000+tramp)[0])
            add(name+'_trampoline',tramp,code,'replayed exact original entry before PC-relative instruction')
            consumer=0x08000000+tramp+1
        wrapper=assemble_sync_wrapper(0x08000000+at,decoder=0x08c91601,
            source_register=source,consumer=consumer,fail_stop=0x08c91b01,resolve=resolve,caller_buffer=a.caller_buffer)
        if len(wrapper)>0x80:raise ValueError('Wrapper extent')
        add(name+'_wrapper',at,wrapper,'owned native input remains valid through synchronous consumer')
        # 8-byte entry veneer; r3 is dead in these selected native prologues.
        patch=b'\x00\x4b\x18\x47'+struct.pack('<I',0x08000000+at+1)
        add(name+'_entry',entry,patch,'explicit consumer entry')
        hooks.append(dict(name=name,entry=entry,source_argument=source,original_consumer=consumer))
    wrap('template',0x2648,0xc91c00,1,prelude='push {r4-r7,lr}; sub sp,#8; movs r7,r0; movs r4,r1',expected=jp[0x2648:0x2650])
    # 98960 must preserve r3 and replay the full 16-byte high-register prologue.
    event=assemble_sync_wrapper(0x08c91d00,decoder=0x08c91601,source_register=0,consumer=0x08c91d81,fail_stop=0x08c91b01,caller_buffer=a.caller_buffer)
    event_tramp=bytes(ks.asm('push {r4-r7,lr}; mov r7,sl; mov r6,sb; mov r5,r8; push {r5-r7}; sub sp,#8; movs r5,r0; movs r0,#58; ldr r3,target; bx r3; .balign 4,0; target: .word 0x08098971',addr=0x08c91d80)[0])
    add('event_wrapper',0xc91d00,event,'before strlen and variable expansion')
    add('event_tramp',0xc91d80,event_tramp,'exact original16-byte event prologue')
    if base[0x98960:0x98970]!=jp[0x98960:0x98970]:raise ValueError('Event entry differs')
    add('event_entry',0x98960,dialogue_veneer(0x08098960,0x08c91d00),'decode before event expansion')
    wrap('argument',0x25d8,0xc91e00,0,consumer=0x08c1ea81,resolve=0x08c1e881)
    wrap('small',0x1ac8,0xc91f00,1,consumer=0x08c1ea01,resolve=0x08c1e881)
    wrap('simple',0x1df0,0xc92000,2,prelude='push {r4-r7,lr}; movs r5,r0; movs r6,r1; movs r3,r2',expected=jp[0x1df0:0x1df8])
    wrap('full_native',0x15b8,0xc92100,0,prelude='push {r4-r6,lr}; sub sp,#8; movs r4,r0; movs r6,#0',expected=jp[0x15b8:0x15c0])
    if a.default_names:
        if not a.caller_buffer:raise ValueError('Name initializer needs caller-owned output')
        from build_banked_font import assemble as assemble_adopted
        from strict_default_names import pack_name,assemble_decoder,assemble_initializer
        add('default_name_decoder',0xc92400,assemble_decoder(0x08c92400),'two additional original four-byte fixed-name fields')
        extras=[]
        for second,entry,at,name,storage in ((False,0xc01400,0xc92200,'banked_name_init_first',0x9780),
                                           (True,0xc01480,0xc92300,'banked_name_init_second',0x9788)):
            if any(int(r['jp_pointer_storage'])==storage for r in rows):raise ValueError('Extra field now duplicated')
            original=struct.unpack_from('<I',jp,storage)[0]-0x08000000
            after=struct.unpack_from('<I',jp,storage+4)[0]-0x08000000
            oldstart=struct.unpack_from('<I',base,storage)[0]-0x08000000
            native=base[oldstart:base.index(b'\0',oldstart)]
            if after!=original+4 or jp[original+3]!=0 or len(native)!=(6 if second else 9):
                raise ValueError('Default-name original slot/count contract')
            fullold=struct.unpack_from('<I',base,storage+4)[0]-0x08000000
            if second and base[fullold+4:fullold+7]!=b'\0'*3:raise ValueError('Second full name padding')
            packed=pack_name(native)
            add(name+'_stream',original,packed,'actual existing glyph IDs packed into original four-byte slot')
            add(name+'_pointer',storage,jp[storage:storage+4],'additional fixed-field JP pointer restored')
            extras.append(dict(storage=storage,start=original,slot_bytes=4,encoding='FIXED_COMPACT_GLYPH9_V1',
                glyph_count=len(native)//3,output_sha256=sha(native+b'\0'),packed_sha256=sha(packed)))
            old=assemble_adopted(ROOT/'asm'/(name+'.s'),entry,512,128)
            if base[entry:entry+len(old)]!=old:raise ValueError('Adopted name shim differs')
            new=assemble_initializer(0x08000000+at,fixed_decoder=0x08c92401,stream_decoder=0x08c91601,
                count=len(native)//3,second=second,fail_stop=0x08c91b01)
            add(name+'_new',at,new,'decode into existing game-owned 19-byte name field')
            add(name+'_entry',entry,b'\x00\x4b\x18\x47'+struct.pack('<I',0x08000000+at+1),'replace exact adopted name initializer')
    if a.actor_store:
        if not a.caller_buffer:raise ValueError('Actor store needs caller-owned output')
        from build_banked_font import assemble as assemble_adopted
        from strict_actor_name_store import assemble as assemble_actor_store
        old=assemble_adopted(ROOT/'asm/banked_actor_name_store.s',0xc1e800,512,128)
        if base[0xc1e800:0xc1e800+len(old)]!=old:raise ValueError('Adopted actor store differs')
        shadow=assemble_adopted(ROOT/'asm/banked_actor_name_store.s',0xc92700,512,128)
        add('native_actor_store',0xc92700,shadow,'same adopted native store, called only for unregistered native input')
        code=assemble_actor_store(0x08c92600,decoder=0x08c91601,native_store=0x08c92701,fail_stop=0x08c91b01)
        add('actor_store',0xc92600,code,'persist original compressed ROM identity rather than temporary decoded pointer')
        add('actor_store_entry',0xc1e800,b'\x00\x4b\x18\x47'+struct.pack('<I',0x08c92601),'exact adopted actor-name hook')
    if a.aliases:
        from strict_alias_link import assemble_job,assemble_arte_accessor
        from strict_runtime_select_job import descriptors,assemble_veneer
        from strict_asset_writeplan import title_veneer_owner
        owner=title_veneer_owner(jp,base)
        desc=descriptors(rows,fits)
        job,entry=assemble_job(0x08ca3200,descriptors=0x08ca3400,book=symbols['COMPACT_BOOK'],
            book_bytes=symbols['COMPACT_BOOK_BYTES'],unit_decoder=symbols['UNIT_DECODER'])
        if len(job)>0x200:raise ValueError('Alias job code overlaps descriptors')
        add('select_job',0xca3200,job,'common v2 decoder; menu owns one 3008-byte heap object until return')
        add('select_descriptors',0xca3400,desc,'actual table index selects all six shared-name variants')
        veneer=assemble_veneer(ROOT/'asm/strict_runtime_select_job_veneer.s',0x0837d980,0x08ca3201+entry)
        add('select_veneer',0x37d980,veneer,'audited retired title suffix verified by title_veneer_owner')
        if base[0x1c3b4:0x1c3b8]!=bytes.fromhex('e8f7f0fc'):raise ValueError('SELECT_JOB native call differs')
        add('select_call',0x1c3b4,bytes(ks.asm('bl 0x0837d980',addr=0x0801c3b4)[0]),'single SELECT_JOB owned menu boundary')
        arte=assemble_arte_accessor(0x08ca3a80,fail_stop=0x08c91b01)
        if len(arte)>0x180:raise ValueError('ARTE accessor extent')
        add('arte_accessor',0xca3a80,arte,'record index/mode produce exact opaque variant tag')
        if base[0x8c54:0x8c80]!=jp[0x8c54:0x8c80]:raise ValueError('ARTE original accessor differs')
        add('arte_entry',0x8c54,b'\x00\x4b\x18\x47'+struct.pack('<I',0x08ca3a81),'replay native lookup; full entry eight-byte branch is covered')
    if a.event_allocation:
        from strict_event_allocation import assemble as assemble_event_allocation
        from strict_runtime_select_job import assemble_veneer
        from strict_asset_writeplan import validate_reclaimed_suffix,plan_title_assets
        _,proof=plan_title_assets(jp,base)
        validate_reclaimed_suffix(0x37d978,0x37e36d,((0x37d980,0x37d990),(0x37d9a0,0x37e1ad),(0x37e1b0,0x37e1c0)))
        code=assemble_event_allocation(0x08c92800,fail_stop=0x08c91b01)
        add('event_allocation',0xc92800,code,'exact bounded native result size for original name expansion')
        add('event_allocation_veneer',0x37e1b0,assemble_veneer(ROOT/'asm/strict_runtime_select_job_veneer.s',0x0837e1b0,0x08c92801),'audited title suffix after staff-font consumed end')
        if base[0x98980:0x98984]!=jp[0x98980:0x98984]:raise ValueError('Original event allocation call differs')
        add('event_allocation_call',0x98980,bytes(ks.asm('bl 0x0837e1b0',addr=0x08098980)[0]),'replace only allocation call; original variable expansion loop and ownership preserved')
    ordered=sorted(writes,key=lambda w:w.start);previous=0;target=bytearray(base)
    for w in ordered:
        if w.start<previous or w.end>len(base) or len(w.before)!=len(w.after) or base[w.start:w.end]!=w.before:
            raise ValueError('Overlap/extent/guard: '+w.writer_id)
        if w.start>=notice['arena_start'] and not notice['arena_start']<=w.start<w.end<=notice['arena_end']:
            raise ValueError('Diagnostic code outside owned notice suffix')
        memoryview(target)[w.start:w.end]=w.after;previous=w.end
    if len(target)!=len(base):raise ValueError('Diagnostic size changed')
    for row in rows:
        s=int(row['jp_pointer_storage'])
        if target[s:s+4]!=jp[s:s+4]:raise ValueError('Protected pointer')
    a.out.mkdir(parents=True)
    (a.out/'RUNTIME_COMPONENT_SOURCE.bin').write_bytes(target)
    report=dict(input_files=frozen,status='DISCOVERY_DIAGNOSTIC_NOT_PRODUCT',size=len(target),sha256=sha(target),
        bindings=len(rows),unique_starts=len(starts),symbols=symbols,hooks=hooks,
        caller_owned_stack_buffer=a.caller_buffer,bounds24=a.bounds24,
        default_name_initializers=a.default_names,
        actor_store=a.actor_store,
        aliases=a.aliases,
        event_allocation=a.event_allocation,
        extra_fixed_fields=extras if a.default_names else [],
        extra_ui=extra_report,
        remaining_consumers='OPEN',runtime='NOT_RUN',release_eligible=False,
        writes=[w.manifest() for w in ordered])
    (a.out/'BUILD.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:report[k] for k in ('status','size','sha256','bindings','unique_starts')}))


if __name__=='__main__':main()
