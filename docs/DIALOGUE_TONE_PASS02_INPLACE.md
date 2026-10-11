# 대사 말투 pass02 원슬롯 로컬 후보

입력은 사용자가 펍 로즈 장면의 정상 진행을 확인한 pass01 원슬롯 ROM(SHA-256 `8d4c8dca40d7fdaa561dfa64fecc6ef42c04a11cdd345553e7bc5bb30313c142`)이다. pass02는 원래 텍스트 슬롯 70곳만 수정하며, 5개의 공유 바인딩을 포함해 총 75개 full 바인딩의 한국어 표시문이 바뀐다. 원본 포인터와 ROM 길이 13,270,790바이트를 유지한다. 기존 pass01의 펍 장면 세 교정도 그대로 포함한다. 이 파일은 개발 후보 기록이며 공개 릴리스나 실기 합격 판정이 아니다.

전체 full 바인딩 8,945개의 일본어와 한국어 문장을 한 번 이상 읽고 각 binding ID로 판정을 보존했다. 정적 이벤트 명령 문맥이 확인된 바인딩은 3,944개다. 그 밖의 사용처가 미확정인 4,269개도 문장 초벌 검수를 했지만 화자·상대·분기·실행 순서를 추측해 채우지 않았다. 비대사로 확인된 732개와 미사용 sentinel 1개는 별도 관리한다. 카탈로그에 없는 이벤트 텍스트 호출 92건도 별도로 읽었으며 본문 분모에 억지로 넣지 않았다. 이 전량 텍스트 검수는 전량 장면·화자·런타임 경로 확인과 다르다. `D00308:0009C888`과 `D06151:00380A6C`의 말투는 근거가 부족해 원문을 유지하고 `NEEDS_CONTEXT`로 남겼다.

공개 결정 파일 `translation/dialogue_tone_pass02.json`에는 수정문, binding ID, 원문 해시, 원슬롯 주소와 길이, 영향받는 모든 바인딩의 일본어 원문 해시가 있다. 전체 일본어 원문과 수정 전 한국어 대조표는 `private_validation/tone-pass02/DECISIONS_FULL_PRIVATE.json`에만 둔다. 원본 레코드 ID는 중복될 수 있으므로 합치거나 단독 고유키로 사용하지 않는다. 정적 이벤트 바인딩도 저장 주소의 인접성만으로 장면 진행 순서를 확정하지 않았다.

`tools/build_dialogue_tone_pass02_inplace.py`는 각 결정의 일본어 원문·수정 전 한국어 원문·raw 슬롯 해시를 정확한 입력 ROM에서 재추출하여 확인한다. 공유 슬롯의 모든 소비 바인딩, 원문별 해시, byte capacity, 제어 토큰·모드·개행·숫자, 명시한 우연 포인터 패턴과 정렬 주변 수치, 슬롯 겹침을 검사한다. 수정은 한 슬롯에 한 번만 쓰며 남는 바이트는 0으로 채운다. 전체 포인터 카탈로그 10,380개 storage word와 슬롯 밖 바이트가 변경되지 않았음을 확인하고, full 8,945개를 새 ROM에서 재추출한다. compact 1,227개는 원본 corpus와 바이트 단위로 같은 레코드를 보존한다. 일본어 원본용 누적 BPS도 왕복 검증한다.

정적 레이아웃 검사는 표시 글리프를 최대 12픽셀로 보수적으로 계산하고, 관찰된 18칸 대화창에서 새 줄·자동 줄바꿈 행이 늘지 않게 한다. 이 모델은 동적 변수 폭이나 모든 소비자 화면 폭을 확정하지 못한다. `D06466:00738390`의 마지막 페이지는 표시 글리프가 3→5개(상한 36→60픽셀)로 늘지만 같은 자동 줄바꿈 행 하나 안에 있다. 해당 소비자의 실제 화면 렌더 확인은 별도다.

로컬 후보는 `private_validation/tone-pass02/build-inplace-d/`에 있다. ROM SHA-256은 `26da89ccb5441af705e10c7660b533216ab39390bc4caa06827ccd12ce77fda1`, 누적 BPS SHA-256은 `e43edc74c1dea7bd342cce99fbfb2e6de55dbbd89356e362d53b4a1cc32261a9`, 전체 내보내기용 corpus SHA-256은 `957f7c29eb3f211a7def73886f084a1b163dfdaf1d601506a0aba923e4ed7e9a`이다. 독립 정적 검사에서 70원슬롯/75영향 바인딩/수정 바이트 1,331개/전체 포인터 불변/전체 corpus 재추출/BPS 왕복이 통과했다. 잘못된 입력·원문 해시·공유 참조·제어·숫자·슬롯 길이·중복 쓰기를 포함한 부정시험 10건도 예상대로 거부됐다.

`private_validation/tone-pass02/ROOT_RUNTIME_REPORT.json`에는 복사한 사용자 SAV로 게임 내 이어하기→교회→마을→펍 로즈→민트→훌리오→마을을 31개 화면 단계까지 진행한 결과가 있다. 가상 mGBA 0.11 및 headless VBA-M 2.1.3에서 RAM 수정 없이 통과했고, 각각 기존 정상 확인 baseline과 31장 모두 동일했다. 두 코어끼리는 첫 화면에 1픽셀 폭 차이가 있고 나머지 30장은 일치한다. 첫 차이는 글자 진행 시점으로 보이며 기존 baseline 비교에서도 동일하므로 이 후보의 새 회귀는 아니다. 펍 입구·대화 시작·과거 정지 지점의 실제 VBA-M 호환 `.sgm` 세 개는 형식 역변환과 별도 가상 코어 재개 시험을 통과했다. 이들은 해당 후보 전용이며 외부 BIOS 없이 사용하는 상태다. 데스크톱 VBA-M UI의 직접 `.sgm` 불러오기, 새로 수정한 75개 바인딩 장면의 전부, 전체 플레이, 최종 실기 시험은 아직 실행하지 않았다. 접근하지 못한 장면용 상태 파일을 추정으로 만들지 않는다.

재현 명령:

```powershell
python tools/build_dialogue_tone_pass02_inplace.py --base private_validation/tone-freeze-debug/build-inplace-a/Xagros_Narikiri2_KOR_v1.0_tone-pass01-inplace-retest.gba --japanese Japanese.gba --changes translation/dialogue_tone_pass02.json --dialogue-book private_validation/tone-freeze-debug/build-inplace-a/final-dialogue-book.json --catalog analysis/v0.9c/pointer_audit.csv --out <새-비공개-출력-경로>
python -m unittest tests.test_dialogue_tone_pass02_inplace -v
```
