# v1.0 재현 빌드 안내

두 개의 새 전체 체인 빌드(A/B)를 실행해 같은 최종 ROM을 재현했습니다. 아래 명령은 빌드 절차를 설명합니다. `BETA2`, `BETA3`, `JP`, `SCREEN`, `OUT`은 사용자 로컬에서 제공되는 정확한 입력 경로로 지정하십시오. 두 실행에서 `OUT`은 서로 다른 새 경로여야 합니다.

## 입력 식별

- 게임 코드: AN9J.
- 일본어 원본: 8,388,608 bytes / `a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7`.
- BETA2와 BETA3는 제품 재현용 고정 빌드 입력입니다. 공개 패치 사용자는 이 파일이 필요하지 않습니다.
- 부팅 안내용 `SCREEN`은 240×160 기존 runtime screenshot에서 유래한 source-equivalent 결과입니다. 양자화 픽셀 SHA-256 `82773ec065898089374f4e7834a1d8e83adb8e5be8f5ebbc91dd0bd742e52a75`가 채택된 안내 manifest와 일치합니다. 원래 사용자 제공 PNG 자체는 현재 로컬에 보존되어 있지 않습니다.

## A/B 명령 순서

한 새 출력 루트에서 아래 단계를 순서대로 실행하고, 별도의 새 루트에 같은 순서를 반복하십시오. 각 단계의 실제 입력/결과 해시와 빌드별 manifest는 해당 run 증거에 기록합니다.

```powershell
python tools/build_title_credits.py --beta2-reference "$BETA2" --beta3 "$BETA3" --japanese "$JP" --out-dir "$OUT/title"
python tools/build_boot_notice.py --base "$OUT/title/Xagros_Narikiri2_KOR_title_credits_test.gba" --screen "$SCREEN" --japanese "$JP" --out "$OUT/notice"
python tools/build_place_names.py --base "$OUT/notice/Xagros_Narikiri2_KOR_notice_test.gba" --japanese "$JP" --out "$OUT/places"
python tools/build_hint_graphics.py --base "$OUT/places/Xagros_Narikiri2_KOR_places_test.gba" --japanese "$JP" --out "$OUT/hints"
python tools/build_description_review.py --base "$OUT/hints/Xagros_Narikiri2_KOR_hints_test.gba" --japanese "$JP" --out "$OUT/descriptions"
python tools/build_dialogue_proofread.py --base "$OUT/descriptions/Xagros_Narikiri2_KOR_descriptions_test.gba" --japanese "$JP" --changes translation/dialogue_proofread_20260923.json --out "$OUT/proofread"
```

마지막 명령의 ROM/BPS 재현에는 전체 비공개 대사집이 필요하지 않습니다. 개인 대사집 내보내기가 필요한 경우에만 `--dialogue-book <비공개 latest-dialogue-book.json>`을 추가하십시오. 생략하면 `private_dialogue_book_export=NOT_RUN`으로 보고하고 ROM/BPS 빌드는 완료됩니다.

최종 두 산출물 `proofread/Xagros_Narikiri2_KOR_proofread_test.gba`는 모두 13,270,790 bytes, SHA-256 `7505ef506e4fc11e1e0f36672956627e7522d2441cedfb06a5f359e7f5bd2b50`로 보고되었습니다.

## 실행 환경

A/B에서 보고된 환경: Python 3.14.6; Pillow 12.3.0; Keystone 0.9.2; Capstone 5.0.9; Unicorn 2.1.4. Node 24.19.0과 pnpm 11.25.0은 설치되어 있었으나 이 A/B full-chain에는 호출되지 않았습니다. Dalmoori 생성 폰트 체크아웃은 commit `897f0e71224d9964a84b888f2596b2bfd7f98def`에 고정되어 있었습니다. 별도 글리프 재생성이 필요한 개발 작업은 현행 생성기 지침에 고정된 pnpm 7.33.7을 따릅니다.

## 사용자 적용 빌드와 제품 재현 구분

일본어 원본용 패치는 위 제품 재현 산출물에서 생성합니다. 일반 사용자는 AN9J 일본어 원본과 동봉 적용기만 필요합니다. 적용기 검사 7개와 비공개 패키지 결정성·새 폴더 재적용 검사를 통과했습니다. 공개 다운로드 적용 결과는 발행 후 `verification/v1.0.json`과 외부 릴리스 manifest에서 확인하십시오.
