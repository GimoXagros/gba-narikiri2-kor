"""ABI and adversarial checks of the assembled decoder, not game coverage."""
import random
import struct
import unittest

from test_strict_unit_codec import UnitThumbDecoder
from strict_unit_codec import build_book, encode_parts, decode_parts, factor_variants
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
    UC_ARM_REG_R3, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6,
    UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10,
    UC_ARM_REG_R11, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)


class ContractHarness(UnitThumbDecoder):
    def __init__(self):
        super().__init__(bundle=True)
        self.writes = []
        self.uc.hook_add(UC_HOOK_MEM_WRITE,
            lambda uc, access, address, size, value, data: self.writes.append((address, size)))

    def prepare(self, stream, book, capacity, *, src=0x200103, dst=0x300103,
                ptr=0x400102, stack=0x500f00, parts=1, selection=1,
                input_size=None, book_size=None):
        uc = self.uc
        # None permits unmapped invalid pointers in preflight rejection tests.
        if stream is not None:
            uc.mem_write(src, stream)
        if book is not None:
            uc.mem_write(ptr, book)
        uc.mem_write(stack, struct.pack('<IIII', ptr,
            len(book) if book_size is None else book_size, parts, selection))
        args = (src, len(stream) if input_size is None else input_size, dst, capacity)
        for reg, value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3), args):
            uc.reg_write(reg,value)
        for reg in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,
                    UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11):
            uc.reg_write(reg,0x12345678)
        uc.reg_write(UC_ARM_REG_SP,stack)
        uc.reg_write(UC_ARM_REG_LR,0x600001)
        self.count=0
        self.writes.clear()
        return args

    def execute(self, start=0x100001, stack=0x500f00):
        self.uc.emu_start(start,0x600002,count=200010)
        if self.uc.reg_read(UC_ARM_REG_PC)&~1 != 0x600000:
            raise AssertionError('Decoder did not return within instruction bound')
        if self.uc.reg_read(UC_ARM_REG_SP)!=stack:
            raise AssertionError('Stack not restored')
        for reg in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,
                    UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11):
            if self.uc.reg_read(reg)!=0x12345678:
                raise AssertionError('Callee-saved register changed')
        return self.uc.reg_read(UC_ARM_REG_R0), self.uc.reg_read(UC_ARM_REG_R1)


class DecoderContractTests(unittest.TestCase):
    def setUp(self):
        self.vm=ContractHarness()
        self.raw=b'ABCDEFGABC'
        self.book=build_book([self.raw,b''],'compact')
        self.stream=encode_parts([self.raw],'compact',self.book)

    def rejected(self, **kwargs):
        options=dict(stream=self.stream,book=self.book,capacity=64)
        options.update(kwargs)
        self.vm.prepare(**options)
        self.assertEqual(self.vm.execute(),(0,0))
        # Argument rejection may write only callee-owned stack locals.
        self.assertTrue(all(0x500ed0<=a and a+n<=0x500f00 for a,n in self.vm.writes))

    def test_misaligned_book_rejected_but_byte_input_output_and_halfword_book_valid(self):
        self.rejected(ptr=0x400103)
        self.vm.prepare(self.stream,self.book,64)
        self.assertEqual(self.vm.execute(),(len(self.raw)+1,len(self.stream)))
        self.assertEqual(bytes(self.vm.uc.mem_read(0x300103,len(self.raw)+1)),self.raw+b'\0')

    def test_unsigned_range_wrap_and_empty_extents_rejected_without_dereference(self):
        self.rejected(stream=None,src=0xfffffff0,input_size=32)
        self.rejected(dst=0xfffffff0,capacity=32)
        self.rejected(book=None,ptr=0xfffffff0,book_size=32)
        self.rejected(stream=None,src=0xfffffff0,input_size=0)
        self.rejected(dst=0xffffffff,capacity=0)

    def test_overlap_in_both_directions_and_stack_frame_rejected(self):
        for dst in (0x200102,0x200103,0x200104):
            self.rejected(dst=dst)
        for dst in (0x400101,0x400102,0x400103):
            self.rejected(dst=dst)
        for dst,cap in ((0x500ecc,8),(0x500ed0,1),(0x500eff,1),(0x500f0f,1)):
            self.rejected(dst=dst,capacity=cap)

    def test_missing_and_unsupported_variant_context_rejected(self):
        for parts in (0,1,2,3,4,5,0xffffffff):
            for selection in (0,1,2,3,7,10,11,12,13,14,15,16,0xffffffff):
                if (parts,selection) in ((1,1),(4,11),(4,13)):
                    continue
                self.rejected(parts=parts,selection=selection)

    def test_fixed_seed_differential_fuzz_and_guarded_capacity(self):
        rng=random.Random(0x6CAA056)
        for case in range(512):
            alphabet=[bytes([x]) for x in b'ABCDE %hs\n']+[b'\x7f\x01\x01',b'\x7f\x01\x02']
            raws=[b''.join(rng.choice(alphabet) for _ in range(rng.randrange(80))) for _ in range(2)]
            parts=factor_variants(raws if raws[0]!=raws[1] else raws[:1],'compact')
            book=build_book(parts,'compact')
            stream=encode_parts(parts,'compact',book)
            selection=1 if len(parts)==1 else rng.choice((11,13))
            raw=raws[0] if selection in (1,11) else raws[1]
            data=bytearray(stream)
            if case%4==1:
                data[rng.randrange(len(data))]^=1<<rng.randrange(8)
            if case%4==2:
                data=data[:rng.randrange(len(data))]
            capacity=max(1,len(raw)+1-(case%4==3))
            try:
                expected,used=decode_parts(bytes(data),book,capacity,len(parts),selection,allow_suffix=True)
            except ValueError:
                expected,used=None,0
            self.vm.uc.mem_write(0x3000f0,b'\xa5'*0x300)
            self.vm.prepare(bytes(data),book,capacity,parts=len(parts),selection=selection)
            written,actual_used=self.vm.execute()
            self.assertEqual(bytes(self.vm.uc.mem_read(0x300102,1)),b'\xa5')
            self.assertEqual(bytes(self.vm.uc.mem_read(0x300103+capacity,1)),b'\xa5')
            if expected is None:
                self.assertEqual((written,actual_used),(0,0),case)
            else:
                self.assertEqual((written,actual_used),(len(expected),used),case)
                self.assertEqual(bytes(self.vm.uc.mem_read(0x300103,written)),expected,case)

    def test_interrupted_decode_resumes_after_nested_decode_with_separate_owned_buffers(self):
        vm=self.vm
        vm.prepare(self.stream,self.book,64)
        stopped=[]
        def pause(uc,address,size,data):
            if vm.count>=80 and address!=0x600000:
                stopped.append(address)
                uc.emu_stop()
        handle=vm.uc.hook_add(UC_HOOK_CODE,pause)
        vm.uc.emu_start(0x100001,0x600002,count=200010)
        vm.uc.hook_del(handle)
        self.assertTrue(stopped)
        outer=vm.uc.context_save()
        before=bytes(vm.uc.mem_read(0x500ed0,64))
        # A genuine second invocation uses lower stack and disjoint output;
        # CPU context save/restore models suspension, not an IRQ-safety claim.
        vm.prepare(self.stream,self.book,64,dst=0x300203,stack=0x500d00)
        self.assertEqual(vm.execute(stack=0x500d00),(len(self.raw)+1,len(self.stream)))
        self.assertEqual(bytes(vm.uc.mem_read(0x500ed0,64)),before)
        vm.uc.context_restore(outer)
        vm.count=0
        self.assertEqual(vm.execute(start=stopped[0]|1),(len(self.raw)+1,len(self.stream)))
        for dst in (0x300103,0x300203):
            self.assertEqual(bytes(vm.uc.mem_read(dst,len(self.raw)+1)),self.raw+b'\0')


if __name__=='__main__':
    unittest.main()
