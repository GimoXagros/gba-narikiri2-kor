# Build and tests

The local v1.0 candidate build and its exact source chain are documented in [docs/V1_BUILD.md](docs/V1_BUILD.md). Release readiness is recorded in [verification/v1.0.json](verification/v1.0.json); the candidate is not public while required final-artifact progression evidence is incomplete.

Current original-Japanese-input prerelease: see [v0.9d generation and verification](docs/V09D_PRERELEASE.md). End users apply the new test package directly to the exact Japanese ROM; no separate FFR input is required. The historical build below remains unchanged for reproduction of v0.9b/v0.9c.

## Historical v0.9b build

Applying the ZIP needs Python 3.10+ and the standard library. Reproduction additionally needs the exact BETA2, BETA3(071102) and Japanese inputs from config/source_profiles.json, Node.js, requirements-dev.txt and the pinned font source. End users need only BETA3; BETA2 and Japanese are local build/review references.

```powershell
python -m pip install -r requirements-dev.txt
git clone https://github.com/RanolP/dalmoori-font third_party/_work/dalmoori-font
git -C third_party/_work/dalmoori-font checkout --detach 897f0e71224d9964a84b888f2596b2bfd7f98def
```

In third_party/_work/dalmoori-font/generator, use **pnpm 7.33.7**:

```powershell
pnpm install --frozen-lockfile
pnpm run build:debug
```

This reproduction used Python 3.14, Node.js 24.19.0 and pnpm 7.33.7 with an independent font checkout. Follow third_party/dalmoori-font/SOURCE_MANIFEST.json. Do not substitute fonts, revise the lockfile, or link the font work directory to another project.

```powershell
python tools/build_ffr_v09b.py --beta2-reference "BETA2.gba" --beta3 "BETA3.gba" --japanese-reference "Japanese.gba" --output-dir output/v0.9b-final-build
python tools/package_ffr_v09b_release.py --build-dir output/v0.9b-final-build --output-dir dist/v0.9b
```

Both directories must be new. The builder reproduces frozen BETA2 v0.9/v0.9a, validates every transferred writer against BETA3, rebinds the historical review, applies the source-bound Japanese comparison decisions and restores the non-text trade table. It checks controls/numbers, glyph round trips, description capacity, overlaps, ownership, protected font/sound/EEPROM ranges and deterministic BPS reapplication. verification/v0.9b.json must match the exact output and both new ledgers. `--candidate` creates a local validation candidate that the packager rejects.

The ignored review_intermediate.gba in the build directory is the reproducible pre-Japanese-correction fixture. It is not a release artifact. Public decisions contain authored corrections and source hashes, not the full extracted Japanese or FFR script. End-user application and ZIP read-back verify the final target hash and preserve existing output files.

## Local real-data tests

The local suite needs the exact Japanese and BETA2 ROMs in the repository root, BETA3-reference.gba there, Candidate A at output/NARIKIRI2_AN9J_K_EEPROM_RESTORED.gba, frozen v0.9 at output/v0.9-final-build/NARIKIRI2_AN9J_K_DALMOORI_v0.9.gba, and the v0.9b review_intermediate.gba above. Input filenames expected by older tests are documented in the historical v0.9a BUILDING.md; their content hashes remain mandatory. All ROM fixtures are ignored. Candidate A is reproducible with restore.py and v0.9 with tools/build_ffr_v09.py.

```powershell
python -m unittest discover -s tests -v
python tools/run_public_tests.py
python tools/audit_repository.py
```

The local real-data suite runs **139 tests**. Public CI runs a deliberately smaller **43 synthetic/source-contract tests** and the repository audit without game data or extra dependencies. Public CI does not substitute for real-data tests; missing local fixtures are errors.

The local diagnostic host is tools/libretro_probe.py. Supply an exact local libretro core and a new private run directory; add --save only for a copied 8 KiB save. Runtime logs bind ROM/core/save identities, controller operations, and explicit RAM preparation. See VERIFICATION.md for tested populations and limitations.

Historical release assets are immutable. Preserve tools/build_ffr_v09.py and tools/build_ffr_v09a.py and their recorded gates; never overwrite their existing release ZIPs with a ZIP regenerated from current documentation.
