# Boot notice local test, 2026-09-23

Base SHA256: 6ce5726f7621af335c7042f4f6481ed98c3b6dc53046e7a9412f22ae984f3070
Target SHA256: d3c4b127cde5b3f0d29970369a6f54c02560e4e591dfc42deffbabc0c0fe2209

Only existing write is the aligned main function pointer at ROM 0x100, from 0x08007401 to 0x08C90001. All bytes outside that four-byte field in the prior 0xC90000-byte image are identical. Thumb code begins at newly appended 0xC90000; 240x160 RGB555 pixels at 0xC91000. No old data moves. Source screen is the user-provided native PNG, identical to the supplied Narikiri3 ROM's actual frame 120.

Startup at 0xC0 has initialized IRQ and system stacks before indirect BX through 0x100. Wrapper saves r0-r7/LR, does not touch high registers or save memory, saves DISPCNT and IME, uses mode 3, waits for release/press/release, clears VRAM and restores display/interrupt state, SP and LR. r3 is the branch scratch on return; original main 0x7400 calls 0x240 whose r3 is unconditionally initialized at 0x24C before use. Original initialization clears RAM/VRAM itself. Thumb instructions verified by the existing assembler/disassembler guard. Header entry/checksum remain unchanged.

mGBA and VBA-M libretro cores passed all ten GBA button routes, boot-held input handling, identical notice pixels, unchanged resource 9/16 in live VRAM, and visual existing-save world map load. Japanese BPS roundtrip and repeated build are identical. No natural full playthrough/hardware claim. VBA-M diagnostic required frontend logging and controller port setup; initial missing-controller failures are retained under private_validation/boot-notice-20260923. Product bytes did not change to work around that harness issue.

Private evidence: private_validation/boot-notice-20260923/{product-a,mgba-buttons,vbam-buttons-logged}. Local delivery only; no release update.
