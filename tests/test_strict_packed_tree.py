"""Dictionary format change preserves stream codes and actual Thumb outputs."""
from pathlib import Path
import struct,sys,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from strict_packed_tree import pack_tree,unpack_tree,decoder_source
from strict_unit_codec import build_book,code_table,encode_parts,factor_variants
from test_strict_unit_codec import UnitThumbDecoder
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB


class PackedThumbDecoder(UnitThumbDecoder):
    def __init__(self):
        super().__init__(bundle=True)
        self.code=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(
            (ROOT/'asm/strict_unit_bundle_decode_v2.s').read_text(),addr=0x100000)[0])
        self.uc.mem_write(0x100000,self.code)


class PackedTreeTests(unittest.TestCase):
    def test_lossless_dictionary_and_unchanged_streams_both_modes(self):
        cpu=PackedThumbDecoder()
        for kind,raws in [('full_text',[b'\x81\x40@BABC',b'\xe0\xff',b'']),
                          ('compact',[b'\x7f\x01\x01A',b'\x7f\x1f\x1fB',b''])]:
            original=build_book(raws,kind);packed=pack_tree(original)
            self.assertEqual(unpack_tree(packed),original)
            self.assertEqual(len(packed),(len(original)+4)//2)
            for raw in raws:
                stream=encode_parts([raw],kind,original)
                n,out,used,_=cpu.run(stream,packed,len(raw)+1)
                self.assertEqual((n,out,used),(len(raw)+1,raw+b'\0',len(stream)))

    def test_inline_aliases_keep_original_part_bits_and_selectors(self):
        pair=[b'ABXDE',b'ABYYDE'];parts=factor_variants(pair,'compact')
        book=build_book(parts,'compact');packed=pack_tree(book)
        stream=encode_parts(parts,'compact',book);cpu=PackedThumbDecoder()
        for raw,mask in zip(pair,(11,13)):
            n,out,used,_=cpu.run(stream,packed,len(raw)+1,parts=4,selection=mask)
            self.assertEqual((n,out,used),(len(raw)+1,raw+b'\0',len(stream)))

    def test_versions_and_malformed_tree_cannot_be_silently_mixed(self):
        raw=b'ABC';old=build_book([raw],'compact');new=pack_tree(old);stream=encode_parts([raw],'compact',old)
        cpu=PackedThumbDecoder()
        self.assertEqual(cpu.run(stream,old,4)[0],0)
        self.assertEqual(UnitThumbDecoder(bundle=True).run(stream,new,4)[0],0)
        for book in (new[:-1],new[:2]+b'\0\0'+new[4:],new[:4]+b'\xff\xff\xff\xff'+new[8:]):
            with self.assertRaises(ValueError):unpack_tree(book)
            self.assertEqual(cpu.run(stream,book,4)[0],0)
        for data,capacity in ((stream[:-1],4),(stream,3),(stream,0)):
            self.assertEqual(cpu.run(data,new,capacity)[0],0)

    def test_derivation_keeps_v1_guard_logic_and_thumb1_instruction_widths(self):
        self.assertEqual((ROOT/'asm/strict_unit_bundle_decode_v2.s').read_text(),decoder_source())
        from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
        code=PackedThumbDecoder().code
        instructions=list(Cs(CS_ARCH_ARM,CS_MODE_THUMB).disasm(code,0x100000))
        self.assertEqual(sum(i.size for i in instructions),len(code))
        self.assertTrue(all(i.size==2 for i in instructions))


if __name__=='__main__':unittest.main()
