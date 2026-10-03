# Original-address text storage experiment

This is a local, non-playable storage prototype. It is **not** a completed
8 MiB Korean ROM, and must not be distributed as a patch or loaded with a
player's save state. Existing expanded build paths remain unchanged.

The fixed sources are AN9J JP Rev 0 (SHA-256
`a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7`)
and the adopted A11 plus credits baseline (SHA-256
`eac45b3345e865f1fea68bbb07f62aff0f6ccdf03004090f57b55f75b6f82b73`).

## Implemented and checked

- The independent source catalog covers 8,945 full-text and 1,227 compact-name
  bindings at 9,246 distinct Japanese starts. Slot ownership is restricted to
  each original first-NUL-inclusive extent, with no guessed padding.
- `strict_layout_core.py` writes into a fixed 8,388,608-byte source buffer.
  It checks expected source bytes, ownership declarations, overlapping writers,
  protected pointer values, aliases, output bounds, and final content.
- `strict_unit_codec.py` encodes native glyphs/literal bytes through two shared
  prefix trees. Compact private glyph IDs and native control bytes are preserved.
  Full text follows the game's glyph rules, including trail bytes `7F` and
  `FD..FF`; standard CP932 trail validation would be incorrect here.
- An inline four-part form stores `[prefix, left, right, suffix]` for the seven
  original addresses with distinct adopted Korean variants. Both alternatives
  remain in that address's original slot. Masks 11 and 13 select the appropriate
  output; their association with actual game consumers is **not implemented**.
- `strict_unit_bundle_decode.s` is a 272-byte Thumb-1 decoder. It bounds source,
  dictionary nodes, and output; preserves callee-saved registers; validates EOS
  padding; and returns consumed input bytes. Its two trees total 26,008 bytes.
- The actual data-only image was independently read and decoded for all 10,172
  bindings, using a separate bit reader and guarded Thumb execution. Pointer,
  start, content, and slot-overflow checks found zero mismatches. Swapping the
  seven alias selectors caused the expected fourteen content failures.
- Normal Python and `python -O` produced identical data-image, codebook, slot,
  binding, and write-manifest bytes. Product ROM/BPS determinism is not claimed.

The data-only image is named `TEXT_SLOT_IMAGE_NOT_PLAYABLE.bin`; its SHA-256 is
`ba9a42690ce2899d9465a41cb326f31f4af6f4cc8047fcb4840f22e0ed3e5006`.
Its length alone is not C1-C6 product compliance: codebooks are separate
experiment inputs, and the image still lacks the Korean runtime integration.

## Remaining implementation

1. Trace and intercept every length, copy, formatting, dialogue/page, and render
   consumer. Establish owned RAM buffers and lifetimes before any game hook.
2. Carry actual use-site context into the seven inline variant selections.
   The selector job menu includes a native length consumer; a renderer-only
   hook is insufficient. No complete text table may be substituted externally.
3. Place the decoder, both trees, existing fonts, A11 code, boot notice, title,
   credits, and other live assets inside 8 MiB with reference closure.
4. Preserve the save repair. The eight-byte aligned `NARIKIRI` source also exists
   at original JP offset `002BF4C8`, with an unchanged CpuSet consumer, but the
   proposed signature-pointer restoration has not been applied or tested in a
   completed runtime. The historical save guard is deliberately unchanged.
5. Re-run offscreen boot/dialogue/menu/save/SGM regression on the integrated ROM.
   No old saved-state pass transfers automatically to a new text representation.

The extra A11 branch-layout performance experiment still measured P99 9 frames
for both item and shop-sell lists against the target of 8, using the frozen
measurement protocol. It was not adopted. The original A11 baseline remains.

`strict_asset_inventory.py` independently matched 25 named code/asset ranges.
The 76,800-byte boot bitmap losslessly compresses to 9,156 bytes, but that change
has not been integrated into its consumer. Unknown expansion bytes remain
unknown, not free space.

## Local reproduction

Run from the repository with the existing validation Python and dependencies.
Use fresh output directories; the tools reject existing output folders.

```powershell
python tools/build_jp8mib_strict.py --encoding unit_inline --out-dir private_validation/strict-next-build --require-product
python -O -m unittest discover -s tests -p 'test_strict*.py' -v
python tools/strict_asset_inventory.py --out private_validation/strict-next-assets
```

The first command intentionally returns nonzero for the unfulfilled **product**
gate, even when the storage-only image passes. The independent full-source
corpus reader and private evidence are retained under
`private_validation/strict-layout-20261003/`; they are not public ROM inputs.
