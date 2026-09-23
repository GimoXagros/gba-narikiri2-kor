"""Package the reviewed local test build without altering prior deliveries."""
from pathlib import Path
import json, shutil, hashlib, zipfile
R=Path(__file__).resolve().parents[1]
W=R/'private_validation/dialogue-proofread-20260923'
P=W/'product-final-c'
D=R.parent/'나리키리 던전2 추가작업/전체대사_검교정_최종대사집_20260923'
B=R/'output/dialogue-proofread-20260923/outputs/final/나리키리2_일본어_한국어_최종대사집.xlsx'
D.mkdir(exist_ok=True)
assert hashlib.sha256((P/'Xagros_Narikiri2_KOR_proofread_test.gba').read_bytes()).hexdigest()=='7505ef506e4fc11e1e0f36672956627e7522d2441cedfb06a5f359e7f5bd2b50'
for f in P.glob('*'):
 if f.suffix in ('.gba','.bps'):shutil.copy2(f,D/f.name)
(D/'검증').mkdir(exist_ok=True)
for f in ['REVIEW_COVERAGE.json','independent-final-c-audit.json','final-semantic-check.json','final-book-verification.json']:
 shutil.copy2(W/f,D/'검증'/f)
shutil.copy2(P/'BUILD_MANIFEST.json',D/'검증/BUILD_MANIFEST.json')
shutil.copy2(W/'CHANGE_DECISIONS_PRIVATE.json',D/'검증/교정내역.json')
for kind in ['item','monster']:
 shutil.copy2(W/f'final-c-vbam-{kind}/report.json',D/f'검증/VBA-M_{kind}_표시검증.json')
(D/'확인화면').mkdir(exist_ok=True)
for kind,src,name in [('item','063_063','슬레이어_소드_한줄'),('item','039_039','스틸_소드_고유명사'),('monster','015_103','풍속성_공백제거'),('monster','020_080','뇌속성_공백제거')]:
 shutil.copy2(W/f'final-c-vbam-{kind}/screens/{src}_4x.png',D/f'확인화면/{name}.png')
readme='''나리키리 던전 2 전체 대사 검교정 — 2026-09-23

Xagros_Narikiri2_KOR_proofread_test.gba를 VBA / VBA-M에서 여세요.
기존 일반 세이브(.sav)는 원본을 보관한 뒤 복사본의 이름을 롬 이름과 맞춰 사용하세요.
이 파일은 이전 아이템·몬스터 설명 교정판에 이번 대사 교정을 추가한 로컬 테스트본입니다.

수정 내용
- 슬레이어 소드: 살아 있는 자를 죽이는 마검 (한 줄)
- 몬스터 도감: ＜풍＞속성, ＜뇌＞속성 등 괄호 뒤 공백 제거
- 아이템 설명의 속성은 풍속성 등의 문장형 유지
- 본문 8,037개 항목(실제 참조 8,945곳)과 명칭/UI 1,227곳을 일본어 원문 및 기존 대사집과 대조
- 본문 60개 항목, 실제 참조 98곳 교정. 확정 지명·인명·아이템명·속성 용어 적용
- 속성 한자 아이콘 유지

대사집
한국어대사집, 이름_UI, 변경내역, 고정용어, 요약 시트에 원문·최종문과 교정 이유를 기록했습니다.
동일 대사라도 연결 위치 또는 원문이 다르면 개별 행으로 수록되어 있습니다.

검증 범위
- 기존 데이터를 옮기지 않고 새 문장을 롬 끝에 추가하고 해당 포인터만 변경
- 전체 본문 인코딩, 제어문자, 수치, 줄폭, 포인터 및 BPS 복원 검사 통과
- 최종 롬의 아이템 156개·몬스터 도감 142개를 VBA-M에서 표시 점검
- mGBA에서도 동일한 아이템·도감 데이터 표시 점검
  (mGBA 검증본과 최종본의 차이는 레그니아 마을 대사 한 곳이며 별도 비교 검사)
- 표시 검증은 검사용 메모리에서 아이템/도감 목록을 열어 수행했습니다.
  모든 스토리 분기를 실제 플레이하여 완주한 검증은 아닙니다.

BPS는 일본어 원본에 적용하는 전체 패치이며, 기존 한글 롬에 중복 적용하지 않습니다.
일본어 원본 SHA256: a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7
최종 롬 SHA256: 7505ef506e4fc11e1e0f36672956627e7522d2441cedfb06a5f359e7f5bd2b50
'''
(D/'먼저읽어주세요.txt').write_text(readme,'utf-8-sig')
assert B.exists(), 'Final workbook not ready; package staging retained.'
shutil.copy2(B,D/B.name)
manifest={str(f.relative_to(D)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(D.rglob('*')) if f.is_file() and f.name!='SHA256.json'}
(D/'SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
z=D.with_suffix('.zip')
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as out:
 for f in sorted(D.rglob('*')):
  if f.is_file():out.write(f,f.relative_to(D.parent))
with zipfile.ZipFile(z) as out:assert out.testzip() is None
print(json.dumps({'package':str(z),'files':len(manifest),'bytes':z.stat().st_size},ensure_ascii=False))
