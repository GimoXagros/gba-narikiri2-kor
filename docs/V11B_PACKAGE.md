# v1.1b 적용과 재현 빌드

일본어 원본 AN9J에 누적 BPS를 직접 적용합니다. 이전 한국어 패치 위에 적용하지 않습니다.

```powershell
python apply_japanese_patch.py Japanese.gba --output Xagros_Narikiri2_KOR_v1.1b.gba
```

적용기는 Python 3.10 이상과 표준 라이브러리를 사용합니다. 원본·BPS·결과 크기와 SHA-256이 고정값과 다르면 중단합니다. 기존 출력은 덮어쓰지 않습니다. 원본은 8,388,608바이트, SHA-256 `a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7`입니다.

개인 SAV를 백업한 뒤 ROM과 파일명을 맞추십시오. 다른 버전의 SGM은 재사용하지 마십시오. 공개 ZIP에는 ROM·저장·BIOS·글꼴 바이너리·전체 대사집이 없습니다.

## 개발용 재현

`tools/build_v11b.py`는 일본어 ROM, v1.1a BPS, 기존 LINK/BUILD 레이아웃 및 검토 대사 자료를 명시적으로 받습니다. 비공개 입력의 SHA-256은 `INPUTS`에 고정되어 있습니다. 해당 자료를 가진 개발자만 전체 재현 빌드를 실행할 수 있으며 소스 ZIP만으로 게임 데이터를 만들 수는 없습니다. 개발 의존성은 `requirements-dev.txt`를 따릅니다.

```powershell
python tools/build_v11b.py --japanese Japanese.gba --baseline-patch Xagros_Narikiri2_KOR_v1.1a.bps --link LINK.json --components BUILD.json --corpus reviewed-dialogue-data.json --expected-target 32ed708c0c8c26074829a163000dd5504a5a7a1fbcd4f1319c2eb1f45d438677 --out new-build
```

빌더 성공은 배포 승인이 아닙니다. `tools/package_v11b.py`는 최종 해시에 연결한 10개 검증 관문, 조건부 공개 요청, 성능 수치와 공개 파일 목록을 검사합니다. 증거의 원본 보고서 해시는 검토자가 실제 보고서와 대조해야 하며 패키지 도구가 실행 시험을 대신하지 않습니다.

공개 CI는 ROM을 사용하지 않는 계약 검사입니다. CPU fixture·가상 실행·실기 범위는 [릴리스 노트](RELEASE_NOTES_V11B.md)와 `verification/v1.1b-evidence.json`에 구분합니다.
