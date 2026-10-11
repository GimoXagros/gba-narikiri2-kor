"""ROM-free structural checks for the bounded direct-dialogue diagnostic."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT if (ROOT / "tools/strict_owned_decode.py").exists() else ROOT.parent / "narikiri2-v09d-graphics-test"
sys.path.insert(0, str(SOURCE / "tools"))
sys.path.insert(0, str(ROOT / "tools"))
from strict_direct_dialogue import (ENTRY, TRAMPOLINE, TRAMPOLINE_CAPACITY,
                                    WRAPPER, WRAPPER_CAPACITY, assemble,
                                    diagnostic_patch)


class DirectDialogueTest(unittest.TestCase):
    @staticmethod
    def images():
        japanese = bytearray(0x800000)
        guarded = bytearray(0x800000)
        # The source guard needs equality, not a hard-coded expected prologue.
        japanese[ENTRY:ENTRY+20] = b"\x01" * 20
        guarded[ENTRY:ENTRY+20] = japanese[ENTRY:ENTRY+20]
        return japanese, guarded

    def test_adapter_fits_owned_slices(self):
        japanese, guarded = self.images()
        writes = assemble(japanese, guarded)
        self.assertEqual([offset for offset, _ in writes], [WRAPPER, TRAMPOLINE, ENTRY])
        self.assertLessEqual(len(writes[0][1]), WRAPPER_CAPACITY)
        self.assertLessEqual(len(writes[1][1]), TRAMPOLINE_CAPACITY)
        self.assertEqual(len(writes[2][1]), 16)
        self.assertTrue(all(len(payload) for _, payload in writes))

    def test_rejects_changed_entry_and_owners(self):
        japanese, guarded = self.images()
        guarded[ENTRY] ^= 1
        with self.assertRaisesRegex(ValueError, "prologue"):
            assemble(japanese, guarded)
        guarded[ENTRY] ^= 1
        guarded[WRAPPER] = 1
        with self.assertRaisesRegex(ValueError, "cleared retired font"):
            assemble(japanese, guarded)
        guarded[WRAPPER] = 0
        guarded[TRAMPOLINE] = 1
        with self.assertRaisesRegex(ValueError, "original free suffix"):
            assemble(japanese, guarded)

    def test_diagnostic_rejects_unbound_roms(self):
        japanese, guarded = self.images()
        with self.assertRaisesRegex(ValueError, "Exact Japanese"):
            diagnostic_patch(japanese, guarded)


if __name__ == "__main__":
    unittest.main()
