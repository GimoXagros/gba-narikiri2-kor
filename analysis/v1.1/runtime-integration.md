# v1.1 runtime integration checkpoint

Status: **INTEGRATED_DIAGNOSTIC__PERFORMANCE_NOT_MET**. This record is not a
release approval. No v1.1 release, tag or remote update has been performed.

The baseline is local commit `6caa05608d65d565181474c7e29e6768df07d6a0`.
The integrated diagnostic is exactly 8,388,608 bytes with SHA-256
`7105161a1d81c8e445265163c786880d66a79dacfb1f214e358313ef6b6c5916`.
The earlier integrated baseline was `dc14db5d22f43657d61cd25f9fb672fa122a81b292f7cdf15a869cfa20fa599e`.

## Implemented

- Original storage and pointer values for 10,172 historical bindings and
  9,246 original stream starts; separately identified 197 UI bindings.
- Packed glyph dictionary v2, exact bounded stream lookup, caller-owned
  decoding, event allocation, default name and persistent actor adapters.
- Six static menu tables and the bounded thirteen-command runtime table
  decode into a menu-owned buffer with explicit release.
- Lossless full-font compression, compact font derivation, and in-cartridge
  placement of the adopted title, notice, credits and map resources.
- A Thumb-1 full-font compositor uses nibble lookup to preserve native pixels,
  neighboring pixels and background colors. It occupies 328 bytes of the
  verified retired small-font suffix and changes two original callsites.
  It adds no persistent RAM and preserves unusual background-byte behavior
  through the original routine. Pixel/ABI differential: 122,880 cases pass.
- Restoration of the omitted map table references that caused palette
  corruption in an earlier diagnostic. The aligned changed-word census now
  classifies all 865 address-shaped values. This does not establish complete
  unaligned/relative reference or consumer coverage.

## Evidence and limits

The linked decoder executes all 10,172 historical and 197 additional binding
cases with exact output and intact guards in a CPU harness. Caller context
supplied by that corpus is not proof of natural alias reachability.

The 222-test baseline remains intact. The later source suite passed 337 tests
with no failures or skips. The private linked-menu CPU suite passed two cases covering all
six static tables, dynamic entries and native-RAM passthrough.

Offscreen game evidence includes the Pub Rose dialogue, ordinary menu
routes, default and mixed-name new-game saves, two process-cold loads and
resaving. Two party records (120 bytes) and inventory quantities (79 bytes)
match before saving and after both cold loads. These save checks are bound
to the dc14 baseline; final-candidate repetition remains required. Legacy and
newly created suspend data resume and are consumed. The full default new-game
controller route (38,091 frames) reproduces the same save and final pixels.
Same-ROM VBA v10 state conversion has exact inverse checks
and two separate offscreen resume trials; desktop UI and hardware are not
claimed.

SGM publication now stages both the state and its provenance file before
publication, and rolls back only owned files on ordinary failure. Injected
second-write failure, retry and competing-output preservation pass. This is
not an assertion of two-path atomicity across abrupt power/process loss.

The private bilingual export directly decodes 10,371 final-ROM bindings
(10,172 historical, 197 additional UI and two fixed names). CSV roundtrips
and XLSX text/address cells match all rows; the workbook contains no formulas
or macros. Export publication failure/retry and foreign-file preservation
are tested. Two keyboard rows retain explicit raw font-code markers; their
Unicode appearance is not inferred. This is a candidate export, not a new
translation review or a final release artifact.

A naturally entered battle and command submenu, without RAM modification,
has a pixel-identical final screen and identical 180-byte party records to
the adopted Korean baseline. A different historical battle input replay
failed to reach battle and is explicitly excluded from that evidence.

`build_strict_8m_diagnostic.py` builds text, runtime components and the
integrated diagnostic from explicit local inputs. Two output trees reproduced
the dc14 baseline. Two fresh complete source builds with the fast compositor
match the independently built 7105 candidate, with exact BPS roundtrip.
Current diagnostic BPS SHA-256:
`b4e0fcece9bce5d0f5b4e1e33d3beaa96c472eea13225542b61e809e5c13ccba`.
This is not a clean public-history or final-package approval.

## Remaining gates

The fast compositor yields frozen-route P99 values of item 8, monster 8,
shop buy 7, shop sell 8, costume 8 and character 17. Costume still misses its
frozen 7-frame baseline target, so the overall performance gate is not met.
All six paths have zero unresolved display observations. A separate faster
font decoder and proposed caches are not enabled in the integrated diagnostic.

All six SELECT_JOB alias pairs have controlled game-context menu evidence:
after natural battle entry, one explicit WRAM state intervention reaches the
original menu, and controller inputs select all 18 alternating indices.
All 201 live strings match a frozen independent oracle on every entry.
This fixture does not prove natural reachability of that battle substate.

A bounded reference audit verifies 69 relocated PC-relative loads, 23 hooks,
23 relative resources and 22 signed map references. These checks pass, but
dynamic computed-pointer and full consumer closure remain open. The ARTE
accessor's out-of-range index handling also remains under review; valid
indices and the two shared variants are covered by the existing CPU tests.

Required shared-variant game contexts, complete consumer/reference closure,
final six-path performance, final-ROM save/state regression, hardware
evidence, private final dialogue exports, and the public source/package
audit remain open. Earlier v1.0 hardware evidence is not transferred to this
new ROM hash. Diagnostic tools cannot mark their output release eligible.
