# v1.1 재현 빌드 안내

일반 패치 적용에는 [패키지 안내](V11_PACKAGE.md)의 일본어 원본과 Python 표준 라이브러리만 필요합니다. 아래는 기존 번역·검증 입력을 보유한 개발자를 위한 전체 통합 재현 절차입니다. 비공개 ROM·전체 대사 카탈로그는 저장소에서 제공하지 않습니다.

## 고정 입력

| 입력 | 크기/역할 | SHA-256 |
| --- | --- | --- |
| JP | 일본어 AN9J, 8,388,608바이트 | `a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7` |
| ADOPTED | 채택한 번역·그래픽·감사 문구, 13,270,790바이트 | `eac45b3345e865f1fea68bbb07f62aff0f6ccdf03004090f57b55f75b6f82b73` |
| CATALOG | 비공개 TEXT_SLOT_MAP.csv | `c95741c2a216ddd7ff0027a54c4f5529cbfd3d4e4926772dd804398a69a6ac1e` |
| AUDIT | analysis/v0.9c/pointer_audit.csv | `8bc337e9d514e5f0bbd79f69f4f07c1d3d8ffc03dd4d2d9e14b36ca4878c3892` |

## 명령

태그의 새 checkout 두 곳에서 각각 실행합니다. JP·ADOPTED·CATALOG에는 위 식별자와 일치하는 로컬 파일 경로를 넣고 OUT_A/OUT_B는 서로 다른 새 폴더로 지정합니다.

```powershell
python -m pip install -r requirements-dev.txt
python -B -O tools/build_strict_8m_diagnostic.py --japanese "$JP" --adopted "$ADOPTED" --catalog "$CATALOG" --audit analysis/v0.9c/pointer_audit.csv --stage4-perf --out "$OUT_A"
```

같은 명령에서 출력 폴더를 OUT_B로 바꿔 다시 실행합니다. 역사적 도구·파일명의 DIAGNOSTIC은 유지하며, 이 명칭만으로 공개 자격을 결정하지 않습니다. 공개 자격은 정확한 출력 식별자에 연결된 검사와 현재 사용자 결정 및 배포 검사를 따릅니다.

`REPRODUCTION.json`의 입력 fingerprint, 사용 소스, 결과 ROM/BPS, 패치 재적용을 두 실행에서 대조합니다. 최종 게임 파일은 `stage4/STAGE4_PERF_DIAGNOSTIC_NOT_PRODUCT.gba`, 패치는 `FIXED_8MIB_DIAGNOSTIC_NOT_PRODUCT.bps`입니다.

- 결과 ROM: 8,388,608바이트 / `9fd341b827a8ba282781d7f8f214f2ba8641365b541564d53e9ef5267511889b`.
- BPS: 378,033바이트 / `4e4ad0229b22ea5bd8e6b351adfa79a749e2b5288aabb24d7d1e356a7bfafade`.

재현 환경은 Python 3.14.6과 고정 requirements를 사용했습니다. 빌드는 기존 8MiB만 매핑한 실제 CPU 검사, 52개 배치와 소유 영역, 원래 포인터·시작 위치·문구 출력의 검사를 수행합니다. 전체 실행 경로와 실기를 이 빌드만으로 증명하지 않습니다.

`tools/package_v11.py`는 위 BPS를 변경하지 않고 명시한 13파일만 묶습니다. 현재 사용자 승인 기록과 G0~G10, 원본·결과·패치 식별자를 확인하며, 기록 없는 release_eligible=true는 거부합니다. ZIP 내부 manifest는 자신과 ZIP을 해시하지 않습니다. 최종 commit/tree·ZIP 및 공개 다운로드 증거는 외부 배포 기록으로 연결합니다.
