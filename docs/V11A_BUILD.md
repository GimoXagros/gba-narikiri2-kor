# v1.1a 재현 빌드 및 패키지 안내

일반 사용자는 [적용 안내](V11A_PACKAGE.md)를 따릅니다. 아래 절차는 고정된 비공개 입력을 보유한 개발자용입니다. ROM·전체 교정 계획·대사 카탈로그는 공개 저장소에 제공하지 않습니다.

## 교정본 재현

`build_v11a.py`는 일본어 원본과 v1.1 BPS에서 시작하여 SHA-256으로 고정된 교정 계획·배치·구성·카탈로그를 읽습니다. 각 변수에는 해당 로컬 파일 경로를 지정하고 OUT_A에는 아직 없는 출력 폴더를 지정합니다. 입력 해시는 도구의 `JP`, `INPUTS` 상수와 일치해야 합니다.

```powershell
python tools/build_v11a.py --japanese "$JP" --baseline-patch "$V11_BPS" --plan "$PLAN" --link "$LINK" --components "$COMPONENTS" --corpus "$CORPUS" --out "$OUT_A"
```

별도 새 checkout과 새 OUT_B에서 같은 고정 입력으로 다시 실행하여 결과를 비교합니다. 출력은 `Xagros_Narikiri2_KOR_v1.1a.gba`, `Xagros_Narikiri2_KOR_v1.1a.bps`, `BUILD_RESULT.json`입니다.

| 결과 | 바이트 | SHA-256 |
| --- | ---: | --- |
| ROM | 8,388,608 | `8823db1cb72f1328136ccfd8fff1fbdca0c8489cbc7ccf90f7e4ecdbb1c37776` |
| BPS | 378,236 | `75a16466feaae9612c6827d8fac5faf5b9a40eb968a740d9954aae10be5eadce` |

교정 552개 바인딩·544개 시작 위치, 전체 10,371개 바인딩의 포인터·시작 위치·출력과 보호 구간 52곳을 검사하고 일본어 원본용 누적 BPS를 재적용합니다. 정적 재현과 CPU fixture는 일반 플레이·실기 검증을 대신하지 않습니다. 사용자 수정 수락과 환경·개별 검사의 NOT_REPORTED 범위는 [검증 기록](../verification/v1.1a.json)에 따릅니다.

## 공개 ZIP 작성

DOCUMENTS에는 [패키지 안내](V11A_PACKAGE.md)의 공개 문서 7개를 준비합니다. MANIFEST는 고정 원본·결과·BPS 식별자를 담는 `narikiri2-v11a-package-1` 문서이며, `VERIFICATION.json`은 `narikiri2-v11a-verification-1` 계약의 수정 수락 기록을 사용합니다. 기존 출력 파일은 사용할 수 없습니다.

```powershell
python tools/package_v11a.py --japanese "$JP" --target "$TARGET" --patch "$BPS" --manifest "$MANIFEST" --documents "$DOCUMENTS" --output "$NEW_ZIP"
python -m unittest discover -s tests -p test_v11a_package.py
```

패키저는 BPS를 재적용하고 고정된 결과와 대조한 뒤 명시한 공개 파일 13개만 묶습니다. 내부 manifest는 자신과 ZIP을 해시하지 않습니다. 최종 commit/tree·ZIP 식별자와 공개 다운로드 증거는 외부 배포 기록으로 연결합니다. ROM·저장 파일·비공개 입력은 첨부하지 않습니다.
