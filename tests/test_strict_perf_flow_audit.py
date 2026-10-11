"""Fail-closed code/data ownership guards, without private ROM fixtures."""
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import strict_perf_flow_audit as audit


class FlowAuditTests(unittest.TestCase):
    def triple(self):
        return bytearray(struct.pack('<4H3I', 0xA301, 0xCB61, 0x4770, 0xDE00,
                                     283, 0x080B0000, 9312))

    def inspect_triple(self, data, end=20):
        with patch.dict(audit.OWNERS, {'owned': (0, end, [0])}, clear=True):
            return audit.inventory(data)

    def compact(self):
        data=bytearray(0xB9D3C)
        struct.pack_into('<4H', data, 0xB9C78, 0x201D, 0xA326, 0xCB60, 0x4770)
        struct.pack_into('<2I', data, 0xB9D14, 0x080B0000, 3696)
        return data

    def inspect_compact(self, data, end=0xB9D3C, entries=None):
        with patch.dict(audit.OWNERS, {'owned': (0xB9C78, end, entries or [0xB9C78])}, clear=True):
            return audit.inventory(data)

    def test_three_word_profile_exact_end(self):
        row=self.inspect_triple(self.triple())[0]
        self.assertEqual(row['adr_data'][0]['span_bytes'], 12)
        self.assertEqual(row['instruction_count'], 3)

    def test_three_word_profile_crossing_end_rejected(self):
        with self.assertRaises(ValueError):
            self.inspect_triple(self.triple(), end=16)

    def test_unknown_ldm_registers_rejected(self):
        for value in (0xCB01, 0xCA61, 0xCBFF):
            data=self.triple();struct.pack_into('<H', data, 2, value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.inspect_triple(data)

    def test_adr_unsupported_register_rejected(self):
        data=self.triple();struct.pack_into('<H', data, 0, 0xA201)
        with self.assertRaises(ValueError):self.inspect_triple(data)

    def test_pc_literal_crossing_owner_rejected(self):
        data=struct.pack('<4H',0x4801,0x4770,0,0)
        with patch.dict(audit.OWNERS, {'unit':(0,8,[0])}, clear=True):
            with self.assertRaises(ValueError):audit.inventory(data)

    def test_direct_branch_outside_owner_rejected(self):
        data=struct.pack('<2H',0xE010,0x4770)
        with patch.dict(audit.OWNERS, {'unit':(0,4,[0])}, clear=True):
            with self.assertRaises(ValueError):audit.inventory(data)

    def test_executable_literal_overlap_rejected(self):
        data=struct.pack('<4H',0x4800,0x46C0,0x4770,0)
        with patch.dict(audit.OWNERS, {'unit':(0,8,[0])}, clear=True):
            with self.assertRaises(ValueError):audit.inventory(data)

    def test_compact_two_words_immediate_capacity(self):
        row=self.inspect_compact(self.compact())[0]
        self.assertEqual(row['adr_data'][0]['span_bytes'], 8)

    def test_compact_capacity_cannot_change(self):
        data=self.compact();struct.pack_into('<H',data,0xB9C78,0x201C)
        with self.assertRaises(ValueError):self.inspect_compact(data)

    def test_compact_cannot_read_third_word(self):
        data=self.compact();struct.pack_into('<H',data,0xB9C7C,0xCB61)
        with self.assertRaises(ValueError):self.inspect_compact(data)

    def test_compact_profile_crossing_end(self):
        with self.assertRaises(ValueError):self.inspect_compact(self.compact(),end=0xB9D18)

    def test_compact_branch_bypassing_capacity_rejected(self):
        data=self.compact();struct.pack_into('<H',data,0xB9C80,0xE7FB)
        with self.assertRaises(ValueError):
            self.inspect_compact(data,entries=[0xB9C78,0xB9C80])

    def test_branch_to_ldm_when_adr_is_unreachable(self):
        data=self.compact();struct.pack_into('<H',data,0xB9C80,0xE7FC)
        with self.assertRaises(ValueError):
            self.inspect_compact(data,entries=[0xB9C80])

    def test_unrecognized_two_word_profile_rejected(self):
        data=self.triple();struct.pack_into('<H',data,2,0xCB60)
        with self.assertRaises(ValueError):self.inspect_triple(data)


if __name__=='__main__':unittest.main()
