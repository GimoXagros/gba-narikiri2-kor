# v0.9c PC 검증 후보

이 후보는 v0.9b의 PC 적용·패키징 도구와 검증 기록 3건을 고친 로컬 시험판입니다. 게임 ROM과 BPS의 바이트는 공개 v0.9b와 같습니다. 번역·전투·저장 코드를 추가로 수정한 버전으로 해석하지 마세요. 정식 릴리스는 승인되지 않았습니다.

BETA3(071102) 원본 한국어 ROM에만 적용합니다. ZIP에는 ROM·세이브가 없습니다. 기존 세이브는 별도로 백업하고, 같은 ROM/세이브 파일명 규칙을 사용하는 에뮬레이터에서는 후보 이름에 맞춘 복사본으로 시험하세요.

```text
python apply_ffr_v09c.py "BETA3(071102).gba" --output "검증 후보.gba"
```

기존 출력 파일, 잘못된 원본, 이미 패치된 ROM은 거부합니다. 적용 중 쓰기가 실패하면 완성되지 않은 파일을 최종 ROM 이름으로 남기지 않도록 변경했습니다. 갑작스러운 전원 차단 자체의 복구를 보장하는 기능은 아닙니다.

PC 검증 범위와 한계는 V09C_PC_TEST_NOTES.md, 실기 확인은 HARDWARE_RETEST.md를 참고하세요. PC_VALIDATION_PASS / AWAITING_USER_HARDWARE_RETEST / RELEASE_NOT_AUTHORIZED.
