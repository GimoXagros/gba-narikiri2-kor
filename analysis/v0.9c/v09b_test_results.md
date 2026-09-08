# Test results

Frozen baseline: 139 collected, 139 executed, 139 PASS, 0 FAIL/SKIP/ERROR. Public baseline: 43/43. v0.9c: 150 collected/executed/PASS, 0 FAIL/SKIP/ERROR; public subset 49/49. The increase is 6 synthetic file-publication tests and 5 real candidate contract tests; no previous test was removed, renamed or skipped. Tests in the public subset overlap the full suite and must not be added to it as unique coverage.

The same injected write failure is observed against old and new applicators. Old leaves a 128-byte final ROM; new removes the temporary and publishes no final ROM. Contradictory manifest accepted by the frozen packager is rejected by the candidate validator. Full logs and machine-readable counts are beside this report. Historical component fixtures are dependencies within the v0.9b audit, not a separate full audit of old releases.
