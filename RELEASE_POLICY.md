# 배포 정책

## v1.1 — 2026-10-11 공개 범위 결정

사용자의 현재 요청: “검증 결과 정상적인것을 확인했어. 깃허브 저장소에 v1.1버전으로 업데이트 해줘”. 직전 전달본 `9fd341b8…11889b`에 대한 정상 동작 확인과 공개 요청을 USER_ATTESTED 범위 결정으로 연결한다. 사용자가 직접 SHA-256을 확인했다고 추정하지 않는다. 기기·실행 프로그램과 개별 실기 항목은 NOT_REPORTED로 남긴다.

G8의 PASS는 이 공개 범위 결정의 수락이며 모든 실기 시험 통과를 뜻하지 않는다. 이전 v1.0의 공개 유예 결정이나 기기 기록을 승계하지 않는다. 나머지 관문은 원본 주소·8MiB 크기·복원 출력·저장·고정 성능 표본·재현 빌드·배포 무결성의 기록된 범위를 따른다. 알려진 후보 실패 기록과 남은 자연 진행·분기·통신 한계를 보존한다.

게임 바이트가 바뀌면 이번 확인은 승계하지 않는다. 적용기·문서만 변경해도 해당 검사를 재실행한다. 승인한 commit/tree/입력/ROM/BPS/ZIP은 외부 배포 manifest에 연결하며, 태그는 이동하지 않는다. 공개 다운로드와 새 폴더 적용을 확인한 뒤에만 RELEASED_AND_VERIFIED로 기록한다. 이슈 #4의 미확인 항목은 일괄 종료하지 않는다.

## 이전 버전 정책 기록

v0.9b is the BETA3(071102) Japanese-source-comparison public verification prerelease. Known reproduced in-scope defects must be repaired before release. The final source/target/patch identities, authored ledgers, save/name regressions, display checks and preserved assets are bound in verification/v0.9b.json. A candidate flag never authorizes packaging. v0.9 and v0.9a remain reproducible historical releases.

v1.0 additionally requires extended complete game progression and hardware verification of the final artifact (issue #4). Candidate A hardware success is not v0.9b hardware evidence. Do not claim unplayed branches, natural unlocks from RAM fixtures, two-console link completion from a pointer consumer test, or independent human literary review from agent proofreading.

For the 2026-09-24 v1.0 publication, the user explicitly chose public distribution before user and second-pass validation. This is a release-specific scope decision, not a claim that the hardware, cold-load, branch/event, natural-progression, or link checks above passed. Publish only the byte-identified patch package with the unverified cases named in `verification/v1.0.json` and the release notes; keep issue #4 open for post-release evidence. Repository/build/package integrity checks and source/target identity remain pre-publication requirements. A release is verified only after its public downloads and patch application match the approved bytes.

v0.5 distribution is retired for the current BETA3 workflow. Preserve its tag, source history, archived assets and BETA2-specific technical conclusions. See docs/V05_RETIREMENT.md.
