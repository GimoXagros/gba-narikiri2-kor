# v0.9c PC 검증 후보 결과 — 2026-09-09

**PC_VALIDATION_PASS / AWAITING_USER_HARDWARE_RETEST / RELEASE_NOT_AUTHORIZED**

검증 범위는 공개 v0.9b와 그 PC 적용·빌드·패키징 경로입니다. 발견한 3건은 PC 도구·검증 기록 문제이며, 게임 바이트를 바꿀 근거는 발견되지 않았습니다. v0.9c 후보 ROM/BPS는 v0.9b와 완전히 동일합니다. ROM 변경을 꾸며내지 않았으며 공개 릴리스는 하지 않습니다.

1. 저장소: https://github.com/GimoXagros/narikiri2-save-compat ; branch `fix/v0.9c-pc-validation`; 시작 HEAD `09eccf0a079cbe6106a8c1f5427b8a2cffa6681a`. 최종 커밋·초안 PR은 `analysis/v0.9c/final_review.md`에 기록합니다.
2. 동결한 v0.9b ROM SHA-256: `d761088a8549cb5bc60a2f03a4b78eea5282dbc17ed5da4ef1de27da4ad8d4d4`. BPS: `51dbdb8ef24a32ca5efb05ec3196b98ae08a32f3a4d6bb88673d58266837dcf6`. ZIP: `800a49eb411f9d251ca37eaacd50a61733c2ce3d7939db9ed3719b18ff432529`.
3. 일본어 원본 SHA-256 시작/종료 동일: `a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7` — PASS.
4. BETA3(071102) SHA-256 시작/종료 동일: `c6d7a401aa2a22362b2d27d0d31632cb2180a86b094788815d949b84c7fc944d` — PASS.
5. v0.9b clean build A/B ROM·BPS 일치, 공개 해시 일치, 태그 소스에서 ZIP 재현 일치. v0.9c clean build A/B도 일치.
6. 기준선 local: collected/executed/PASS 139/139/139, FAIL/SKIP/ERROR 0/0/0. 후보 local: 150/150/150, 0/0/0. public subset: 기준선 43/43, 후보 49/49. 후보 증가분은 파일 쓰기 테스트 6개와 실제 후보 계약 테스트 5개이며, public 수를 local 수에 더하지 않습니다.
7. 발견 오류: 총 3건. 게임 코드 결함으로 확정한 추가 건수는 0입니다.
8. 출처별: V09B_REGRESSION 0 / BETA3_INHERITED_BUG 0 / ORIGINAL_INHERITED_BUG 0 / PATCH_INTERACTION_BUG 0 / BUILD_OR_PACKAGING_BUG 3. PC 도구가 없는 일본어/BETA3 비교 칸은 NOT_APPLICABLE이며 게임 정상 판정으로 간주하지 않습니다.
9. 심각도: MEDIUM 2 / LOW 1 / HIGH·CRITICAL 0.
10. **001**: 쓰기 실패 시 최종 이름의 128바이트 ROM이 남음. 완료 전에 최종 경로를 생성하는 것이 원인. **002**: 실제 ROM/BPS가 맞으면 잘못된 version·크기 정보를 허용. 일부 manifest 값만 검사하는 것이 원인. **003**: 2077을 compact 포인터 수로 표시. 실제로는 본문·UI 등을 포함하는 첫 단계 절대 포인터 집계입니다. 모든 ID는 `ND2-V09C-20260909-` 접두사를 사용합니다.
11. 후보 수정: 임시 파일 검증 후 덮어쓰기 없는 최종 게시, 실패 시 자신이 만든 파일만 정리; manifest 전체 값·중첩 자료형·실제 크기·출처·권한 검사; 이름 1227필드와 절대 포인터 2077개를 구분.
12. 수정 소스: `apply_ffr_v09c.py`, `tools/v09c_io.py`, `tools/build_ffr_v09c.py`, `tools/package_ffr_v09c_release.py`; 회귀검사는 `tests/test_v09c_io.py`, `tests/test_v09c_contracts.py`.
13. ROM offset / before·after bytes: **해당 없음**. v0.9b→v0.9c 변경 0바이트. BETA3→두 버전의 공통 변경은 `binary_diff_manifest.csv`에 작성자·범위·해시별로 기록했습니다.
14. 수정 전 FAIL / 수정 후 PASS: 동일 ENOSPC 주입, 잘못된 manifest 입력, 잘못된 2077 이름 필드 주장. 추가로 flush/read-back 실패, 기존 파일·하드링크·경합 보호, 누락·추가·중첩 자료형 불일치, 재패치·손상 BPS 거부를 검사했습니다.
15. EEPROM `0xA601C..0xA6800`은 BETA3/일본어와 동일. 대형 글꼴·음성 `0xAC3F4..0x2B2CAC`은 BETA3와 동일. v0.5의 79바이트 복구를 적용하지 않습니다.
16. 검사한 missing glyph / writer collision / layout overflow: 0/0/0. 글꼴·정렬·종단 검사와 실제 화면 검사를 구분해 `font_audit.md`, `text_audit.md`에 기록했습니다.
17. UNEXPECTED / UNOWNED diff: 0/0. 세 단계의 선언된 쓰기로 최종 ROM을 독립 재구성했습니다. 본문 검토 대상은 8037건, 본문 포인터 바인딩은 8946개입니다.
18. 후보 ROM: **13,107,200 bytes**, SHA-256 `d761088a8549cb5bc60a2f03a4b78eea5282dbc17ed5da4ef1de27da4ad8d4d4`.
19. 후보 BPS: **3,189,401 bytes**, SHA-256 `51dbdb8ef24a32ca5efb05ec3196b98ae08a32f3a4d6bb88673d58266837dcf6`.
20. BPS를 정확한 BETA3에 적용한 결과가 직접 빌드 ROM과 같습니다. 최종 로컬 ZIP의 독립 적용 결과·패키지 해시는 별도 `package_verification.json`에 기록합니다.
21. mGBA 0.11-219-e31759b / HLE: 기준선과 후보 각각 14경로·134화면 재현. 아이템 156종/157화면, 코스튬 200종, 몬스터 142종, 인물 22명, 의상 기술명 224종, 기술 설명 231화면 재검증. 정보창과 저장·로드·중단 재개 화면을 확인했습니다. 도감·기술 매트릭스는 격리된 RAM 시험 상태를 사용하며 자연 해금 검증이 아닙니다.
22. bug 001 커밋 `184f5cdbd8850f6892b89f44d99543ba98852a9d`; bug 002 커밋 `4e6b4fbd4d541e701bea1a3667380728030ceddf`. 집계 정정·감사 문서 커밋과 draft PR은 `fix_history.md` 및 `final_review.md`를 참조합니다. merge/tag/release는 하지 않습니다.
23. 실기 재확인: 새 게임/기본 이름/6칸 혼합 이름, 첫 저장과 두 번 완전 재시작, 기존 세이브 복사본, 중단 저장과 재개, 아이템·필리아 적 정보창, 전투·도감·상점·의상 교환. 모든 bug ID가 포함된 `docs/v0.9c/HARDWARE_RETEST.md`를 사용합니다.
24. 남은 한계: 실기·저장 장치·2기기 통신 미검증, 모든 이야기 분기·자연 해금·엔딩을 전수 플레이한 것은 아닙니다. 기존 일본어 개별 대조 기록의 재현이며 이번에 전체 8037문장을 독립 문학 검수한 것으로 주장하지 않습니다. 현 RIGHTS.md의 허가 요청 중 문구를 보존했으며 추후 공개 전 확인이 필요합니다.
25. 상태: **PC_VALIDATION_PASS**는 수행한 PC 검증 범위의 통과입니다. **AWAITING_USER_HARDWARE_RETEST**, **RELEASE_NOT_AUTHORIZED**를 유지합니다. issue #4를 닫거나 PC를 종료하지 않습니다.
