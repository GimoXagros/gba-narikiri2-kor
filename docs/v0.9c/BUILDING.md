# Reproduce the local PC candidate

Use the same immutable BETA2 reference, BETA3(071102), Japanese reference and pinned Dalmoori setup documented in the frozen BUILDING.md. The BETA2 input is solely a frozen build dependency. The candidate never patches or writes the Japanese reference. Use new output directories on every run.

```text
python tools/build_ffr_v09c.py --beta2-reference BETA2.gba --beta3 BETA3.gba --japanese-reference JAPANESE.gba --output-dir private_validation/v09c-build-A
python tools/build_ffr_v09c.py --beta2-reference BETA2.gba --beta3 BETA3.gba --japanese-reference JAPANESE.gba --output-dir private_validation/v09c-build-B
python -m unittest discover -s tests -v
python tools/run_v09c_public_tests.py
python tools/audit_repository.py
python tools/package_ffr_v09c_release.py --build-dir private_validation/v09c-build-A --output-dir private_validation/v09c-package-A
```

Real-data tests require the exact private fixtures, including the v09b baseline built in private_validation/v09b-repro-A, BETA3-reference.gba and historical component inputs documented by the frozen build. Missing fixtures fail; public CI executes only the explicit no-ROM subset. Package creation also requires the artifact-bound PC candidate verification file, and never authorizes publication. No gh release/tag/merge command is part of this workflow.

New audit harnesses accept explicit private inputs: replay_pc_route.py, audit_item_pages.py, audit_book_pages.py, audit_arte_descriptions.py (use --help). Operations, save exports, screenshots and full expected-name catalogues stay private. The three matrix harnesses are ports of the prior authored local runtime checks with CLI paths; their fixtures and semantic limitations remain explicit.
