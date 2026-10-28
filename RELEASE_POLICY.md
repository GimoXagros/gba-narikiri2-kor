# 배포 정책

## v1.1b — 조건부 공개 요청과 최종 해시 검증

사용자의 “최종 검증까지 통과하면 v1.1b로 배포해줘” 요청을 `USER_REQUESTED_CONDITIONAL`로 기록합니다. 정확한 요청 원문은 `verification/v1.1b.json`에 보존합니다. 최종 결과 `32ed708c0c8c26074829a163000dd5504a5a7a1fbcd4f1319c2eb1f45d438677`의 재현·주소·소유 영역·CPU fixture·가상 실행·저장·성능·독립 검토·BPS·패키지 관문을 각각 검증합니다.

관문의 PASS는 명시된 범위에 한합니다. 사용자 최종 파일 수락은 `NOT_REPORTED`, 최종 실기는 `NOT_RUN`입니다. 이전 수락·실기 결과를 승계하지 않습니다. 기존 기술 설정 제목 잘림과 기준선 대비 오디오 한 스테레오 프레임 차이는 공개하며 전체 분기·통신·청취 시험을 통과로 바꾸지 않습니다. 기존 이슈 #4는 유지합니다.

CI와 실제 공개 다운로드·새 폴더 재적용이 동일한 바이트를 만들 때만 별도 배포 기록을 `RELEASED_AND_VERIFIED`로 갱신합니다. ROM·개인 저장·SGM·전체 대사집은 공개하지 않으며 기존 태그와 릴리스를 보존합니다.

## v1.1a — 2026-10-19 수정 수락 및 배포 결정

사용자 요청: “수정된 사항을 확인했어. **v1.1**a로 저장소에 업데이트 및 배포해줘”. 최종 교정본 `8823db1cb72f1328136ccfd8fff1fbdca0c8489cbc7ccf90f7e4ecdbb1c37776` 및 BPS `75a16466feaae9612c6827d8fac5faf5b9a40eb968a740d9954aae10be5eadce`에 연결한 USER_ATTESTED 수정 수락이다. 사용자 환경·항목별 검사·직접 해시 대조를 추정하지 않는다.

검증 계약 `narikiri2-v11a-verification-1`은 수정 수락, 고정된 원본·결과·BPS 식별자, CPU_FIXTURE_ONLY 증거를 구분한다. hardware_status·runtime_status·individual_checks와 사용자 환경은 NOT_REPORTED로 남긴다. 이전 v1.1의 G0–G10 PASS를 복사하거나 CPU fixture를 일반 플레이·실기 통과로 바꾸지 않는다.

게임 바이트가 바뀌면 이 수락을 승계하지 않는다. 새 폴더 재적용과 공개 다운로드의 크기·해시가 승인한 바이트에 일치한 뒤에만 RELEASED_AND_VERIFIED로 기록한다. 태그를 이동하지 않으며 이전 릴리스·이슈 #4의 미확인 범위를 보존한다.

## v1.1 — 2026-10-11 공개 범위 결정

사용자의 현재 요청: “검증 결과 정상적인것을 확인했어. 깃허브 저장소에 v1.1버전으로 업데이트 해줘”. 직전 전달본 `9fd341b8…11889b`에 대한 정상 동작 확인과 공개 요청을 USER_ATTESTED 범위 결정으로 연결한다. 사용자가 직접 SHA-256을 확인했다고 추정하지 않는다. 기기·실행 프로그램과 개별 실기 항목은 NOT_REPORTED로 남긴다.

G8의 PASS는 이 공개 범위 결정의 수락이며 모든 실기 시험 통과를 뜻하지 않는다. 이전 v1.0의 공개 유예 결정이나 기기 기록을 승계하지 않는다. 나머지 관문은 원본 주소·8MiB 크기·복원 출력·저장·고정 성능 표본·재현 빌드·배포 무결성의 기록된 범위를 따른다. 알려진 후보 실패 기록과 남은 자연 진행·분기·통신 한계를 보존한다.

게임 바이트가 바뀌면 이번 확인은 승계하지 않는다. 적용기·문서만 변경해도 해당 검사를 재실행한다. 승인한 commit/tree/입력/ROM/BPS/ZIP은 외부 배포 manifest에 연결하며, 태그는 이동하지 않는다. 공개 다운로드와 새 폴더 적용을 확인한 뒤에만 RELEASED_AND_VERIFIED로 기록한다. 이슈 #4의 미확인 항목은 일괄 종료하지 않는다.

## 이전 버전 정책 기록

v0.9b is the BETA3(071102) Japanese-source-comparison public verification prerelease. Known reproduced in-scope defects must be repaired before release. The final source/target/patch identities, authored ledgers, save/name regressions, display checks and preserved assets are bound in verification/v0.9b.json. A candidate flag never authorizes packaging. v0.9 and v0.9a remain reproducible historical releases.

v1.0 additionally requires extended complete game progression and hardware verification of the final artifact (issue #4). Candidate A hardware success is not v0.9b hardware evidence. Do not claim unplayed branches, natural unlocks from RAM fixtures, two-console link completion from a pointer consumer test, or independent human literary review from agent proofreading.

For the 2026-09-24 v1.0 publication, the user explicitly chose public distribution before user and second-pass validation. This is a release-specific scope decision, not a claim that the hardware, cold-load, branch/event, natural-progression, or link checks above passed. Publish only the byte-identified patch package with the unverified cases named in `verification/v1.0.json` and the release notes; keep issue #4 open for post-release evidence. Repository/build/package integrity checks and source/target identity remain pre-publication requirements. A release is verified only after its public downloads and patch application match the approved bytes.

v0.5 distribution is retired for the current BETA3 workflow. Preserve its tag, source history, archived assets and BETA2-specific technical conclusions. See docs/V05_RETIREMENT.md.
