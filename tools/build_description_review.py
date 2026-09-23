"""Source-bound item/monster description revision; append strings, redirect fields."""
import argparse,csv,json,struct,hashlib,re,unicodedata
from pathlib import Path
from confirmed_text_edits import encode_full,normalized
from extract_dialogue_book_data import source_text,compact_korean
from narikiri2_text_spec import decode_game_text
from bps import create_bps,apply_bps
ROOT=Path(__file__).resolve().parents[1]
BASE='583b5bdf08f6b2c40147deef517694891ed687b6bf107a9a3dc1ecf5a81d7a6b'
JP='a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7'
def sha(b):return hashlib.sha256(b).hexdigest()
def build(base,jp):
    assert sha(base)==BASE and sha(jp)==JP
    ledger=json.loads((ROOT/'translation/description_review_20260923.json').read_text('utf-8'))
    assert len(ledger)==299 and sum(bool(r['changed']) for r in ledger)==88
    assert len({(r['kind'],r['id']) for r in ledger})==299
    result=bytearray(base);writes=[];checks=[]
    for r in ledger:
        st=r['storage'];_,jr=source_text(jp,st);_,old=source_text(base,st)
        assert sha(jr.decode('cp932').encode('utf-8'))==r['jp_sha256']
        previous=normalized(decode_game_text(base,old))
        assert sha(previous.encode('utf-8'))==r['previous_sha256']
        if not r['changed']:
            assert 'final' not in r
            checks.append(dict(kind=r['kind'],id=r['id'],source_review='JAPANESE_SOURCE_COMPARED',changed=False))
            continue
        text=r['final'];lines=text.split('\n')
        assert len(lines)<=2 and max(map(len,lines))<=18
        assert not re.search(r'@[A-Za-z]|%[0-9]*[A-Za-z]',text)
        assert all(t not in text for t in ('〈뢰〉','〈원〉','<뢰>','<원>'))
        if r['kind']=='item':assert not re.search(r'<[화수지풍뇌광암무]>',text)
        nums=lambda t:re.findall(r'\d+',unicodedata.normalize('NFKC',t))
        assert nums(jr.decode('cp932'))==nums(text) or (r['kind']=='item' and r['id'] in (23,127))
        raw=encode_full(text);assert normalized(decode_game_text(base,raw))==text
        assert text!=previous
        at=len(result);result.extend(raw+b'\0');new=struct.pack('<I',0x8000000+at)
        writes.append(dict(kind=r['kind'],id=r['id'],storage=hex(st),before=base[st:st+4].hex(),after=new.hex(),text_offset=hex(at),text_sha256=sha(raw)))
        result[st:st+4]=new
        checks.append(dict(kind=r['kind'],id=r['id'],widths=list(map(len,lines)),source_review='JAPANESE_SOURCE_COMPARED',changed=r['changed']))
    # Class's costume description must identify Claus, not the distinct Cress.
    st=0x3A77B8;assert source_text(jp,st)[1].decode('cp932')=='クラース'
    assert normalized(decode_game_text(base,source_text(base,st)[1]))=='크레스'
    raw=encode_full('클라스');at=len(result);result.extend(raw+b'\0');new=struct.pack('<I',0x8000000+at)
    result[st:st+4]=new;writes.append(dict(kind='proper_name',id='CLAUS_COSTUME',storage=hex(st),before=base[st:st+4].hex(),after=new.hex(),text_offset=hex(at),text_sha256=sha(raw)))
    allowed={int(w['storage'],16)+i for w in writes for i in range(4)}
    assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(base,result)))
    for r in ledger:
        text=normalized(decode_game_text(result,source_text(result,r['storage'])[1]))
        assert text==(r['final'] if r['changed'] else normalized(decode_game_text(base,source_text(base,r['storage'])[1])))
    return bytes(result),dict(base_sha256=sha(base),target_sha256=sha(result),item_descriptions=156,excluded_item_zero='unused sentinel retained',monster_descriptions=142,writes=writes,checks=checks,original_data_moved=False,element_icon_bytes_unchanged=True)
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('base','japanese','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();rom,report=build(a.base.read_bytes(),a.japanese.read_bytes());patch=create_bps(a.japanese.read_bytes(),rom);assert apply_bps(a.japanese.read_bytes(),patch)==rom
    a.out.mkdir(parents=True,exist_ok=False)
    (a.out/'Xagros_Narikiri2_KOR_descriptions_test.gba').write_bytes(rom)
    (a.out/'Xagros_Narikiri2_KOR_descriptions_test_JP.bps').write_bytes(patch)
    (a.out/'BUILD_MANIFEST.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
