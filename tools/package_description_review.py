"""Package the source-reviewed local test revision and its evidence."""
import ast,csv,json,shutil,zipfile,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'private_validation/description-review-20260923'
out=ROOT.parent/'나리키리 던전2 추가작업/아이템_몬스터설명_교정_테스트_20260923'
out.mkdir(exist_ok=False)
for f in (work/'product-final').iterdir():shutil.copy2(f,out/f.name)
rows=json.loads((ROOT/'private_validation/description-review-20260923/review_full_private.json').read_text('utf-8'))
with (out/'일본어_한국어_설명대조표.tsv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f,delimiter='\t');w.writerow(['구분','내부ID','도감번호','일본어명','한국어명','일본어설명','이전번역','수정번역','변경'])
 for r in rows:
  if r['kind']=='item' and not r['id']:continue
  w.writerow([r['kind'],r['id'],r.get('book_no',''),r['name_jp'],r['name'],r['jp'],r['previous'],r['final'],r['changed']])
with (out/'고정용어.tsv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f,delimiter='\t');w.writerow(['구분','원문','고정표기','비고'])
 for r in rows:
  if r['id']:w.writerow([r['kind'],r['name_jp'],r['name'],'기존 명칭 유지'])
 terms=json.loads((ROOT/'translation/v09a_character_terms.json').read_text('utf-8'))
 for v in terms.values():
  if isinstance(v,list):
   for t in v:
    if isinstance(t,dict) and 'japanese' in t and 'short' in t:w.writerow(['캐릭터',t['japanese'],t['short'],t.get('full','')])
 tree=ast.parse((ROOT/'tools/build_place_names.py').read_text('utf-8'))
 names=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='NAMES' for t in n.targets))
 for n in names:w.writerow(['지명','',n,'기존 확정 표기'])
 for a,b in zip('火水地風雷光闇元','화수지풍뇌광암무'):w.writerow(['속성',a,b,f'아이템: {b}속성 / 도감: ＜{b}＞ / 한자 아이콘 유지'])
screens=out/'확인화면';screens.mkdir()
for kind in ['item','monster']:
 for core in ['checked','vbam']:
  report=json.loads((work/f'{kind}-{core}/REPORT.json').read_text('utf-8'))
  assert report['rom_sha256']==hashlib.sha256((out/'Xagros_Narikiri2_KOR_descriptions_test.gba').read_bytes()).hexdigest()
  assert len(report['records'])=={'item':156,'monster':142}[kind]
  shutil.copy2(work/f'{kind}-{core}/REPORT.json',out/f'{kind}_{core}_검증.json')
 for f in (work/f'{kind}-checked').glob('contact_*.png'):shutil.copy2(f,screens/f'{kind}_{f.name}')
for kind,files in [('item',['149_149','098_098']),('monster',['042_084','044_138','063_115','129_134'])]:
 for s in files:shutil.copy2(work/f'{kind}-checked/screens/{s}_4x.png',screens/f'{kind}_{s}.png')
(out/'읽어주세요.txt').write_text('''아이템 및 몬스터 설명 교정 테스트 — 2026-09-23

아이템 설명 156개와 몬스터 도감 설명 142개를 일본어 원문과 대조했습니다.
아이템은 원문 스타일에 맞춰 풍속성·광속성·뇌속성 등으로 표기합니다.
예: ＜녹정석＞ / 풍속성의 옷을 만드는 돌
도감의 속성 표시는 요청하신 ＜화＞·＜수＞·＜지＞·＜풍＞·＜뇌＞·＜광＞·＜암＞·＜무＞입니다.
속성 한자 아이콘은 변경하지 않았습니다.
줄넘침 문장은 원문 뜻과 효과 수치를 유지하며 최대 두 줄로 교정했습니다.
클라스의 옷 설명에 잘못 들어갔던 크레스도 클라스로 수정했습니다.

GBA 파일을 실행하세요. 기존 .sav는 먼저 백업하고, ROM과 같은 기본 파일명으로 복사하여 사용하세요.
기존 저장 상태 대신 게임 내 저장을 불러오면 새 설명을 확인하기 좋습니다.
JP.bps는 일본어 원본에 적용하는 패치입니다. 원본 SHA-256은 BUILD_MANIFEST.json의 기반 검사 및 빌드 자료에 기록되어 있습니다.
일본어 원본 SHA-256: a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7

검증: mGBA와 VBA-M 코어에서 아이템 156개/몬스터 142개를 각각 순회하고 항목명 픽셀을 확인했습니다.
모든 설명은 두 줄·줄당 18칸 이내이며, 첨부 모아보기에서 표시를 점검했습니다.
검증에는 별도 메모리의 보유/발견 플래그를 사용했으며 실제 플레이로 전부 획득한 검증은 아닙니다.
테스트 플래그는 배포 ROM이나 사용자 저장 파일에 기록하지 않았습니다.
기존 데이터는 이동하지 않았고 새 설명을 끝에 추가한 뒤 해당 설명 포인터만 바꿨습니다.
''','utf-8-sig')
with zipfile.ZipFile(out.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as z:
 for f in out.rglob('*'):
  if f.is_file():z.write(f,f.relative_to(out))
print(out.with_suffix('.zip'))
