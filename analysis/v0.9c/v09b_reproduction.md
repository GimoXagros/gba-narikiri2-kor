# Frozen v0.9b reproduction

PASS. Two new output directories private_validation/v09b-repro-A and -B were built with the unchanged v0.9b CLI, exact declared inputs, a new pinned font clone and dependency store. Their ROM and BPS are byte-identical and match the published hashes. Both builds enforce BPS reapplication and historical gates.

The published ZIP was also reproduced byte-for-byte (800a49eb411f9d251ca37eaacd50a61733c2ce3d7939db9ed3719b18ff432529) using a detached v0.9b tag checkout for packaging. Main's later RIGHTS.md edit is preserved and is not silently included when reproducing the old ZIP. JSON contains the complete identities.
