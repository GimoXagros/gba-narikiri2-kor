"""Actor name records never retain a transient decompression pointer."""
import struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
from strict_actor_name_store import assemble
from test_strict_owned_decode import OwnedHarness
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *

class ActorStoreTests(unittest.TestCase):
    def test_compressed_hangul_retains_original_identity_not_stack(self):
        h=OwnedHarness(caller_buffer=True)
        code=assemble(0x080b9200,decoder=h.CODE|1,native_store=0x080b9001,fail_stop=0x080b9801)
        h.u.mem_write(0x080b9200,code)
        h.u.mem_write(0x02002000,b'\xa5'*32)
        result=h.run(0,start=0x080b9200,arguments=(0x02002004,0x08200010,0,0))
        self.assertEqual(result[0],0x02002004)
        self.assertEqual(bytes(h.u.mem_read(0x02002004,10)),struct.pack('<IIH',0x444e007f,0x08200010,0))
        self.assertEqual(bytes(h.u.mem_read(0x02002000,4)),b'\xa5'*4)
        self.assertEqual(bytes(h.u.mem_read(0x0200200e,18)),b'\xa5'*18)
        self.assertEqual(h.allocs,[])

    def test_ascii_variant_copy_uses_decoded_bytes_and_native_passes_through(self):
        for pointer,expected in [(0x0a2bcfe0,b'ABCD\0'),(0x0c2bcfe0,b'ABYYD\0')]:
            h=OwnedHarness(caller_buffer=True)
            h.u.mem_write(0x080b9200,assemble(0x080b9200,decoder=h.CODE|1,native_store=0x080b9001,fail_stop=0x080b9801))
            h.u.mem_write(0x080a6b90,b'\x70\x47')
            def copy(uc,at,size,data):
                if at==0x080a6b90:
                    src=uc.reg_read(UC_ARM_REG_R1);dst=uc.reg_read(UC_ARM_REG_R0)
                    self.assertEqual(bytes(uc.mem_read(src,len(expected))),expected)
                    uc.mem_write(dst,bytes(uc.mem_read(src,len(expected))))
            h.u.hook_add(UC_HOOK_CODE,copy)
            h.run(0,start=0x080b9200,arguments=(0x02002004,pointer,0,0))
            self.assertEqual(bytes(h.u.mem_read(0x02002004,len(expected))),expected)
        h=OwnedHarness(caller_buffer=True);seen=[]
        h.u.mem_write(0x080b9200,assemble(0x080b9200,decoder=h.CODE|1,native_store=0x080b9001,fail_stop=0x080b9801))
        h.consumer=lambda u:seen.append((u.reg_read(UC_ARM_REG_R0),u.reg_read(UC_ARM_REG_R1)))
        h.run(0,start=0x080b9200,arguments=(0x02002004,0x02001000,0,0))
        self.assertEqual(seen,[(0x02002004,0x02001000)])

if __name__=='__main__':unittest.main()
