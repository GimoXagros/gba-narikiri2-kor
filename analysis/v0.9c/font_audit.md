# Font audit

Pinned Dalmoori revision 897f0e71224d9964a84b888f2596b2bfd7f98def, independent local checkout, pnpm 7.33.7 frozen install. Original large font/audio is byte-preserved. Frozen build gates reject missing encodings/glyphs, writer overlaps, capacity overflow; current v09b/v09c A/B pass. Existing component tests cover small/simple/large consumers, transparent/solid palettes, decoder bounds, preserved registers, popup sentinels, 188 formatter templates, previous-page retention, banner upload/cache boundaries, name editor and six-cell party names. These are inherited component fixtures, supplemented by final-ROM matrices and routes.

Current item matrix: 156 IDs, 157 screens, exact expected name pixels, all 8192 base-font/transparency bytes unchanged on every screen, maximum live private tiles 28. Costume/monster/character lists: 200/142/22, detail return names retained; costume details verify 224 arte-name pixel patterns. All 231 skill-description captures equal frozen verified screens; ten contact sheets reviewed with no visible new clipping/garbling. No synthetic screenshot repair is used.

Zero measured missing glyph/collision/overflow. Discovery and skill fixtures do not prove natural unlock, every palette/environment combination, all dynamic player strings or every combat event. Hardware remains pending.
