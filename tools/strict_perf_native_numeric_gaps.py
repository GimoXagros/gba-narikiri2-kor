"""Pure derivation of source-semantic immutable native numeric input gaps.

All inputs are caller supplied. No local/private path, cached pointer list,
original text payload or runtime observation is a build input.
"""
import bisect,hashlib,re,struct
sha=lambda b:hashlib.sha256(b).hexdigest()
NAMES=('full_bounds','compact_bounds','extra_bounds')

def unpack_bounds24(blob):
    """Strict read-only SBS2 decoder, independent of repository build imports."""
    if len(blob)<12:raise ValueError('Truncated bounds header')
    magic,pages,total,offset=struct.unpack_from('<IHHI',blob)
    if magic!=0x32534253 or not pages or not total or offset!=12+8*pages or len(blob)!=offset+3*total:
        raise ValueError('Bounds version/extent')
    rows=[];lastpage=0
    for i in range(pages):
        page,count,first=struct.unpack_from('<IHH',blob,12+8*i)
        if page&32767 or page<=lastpage or not count or first!=len(rows) or first+count>total:
            raise ValueError('Invalid page directory')
        lastpage=page
        for index in range(first,first+count):
            at=offset+3*index;word=int.from_bytes(blob[at:at+3],'little')
            rows.append((page+(word&32767),word>>15))
    if len(rows)!=total or rows!=sorted(rows) or len({p for p,n in rows})!=len(rows):
        raise ValueError('Bounds order/count/duplicates')
    if any(not 1<=n<=511 or not 0x08000000<=p<p+n<=0x08800000 for p,n in rows):
        raise ValueError('Input exact slot outside original ROM')
    return rows

def current_bounds(base,link):
    """Read exactly the three current linked bounds owners."""
    result={}
    for s in link['layout']['segments']:
        if s['name'] not in NAMES:continue
        start,end=s['new'],s['end']
        if not 0<=start<end<=len(base) or end-start!=s['size']:raise ValueError('Bounds owner extent')
        if s['name'] in result:raise ValueError('Duplicate bounds owner')
        result[s['name']]=base[start:end]
    if set(result)!=set(NAMES):raise ValueError('All three current bounds owners required')
    return result

def derive_native_numeric_gaps(jp,adopted,base,bounds,link):
    if len(base)!=0x800000 or len(jp)%4 or len(jp)<0x800000 or len(adopted)<0x800000:
        raise ValueError('Complete original/adopted/current 8MiB input extents')
    if sha(jp)!=link['source_sha256'] or sha(adopted)!=link['adopted_sha256']:
        raise ValueError('Source identities differ from explicit link')
    if bounds!=current_bounds(base,link):raise ValueError('Explicit bounds differ from current linked owners')
    tables={name:unpack_bounds24(bounds[name]) for name in NAMES}
    union=sorted({p for entries in tables.values() for p,n in entries})
    original_slots=[(p-0x08000000,n) for name in ('full_bounds','compact_bounds') for p,n in tables[name]]
    region=(min(p for p,n in original_slots),max(p+n for p,n in original_slots))
    literal_refs={}
    for storage,(pointer,) in enumerate(struct.iter_unpack('<I',jp)):
        offset=pointer-0x08000000
        if not region[0]<=offset<region[1] or pointer in union:continue
        end=jp.find(b'\0',offset,min(offset+65,len(jp)))
        if end<0:continue
        raw=jp[offset:end]
        cleaned=re.sub(rb'%[-+ #0]*[0-9]*(?:\.[0-9]+)?[dguxXfFc]',b'',raw)
        if not raw or not re.fullmatch(rb'[0-9 \t\r\n.,:/+\-]*',cleaned):continue
        if adopted[offset:end+1]!=jp[offset:end+1] or base[offset:end+1]!=jp[offset:end+1]:continue
        literal_refs.setdefault(pointer,{'native_hex':(raw+b'\0').hex(),'ascii_repr':repr(raw),
            'pointer_storages':[]})['pointer_storages'].append(storage*4)
    gaps={}
    for pointer,literal in sorted(literal_refs.items()):
        at=bisect.bisect_left(union,pointer)
        if at==0 or at==len(union):continue
        low,high=union[at-1]+1,union[at]
        if any(low<=start<high for start in union):raise AssertionError('Registered start in native gap')
        gaps.setdefault((low,high),[]).append({'pointer':hex(pointer),**literal})
    return {'status':'COMPLETE_SOURCE_REFERENCED_NATIVE_NUMERIC_GAPS',
        'jp_sha256':sha(jp),'adopted_sha256':sha(adopted),'base_sha256':sha(base),
        'historical_region':list(region),'registered_union_count':len(union),
        'literal_count':len(literal_refs),'gap_count':len(gaps),
        'gaps':[{'low':low,'high':high,'literals':literals} for (low,high),literals in sorted(gaps.items())],
        'contract':'All gap pointers are native under exact-start semantics. No compressed input bytes are inspected.'}
