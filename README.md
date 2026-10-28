# 테일즈 오브 더 월드 나리키리 던전 2 한국어화

![테일즈 오브 더 월드 나리키리 던전 2](logo.png)

**v1.1b**는 일본어 원본 ROM(게임 코드 AN9J)에 직접 적용하는 8MiB 누적 한국어 패치입니다. 일반 대사와 지원되는 소형 문자열에 반각 단어 간격을 적용하고 목록 성능을 개선했습니다. FFR 패치를 먼저 적용할 필요는 없습니다.

## 적용

[v1.1b 릴리스](https://github.com/GimoXagros/gba-narikiri2-kor/releases/tag/v1.1b)에서 `Xagros_Narikiri2_KOR_v1.1b_JP_PACKAGE.zip`을 받아 새 폴더에 모두 풉니다. Python 3.10 이상과 표준 라이브러리를 사용합니다.

```powershell
python apply_japanese_patch.py Japanese.gba --output Xagros_Narikiri2_KOR_v1.1b.gba
```

수정하지 않은 일본어 원본에 적용합니다. 적용기는 원본·패치·결과를 확인하고 기존 출력 파일을 덮어쓰지 않습니다.

| 구분 | 바이트 | SHA-256 |
| --- | ---: | --- |
| 일본어 원본 AN9J | 8,388,608 | `a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7` |
| v1.1b 결과 ROM | 8,388,608 | `32ed708c0c8c26074829a163000dd5504a5a7a1fbcd4f1319c2eb1f45d438677` |
| 일본어 원본용 BPS | 383,084 | `98e885adbc075ff0e953abb6e49dd5e03cd12dd07c755e9e7dde230408446eaf` |

ZIP의 포함 파일과 체크섬은 `manifest.json`, `SHA256SUMS.txt`에서 확인합니다. ROM·개인 저장·전체 대사집은 공개 첨부물에 포함하지 않습니다.

## v1.1b 변경 및 검증 범위

큰 글자 단어 간격은 6px, 지원되는 소형 문자열은 4px로 표시합니다. 숫자 열·들여쓰기·이름 입력판·사용자 이름과 숨겨진 개발용 목록의 예외는 보존합니다. `아니요`는 이전 느낌을 유지한 그래픽으로 교정했습니다. 10,371개 원래 포인터와 문자열 시작 위치, 8MiB 크기는 유지합니다.

분리된 소스 폴더에서 ROM/BPS 재현, 실제 CPU 디코더와 코드 경계, 고정 목록 7,330회 이동, 가상 화면·일반 저장 두 번 불러오기·중단 저장·펍 로즈 SGM 복원을 최종 해시로 검증했습니다. 상세 수치와 범위는 [v1.1b 릴리스 노트](docs/RELEASE_NOTES_V11B.md), [적용·빌드 안내](docs/V11B_PACKAGE.md), [검증 계약](verification/v1.1b.json), [관문별 증거](verification/v1.1b-evidence.json)를 참조하세요.

기술 설정 제목의 기존 잘림은 남아 있습니다. 오디오는 1,500,002개 스테레오 프레임 중 1개가 기준선과 달라 비트 단위 동일 판정은 하지 않습니다. 최종 v1.1b 실기·청취·전체 분기·통신은 미검증이며 이슈 #4를 유지합니다. 사용자의 조건부 배포 요청과 최종본 직접 수락은 구분합니다.

## 이전 v1.1a 기록

597개 검토 바인딩 가운데 552개를 교정하고 45개는 유지했습니다. 교정은 원래 문자열 시작 544곳에 반영했고, 공백 578개와 화면 지우기 제어 1개를 조정했습니다. 10,371개 바인딩의 포인터·문자열 시작 위치, 8MiB 크기와 보호 구간 52곳은 유지합니다.

2026-10-19 사용자는 수정 사항을 확인하고 v1.1a 업데이트·배포를 요청했습니다. 이를 전달한 최종 교정본에 연결한 `USER_ATTESTED` 수정 수락으로 기록합니다. 사용자가 직접 해시를 대조했다고 추정하지 않으며, 기기·에뮬레이터·항목별 검사 내역은 `NOT_REPORTED`입니다.

실제 CPU 명령을 실행한 고정 시험은 `PASS_CPU_FIXTURE_NOT_NORMAL_PLAY`로 구분합니다. 이 결과는 일반 플레이·전체 자연 진행·분기·통신·저장 호환·실기 시험의 통과를 뜻하지 않습니다. v1.1의 실행·성능 기록과 이전 버전의 기기 기록을 v1.1a의 새 검증으로 승계하지 않습니다. 미확인 범위의 [이슈 #4](https://github.com/GimoXagros/gba-narikiri2-kor/issues/4)는 유지합니다.

기존 8KiB 게임 내 저장(SAV)은 먼저 백업하고 ROM/SAV의 파일명을 확장자를 제외하고 맞추세요. 다른 ROM 버전의 강제저장(SGM)은 재사용하지 마세요.

[적용 안내](docs/V11A_PACKAGE.md) · [빌드 안내](docs/V11A_BUILD.md) · [릴리스 노트](docs/RELEASE_NOTES_V11A.md) · [검증 기록](verification/v1.1a.json) · [이전 v1.1](docs/RELEASE_NOTES_V11.md) · [이전 v1.0](https://github.com/GimoXagros/gba-narikiri2-kor/releases/tag/v1.0)

## 출처와 권리

기존 한국어 번역은 FFR 팀의 작업을 출처로 합니다. 달무리 비트맵 글꼴은 별도 Apache-2.0 조건과 출처 고지를 따릅니다. MIT는 신규 코드와 문서에만 적용되며 게임, 기존 번역, 로고의 권리를 바꾸지 않습니다. 공식 제휴·승인이나 ROM 재배포 허가를 뜻하지 않습니다. 자세한 내용은 CREDITS.md, RIGHTS.md, THIRD_PARTY_NOTICES.md를 참조하세요.
