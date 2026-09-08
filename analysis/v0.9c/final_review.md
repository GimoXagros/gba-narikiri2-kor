# Final review — v0.9b PC audit / v0.9c local candidate

PC_VALIDATION_PASS / AWAITING_USER_HARDWARE_RETEST / RELEASE_NOT_AUTHORIZED.

Repository: https://github.com/GimoXagros/narikiri2-save-compat. Branch fix/v0.9c-pc-validation. Audited implementation/report commit: 33c79f6817c1750c5385f343bab542a89e1e58fb; subsequent bookkeeping only records final delivery/status. Main remains 09eccf0a079cbe6106a8c1f5427b8a2cffa6681a. Bug commits are listed in fix_history.md and the ledger. Draft PR: https://github.com/GimoXagros/narikiri2-save-compat/pull/8 (OPEN, draft).

Validation: baseline 139 local / 43 public; candidate 150 local / 49 public, no failures/skips/errors. Candidate Windows and Ubuntu jobs and existing public contracts succeeded on the audited implementation. CI push run 34259699027 and PR run 34259748285; baseline contract workflows 34259699043 and 34259748308. Public CI contains no private ROM and does not replace local real-data tests.

ROM/BPS candidate A/B and baseline A/B agree; final tool-only game delta zero. ZIP A/B hash 206d97f7b8292c60adaef8bc925d04c4faffd08869f164166c5494be236e25e0 (191,782 bytes). ZIP read-back and standalone Unicode application pass. Wrong JP/BETA2/repatched input and existing file/source/hardlink protection pass. No ROM or save is in ZIP/public tracked content. Candidate ROM/BPS identities, sizes and all 25 requested report items are in V09C_PC_VALIDATION.md. Private evidence remains local.

Final source/reference recheck: seven snapshots unchanged, 108 frozen historical source/doc/gate files unchanged, 4 public v0.9b assets retain digest/size/update timestamp and URLs, v0.9b annotated tag and peeled commit unchanged. No v0.9c tag exists. Issue #4 remains OPEN. Current RIGHTS.md and all historical build/verification sources are preserved. CHANGELOG only prepends the candidate correction.

Public tracked-file signature/path audit passes; staged diff checked for whitespace, private ROM/save/patch signatures, full game corpora, credentials and active personal absolute paths. New audit CSVs contain offsets/owners/hashes, not original game byte dumps or complete script text. Logs and tool source are explicit; inherited build dependencies are documented.

Local handoff: user-supplied additional-work folder, subfolder v0.9c_PC_검증후보_20260909. Contains a private candidate ROM, BPS, candidate ZIP, manifest, checksums and Korean test instructions; LOCAL_SHA256SUMS includes the ROM. This is local delivery, not a public release.

Known limitations remain explicit: no full natural end-to-end game playthrough, all event branches, independent literary re-review, physical hardware/flashcart certification or two-device trade. Display fixtures support renderer coverage only. User hardware retest checklist includes all three host bug IDs. No merge/tag/release/issue closure/shutdown performed.
