# Map place labels, 2026-09-23

Source: latest boot-notice product d3c4b127cde5b3f0d29970369a6f54c02560e4e591dfc42deffbabc0c0fe2209.

Native consumer 0x0800CA00 reads 25 eight-byte label records from 0x082C23B8. Rows 0..2 are INFO and hint graphics; rows 3..24 are 22 place labels. Each record points to an animation frame and lists up to four signed resource IDs. Consumer computes allocation from compressed resource lengths and uses the matching frame's OBJ shape and tile offsets. Korean and Japanese labels were compared as graphics, not guessed from dialogue IDs. Native アナスイ通り verified directly from concatenated resource 31/32.

New copies of the asset and label tables are appended. All 135 relative asset references are rebased modulo 32 bits. Only the label consumer's literals at 0xCAEC/0xCAF0 point to the new copies; unrelated consumers keep originals. Place rows use unique resource IDs 9..30 within this copy and generated 32x16 pieces with matching OAM geometry. All text fits at most 96px. Header, boot notice, title/credits and other existing bytes outside declared writes remain unchanged. User-specified longest name is preserved in full. Current spelling 훈다르크 replaces earlier 훈다크르 in two compact-name fields and 27 full-text occurrences of identical byte length.

22 real-renderer table fixtures verify each label is in live OBJ VRAM and every nontransparent screen pixel matches the generated shape. RGB565 host conversion is accounted for. Fixtures replace the church label record only, not natural travel through all dungeons. VBA-M regression checks all ten boot buttons and normal save load. Rebuild and Japanese BPS roundtrip pass. Private manifests/screenshots are under private_validation/place-names-20260923/final-product, all-labels-final and vbam-regression.

Investigation of INFO text confirmed the existing 8px glyphs match every displayed ink pixel; a speculative window-mode hook in product-b had no effect and was removed. No such hook is in the final product. Historical candidate and failed verifier outputs remain private evidence. Public release unchanged.
