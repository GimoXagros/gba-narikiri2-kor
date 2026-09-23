"""Apply explicit source-bound review decisions without moving existing assets."""
import argparse,hashlib,json,re,struct,unicodedata,math
from pathlib import Path
from confirmed_text_edits import encode_full,normalized
from extract_dialogue_book_data import source_text,compact_korean,readable
from narikiri2_text_spec import decode_game_text
from bps import create_bps,apply_bps
ROOT=Path(__file__).resolve().parents[1]
BASE_SHA='64faac67ef9800758cc632af8316232e0d73489178cebac8172d1f2adfd711af'
JP_SHA='a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7'
TOKENS=re.compile(r'@[A-Za-z]|%[0-9]*[A-Za-z]')
def sha(b):return hashlib.sha256(b).hexdigest()
def build(base,jp,changes):
 assert sha(base)==BASE_SHA and sha(jp)==JP_SHA
 result=bytearray(base);writes=[];owners=set()
 for r in changes:
  st=int(r['storage'],16) if isinstance(r['storage'],str) else r['storage']
  assert st not in owners and 0<=st<len(jp)-3
  assert not any(st<b and st+4>a for a,b in [(0xA601C,0xA6800),(0xAC3F4,0x2B2CAC)])
  owners.add(st);_,jr=source_text(jp,st);_,raw=source_text(base,st)
  old=normalized(decode_game_text(base,raw));source=jr.decode('cp932');final=r['after']
  assert sha(old.encode('utf-8'))==r['before_sha256'] and sha(source.encode('utf-8'))==r['source_sha256'],f"Source mismatch {r.get('id')} {st:x}"
  assert old!=final and TOKENS.findall(old)==TOKENS.findall(final)
  nums=lambda t:re.findall(r'\d+',unicodedata.normalize('NFKC',TOKENS.sub('',t)))
  assert nums(old)==nums(final) or (r.get('numeric_source_correction') and nums(source)==nums(final)),f"Number change {r.get('id')}"
  oldlines=TOKENS.sub('',old).split('\n');lines=TOKENS.sub('',final).split('\n')
  description=(0x2B2CBC<=st<0x2B2CAC+157*20 and (st-0x2B2CBC)%20==0) or 0x3A7824<=st<=0x3A7A58
  if description:assert len(lines)<=2 and max(map(len,lines))<=18
  else:
   # Existing dialogue automatically wraps at 18 full-width cells. Preserve
   # every page/wait token and do not add a wrapped row to any existing page.
   pages=lambda s:re.split(r'@P|%k',s)
   row_count=lambda s:sum(max(1,math.ceil(len(TOKENS.sub('',line))/18)) for line in s.split('\n'))
   assert all(row_count(b)<=row_count(a) for a,b in zip(pages(old),pages(final))),f"Wrapped page grew {r.get('id')}"
   assert len(lines)<=len(oldlines),f"New row needs consumer evidence {r.get('id')}"
  encoded=encode_full(final);assert normalized(decode_game_text(base,encoded))==final
  at=len(result);result.extend(encoded+b'\0');pointer=struct.pack('<I',0x08000000+at)
  result[st:st+4]=pointer
  writes.append({**r,'storage':f'{st:08X}','offset':f'{at:08X}','before_pointer':base[st:st+4].hex(),'after_pointer':pointer.hex(),'payload_sha256':sha(encoded)})
 assert len(result)<=0x2000000
 allowed={int(w['storage'],16)+i for w in writes for i in range(4)}
 assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(base,result)))
 for r in writes:assert normalized(decode_game_text(result,source_text(result,int(r['storage'],16))[1]))==r['after']
 return bytes(result),dict(base_sha256=sha(base),japanese_sha256=sha(jp),target_sha256=sha(result),changed_bindings=len(writes),original_data_moved=False,existing_changes_limited_to_reviewed_pointers=True,element_icons_unchanged=True,writes=writes)
def final_dataset(rom,report,dialogue_book):
 d=json.loads(dialogue_book.read_text('utf-8'))
 originals={r[10]:(r[4],normalized(r[5])) for r in d['full']}
 changes={r['storage']:r for r in report['writes']}
 for r in d['full']:
  off,raw=source_text(rom,int(r[10],16));text=decode_game_text(rom,raw)
  r[5]=text;r[6]=readable(text);r[12]=f'{off:08X}'
  r[7]='교정' if r[10] in changes else '원문 대조·유지'
 d['changes']=[{**r,'source':originals[r['storage']][0],'before':originals[r['storage']][1]}
               for r in report['writes']]
 d['meta']['korean_sha256']=sha(rom)
 d['meta']['review_status']='Awaiting complete review coverage ledger; builder does not confer semantic review'
 return d
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for n in ['base','japanese','changes','out']:p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--dialogue-book',type=Path,help='Optional private source-bound book dataset to export alongside the ROM')
 a=p.parse_args();base=a.base.read_bytes();jp=a.japanese.read_bytes();changes=json.loads(a.changes.read_text('utf-8'))
 rom,report=build(base,jp,changes);patch=create_bps(jp,rom);assert apply_bps(jp,patch)==rom
 a.out.mkdir(parents=True,exist_ok=False)
 (a.out/'Xagros_Narikiri2_KOR_proofread_test.gba').write_bytes(rom)
 (a.out/'Xagros_Narikiri2_KOR_proofread_test_JP.bps').write_bytes(patch)
 (a.out/'BUILD_MANIFEST.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
 if a.dialogue_book:
  (a.out/'final-dialogue-book.json').write_text(json.dumps(final_dataset(rom,report,a.dialogue_book),ensure_ascii=False),'utf-8')
 print(json.dumps({**{k:v for k,v in report.items() if k!='writes'},
                   'private_dialogue_book_export':'PASS' if a.dialogue_book else 'NOT_RUN'}))
