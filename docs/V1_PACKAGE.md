# v1.0 일본어 원본용 패키지 안내

수정하지 않은 AN9J 일본어 원본에 한 번 적용하는 패치 패키지입니다. 입력 ROM, SAV, BIOS, savestate, 전체 추출 대본 및 개인 대사집은 이 패키지에 포함하지 않습니다.

## 적용

Python 3.10 이상, 표준 라이브러리만 필요합니다.

```powershell
python apply_japanese_patch.py "일본어 원본.gba" --output "Xagros_Narikiri2_KOR_v1.0.gba"
```

도구는 입력 식별과 패치 적용을 확인하고 기존 파일을 덮어쓰지 않도록 동작합니다. 일본어 원본용 적용기는 7개 검사를 통과했습니다: 정상 적용/왕복, 기존 출력 보호, 변조 원본 거부, 이미 패치된 원본 거부, 손상 BPS 거부, 입력/출력 경로 충돌 거부, 실패 중 원본 보호. ZIP 두 개의 결정성, 허용 목록, 새 폴더 압축 해제와 동봉 적용기 재적용을 확인했습니다. 공개 다운로드의 검증 결과는 배포 후 별도로 확인하며, 사전 검사 범위는 `verification/v1.0.json`에 기록합니다. 실기·2차 검증은 사용자의 2026-09-24 공개 결정에 따라 배포 후 계속됩니다.

## 허용 파일 목록

패키지에는 `Xagros_Narikiri2_KOR_v1.0.bps`, `apply_japanese_patch.py`, `bps.py`, `v09c_io.py`, `README.txt`, `CREDITS.md`, `RIGHTS.md`, `LICENSE`, `THIRD_PARTY_NOTICES.md`, `VERIFICATION.json`, `DALMOORI_LICENSE`, `MANIFEST.json`만 포함합니다. 내부 manifest는 각 동봉 파일의 크기와 SHA-256을 기록하며 ZIP 자체와 manifest 자신은 내부 해시 대상에서 제외합니다. 외부 릴리스 manifest와 SHA256SUMS는 최종 커밋과 ZIP을 확정한 뒤 생성합니다.

최종 입력/타깃/BPS 기준:

| 항목 | 크기 | SHA-256 |
| --- | ---: | --- |
| 일본어 원본 AN9J | 8,388,608 | `a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7` |
| 최종 ROM (로컬 전용) | 13,270,790 | `7505ef506e4fc11e1e0f36672956627e7522d2441cedfb06a5f359e7f5bd2b50` |
| 일본어 원본용 BPS | 5,045,193 | `8d4a102714dccca1228215d97ae38b55eaca7ed9b74552150d3ab6aee2fa16e6` |

최종 ROM은 공개 첨부물에 올리지 않습니다. 공개 릴리스의 기본 첨부물은 ZIP, BPS, manifest, SHA256SUMS로 제한합니다. 개인 XLSX/CSV와 전체 대사 corpus는 공개하지 않습니다.
