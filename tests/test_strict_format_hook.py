"""Execute diagnostic entry, decoder, native trampoline and owned-buffer return.

The native allocator/consumer are explicit harness substitutes. Actual game
event evidence is separate; this suite does not certify their implementation.
"""
from pathlib import Path
import struct
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from strict_format_hook import assemble_format_hook,descriptor_blob,dialogue_veneer
from strict_unit_codec import build_book,encode
from strict_stream_lookup import pack_bounds,assemble_lookup
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE
from unicorn.arm_const import *


class FormatHookTests(unittest.TestCase):
    def run_hook(self, *, compressed=True, capacity=None, oom=False, packed=False):
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        u.mem_map(0x08000000,0x800000)
        u.mem_map(0x02000000,0x40000)
        u.mem_map(0x03000000,0x8000)
        raw=b'\x81\x40@B\x81\x41\x81\x49'
        book=build_book([raw],'full_text')
        stream=encode(raw,'full_text',book)
        source,descriptors,book_at=0x08349780,0x08200000,0x08400000
        hook,decoder=0x08700000,0x08701000
        cap=len(raw)+1 if capacity is None else capacity
        asm=Ks(KS_ARCH_ARM,KS_MODE_THUMB)
        u.mem_write(source,stream)
        u.mem_write(descriptors,pack_bounds([(source,len(stream))]) if packed else descriptor_blob([(source,len(stream),cap)]))
        u.mem_write(book_at,book)
        u.mem_write(decoder,bytes(asm.asm((ROOT/'asm/strict_unit_bundle_decode.s').read_text(),addr=decoder)[0]))
        u.mem_write(0x08702000,assemble_lookup(0x08702000))
        u.mem_write(hook,assemble_format_hook(address=hook,decoder=decoder,
            descriptors=descriptors,count=1,book=book_at,book_bytes=len(book),consumer='event_expand',
            lookup=0x08702000 if packed else None,output_capacity=cap))
        u.mem_write(0x08098960,dialogue_veneer(0x08098960,hook))
        epilogue='add sp,#8; pop {r3-r5}; mov r8,r3; mov sb,r4; mov sl,r5; pop {r4-r7}; pop {r1}; bx r1'
        u.mem_write(0x08098970,bytes(asm.asm(epilogue,addr=0x08098970)[0]))
        u.mem_write(0x08003520,b'\x70\x47')
        u.mem_write(0x080035dc,b'\x70\x47')
        heap,result,stack,stop=0x02001010,0x02002000,0x03007d00,0x08000100
        u.mem_write(heap-16,b'\xa5'*(cap+32))
        native_source=0x083497c0
        u.mem_write(native_source,raw+b'\0')
        u.reg_write(UC_ARM_REG_R0,source if compressed else native_source)
        for reg,v in ((UC_ARM_REG_R1,0x11223344),(UC_ARM_REG_R2,0x55667788),(UC_ARM_REG_R3,0x99aabbcc)):
            u.reg_write(reg,v)
        saved={reg:0x11110000+i for i,reg in enumerate((UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11))}
        for reg,v in saved.items():u.reg_write(reg,v)
        u.reg_write(UC_ARM_REG_SP,stack);u.reg_write(UC_ARM_REG_LR,stop|1)
        calls=[]
        def watch(uc,address,size,_):
            if address==stop:
                calls.append('return');uc.emu_stop()
            elif address==0x08003520:
                self.assertEqual(uc.reg_read(UC_ARM_REG_R0),cap)
                calls.append('allocate');uc.reg_write(UC_ARM_REG_R0,0 if oom else heap)
            elif address==0x080035dc:
                self.assertEqual(uc.reg_read(UC_ARM_REG_R0),heap)
                calls.append('free');uc.reg_write(UC_ARM_REG_R0,0xdeaddead)
            elif address==0x08098970:
                ptr=uc.reg_read(UC_ARM_REG_R5)
                self.assertEqual(ptr,heap if compressed else native_source)
                self.assertEqual(bytes(uc.mem_read(ptr,len(raw)+1)),raw+b'\0')
                calls.append('native_consumer')
                uc.reg_write(UC_ARM_REG_R0,result)
        u.hook_add(UC_HOOK_CODE,watch)
        u.emu_start(0x08098961,0x08800000,count=30000)
        self.assertEqual(bytes(u.mem_read(heap-16,16)),b'\xa5'*16)
        self.assertEqual(bytes(u.mem_read(heap+cap,16)),b'\xa5'*16)
        if not oom and (capacity is None or cap>=len(raw)+1):
            self.assertEqual(u.reg_read(UC_ARM_REG_SP),stack)
            self.assertEqual(u.reg_read(UC_ARM_REG_R0),result)
            for reg,v in saved.items():self.assertEqual(u.reg_read(reg),v)
        return calls

    def test_compressed_before_native_consumer_owned_input_freed_after_return(self):
        self.assertEqual(self.run_hook(),['allocate','native_consumer','free','return'])

    def test_unknown_native_source_not_decoded_or_freed(self):
        self.assertEqual(self.run_hook(compressed=False),['native_consumer','return'])

    def test_packed_lookup_uses_same_ownership_and_native_passthrough(self):
        self.assertEqual(self.run_hook(packed=True),['allocate','native_consumer','free','return'])
        self.assertEqual(self.run_hook(packed=True,compressed=False),['native_consumer','return'])
        self.assertEqual(self.run_hook(packed=True,capacity=1),['allocate','free'])

    def test_diagnostic_fail_stop_does_not_invoke_consumer_or_return(self):
        self.assertEqual(self.run_hook(oom=True),['allocate'])
        self.assertEqual(self.run_hook(capacity=1),['allocate','free'])

    def test_descriptors_reject_duplicate_address_and_unbounded_extent(self):
        for entries in ([],[(0x08349780,10,5)]*2,[(0x087fffff,2,5)],[(0x08349780,0,5)]):
            with self.assertRaises(ValueError):descriptor_blob(entries)


if __name__=='__main__':unittest.main()
