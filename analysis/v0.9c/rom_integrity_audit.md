# ROM integrity audit

All three declared build stages were independently replayed over immutable BETA3 plus FF extension. Stage writer counts: 4042 / 10793 / 627. Reconstructed bytes equal frozen target `d761088a8549cb5bc60a2f03a4b78eea5282dbc17ed5da4ef1de27da4ad8d4d4`. There are 21,924 nonpadding changed ranges (380,833 bytes). Every changed byte has a declared writer. `binary_diff_manifest.csv` applies identically to BETA3→v0.9b and BETA3→v0.9c. Unchanged FF extension is padding, not a fabricated bug fix. v0.9b→v0.9c has zero changed bytes/ranges.

10,380 typed pointer storage fields were inspected; zero unaligned storage fields. Actual compact/full text targets are in ROM and terminated. Relative/non-text pointers are typed, not incorrectly treated as strings. D00549 remains a pointer table; literal at 0xA4918 is `60 37 37 08`, entries at 0x373760/0x373764 lead to translated D05660/D05661. Existing real Thumb consumer test executes the loads. Code/literal/branch integrity is supported by frozen writer reconstruction, inherited ARM/Thumb tests and current mGBA routes, not by scanning every 32-bit word as a pointer.

AN9J / NARIKIRI2 / AF / revision 0 / header checksum 2D (computed 2D). Size 13,107,200. EEPROM 0xA601C..0xA6800 equals BETA3 and Japanese; large font/audio 0xAC3F4..0x2B2CAC equals BETA3. No v0.5 save restoration is applied to BETA3.

Missing glyph/encoding, planned-writer collision and measured text-capacity overflow gates passed (zero). UNEXPECTED=0; UNOWNED_DIFF=0. This does not establish execution coverage for every game branch.
