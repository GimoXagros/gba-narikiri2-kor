# Third-party notices

Dalmoori Font, version 0.200, https://github.com/RanolP/dalmoori-font
Pinned commit: 897f0e71224d9964a84b888f2596b2bfd7f98def
License: Apache License, Version 2.0; the complete license is in third_party/dalmoori-font/LICENSE.

This project imports the upstream generator's native bitmap glyphs/components, packs them as GBA 4bpp tiles, and arranges them in UI word images. These format/layout changes are this project's modifications. No TTF rasterization, system font, or fallback glyph is used.

`config/title_trade_glyphs.json` records the native 교/환 bitmap rows and their upstream generated-file identities for the v0.9d title menu. The product build verifies them against the pinned generator output. They are covered by the same Apache-2.0 font notice.

The font generator and development/test dependencies are fetched separately and are not included as executables. Their respective upstream licenses continue to apply. The game, original graphics/audio, and pre-existing FFR translation are not licensed by this project's MIT license.

The optional reference-core source patch in `docs/audio/mgba-e31759b-fifo-timing.patch` modifies mGBA (Jeffrey Pfau and contributors), revision e31759b24e7a4e3899285ff720d7b573ac328ae7. It is provided under MPL-2.0; see https://github.com/mgba-emu/mgba/blob/e31759b24e7a4e3899285ff720d7b573ac328ae7/LICENSE. No emulator binaries are included. This exception is separate from the MIT license for original project code.
