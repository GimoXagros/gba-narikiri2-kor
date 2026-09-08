# Text audit

Frozen review corpus has 8038 ledger records, of which D00549 is a pointer table, leaving 8037 actual Japanese body strings. The existing authored 285 full-text corrections (325 bindings), 16 compact corrections, and two BETA3-specific dialogue decisions are reproduced. Ledger hashes are validated by the frozen build; names and game prose are unchanged in v0.9c. No automated prose replacement was performed.

Pointer/text termination checks cover the final ROM's typed catalogue. Nine broad Japanese-range flags were inspected: all are U+30FB middle-dot punctuation (eight unique text IDs plus an alias), not residual kana words. Do not report these nine as untranslated dialogue. Existing terminology/controls/numbers/layout assertions pass; actual list/name/detail consumers were re-executed.

The previous individual Japanese comparison is retained with its exceptions and exact hashes. This audit does not claim a second independent literary review of all 8037 dialogues, a new full playthrough, or all event branches. Display matrix coverage is not proof of natural acquisition. No new confirmed mistranslation was found in the reviewed scope.

Correction ND2-V09C-20260909-003: 2077 counts first-stage absolute pointer writers (including full-width names/body/UI); 1227 counts compact name fields. The historical verification file is unchanged; the candidate manifest and claim audit use accurate labels.
