"""Bounded native glyph compression; execute real Thumb-1 with guard pages."""
import sys
from pathlib import Path
import unittest
import struct

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from strict_unit_codec import (build_book, fit_book, code_table, units, encode, decode,
                               factor_variants, fit_parts_book, encode_parts, decode_parts)
from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
    UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)


class UnitThumbDecoder:
    def __init__(self, bundle=False):
        self.code = bytes(Ks(KS_ARCH_ARM, KS_MODE_THUMB).asm(
            (ROOT/('asm/strict_unit_bundle_decode.s' if bundle else 'asm/strict_unit_decode.s'))
                .read_text(encoding='utf-8'), addr=0x100000)[0])
        disasm = list(Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(self.code, 0x100000))
        if sum(i.size for i in disasm) != len(self.code) or any(i.size != 2 for i in disasm):
            raise ValueError('Decoder must use Thumb-1 16-bit instructions only')
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        for address in (0x100000,0x200000,0x300000,0x500000,0x600000):
            self.uc.mem_map(address,0x1000)
        self.uc.mem_map(0x400000, 0x10000)
        self.uc.mem_write(0x100000,self.code)
        self.count=0
        def on_code(uc,address,size,_):
            if address==0x600000:
                uc.emu_stop()
            else:
                self.count+=1
                if self.count>200000:
                    raise AssertionError('Instruction ceiling')
        self.uc.hook_add(UC_HOOK_CODE,on_code)

    def run(self, stream, book, capacity, *, book_size=None, parts=1, selection=1):
        if len(stream)>0x1000 or not 0<=capacity<=0xf00 or not 0<len(book)<=0x10000:
            raise ValueError('Fixture extent')
        uc=self.uc
        src,dst,ptr,stack=0x201000-len(stream),0x301000-capacity,0x410000-len(book),0x500f00
        uc.mem_write(src,stream)
        uc.mem_write(dst-16,b'\xa5'*(capacity+16))
        uc.mem_write(ptr,book)
        uc.mem_write(stack,struct.pack('<IIII',ptr,len(book) if book_size is None else book_size,parts,selection))
        uc.reg_write(UC_ARM_REG_R0,src);uc.reg_write(UC_ARM_REG_R1,len(stream))
        uc.reg_write(UC_ARM_REG_R2,dst);uc.reg_write(UC_ARM_REG_R3,capacity)
        for reg in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7):
            uc.reg_write(reg,0x12345678)
        uc.reg_write(UC_ARM_REG_SP,stack);uc.reg_write(UC_ARM_REG_LR,0x600001)
        self.count=0
        uc.emu_start(0x100001,0x600002,count=200010)
        if uc.reg_read(UC_ARM_REG_SP)!=stack or uc.reg_read(UC_ARM_REG_PC)&~1!=0x600000:
            raise AssertionError('Return/stack ABI violated')
        if any(uc.reg_read(reg)!=0x12345678 for reg in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7)):
            raise AssertionError('Callee-saved register changed')
        if bytes(uc.mem_read(dst-16,16))!=b'\xa5'*16:
            raise AssertionError('Output prefix guard changed')
        return uc.reg_read(UC_ARM_REG_R0),bytes(uc.mem_read(dst,capacity)),uc.reg_read(UC_ARM_REG_R1),self.count


class UnitCodecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raws=[b'\x7f\x01\x01\x7f\x01\x02', b'\x7f\x01\x01A', b'AB', b'']
        cls.book=build_book(cls.raws,'compact')
        cls.thumb=UnitThumbDecoder()

    def test_roundtrip_and_slot_suffix(self):
        for raw in self.raws:
            stream=encode(raw,'compact',self.book)
            self.assertEqual(decode(stream,self.book,len(raw)+1),(raw+b'\0',len(stream)))
            for suffix in (b'',b'\xff\x00\x01'):
                written,out,used,_=self.thumb.run(stream+suffix,self.book,len(raw)+1)
                self.assertEqual((written,out,used),(len(raw)+1,raw+b'\0',len(stream)))
                self.assertEqual(decode(stream+suffix,self.book,len(raw)+1,allow_suffix=True),(raw+b'\0',len(stream)))

    def test_guards_malformed_tree_truncation_and_capacity(self):
        stream=encode(self.raws[0],'compact',self.book)
        for data,cap in ((b'',100),(stream[:-1],100),(stream,len(self.raws[0])),(stream,0)):
            with self.assertRaises(ValueError):decode(data,self.book,cap)
            self.assertEqual(self.thumb.run(data,self.book,cap)[0],0)
        for booksize in (0,27,len(self.book)-1,len(self.book)+1):
            self.assertEqual(self.thumb.run(stream,self.book,100,book_size=booksize)[0],0)
        # Every root edge is outside the supplied tree; no out-of-range read.
        bad=bytearray(self.book);bad[4:8]=b'\xff\x7f\xff\x7f'
        with self.assertRaises(ValueError):code_table(bytes(bad))
        self.assertEqual(self.thumb.run(stream,bytes(bad),100)[0],0)
        # Cyclic trees must terminate on bounded input exhaustion, not spin.
        bad[4:8]=b'\0'*4
        with self.assertRaises(ValueError):code_table(bytes(bad))
        self.assertEqual(self.thumb.run(stream,bytes(bad),100)[0],0)

    def test_nonzero_padding_and_strict_trailing(self):
        for raw in self.raws:
            stream=encode(raw,'compact',self.book)
            bits=sum(code_table(self.book)[g][1] for g in units(raw,'compact')+[b''])
            if bits%8:
                bad=stream[:-1]+bytes([stream[-1]|1])
                with self.assertRaisesRegex(ValueError,'padding'):decode(bad,self.book,100)
                self.assertEqual(self.thumb.run(bad,self.book,100)[0],0)
            with self.assertRaisesRegex(ValueError,'Trailing'):decode(stream+b'\x00',self.book,100)

    def test_units_preserve_native_bytes_and_dictionary_is_glyph_only(self):
        for raw,kind in [(b'\x81\x40\x9f\xffA\xe0\x7f','full_text'),(self.raws[0],'compact')]:
            self.assertEqual(b''.join(units(raw,kind)),raw)
        self.assertEqual(units(b'\x80\x7f\x9f\xff\xe0\xfd','full_text'),
                         [b'\x80\x7f',b'\x9f\xff',b'\xe0\xfd'])
        with self.assertRaises(ValueError):units(b'\xe0','full_text')
        for raw in (b'\x7f',b'\x7f\x01',b'\x7f\x20\x01',b'\x00'):
            with self.assertRaises(ValueError):units(raw,'compact')
        self.assertTrue(all(len(k)<=3 for k in code_table(self.book)))
        with self.assertRaises(TypeError):code_table(self.book)[b'bad']=(0,1)

    def test_fit_is_deterministic_and_reports_unsolved_slot(self):
        a,report=fit_book(self.raws,'compact',[4,4,4,1])
        self.assertEqual(a,fit_book(self.raws,'compact',[4,4,4,1])[0])
        self.assertEqual(report['best_overflow_count'],0)
        _,bad=fit_book([b'ABCDEFGHIJKLMNOPQRSTUVWXYZ'],'compact',[1],max_attempts=3)
        self.assertEqual(bad['best_overflow_count'],1)

    def test_inline_variants_preserve_both_outputs_on_thumb(self):
        thumb=UnitThumbDecoder(bundle=True)
        for pair in ([b'ABXDE',b'ABYYDE'],[b'ABC',b'XYZ'],[b'PREFIX',b'PREFIXTAIL']):
            parts=factor_variants(pair,'compact')
            book,fit=fit_parts_book([parts],'compact',[16])
            stream=encode_parts(parts,'compact',book)
            for raw,selection in zip(pair,(11,13)):
                expected=raw+b'\0'
                self.assertEqual(decode_parts(stream,book,len(expected),4,selection),(expected,len(stream)))
                written,out,used,_=thumb.run(stream+b'\xff',book,len(expected),parts=4,selection=selection)
                self.assertEqual((written,out,used),(len(expected),expected,len(stream)))
                self.assertEqual(thumb.run(stream,book,len(raw),parts=4,selection=selection)[0],0)
            for count,mask in ((0,1),(2,1),(4,0),(4,16),(1,2)):
                self.assertEqual(thumb.run(stream,book,100,parts=count,selection=mask)[0],0)
        for raw in self.raws:
            stream=encode(raw,'compact',self.book)
            written,out,used,_=thumb.run(stream,self.book,len(raw)+1)
            self.assertEqual((written,out,used),(len(raw)+1,raw+b'\0',len(stream)))


if __name__=='__main__':unittest.main()
