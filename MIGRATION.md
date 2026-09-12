# v0.9 canonical integration

Canonical: https://github.com/GimoXagros/gba-narikiri2-kor

2026-09-13: renamed from `narikiri2-save-compat` to `gba-narikiri2-kor` at the user's request. Repository ID `1356107995`, issues, tags and release history are retained. References below describe the historical consolidation; the new original-Japanese-input package and FFR contribution credit are recorded in `docs/V09D_GRAPHICS_TEST.md` and `CREDITS.md`.
Development archive: https://github.com/GimoXagros/narikiri2-an9j-save-fix

The canonical v0.5 main at 6c26506 is the parent of this integration. Its original restore.py, synthetic tests, verification/v0.5.json and existing tag remain; the original documentation is also preserved under docs/history/v0.5. No history is force-rewritten or deleted.

The validated v0.9 build dependency closure, its assembly/translation/config inputs, and focused regressions are imported as an audited source snapshot from the legacy working tree based on 0e18f64a488901a8a565fbcd9da8b7413aa91e10. Legacy experimentation and private evidence remain in their original repository/workspace.

A whole-history merge is deliberately excluded: the legacy object audit identified a historical Japanese-input BPS blob b568c11d21b516146c84988ff4a4af55a0e739cc at patches/development/b788876e/NARIKIRI2_AN9J_K_COMPLETE_DEV_FROM_JP.bps (4,371,780 bytes). It is not imported or released. The new patch accepts only the exact FFR input.

Raw Japanese full-name reference columns are omitted from the public authored table. Three complete source-text repair matches are represented by source hashes and authored replacement bytes. Description decisions retain authored final text and hash bindings; original description text is read locally. The resulting canonical build must reproduce the exact validated ROM and BPS.

The local comprehensive development suite passed 146 tests. The focused canonical suite has a different denominator, recorded in VERIFICATION.md. Old POC/historical analyses are not presented as current release evidence.

## v0.9a

The v0.9a second stage is built on the byte-frozen v0.9 product. It adds the enemy-inspection consumer and source-bound authored text spans. The private 8,038-entry original corpus is not imported. v0.9 documentation is preserved under docs/history/v0.9; existing tags, source and baseline hashes remain unchanged.

## Repository consolidation, 2026-09-07

The legacy repository is private and was accessible with the owner's authentication. Its current main was `9808c76d821add6bf963279a28dee612ee24749b`; the old `0e18f64` development base does not include the subsequent local working tree. Both remote refs and that dirty working tree were independently backed up and compared.

The canonical development and release location is this repository. Historical legacy links are provenance, never required build inputs. The active product implementation already preserves v0.5/Candidate A/v0.9/v0.9a; the consolidation adds missing reusable regressions, accessor and provenance validators, a local diagnostic host and ROM-free CI. It does not import legacy history or change game bytes.

- [Integration report and validation](https://github.com/GimoXagros/narikiri2-save-compat/blob/main/docs/migration/INTEGRATION_REPORT.md)
- [File/function migration table](https://github.com/GimoXagros/narikiri2-save-compat/blob/main/docs/migration/MIGRATION_TABLE.tsv)
- [Individual legacy test mapping](https://github.com/GimoXagros/narikiri2-save-compat/blob/main/docs/migration/TEST_MAPPING.tsv)
- [Public import allowlist and exclusions](https://github.com/GimoXagros/narikiri2-save-compat/blob/main/docs/migration/PUBLIC_CONTENT.md)
- [Archive gates and actual status](https://github.com/GimoXagros/narikiri2-save-compat/blob/main/docs/migration/LEGACY_ARCHIVE_CHECKLIST.md)
- [Private backup restoration and rollback](https://github.com/GimoXagros/narikiri2-save-compat/blob/main/docs/migration/ROLLBACK.md)
- [Remaining v1.0 work](https://github.com/GimoXagros/narikiri2-save-compat/blob/main/docs/migration/FOLLOW_UP.md)

The reusable imports originate in the owner's authored legacy work. Exact working-file SHA-256 values and any extracted function/class boundaries are recorded in the allowlist. The original files, private corpus, old patches and evidence remain in the private archive; they are not silently relicensed or republished.
