"""A pre-patch pointer-shaped observation must not masquerade as final bytes."""
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from strict_runtime_linker import Ledger,annotate_pointer_shapes


class ReferenceScanStageTest(unittest.TestCase):
    def test_superseded_shape_retains_observed_and_final_words(self):
        source=bytearray(64);struct.pack_into('<I',source,16,0x08C00000)
        ledger=Ledger(bytes(source))
        ledger.put('performance:code',16,source[16:20],bytes.fromhex('13461cde'),stage=3,evidence='Exact instruction write')
        row=annotate_pointer_shapes(ledger,bytes(source),[dict(at=16,value=0x08C00000)])[0]
        self.assertFalse(row['observation_is_current'])
        self.assertEqual(row['value'],0x08C00000)
        self.assertEqual(row['final_word'],0xDE1C4613)
        self.assertEqual(row['classification'],'superseded_scan_observation')
        self.assertIn('independent final-image scan',row['proof']['qualification'])
    def test_partial_writer_is_not_complete_reference_proof(self):
        source=bytearray(64);struct.pack_into('<I',source,16,0x08C00000)
        ledger=Ledger(bytes(source))
        ledger.put('partial',18,source[18:20],b'\0\0',stage=3,evidence='Two byte write')
        row=annotate_pointer_shapes(ledger,bytes(source),[dict(at=16,value=0x08C00000)])[0]
        self.assertEqual(row['classification'],'unclassified_superseded_observation')
    def test_current_observation_remains_explicit(self):
        source=bytearray(64);struct.pack_into('<I',source,16,0x08C00000)
        row=annotate_pointer_shapes(Ledger(bytes(source)),bytes(source),[dict(at=16,value=0x08C00000)])[0]
        self.assertTrue(row['observation_is_current'])
        self.assertEqual(row['final_word'],row['value'])
        self.assertEqual(row['classification'],'unclassified_changed_reference')


if __name__=='__main__':unittest.main()
