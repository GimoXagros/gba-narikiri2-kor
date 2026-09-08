# Bug ledger

All 3 bugs are BUILD_OR_PACKAGING_BUG; MEDIUM 2, LOW 1. No new reproducible game-byte defect was established. No original-ROM defect was dismissed because of its origin.

## ND2-V09C-20260909-001 — Partial ROM remains after interrupted output write

Root cause: Applicator publishes the destination name before write/flush/read-back completes and has no failure cleanup

Fix: Write/read-back/fsync a unique sibling temporary file before no-overwrite publication; clean only owned outputs on failure.

Regression: Inject ENOSPC after 128 bytes using the same real source and patch: v09b leaves final partial file; v09c leaves none.

Status: FIXED_PC_AWAITING_USER_HARDWARE_RETEST. ROM offsets/before/after bytes: N/A (zero ROM changes).

## ND2-V09C-20260909-002 — Package accepts contradictory version and size metadata

Root cause: Packager validates hashes but trusts version, source_size and patch_size from the build manifest

Fix: Validate every candidate manifest field, nested value type, actual size/hash, provenance and no-release status before packaging.

Regression: Authentic frozen build plus WRONG_VERSION/source_size=1/patch_size=2: old packager accepts; new validator rejects. Missing/extra/nested wrong-type values also rejected.

Status: FIXED_PC_AWAITING_USER_HARDWARE_RETEST. ROM offsets/before/after bytes: N/A (zero ROM changes).

## ND2-V09C-20260909-003 — Absolute pointer count mislabeled as compact pointer count

Root cause: The 2077 counter includes full-width name and body/UI absolute pointers; it is not the 1227 compact field population

Fix: Record 2077 as first-stage absolute pointer bindings and 1227 as compact name fields; preserve historical gate.

Regression: Inspect transfer_writes counter and compact catalogue. Candidate contracts reject compact_name_fields=2077.

Status: FIXED_PC_AWAITING_USER_HARDWARE_RETEST. ROM offsets/before/after bytes: N/A (zero ROM changes).
