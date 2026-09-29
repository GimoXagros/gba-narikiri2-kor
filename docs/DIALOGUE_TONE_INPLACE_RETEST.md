# 대사 말투 pass01 원슬롯 재시험 후보

사용자가 VBA-M 2.2.3에서 기존 `tone-pass01` ROM(해시 `4243f300f579277ff63dc6fe15a6043419b0f9684d11f9354972acf6c3bcb080`)의 펍 장면 D04498 다음에 화면 멈춤과 깨진 문자를 보고했다. 사용자 데스크톱 ROM의 실제 해시는 빌드와 일치한다. `.sgm` 로드와 8 KiB SAV를 이용한 게임 내 이어하기 양쪽에서 신고됐다. 원인은 아직 확정되지 않았고, 해당 ROM은 재시험용으로 사용하지 않는다.

새 **로컬 재시험 후보**는 같은 검수 결정 D04485·D04489·D04499를 v1.0의 원래 텍스트 슬롯에 삽입한다. 세 슬롯의 새 원시 문자열 길이는 각각 36/24/14바이트이며 기존 길이 36/28/14바이트 이내다. D04489의 남는 네 바이트는 0으로 채웠다. 이벤트 포인터와 ROM 전체 길이 13,270,790바이트는 v1.0과 같다. ROM 전체에서 세 원슬롯 및 내부를 가리키는 GBA 포인터 형태를 비정렬 위치까지 검사한 결과 각 슬롯 시작에 해당 이벤트 참조 한 개씩만 있었다. 이 방식은 의심되는 새 문자열 위치를 사용하지 않는 회귀 완화 시도이며, VBA-M에서 해결됐다는 증거는 아니다.

`build_dialogue_tone_inplace.py`는 정확한 v1.0/AN9J 입력과 기존 세 장면·화자·제어코드·내용 해시 제약을 재사용하고, 원슬롯 용량·공유 참조·원포인터·바이트 변경 범위를 추가로 검증한다. 독립 `verify_dialogue_tone_inplace.py`가 빌드 A/B 동일, ROM 전체 변경 위치, 세 문자열 재추출, 전체 8,945 full 바인딩과 1,227 compact 바인딩, 이전 후보와 한국어 본문 일치, 일본어 원본용 누적 BPS 왕복을 검증한다. 기존 v1.0 공개 기록은 바꾸지 않는다.

현재 비공개 A/B의 ROM SHA-256은 `8d4c8dca40d7fdaa561dfa64fecc6ef42c04a11cdd345553e7bc5bb30313c142`, 일본어 원본용 누적 BPS SHA-256은 `6e2cc6a32819d5e37877d74676552623f8e6cca197b5ba2d351b5e58448dacd7`이다. 파일 위치는 `private_validation/tone-freeze-debug/build-inplace-a/`이다. `LOCAL_RETEST_CANDIDATE_VBA_UNVERIFIED` 상태이며 원격 배포·태그·릴리스 교체 대상이 아니다.

사용자가 제공한 SAV(복사본 SHA-256 `df856a48219430e28a16afdd54a5e5d25483de16348e89e33355395163d9bde6`)를 mGBA libretro 가상화면에 넣고, 이어하기→교회 대화→지도에서 위쪽·오른쪽으로 `펍 로즈` 선택→이벤트 전체→D04499→캐로 답변→지도 복귀까지 실제 버튼으로 진행했다. RAM 직접 변경은 없었다. 새 후보의 펍 화면 31장은 종전 후보 mGBA 경로와 픽셀 단위로 모두 같았다. 사용자가 겪은 VBA-M 2.2.3 문제는 mGBA에서 재현되지 않았으므로, **새 후보의 VBA-M 확인은 여전히 필요하다**. 재시험은 원본 SAV를 보존한 사본으로 게임을 새로 켜서 이어하기 경로를 권장한다. 과거 `.sgm`을 다른 ROM에 옮겨 사용하는 검증을 권장하지 않는다.

```powershell
python tools/build_dialogue_tone_inplace.py --base private_validation/release-v1.0/Xagros_Narikiri2_KOR_v1.0.gba --japanese Japanese.gba --changes translation/dialogue_tone_pass01.json --dialogue-book private_validation/release-v1.0/build-a/final-dialogue-book.json --prior-candidate-book private_validation/tone-pass01/build-h/final-dialogue-book.json --out <새-비공개-출력-경로>
python tools/verify_dialogue_tone_inplace.py --base private_validation/release-v1.0/Xagros_Narikiri2_KOR_v1.0.gba --japanese Japanese.gba --baseline-book private_validation/release-v1.0/build-a/final-dialogue-book.json --prior-candidate-book private_validation/tone-pass01/build-h/final-dialogue-book.json --build-a <첫-출력-경로> --build-b <둘째-출력-경로> --report <새-비공개-검증-경로>
python -m unittest tests.test_dialogue_tone_inplace -v
```

2026-09-30 후속 확인: 사용자가 위 원슬롯 후보를 받아 신고된 펍 로즈 장면의 정상 진행과 자연스러운 문맥을 확인했다. 기록은 `private_validation/tone-freeze-debug/USER_RETEST_20260930.json`이며 상태는 `USER_CONFIRMED_SCENE_PASS`이다. 사용자 메시지는 직전에 전달한 후보와 연결되지만 사용자 쪽에서 ROM 해시를 새로 측정하지는 않았다. 위의 `LOCAL_RETEST_CANDIDATE_VBA_UNVERIFIED`와 재시험 필요 표기는 당시 빌드·기술 검증의 역사적 상태이다. 후속 대사 검수의 입력 기준은 SHA-256 `8d4c8dca40d7fdaa561dfa64fecc6ef42c04a11cdd345553e7bc5bb30313c142`인 원슬롯 ROM이다. 이 확인이 신고 장면 밖의 전수 검수나 VBA-M 오류의 엔진 원인을 확인한 것은 아니다.
