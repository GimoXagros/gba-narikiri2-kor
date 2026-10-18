# v1.1a — 문구 간격 및 화면 지우기 교정

일본어 원본에 직접 적용하는 누적 한국어 패치입니다. v1.1 ROM에 덧붙이지 않습니다.

597개 검토 바인딩 가운데 552개를 교정하고 45개는 유지했습니다. 교정은 원래 문자열 시작 544곳에 반영했고, 공백 578개와 화면 지우기 제어 1개를 조정했습니다. 10,371개 바인딩의 포인터·문자열 시작 위치, 8MiB 크기와 보호 구간 52곳은 유지합니다.

| 구분 | 바이트 | SHA-256 |
| --- | ---: | --- |
| 일본어 원본 AN9J | 8,388,608 | `a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7` |
| v1.1a 결과 ROM | 8,388,608 | `8823db1cb72f1328136ccfd8fff1fbdca0c8489cbc7ccf90f7e4ecdbb1c37776` |
| 일본어 원본용 BPS | 378,236 | `75a16466feaae9612c6827d8fac5faf5b9a40eb968a740d9954aae10be5eadce` |

## 적용

`Xagros_Narikiri2_KOR_v1.1a_JP_PACKAGE.zip`을 새 폴더에 모두 풀고 Python 3.10 이상에서 실행합니다. 추가 패키지는 필요하지 않습니다.

```powershell
python apply_japanese_patch.py Japanese.gba --output Xagros_Narikiri2_KOR_v1.1a.gba
```

입력·패치·결과의 크기와 SHA-256을 확인하며 기존 출력은 덮어쓰지 않습니다. 기존 SAV는 먼저 백업하고 시험 폴더에서 사용하세요. 다른 ROM 버전의 강제저장 상태는 재사용하지 마세요.

## 검증 범위

2026-10-19 사용자는 수정 사항을 확인하고 v1.1a 업데이트·배포를 요청했습니다. 이를 전달한 최종 교정본에 연결한 `USER_ATTESTED` 수정 수락으로 기록합니다. 사용자가 직접 해시를 대조했다고 추정하지 않으며, 기기·에뮬레이터·항목별 검사 내역은 `NOT_REPORTED`입니다.

실제 CPU 명령을 실행한 고정 시험은 `PASS_CPU_FIXTURE_NOT_NORMAL_PLAY`로 구분합니다. 이 결과는 일반 플레이·전체 자연 진행·분기·통신·저장 호환·실기 시험의 통과를 뜻하지 않습니다. v1.1의 실행·성능 기록과 이전 버전의 기기 기록을 v1.1a의 새 검증으로 승계하지 않습니다. 미확인 범위의 [이슈 #4](https://github.com/GimoXagros/gba-narikiri2-kor/issues/4)는 유지합니다.

공개 첨부물에는 ROM·SAV·SGM·BIOS·전체 대사집이 포함되지 않습니다. 출처와 라이선스는 동봉한 CREDITS.md, RIGHTS.md, THIRD_PARTY_NOTICES.md를 따릅니다.
