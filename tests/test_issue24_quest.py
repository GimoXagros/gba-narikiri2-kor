"""Guard the two native quest quote readers and the ARMv4T menu scanner."""
import struct
import sys
import unittest
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tools"))
import issue_menu_v4t as menu
from issue24_quest import QUOTE_LITERAL, QUOTE_POINTER, QUOTE_SLOT, restore_quest_quotes


class QuestReaderTests(unittest.TestCase):
    def setUp(self):
        self.jp = bytearray(0x800000)
        for address, value in ((0x9A7D4, "22480068"), (0x9A838, "09480068"),
                               (QUOTE_LITERAL, "a8217f08"), (QUOTE_POINTER, "d4d03408"),
                               (QUOTE_SLOT, "81778178")):
            self.jp[address:address+4] = bytes.fromhex(value)
        self.baseline = self.jp.copy()
        self.baseline[QUOTE_SLOT:QUOTE_SLOT+4] = bytes.fromhex("a4a51078")

    def test_native_pair_slices_both_resolve_to_inline_literal(self):
        out, manifest = restore_quest_quotes(self.jp, self.baseline)
        for pc in (0x9A7D4, 0x9A838):
            opcode, nop = struct.unpack_from("<HH", out, pc)
            self.assertEqual((opcode >> 8, nop), (0xA0, 0x46C0))
            self.assertEqual(((pc+4) & ~3) + (opcode & 255)*4, QUOTE_LITERAL)
        self.assertEqual(out[QUOTE_LITERAL:QUOTE_LITERAL+4], "『』".encode("cp932"))
        restored = bytearray(out)
        for record in manifest:
            a, b = record["offset"], record["end"]
            restored[a:b] = self.baseline[a:b]
        self.assertEqual(restored, self.baseline)

    def test_unexpected_binding_or_instruction_is_rejected(self):
        for address in (QUOTE_POINTER, QUOTE_SLOT, QUOTE_LITERAL, 0x9A7D4, 0x9A83A):
            damaged = self.baseline.copy()
            damaged[address] ^= 1
            with self.subTest(address=address), self.assertRaises(ValueError):
                restore_quest_quotes(self.jp, damaged)


class Armv4tMenuTests(unittest.TestCase):
    def test_both_bitmap_address_calculations_use_format_two_add(self):
        base = bytearray(0x800000)
        for offset in menu.ADDS:
            base[offset:offset+2] = bytes.fromhex("2344")
        region_hash = sha256(base[menu.SCAN_START:menu.SCAN_START+menu.SCAN_SIZE]).hexdigest()
        with patch.object(menu, "SCAN_SHA256", region_hash):
            out, records = menu.fix_menu_scan(base)
            self.assertEqual(len(records), 2)
            for offset in menu.ADDS:
                instruction, = struct.unpack_from("<H", out, offset)
                self.assertEqual((instruction >> 9, instruction & 7,
                                  (instruction >> 3) & 7, (instruction >> 6) & 7),
                                 (0xC, 3, 3, 4))
            with self.assertRaises(ValueError):
                menu.fix_menu_scan(out)
