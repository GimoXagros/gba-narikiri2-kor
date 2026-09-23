# Hint graphics test — 2026-09-23

나리키리 던전2 안내 글씨 및 CP 복구 테스트 (2026-09-23)

포함 파일
- Xagros_Narikiri2_KOR_hints_test.gba: 직접 실행하는 테스트 ROM
- Xagros_Narikiri2_KOR_hints_test_JP.bps: 일본어 원본에 적용하는 패치
- 수정 후 화면, 빌드 기록, VBA-M/mGBA 검증 기록

수정 내용
- 지도 ‘소문은 LR’와 의상 화면 ‘LR로 정보’의 잘린 글씨 수정.
- 같은 8픽셀 안내 글씨 17개 조각(캐릭 전환, 페이지, 가격/소지량, 반전, 교신중 등)을 함께 정비.
- 원래 글자보다 큰 폰트를 잘라 넣지 않고, 8픽셀 전용 글꼴의 모든 획을 그대로 사용.
- 44번 CP 그림의 잘못된 압축 헤더 04를 원본 값 30으로 복구.
- 34번은 일본어 ‘セッティング’의 끝부분 ‘ング’. 한국어 ‘설정’은 앞 조각에 있어 빈 조각 유지.
- 기존 타이틀, 엔딩 크레딧, 첫 안내 화면, 지명 수정은 포함되어 있음.

검증
- VBA-M 2.1.3 코어와 mGBA 코어에서 기존 일반 세이브를 불러와 지도와 의상 화면 확인.
- 수정 안내 글씨와 CP는 실제 게임 로더에 항목을 대입하여 각 픽셀 표시 확인.
  CP_복구_표시검증.png는 CP 그림의 표시 확인용 임시 배치이며 실제 CP 메뉴 위치를 뜻하지 않음.
- 그 외 모든 메뉴의 자연 진행을 완료했다는 의미는 아님.
- 기존 데이터 위치, 스프라이트 크기, 메모리 할당 크기를 유지. 새 그림을 ROM 끝에 추가.
- 일본어 원본 → BPS 적용 결과 일치, 재빌드 결과 일치 확인.

사용 방법
ROM을 새로 실행하고 첫 안내를 넘긴 뒤 일반 저장(.sav)을 불러오세요.
기존 .sav를 사용할 경우 새 ROM과 같은 파일명으로 복사하여 사용하세요.
이전 저장 상태(.sgm 등)는 이미 로드된 옛 그림을 포함할 수 있으므로 이번 확인에는 일반 저장을 권장합니다.
이번 파일은 로컬 테스트용이며 공개 릴리스는 변경하지 않았습니다.

ROM SHA-256: 583b5bdf08f6b2c40147deef517694891ed687b6bf107a9a3dc1ecf5a81d7a6b

Build: tools/build_hint_graphics.py; verification: tools/verify_hint_graphics.py.
Private evidence: private_validation/hints-20260923/verified-final-{mgba,vbam}.
The CP source header at 0x3AC014 was 04; the loader at 0x080033D4 only decompresses high-nibble types 1 and 3. Restored 30. Source bitmap otherwise retained.
