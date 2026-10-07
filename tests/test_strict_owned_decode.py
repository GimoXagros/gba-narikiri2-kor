"""Exact-start selection, lifetime and failure contracts for owned native text."""
from pathlib import Path
import struct,sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
from strict_owned_decode import assemble,assemble_sync_wrapper,assemble_name_initializer
from strict_stream_lookup import assemble_lookup,pack_bounds
from strict_unit_codec import build_book,encode_parts,factor_variants
from strict_packed_tree import pack_tree
from test_strict_packed_tree import PackedThumbDecoder
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE
from unicorn.arm_const import *


class OwnedHarness:
    CODE=0x080b8000
    def __init__(self,caller_buffer=False,extra=False):
        self.u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        self.u.mem_map(0x08000000,0x800000)
        self.u.mem_map(0x02000000,0x40000)
        self.u.mem_map(0x03000000,0x8000)
        self.full=b'\x81\x40ABC';self.compact=b'\x7f\x01\x01ABC'
        self.pair=[b'ABCD',b'ABYYD']
        parts=factor_variants(self.pair,'compact')
        fb=build_book([self.full],'full_text')
        cb=build_book([self.compact]+parts,'compact')
        full=encode_parts([self.full],'full_text',fb)
        compact=encode_parts([self.compact],'compact',cb)
        alias=encode_parts(parts,'compact',cb)
        fb,cb=pack_tree(fb),pack_tree(cb)
        symbols=dict(ALIAS_STARTS=0x080d0000,FULL_BOUNDS=0x080d1000,FULL_COUNT=1,
            FULL_BOOK=0x080e0000,FULL_BOOK_BYTES=len(fb),FULL_CAPACITY=64,
            COMPACT_BOUNDS=0x080f0000,COMPACT_COUNT=2,COMPACT_BOOK=0x080f2000,
            COMPACT_BOOK_BYTES=len(cb),COMPACT_CAPACITY=64,
            UNIT_DECODER=0x080c0001,BOUNDS_LOOKUP=0x080c0401)
        self.extra=b'%s\n\x7f\x01\x02:%ld'
        if extra:
            eb=build_book([self.extra],'compact');es=encode_parts([self.extra],'compact',eb)
            eb=pack_tree(eb)
            symbols.update(EXTRA_BOUNDS=0x080f4000,EXTRA_COUNT=1,EXTRA_BOOK=0x080f5000,
                           EXTRA_BOOK_BYTES=len(eb),EXTRA_CAPACITY=64)
            self.u.mem_write(0x080f4000,pack_bounds([(0x08200100,len(es))]))
            self.u.mem_write(0x080f5000,eb);self.u.mem_write(0x08200100,es)
        for at,data in ((self.CODE,assemble(self.CODE,caller_buffer=caller_buffer,**symbols)),
            (0x080c0000,PackedThumbDecoder().code),(0x080c0400,assemble_lookup(0x080c0400)),
            (0x080d0000,struct.pack('<7I',0x082bcfe0,*range(0x082b0000,0x082b0000+24,4))),
            (0x080d1000,pack_bounds([(0x08200000,len(full))])),
            (0x080f0000,pack_bounds([(0x08200010,len(compact)),(0x082bcfe0,len(alias))])),
            (0x080e0000,fb),(0x080f2000,cb),(0x08200000,full),
            (0x08200010,compact),(0x082bcfe0,alias),
            (0x08003520,b'\x70\x47'),(0x080035dc,b'\x70\x47'),
            (0x080b9000,b'\x70\x47')):
            self.u.mem_write(at,data)
        self.live=set();self.allocs=[];self.frees=[];self.oom=False;self.consumer=None
        def hook(uc,at,size,data):
            if at==0x08003520:
                n=uc.reg_read(UC_ARM_REG_R0);self.allocs.append(n)
                ptr=0 if self.oom else 0x02001010+len(self.allocs)*128
                if ptr:
                    self.live.add(ptr);uc.mem_write(ptr-16,b'\xa5'*(n+32))
                uc.reg_write(UC_ARM_REG_R0,ptr)
            elif at==0x080035dc:
                ptr=uc.reg_read(UC_ARM_REG_R0)
                if ptr not in self.live:raise AssertionError('Unowned/double free')
                if bytes(uc.mem_read(ptr-16,16))!=b'\xa5'*16 or bytes(uc.mem_read(ptr+64,16))!=b'\xa5'*16:
                    raise AssertionError('Output bounds violated')
                self.live.remove(ptr);self.frees.append(ptr)
            elif at==0x080b9000 and self.consumer:self.consumer(uc)
        self.u.hook_add(UC_HOOK_CODE,hook)

    def run(self,pointer,start=CODE,arguments=None):
        u=self.u
        for reg in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,
                    UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11):
            u.reg_write(reg,0x12345678)
        for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),
                             arguments or (pointer,0,0,0)):
            u.reg_write(reg,value)
        u.reg_write(UC_ARM_REG_SP,0x03007e00);u.reg_write(UC_ARM_REG_LR,0x080bff01)
        u.emu_start(start|1,0x080bff00,count=10000)
        if u.reg_read(UC_ARM_REG_PC)!=0x080bff00 or u.reg_read(UC_ARM_REG_SP)!=0x03007e00:
            raise AssertionError('Owned decoder did not return/restored SP')
        for reg in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,
                    UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11):
            if u.reg_read(reg)!=0x12345678:raise AssertionError('Callee-saved register')
        return tuple(u.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2))


class OwnedDecodeTests(unittest.TestCase):
    def test_additional_ui_tree_preserves_format_controls_and_native_fallback(self):
        for stack in (False,True):
            h=OwnedHarness(caller_buffer=stack,extra=True)
            for pointer,expected in ((0x08200100,h.extra),(0x08200010,h.compact),
                                     (0x08200000,h.full),(0x0c2bcfe0,h.pair[1])):
                args=(pointer,0x02003000,64,0) if stack else None
                result,owner,n=h.run(pointer,arguments=args)
                self.assertEqual(bytes(h.u.mem_read(result,n)),expected+b'\0')
            self.assertEqual(h.run(0x08200101),(0x08200101,0,0))
            self.assertEqual(h.run(0x02000100),(0x02000100,0,0))
            self.assertEqual(h.run(0x082bcfe0),(0,0,0))

    def test_default_name_initializers_write_native_bytes_into_original_fields(self):
        for second in (False,True):
            h=OwnedHarness(caller_buffer=True);u=h.u
            code=assemble_name_initializer(0x080b9a00,decoder=h.CODE|1,second=second,fail_stop=0x080b9801)
            u.mem_write(0x080b9a00,code)
            u.mem_write(0x08009788 if second else 0x08009780,struct.pack('<I',0x08200010))
            u.mem_write(0x02000800,struct.pack('<I',0x02000900))
            u.mem_write(0x020008f0,b'\xa5'*128)
            u.reg_write(UC_ARM_REG_R0,0x02000900)
            u.reg_write(UC_ARM_REG_R4,0x02000800)
            u.reg_write(UC_ARM_REG_R2,0x12345678)
            u.reg_write(UC_ARM_REG_SP,0x03007e00)
            u.reg_write(UC_ARM_REG_LR,0x080bff01)
            end=0x0800973c if second else 0x08009728
            u.emu_start(0x080b9a01,end,count=10000)
            self.assertEqual(u.reg_read(UC_ARM_REG_PC),end)
            dst=0x0200093c if second else 0x02000900
            self.assertEqual(bytes(u.mem_read(dst,len(h.compact)+1)),h.compact+b'\0')
            self.assertEqual(bytes(u.mem_read(dst-1,1)),b'\xa5')
            self.assertEqual(bytes(u.mem_read(dst+len(h.compact)+1,1)),b'\xa5')
            self.assertEqual(u.reg_read(UC_ARM_REG_R0),0x0200094f if second else 0x02000900)
            self.assertEqual(u.reg_read(UC_ARM_REG_R1),int.from_bytes(h.compact[:4],'little'))
            self.assertEqual(u.reg_read(UC_ARM_REG_R2),0x12345678)
            self.assertEqual(u.reg_read(UC_ARM_REG_R4),0x02000800)
            self.assertEqual(u.reg_read(UC_ARM_REG_SP),0x03007e00)
            self.assertEqual(u.reg_read(UC_ARM_REG_LR),0x080bff01)
            self.assertEqual(h.allocs,[])

    def test_caller_stack_buffer_is_live_through_consumer_with_no_heap(self):
        for source_register in range(4):
            h=OwnedHarness(caller_buffer=True)
            wrapper=assemble_sync_wrapper(0x080b9200,decoder=h.CODE|1,
                source_register=source_register,consumer=0x080b9001,
                fail_stop=0x080b9801,caller_buffer=True)
            h.u.mem_write(0x080b9200,wrapper)
            args=[11,22,33,44];args[source_register]=0x0c2bcfe0
            def consumer(uc):
                regs=(UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)
                ptr=uc.reg_read(regs[source_register])
                self.assertEqual(ptr,0x03007e00-320+24)
                self.assertEqual(bytes(uc.mem_read(ptr,len(h.pair[1])+1)),h.pair[1]+b'\0')
                for i,reg in enumerate(regs):
                    if i!=source_register:self.assertEqual(uc.reg_read(reg),args[i])
                uc.reg_write(UC_ARM_REG_R0,0xdeadbeef)
            h.consumer=consumer
            self.assertEqual(h.run(0,start=0x080b9200,arguments=args)[0],0xdeadbeef)
            self.assertEqual((h.allocs,h.frees,h.live),([],[],set()))

    def test_caller_buffer_insufficient_or_overlap_rejected(self):
        for pointer,capacity in ((0x02002000,5),(0x08200000,64),(0x03007dc0,64)):
            h=OwnedHarness(caller_buffer=True)
            self.assertEqual(h.run(0,arguments=(0x08200000,pointer,capacity,0)),(0,0,0))
            self.assertEqual((h.allocs,h.frees),([],[]))

    def test_full_compact_and_alternating_aliases_exact_native_owner(self):
        h=OwnedHarness()
        for pointer,raw in ((0x08200000,h.full),(0x08200010,h.compact),
                            (0x0a2bcfe0,h.pair[0]),(0x0c2bcfe0,h.pair[1]),
                            (0x0c2bcfe0,h.pair[1]),(0x0a2bcfe0,h.pair[0])):
            ptr,owner,size=h.run(pointer)
            self.assertEqual(ptr,owner);self.assertIn(owner,h.live)
            self.assertEqual(size,len(raw)+1)
            self.assertEqual(bytes(h.u.mem_read(ptr,size)),raw+b'\0')
        self.assertEqual(h.frees,[])  # Returning function transfers ownership.

    def test_native_exact_start_and_invalid_context_oom_decode_failure(self):
        h=OwnedHarness()
        for pointer in (0x02000100,0x03000100,0x08200001,0x08002000):
            self.assertEqual(h.run(pointer),(pointer,0,0))
        for pointer in (0x082bcfe0,0x0a2bcfe1,0x0c2bcfe1):
            self.assertEqual(h.run(pointer),(0,0,0))
        h.oom=True;self.assertEqual(h.run(0x08200000),(0,0,0));self.assertEqual(h.live,set())
        h.oom=False;h.u.mem_write(0x080e0002,b'\0\0') # Wrong immutable tree version.
        self.assertEqual(h.run(0x08200000),(0,0,0));self.assertEqual(h.live,set())
        self.assertEqual(len(h.frees),1)

    def test_each_sync_argument_slot_consumes_before_free_preserves_result(self):
        for source_register in range(4):
            h=OwnedHarness()
            wrapper=assemble_sync_wrapper(0x080b9200,decoder=h.CODE|1,
                source_register=source_register,consumer=0x080b9001,fail_stop=0x080b9801)
            h.u.mem_write(0x080b9200,wrapper)
            args=[11,22,33,44];args[source_register]=0x08200010
            def consumer(uc):
                actual=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
                ptr=actual[source_register];self.assertIn(ptr,h.live)
                self.assertEqual(bytes(uc.mem_read(ptr,len(h.compact)+1)),h.compact+b'\0')
                actual[source_register]=args[source_register];self.assertEqual(actual,args)
                uc.reg_write(UC_ARM_REG_R0,0xdeadbeef)
            h.consumer=consumer
            self.assertEqual(h.run(0,start=0x080b9200,arguments=args)[0],0xdeadbeef)
            self.assertEqual(h.live,set());self.assertEqual(len(h.frees),1)


if __name__=='__main__':unittest.main()
