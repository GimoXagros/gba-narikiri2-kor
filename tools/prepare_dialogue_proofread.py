"""Integrate individually adjudicated reviews, preserving their source evidence."""
import json,re,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];W=ROOT/'private_validation/dialogue-proofread-20260923'
read=lambda p:json.loads(p.read_text('utf-8'))
d=read(W/'latest-dialogue-book.json');early=read(W/'sol-review-00000-03999.json');late=read(W/'late_dialogue_review.json')
rows={r[0]:r for r in d['full']}
norm=lambda s:s.replace('\u3000',' ').replace('⟦','').replace('⟧','')
changes=[];decisions=[]
def add(key,after,reason):
 r=rows[key];changes.append(dict(id=r[1],binding=key,storage=r[10],source=r[4],before=norm(r[5]),after=norm(after),reason=reason))
for r in read(ROOT/'translation/description_format_20260923.json'):
 key=next(k for k,v in rows.items() if int(v[10],16)==r['storage'])
 add(key,r['after'],'사용자 지정: 슬레이어 소드 한 줄 표시' if r['kind']=='item' else '사용자 지정: 속성 괄호 다음 공백 제거')
for r in early['corrections']:
 if r['id'] in ('D03144','D03454'):
  decisions.append(dict(id=r['id'],decision='RETAIN',reason='달 예정은 올바른 문법. 치료 가능한 옷은 직전 의사 설명을 받아 남녀 의사 의상을 통칭하므로 고유 직업 하나로 축소하지 않음.'));continue
 after=r['after_korean']
 if r['id']=='D00252':after='안쪽 숲에서 수상한 여자아이를 봤다는 녀석이 있었는데…%k'
 if r['id']=='D01002':after='그렇군요．원시적이지만 긴급 난방으로는 제격이군요．'
 if r['id']=='D02181':after='앞으로도 남몰래 응원하겠습니다…'
 add(r['binding'],after,r['reason'])
for r in late['corrections']:
 if r['dialogue_id']=='D06356':
  decisions.append(dict(id=r['dialogue_id'],decision='RETAIN',reason='사용자가 元/元素의 시스템 속성을 무로 명시했으므로 원으로 되돌리는 제안을 거부.'));continue
 if r['dialogue_id']=='D04788':
  decisions.append(dict(id=r['dialogue_id'],decision='RETAIN',reason='D03017–D03020에서 불가지의 학문과 불가지/불가사리 말장난을 확립함. 불가지는 불가능한 한국어가 아닌 철학 용어이며, 재등장하는 의미를 유지.'));continue
 after=r['after']
 if r['dialogue_id']=='D04798':after='오우！너희와 함께라면 무슨 일이든 괜찮아！@P좋았어．이번에 함께 세계정복하자！'
 reason={'fixed_place':'확정 지명과 띄어쓰기 통일','place_meaning':'採取場(채집장)와 採掘場(채굴장)을 연결 위치별로 구분','meaning':'원문의 위협 또는 동행 조건을 정확하게 전달'}[r['category']]
 add(r['binding_id'],after,reason)
# These six source pairs and three element statements were individually read by root.
for identity in ['D00193','D00401','D00411','D00424','D03315','D03465']:
 for key,r in rows.items():
  if r[1]==identity:
   assert '浮遊死都' in r[4] and '부유사도' in r[5]
   final=norm(r[5]).replace('부유사도','부유 사도')
   if identity=='D03465':final='@L이『부유 사도』조사차 왔는데…'
   add(key,final,'확정 지명 부유 사도와 일치')
for identity in ['D01673','D06984','D07620']:
 for key,r in rows.items():
  if r[1]==identity:
   assert '＜雷＞' in r[4]
   add(key,norm(r[5]).replace('〈뢰〉','〈뇌〉').replace('〈원〉','〈무〉'),'사용자 확정 속성 표기 뇌·무와 일치')
key='D04455:00348CF8'
add(key,'작별 선물이다．가져가！','センベツ는 떠나는 사람에게 주는 선물. 뒤 대사의 곡괭이 선물 문맥도 확인.')
add('D00600:002B2FC8','명공이 만든 스틸 소드','スティールソード는 확정 아이템명 스틸 소드. 일반명 강철검 대신 동일 고유명사 사용.')
add('D00234:0008BF70','%l『레그니아 마을』에 있지 않을까%k','확정 지명 레그니아 마을과 일치.')
decisions.extend([
 dict(id='D00214',decision='RETAIN',reason='押さえん/開かれん 고어 해석을 단순 부정 오류로 취급하지 않음. 모든 요점을 만족해야 길이 열린다는 현행 의미 유지.'),
 dict(id='D00269',decision='RETAIN',reason='생존의 중요성을 이미 전달하므로 취향에 따른 의역 교체 생략.'),
 dict(id='D00274',decision='RETAIN_CONTROL',reason='기존 한국어 추가 %k는 번역 어휘가 아닌 기다림 제어. 이번 교정은 실행 제어를 보존.'),
 dict(id='D00794',decision='RETAIN',reason='기존 JOB 및 SELECT_JOB 이름은 승인된 의상 카탈로그에 맞춘 표기. 원본의 임시/별도 카탈로그 라벨로 되돌리지 않음.'),
 dict(id='D01381',decision='RETAIN',reason='일본어 女神様 자체가 단복수를 확정하지 않으며 두 여신 문맥과 충돌하는 변경을 피함.'),
 dict(id='D02958',decision='RETAIN',reason='원문 대사의 ドニエス와 아이템 ドエニス 표기가 다르지만 확정 아이템명 도에니스꽃을 유지.'),
 dict(id='D03018',decision='RETAIN',reason='不可知/ふかしイモ의 유사음 농담을 불가지/불가사리로 옮긴 기존 현지화 유지.'),
 dict(id='D04439',decision='RETAIN',reason='鍛冶屋에는 대장간과 대장장이 뜻이 모두 있으므로 대장간을 차리겠다는 현행 유지.'),
 dict(id='D04679',decision='RETAIN',reason='たいれつ/タイヤキ의 유사음 농담을 대열/대어로 옮긴 기존 현지화 유지.'),
 dict(id='NUMERIC_14_GROUPS',decision='RETAIN',reason='모두 한자 숫자·한글 수사·아라비아 표기 또는 루트 중 하나라는 서술 차이. 효과 수치 변화 없음.')])
assert len({r['storage'] for r in changes})==len(changes)
for r in changes:assert r['before']!=r['after']
# Review scope must cover each physical field, including source aliases.
ek=early.get('reviewed_bindings',[])
if isinstance(ek,int):ek=early['reviewed_binding_keys']
lk=late['coverage']['binding_ids']
assert set(ek)|set(lk)==set(rows),(len(ek),len(lk),early.keys())
coverage=dict(source_sha256=d['meta']['korean_sha256'],unique_full_text=8037,full_text_bindings=8945,compact_fields=1227,reviewed_full_bindings=len(set(ek)|set(lk)),reviewed_compact_fields=len(read(W/'compact-review.json')['reviewed_ids']),changed_bindings=len(changes),changed_ids=len({r['id'] for r in changes}),decisions=decisions)
(W/'CHANGE_DECISIONS_PRIVATE.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2),'utf-8')
digest=lambda value:hashlib.sha256(value.encode('utf-8')).hexdigest()
public=[{k:v for k,v in row.items() if k not in ('source','before')} |
        {'source_sha256':digest(row['source']),'before_sha256':digest(row['before'])}
        for row in changes]
(ROOT/'translation/dialogue_proofread_20260923.json').write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n','utf-8')
(W/'REVIEW_COVERAGE.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps({k:v for k,v in coverage.items() if k!='decisions'}))
