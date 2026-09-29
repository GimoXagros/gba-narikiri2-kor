# 대사 말투 검교정: 첫 로컬 부분 후보

## 범위와 근거

기준은 v1.0 ROM SHA-256 `7505ef506e4fc11e1e0f36672956627e7522d2441cedfb06a5f359e7f5bd2b50`와 AN9J 일본어 원본 SHA-256 `a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7`이다. 사용자가 실기에서 언급한 훌리오·캐로·민트의 펍 로즈 방문 장면을 우선 검수했다. 사용자가 당시 실행한 ROM 파일의 해시는 아직 확인되지 않았다.

일본어 ROM의 `003495C8`–`00349728` 이벤트 블록에서 8바이트 명령의 `000E`·actor 슬롯·본문 포인터를 읽어 24개 텍스트 호출을 확인했다. `D02517` 공유 인사가 `D04481`과 `D04482` 사이에 삽입된다. 별도 `00349AC4`–`00349B64` 아나스이 거리 블록의 10개 호출도 검수했다. 두 블록의 내부 명령 순서는 정적 근거로 확인했으나 두 블록 사이 경로, 실행 분기, 이름창과 소비 함수는 실행 확인 전이다. actor의 캐릭터 귀속은 원문 발화와 사용자의 장면 설명에 따른 추론이다. 실제 화면 순서·화자 표시의 실기 검증은 남아 있다.

펍 장면의 로즈→민트 발화 2개(`D04485`, `D04489`)와 훌리오→민트 응답 1개(`D04499`)를 소스/기준 번역 해시에 묶어 최소 변경했다. 로즈의 같은 상대에게 이어지는 반말, 훌리오의 민트향 높임, 일본어 원문을 근거로 삼았다. 훌리오↔캐로의 상대 전환 발화와 공유 인사는 보존했다. 기존 v1.0 교정 결정과 릴리스 기록은 수정하지 않았다.

## 기술 결과

새 결합 단계는 [build_dialogue_tone.py](../tools/build_dialogue_tone.py)와 [dialogue_tone_pass01.json](../translation/dialogue_tone_pass01.json)이다. 정확한 v1.0/AN9J 해시와 세 바인딩·actor·use-site·프로필·원문/수정 전 해시를 검증한다. 그 세 문장의 실제 원시 제어표식과 줄바꿈·모드 바이트를 보존하고 인코딩 왕복 및 페이지 행 수 증가를 검사한다. 과거 빌더의 고정 기준 해시를 바꾸지 않았다. 같은 출력 위 재적용은 기준 해시 검사에서 거부한다.

로컬 `private_validation/tone-pass01/build-h`와 `build-i` A/B는 각각 같은 ROM 13,270,867 bytes / SHA-256 `4243f300f579277ff63dc6fe15a6043419b0f9684d11f9354972acf6c3bcb080`, 일본어 원본용 누적 BPS 5,045,201 bytes / SHA-256 `dab31ea3f849a3f94bb24c40e3d7bf02e4b44a7ea86a007c399b1c1378202596`를 만들었다. [verify_dialogue_tone.py](../tools/verify_dialogue_tone.py)는 JP+BPS 왕복, A/B 일치, 기존 ROM의 허용 포인터 외 바이트 보존, 전체 8,945개 바인딩의 최종 ROM 재추출, 미변경 번역 8,942개와 compact 1,227개 보존을 확인했다. [test_dialogue_tone.py](../tests/test_dialogue_tone.py) 6개 검사도 통과했다.

## 검수와 실행 한계

전체 본문 8,037개 고유 ID / 8,945개 바인딩 중 두 이벤트 블록 34개 발화를 문맥 단위로 읽었다. 3개 교정, 5개 상대 전환에 따른 의도적 유지, 26개 일관성 유지를 기록했다. 남은 8,911개 바인딩은 장면/화자 순서가 확인되지 않았으며, 일부는 대화가 아닌 본문일 수 있다. [scan_dialogue_tone_candidates.py](../tools/scan_dialogue_tone_candidates.py)는 전체 8,945개를 탐색해 12개 형식 후보를 찾았고, 그중 11개는 장면 문맥이 필요하다. 검색은 누락 가능한 보조 탐지이며 의미 검수 완료 수에 포함하지 않았다.

후보 ROM을 mGBA libretro `0.11-219-e31759b`에서 부팅하고 8KiB SAV를 코어에 복사한 상태로 타이틀과 A 입력 후 건물 화면을 확인했다. 이 경로가 실제 저장 데이터를 불러왔는지는 확인하지 못했다. 펍 대화의 실제 연속 입력 재생과 실기 검증도 하지 못했다. 사용자 재확인 위치는 첫 마을 안내 중 로즈의 펍 방문이며, 로즈의 설명·작별 인사와 민트의 감사, 훌리오의 격려 응답 앞뒤를 연속으로 확인해야 한다. 최종 상태는 `PARTIAL_REVIEW_WITH_OPEN_ITEMS`다. 원격 배포·태그·릴리스 교체는 없다.

다음 배치는 별도 요리 이벤트 블록 `00336550`–`00336648`의 `D03248`–`D03263`으로, `D03257`의 말투 혼용 의심을 포함한다. actor 슬롯만으로 민트와 다른 상대 및 메르디 고유 말버릇을 확정하지 말고 전체 장면과 분기·상대를 복원한 뒤 판단한다.

```powershell
python tools/build_dialogue_tone.py --base <정확한-v1.0-ROM> --japanese Japanese.gba --changes translation/dialogue_tone_pass01.json --dialogue-book <v1.0-final-dialogue-book.json> --out <새-비공개-출력-경로>
python tools/verify_dialogue_tone.py --base <정확한-v1.0-ROM> --japanese Japanese.gba --baseline-book <v1.0-final-dialogue-book.json> --build-a <첫-출력-경로> --build-b <둘째-출력-경로> --report <새-비공개-검증-경로>
```
