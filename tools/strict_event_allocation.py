"""Bounded exact allocation for the original synchronous name expander."""
from pathlib import Path
from strict_compact_font import validate_thumb
ROOT=Path(__file__).resolve().parents[1]
def assemble(address,*,fail_stop):
    from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
    if address&3 or not fail_stop&1:raise ValueError('Event allocator ABI')
    source=(ROOT/'asm/strict_event_allocation.s').read_text().replace('FAIL_STOP',str(fail_stop))
    code=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(source,addr=address)[0])
    validate_thumb(code,3)
    return code
