"""Address shapes require a complete, source-bound payload owner."""
import struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from strict_reference_audit import extra_classification
from strict_menu_owned import descriptor_bytes

class ReferenceAuditTests(unittest.TestCase):
    def test_sprite_word_crossing_owner_end_stays_open(self):
        data=bytes(1024);writer=dict(name='asset:map_resource_9',start=256,end=260)
        self.assertEqual(extra_classification(data,data,data,[],256,writer)['kind'],'encoded_native_graphic_payload')
        self.assertIsNone(extra_classification(data,data,data,[],258,writer))

    def test_menu_length_shape_is_not_a_pointer_and_changed_descriptor_is_open(self):
        image=bytearray(1024);start=256;begin=start+268;blob=descriptor_bytes()
        image[begin:begin+len(blob)]=blob
        writer=dict(name='menu:owned_adapter',start=start,end=start+340)
        at=begin+12
        self.assertEqual(struct.unpack_from('<I',image,at)[0],0x088F00A4)
        got=extra_classification(image,image,image,[],at,writer)
        self.assertEqual((got['kind'],got['count'],got['native_bytes']),('menu_count_length_halfwords',164,2191))
        image[at]^=1
        self.assertIsNone(extra_classification(image,image,image,[],at,writer))

    def test_boot_instruction_shape_requires_exact_bytes(self):
        image=bytearray(1024);writer=dict(name='relocated:boot_notice_1bpp_wrapper',start=256,end=596)
        at=292;struct.pack_into('<I',image,at,0x09053402)
        self.assertEqual(extra_classification(image,image,image,[],at,writer)['kind'],'thumb_instruction_pair')
        image[at]^=1
        self.assertIsNone(extra_classification(image,image,image,[],at,writer))

if __name__=='__main__':unittest.main()
