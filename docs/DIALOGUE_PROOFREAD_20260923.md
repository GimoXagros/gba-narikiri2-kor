# 대사 검교정 및 최종 대사집

## 사용자 요청
- 슬레이어 소드: `살아 있는 자를 죽이는 마검`을 한 줄에 표시.
- 몬스터 도감: `＜풍＞속성`처럼 속성 괄호 다음 공백 제거.
- 기존 대사집과 일본어 원문을 바탕으로 전체 대사 검교정, 확정 고유명사 일치.
- 최종 수정 ROM과 대사집 제공. 정형 작업과 분할 대조에는 Sol/Luna 사용.

## 기준
- ROM: `private_validation/description-review-20260923/product-final/Xagros_Narikiri2_KOR_descriptions_test.gba`
- SHA256: `64faac67ef9800758cc632af8316232e0d73489178cebac8172d1f2adfd711af`
- 일본어: `private_validation/japanese.gba`
- 이전 대사집: `output/dialogue-book-20260920/outputs/narikiri2-20260920/나리키리2_일본어_한국어_대사집.xlsx`

## 진행
1. 최신 ROM의 전체 본문/명칭을 원문과 함께 추출하고 중복/비문자 항목 구분.
2. 각 검수 단위에 대해 원문·기존번역·수정번역·이유·상태 기록. 단순 탐색 결과를 의미 검수로 세지 않음.
3. 확정된 교정을 소스 결합 검증 후 끝에 추가하고 포인터만 변경. 제어문자와 효과 수치를 보호.
4. 실제 표시, 글리프, 포인터, BPS 왕복 및 대사집/ROM 일치 확인.
5. 최종 xlsx와 로컬 테스트 파일 제공. 미확정 판단을 완료로 표시하지 않음.

## 역할
- root: 범위/원문 검토, 교정 통합, 빌드, 검증, 납품.
- Sol pipeline: 최신 전체 추출과 구조 조사; 이후 분할 검수.
- Sol terminology_audit: 고유명사 원문 대조와 개별 교정.
- Luna display_fixes: 명시된 포맷 교정 15건 완료; 대사집 작성 준비.

## 최종 결과
- 본문 8,037 ID / 8,945 바인딩 및 명칭·UI 1,227 필드 원문 대조 완료.
- 60 ID / 98 바인딩 교정. 기존 제어문자·수치 유지, 기존 데이터 이동 없음.
- 최종 ROM: `private_validation/dialogue-proofread-20260923/product-final-c/Xagros_Narikiri2_KOR_proofread_test.gba`
- SHA256: `7505ef506e4fc11e1e0f36672956627e7522d2441cedfb06a5f359e7f5bd2b50`
- 독립 검사 25개 통과, BPS 왕복·재현 빌드 일치.
- final-c VBA-M 아이템 156개·몬스터 142개 표시 점검 완료. final-b mGBA 동일 영역 점검 완료; b→c는 D00234의 지명 대사만 변경됨을 독립 검사.
- 실행 검사는 목록을 여는 격리 메모리 플래그를 사용함. 모든 스토리 분기 완주 검증과 구별.
- 최종 대사집: `output/dialogue-proofread-20260923/outputs/final/나리키리2_일본어_한국어_최종대사집.xlsx`
- 패키징: `tools/package_dialogue_proofread.py`. 기존 납품물은 보존.
