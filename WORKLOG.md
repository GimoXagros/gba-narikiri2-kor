# Work log

## v0.9d title correction and requested prerelease

The user reported that title-menu 교환 used a different font and explicitly requested v0.9d prerelease publication. They added 중단부터 to the comparison/verification scope. Isolated resource 12 at 0x37E584 and its three 16x16 OAM pieces (middle/right/left storage order). Replaced only its 124-byte compressed prefix with native Dalmoori pixels, preserving all pointers and other assets. Existing continue/new/suspend resources match the same pinned native glyph geometry, ink and edge exactly.

Three save scenarios, eight menu selections, trade entry/return and actual suspend resumption passed. Rechecked Namco/formation and all-item/book matrices on final hash 69c5a3e22e00bcacfbaaa7eb28f2efc7d06c8ef37a646ac7236bc78bf76d4012. Prepared an independent font checkout and pinned dependencies; rebuilt the full inherited translation from exact immutable BETA2/BETA3/Japanese twice, then applied the declared final graphics writers. Output and package A/B identities match. Standalone application and negative inputs pass; 59 public contracts pass. Full evidence/limits and product commands are in docs/V09D_PRERELEASE.md. ROM/save and raw runtime evidence stay private. Publication is authorized as a prerelease; keep hardware issue #4 and older releases intact.

## 2026-09-13 graphics test and original-Japanese input

Created `fix/v09d-graphics-test` from v0.9c. Reproduced the inherited BETA3 formation-selector defect and traced its invalid RL type byte. Restored only that byte and the original Namco sub-logo resource. The resulting ROM differs from v0.9c in 1,020 bytes, all within the two owned regions. Compared actual boot pixels and formation VRAM/OAM/palette against Japanese reference. Corrected an initial comparison fixture that used unsupported compact names in unmodified ROMs; that failed route is excluded from final evidence.

Created the requested local item/book test save using RAM fixtures followed by native EEPROM saving. A cold boot preserved all fields. Subsequent item and book matrix runs used the persistent save without RAM writes: 156 items, 142 monsters, 200 costumes, 22 characters. Native screenshots and private logs remain outside Git.

User then requested Japanese-original-only patch application, Xagros branding, FFR contributor credit and repository rename. Created and verified the standalone Japanese-input BPS/ZIP twice, with 56 public contracts and standalone positive/negative application checks. Replaced only the user-supplied repository logo and its exact-hash audit exception. Renamed the same remote repository ID to `GimoXagros/gba-narikiri2-kor` and updated the shared Git remote. Existing tags/releases and open hardware validation remain intact. Details and artifact hashes: `docs/V09D_GRAPHICS_TEST.md`.

## Historical v0.9c PC audit

## Preflight

Read the user task document and Korean-patch skill. Inspected parent/repository AGENTS.md, Git status/remotes/branches/worktrees and related PRs/issues. Ran `git fetch origin`, then `git worktree add -b fix/v0.9c-pc-validation ../narikiri2-v09c-pc-validation origin/main`. Main's RIGHTS.md update is preserved.

Downloaded v0.9b with `gh release download v0.9b`; recorded asset metadata and frozen source-file hashes. Read all selected ROMs as bytes, checked AN9J headers, size and SHA-256. Exact local test-fixture copies are private and ignored.

Cloned the declared font source independently, checked out 897f0e71224d9964a84b888f2596b2bfd7f98def, and started pnpm 7.33.7 frozen installation with a new private store.

## Reproduction and baseline audit

Ran frozen build_ffr_v09b.py twice with separate new outputs; exact ROM/BPS identities passed. Rebuilt the ZIP from the detached v0.9b tag; all published identities match. Ran unittest discovery: 139 collected/executed/passed, 0 failed/skipped/errors; public subset 43/43 and repository audit passed. Captured all three stages of declared writers and independently reconstructed the final ROM: 21,924 nonpadding changed ranges, zero unowned/unexpected bytes. Registered two reproduced PC tool failures and the 2077/1227 labeling correction. Rechecked immutable reference hashes. Replaying actual frozen runtime routes; semantic review remains explicit.

## Candidate build and runtime

Ran tools/build_ffr_v09c.py twice into private_validation/v09c-build-A and -B. Both target/patch byte-identical to reproduced v09b. Ran final unittest discovery: 150 collected/executed/passed; 0 fail/skip/error. Public v09c subset 49/49. New source changes are host tooling only.

Ran replay_pc_route.py against both frozen and candidate files: each 14 routes/134 identical screens. Ran audit_item_pages.py, audit_book_pages.py (three books and details), audit_arte_descriptions.py with explicit private core/save/route inputs. Recorded fixture limits, visually inspected native save/inspection/suspend screens and all ten arte-description contact sheets. Rechecked all seven reference snapshots and 108 frozen source/doc/gate files: unchanged. Wrote all claim/origin/bug/runtime reports and artifact-bound PC gate. Next: package A/B, standalone Unicode application, public content audit, draft PR and CI.

## Package and draft PR completion

Ran package_ffr_v09c_release.py with new A/B directories: identical 191,782-byte candidate ZIP, hash 206d97f7b8292c60adaef8bc925d04c4faffd08869f164166c5494be236e25e0. Extracted to a fresh Unicode directory and ran its standalone applicator; exact ROM round-trip. Wrong JP/BETA2/already-patched ROM, existing output/source and source hardlink all rejected without mutation. Candidate package has no ROM/save. Copied the separately verified private ROM and package into the user's new candidate folder, with local checksums.

Committed by bug ID (184f5cd, 4e6b4fb, 33c79f6), pushed only fix/v0.9c-pc-validation and ran gh pr create --draft: PR #8. Windows/Ubuntu candidate public contracts and existing public contracts succeeded. Read-only GitHub checks confirm original main/tag/assets and open #4; no v0.9c tag. Final reference/frozen file/evidence SHA checks pass. No merge/release/shutdown.

## User-authorized prerelease — 2026-09-09

User explicitly requested v0.9c prerelease publication. Added separate artifact-bound authorization, prerelease packaging mode and current user instructions while preserving historical candidate gate and all v0.9b files/assets. Applicator change is only the completion message; game/BPS unchanged. Re-ran all 150 local and 49 public tests: PASS. Packaged A/B identically; extracted standalone ZIP and applied via Unicode path to the exact target. Rejected denied authorization, wrong target, altered hardware claim and changed source before output creation. Next: integrate PR, tag and publish/download-verify assets.
