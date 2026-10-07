# v1.1 runtime integration checkpoint

Status: **INTEGRATED_DIAGNOSTIC__PERFORMANCE_NOT_MET**. This is not release
approval. No v1.1 release, tag or remote update has been performed.

Storage baseline: 6caa05608d65d565181474c7e29e6768df07d6a0.
First integration checkpoint: d00ccb076dae0f49c535b91529b77f12ad25dfac.
Current diagnostic: exactly 8,388,608 bytes, SHA-256
d5c375379369916bd1a5309678be2e9e28c5b0fff6955ebddb73537c64c187f5.
BPS SHA-256:
81930631ded05cd71ff560f8c030663f0c343d2cfe150d14ad28834a462f5110.

## Integrated behavior

- Original storage and raw pointer values for 10,172 historical bindings and
  9,246 original stream starts; 197 additional UI bindings remain separate.
  Korean template bytes and shared variants are preserved.
- Packed glyph dictionaries, exact-start lookup, caller-owned decoding,
  event allocation, original-slot default names and persistent actor adapters.
- Six static menu tables and the bounded thirteen-command runtime table
  decode into menu-owned memory released after the native menu returns.
- Lossless full-font compression, compact-font derivation and in-cartridge
  placement of the adopted title, notice, credits and map resources.
- A 328-byte Thumb-1 full-font compositor preserves pixels and backgrounds.
  Its 122,880 glyph/color/parity CPU cases passed on the earlier compositor
  candidate; those bytes are unchanged here. No persistent RAM was added.
- ARTE indices outside 0..231 are rejected before record memory access.
  Valid records, nonzero modes and both shared-name tags retain their ABI.

Two actual game defects were found after the initial integration:

1. Pub Rose reentry uses the separate native dialogue consumer at 0809A43C.
   The event-expansion adapter did not cover this path. The added synchronous
   wrapper holds decoded bytes in its 288-byte stack buffer until the original
   renderer returns. Offscreen comparison includes the second visit and later
   pages, as well as the unchanged first-visit sequence.
2. The skill-description branch at 08013DEE measured compressed bytes with
   native strlen while its display path already decoded them. A 48-byte adapter
   now decodes for the duration of strlen. The original 35-byte threshold and
   native byte-count semantics are preserved. All 232 linked lengths match
   adopted Korean bytes using the real decoder and real strlen, without stubs.
   Opposite branch directions at skill indices 2 and 153 were reproduced in
   the native menu; repaired pixels match the adopted comparator. These skill
   fixtures modify a learned-skill record and do not prove natural acquisition.

The direct wrapper occupies CAB58..CABAC, its prologue trampoline
CA3A8..CA3C4, and the length helper CA3C4..CA3F4. These are bounded retired-font
owners. No spare full-font suffix remains; the small-font owner has 21 bytes.

## Evidence and limits

The current linked CPU corpus executes all 10,172 historical and 197 additional
bindings with exact output and intact guards. Corpus-supplied alias selection
does not establish natural game-context reachability. Independent review of
the length helper covers 232 records on each of IWRAM and EWRAM stacks:
464 calls preserve native bytes, length, buffer lifetime, registers and guards.

The original 222-test baseline remains intact. The later working-tree suite
passes 344 tests with no failures or skips. This includes preexisting local
experimental tests; it is not a clean public-checkout test count. New adapter
tests cover native pass-through, embedded NUL, long temporary input, ABI and
failure handling.

On this exact ROM, controller-only new-game routes with default and mixed
custom names reach native save completion after 55,503 and 71,788 frames.
No old state was loaded and no RAM was edited. Default, mixed and original
user saves each pass separate-process cold read, native resave and another
cold read. Party records (120 bytes), inventory quantities (79 bytes) and
names agree across each sequence. Original saves remain unchanged. Legacy
suspend data, native suspend creation, cold resume and consumption also pass
the bounded offscreen replay. These are not hardware/full-game claims.

Three SGM v10 checkpoints were freshly generated on this ROM and inverse-
converted for separate offscreen VBA resume trials. The intro, Mint and
reentry trials continue beyond the previously missed second Pub Rose entry.
The intro and Mint trials reach identical final frames/pixels. A changed ROM
requires fresh state generation and binding. Desktop UI compatibility and
cross-ROM state compatibility are not claimed.

SGM and dialogue-export publication stage outputs and roll back only owned
files on ordinary failure. Failure/retry and competing-file preservation are
tested; multi-path atomicity across power loss is not claimed.

The earlier bilingual export has 10,371 rows: 10,172 historical, 197 additional
UI and two fixed names. CSV/XLSX text and address roundtrips matched all rows,
without formulas or macros. Two keyboard rows retain explicit raw font-code
markers. The workbook is still tied to the earlier 7105161a ROM, so it is not
the current diagnostic's final dialogue book.

Two fresh complete builds reproduce the current ROM/BPS byte-for-byte, with
exact BPS reapplication. A bounded reference audit checks 69 relocated
PC-relative loads, 23 original hook relocations, 23 relative resources,
22 signed map references, the new dialogue entry/trampoline/literals and
the description-length call/literals. This is not complete computed-reference
or clean public-source/package closure.

## Frozen performance on the current ROM

Each route was repeated five times under the frozen sampling rules.
Every unresolved display-observation count is zero.

| Route | Observations | P99 frames | Frozen target | Result |
| --- | ---: | ---: | ---: | --- |
| Item | 1,560 | 8 | 8 | pass |
| Monster | 1,420 | 8 | 8 | pass |
| Shop buy | 1,050 | 7 | 7 | pass |
| Shop sell | 1,080 | 8 | 8 | pass |
| Costume | 2,000 | 8 | 7 | **fail** |
| Character | 220 | 17 | 17 | pass |

Profiling identifies the small-font tile cache as the main costume cost.
Skipping live-tile checks changes pixels and is invalid. The tested ARM
scanner preserves pixels but is slower, so it is excluded. Metadata caches
lack complete writer/invalidation proof and are also excluded. No threshold,
cadence, sample selection or display-correctness rule was changed.

## Remaining release gates

All six SELECT_JOB alias pairs have controlled native-menu A/B/A, reentry and
same-ROM state-resume evidence on the preceding guarded diagnostic. The normal
Japanese selector exposes indices 0..3 while this substate needs index 4;
natural reachability remains unproved. ARTE variants have native-menu and
EEPROM-resume evidence with an explicit learned-skill fixture. These fixtures
do not prove natural unlocking or complete shared-context closure.

Required consumer/context closure, computed-reference ownership, costume
performance, complete final-hash regressions, final dialogue/state artifacts,
hardware and public source/package audit remain open. Earlier v1.0 hardware
evidence is not transferred to this ROM. Diagnostic builds cannot mark their
output release eligible.
