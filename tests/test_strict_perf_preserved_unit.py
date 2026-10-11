"""The fast-header experiment must not re-enter the final stage4 write plan."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from strict_packed_tree import assemble_decoder
from strict_perf_stage4_minimal import OWNERS,UNIT_START,UNIT_END,preserved_unit


class PreservedUnitTests(unittest.TestCase):
    def setUp(self):
        code=assemble_decoder(0x08000000+UNIT_START)
        self.assertEqual(len(code),UNIT_END-UNIT_START)
        self.image=bytearray(UNIT_END)
        self.image[UNIT_START:UNIT_END]=code
        self.part=dict(new=UNIT_START,size=len(code))

    def test_original_assembled_decoder_is_preserved_and_not_a_perf_writer(self):
        result=preserved_unit(self.image,self.part)
        self.assertEqual(result['size'],326)
        self.assertEqual(len(OWNERS),5)
        self.assertTrue(all(end<=UNIT_START or start>=UNIT_END for _,start,end,_ in OWNERS))

    def test_moved_or_shortened_decoder_is_rejected(self):
        for changed in (dict(self.part,new=UNIT_START+2),dict(self.part,size=324)):
            with self.subTest(part=changed),self.assertRaises(ValueError):
                preserved_unit(self.image,changed)

    def test_changed_instruction_or_truncated_image_is_rejected(self):
        self.image[UNIT_START]^=1
        with self.assertRaises(ValueError):preserved_unit(self.image,self.part)
        with self.assertRaises(ValueError):preserved_unit(bytes(UNIT_START),self.part)


if __name__=='__main__':unittest.main()
