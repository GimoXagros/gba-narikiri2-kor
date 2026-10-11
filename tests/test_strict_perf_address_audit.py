"""Explicit RAM block consumer checks, independent of private ROM fixtures."""
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import strict_perf_address_audit as audit


class TileGlobalBlockTests(unittest.TestCase):
    def fixture(self):
        data=bytearray(struct.pack('<6HI',0xB5F0,0xB085,0x1C04,0x4801,0xC80E,0x4770,0x0300004C))
        row={'instructions':[{'address':hex(audit.BASE+x)} for x in range(0,12,2)],
             'direct_branches':[],
             'literals':[{'storage':hex(audit.BASE+12),'value':'0x300004c','sites':[hex(audit.BASE+6)]}]}
        return data,row

    def inspect(self,data,row,end=16):
        with patch.dict(audit.OWNERS,{'tile':(0,end,[0])},clear=True):
            return audit.tile_global_block(data,row)

    def test_exact_three_word_read(self):
        result=self.inspect(*self.fixture())
        self.assertEqual((result['source'],result['end_exclusive'],result['span_bytes']),
                         ('0x300004c','0x3000058',12))
        self.assertEqual(result['destinations'],['r1','r2','r3'])

    def test_extra_or_wrong_register_read_rejected(self):
        for value in (0xC81E,0xC80F,0xC806,0xC90E):
            data,row=self.fixture();struct.pack_into('<H',data,8,value)
            with self.subTest(value=value),self.assertRaises(ValueError):self.inspect(data,row)

    def test_wrong_setup_or_base_register_rejected(self):
        for at,value in ((0,0xB5E0),(2,0xB086),(4,0x1C0C),(6,0x4901)):
            data,row=self.fixture();struct.pack_into('<H',data,at,value)
            with self.subTest(at=at),self.assertRaises(ValueError):self.inspect(data,row)

    def test_adjacent_or_rom_source_rejected(self):
        for pointer in (0x03000048,0x03000050,0x08800000):
            data,row=self.fixture();struct.pack_into('<I',data,12,pointer)
            row['literals'][0]['value']=hex(pointer)
            with self.subTest(pointer=pointer),self.assertRaises(ValueError):self.inspect(data,row)

    def test_pointer_literal_crosses_owner(self):
        with self.assertRaises(ValueError):self.inspect(*self.fixture(),end=14)

    def test_branch_cannot_bypass_setup(self):
        for target in (2,4,6,8):
            data,row=self.fixture();row['direct_branches']=[{'target':hex(audit.BASE+target)}]
            with self.subTest(target=target),self.assertRaises(ValueError):self.inspect(data,row)

    def test_unreachable_setup_rejected(self):
        data,row=self.fixture();row['instructions']=row['instructions'][3:]
        with self.assertRaises(ValueError):self.inspect(data,row)

    def test_missing_or_forged_inventory_rejected(self):
        for mode in ('missing','wrong_value','missing_site'):
            data,row=self.fixture()
            if mode=='missing':row['literals']=[]
            elif mode=='wrong_value':row['literals'][0]['value']='0x3000050'
            else:row['literals'][0]['sites']=[]
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.inspect(data,row)

    def test_legacy_individual_loads_use_separate_literal_contract(self):
        data,row=self.fixture();struct.pack_into('<H',data,8,0x6800)
        self.assertIsNone(self.inspect(data,row))


if __name__=='__main__':unittest.main()
