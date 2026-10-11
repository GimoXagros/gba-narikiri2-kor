"""A pre-patch pointer-shaped observation must not masquerade as final bytes."""
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from strict_runtime_linker import Ledger,annotate_pointer_shapes
from strict_reference_audit import extra_classification
from strict_asset_fontrows8 import DECODER,DECODER_SOURCE,WRAPPER_14E0
from strict_asset_fontpages import _assemble


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

    def test_native_decoder_shape_requires_complete_exact_code(self):
        code=_assemble(DECODER_SOURCE,DECODER,WRAPPER_14E0-DECODER)
        self.assertEqual(len(code),128)
        source=bytearray(DECODER+len(code));source[DECODER:]=code
        writer=dict(name='asset:native_row_decoder',start=DECODER,end=len(source))
        def classify(image=source,owner=writer,at=DECODER+8):
            return extra_classification(b'',b'',image,[],at,owner)
        proof=classify()
        self.assertEqual(proof['kind'],'thumb_instruction_pair')
        self.assertEqual(proof['instructions'],'mov r7,r0; lsrs r2,r0,#3')
        # Preserve the address-shaped word while corrupting other owner code.
        changed=bytearray(source);changed[DECODER]^=1
        self.assertIsNone(classify(image=changed))
        changed=bytearray(source);changed[DECODER+8]^=1
        self.assertIsNone(classify(image=changed))
        self.assertIsNone(classify(owner=dict(writer,end=writer['end']-1)))
        self.assertIsNone(classify(owner=dict(writer,start=DECODER-4)))
        self.assertIsNone(classify(owner=dict(writer,name='asset:native_row_decoder_other')))
        self.assertIsNone(classify(at=DECODER+12))

    def test_native_decoder_owner_name_alone_is_not_payload_proof(self):
        source=bytearray(64);struct.pack_into('<I',source,16,0x08C24607)
        ledger=Ledger(bytes(source))
        ledger.put('asset:native_row_decoder',16,source[16:20],source[16:20],
                   stage=3,evidence='Owner-name-only negative fixture')
        row=annotate_pointer_shapes(ledger,bytes(source),[dict(at=16,value=0x08C24607)])[0]
        self.assertEqual(row['classification'],'unclassified_changed_reference')


if __name__=='__main__':unittest.main()
