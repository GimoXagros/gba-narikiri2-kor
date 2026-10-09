"""Decode popup source names before their existing native/banked conversion.

Both callers of 25D00 are synchronous. Keep the original getter/table pointers,
25D00 banked-font adapter, padding and conversion logic. Only the borrowed
source is decoded into a stack buffer owned through that native call.
"""
import hashlib
import struct
from strict_honorific_append import assemble_consumer
from strict_profile_name_copy import JAPANESE_SHA256
from strict_relative_assets import read_resource

INPUT_SHA256='66018681d04de90ec9a58cf7e318f9fe9a6b2a6a209c195d23904358b55d7306'
HELPER=0x3A842C
OWNER_END=0x3A8555
OWNER_SHA256='4cbcca20c2222a6e885ac5524949c487970abdfe65ebc932f66ec277f73743b2'
CALLS=((0x25AC8,bytes.fromhex('00f01af9')),(0x25C00,bytes.fromhex('00f07ef8')))


def assemble():
    helper,calls=assemble_consumer(HELPER,0x08025D01,[at for at,_ in CALLS])
    if len(helper)>OWNER_END-HELPER:raise ValueError('Popup helper exceeds resource owner')
    return helper,calls


def diagnostic_patch(japanese,candidate):
    sha=lambda b:hashlib.sha256(b).hexdigest()
    if len(japanese)!=0x800000 or sha(japanese)!=JAPANESE_SHA256:
        raise ValueError('Exact 8 MiB Japanese source required')
    if len(candidate)!=0x800000 or sha(candidate)!=INPUT_SHA256:
        raise ValueError('Exact honorific diagnostic required')
    if sha(candidate[HELPER:OWNER_END])!=OWNER_SHA256:
        raise ValueError('Retired shop suffix identity changed')
    table=0x3A7ADC
    if candidate[table:table+12]!=japanese[table:table+12]:raise ValueError('Shop table binding changed')
    start=table+struct.unpack_from('<I',candidate,table+4)[0]
    next_start=table+struct.unpack_from('<I',candidate,table+8)[0]
    native,used=read_resource(candidate,start)
    original,old_used=read_resource(japanese,start)
    if (start!=0x3A7C3C or len(native)!=4096 or len(original)!=4096
            or start+used!=0x3A83A9 or start+old_used!=OWNER_END
            or not start+used<=HELPER<OWNER_END<=next_start):
        raise ValueError('Popup owner overlaps consumed shop resource')
    helper,calls=assemble();out=bytearray(candidate);writes=[]
    for at,expected,after in [(HELPER,candidate[HELPER:HELPER+len(helper)],helper),
            *[(at,before,after) for (at,before),after in zip(CALLS,calls)]]:
        if candidate[at:at+len(expected)]!=expected:raise ValueError('Original popup call differs')
        out[at:at+len(after)]=after
        writes.append(dict(offset=at,bytes=len(after),before_sha256=sha(expected),after_sha256=sha(after)))
    if read_resource(out,start)!=(native,used):raise ValueError('Live shop graphic changed')
    return bytes(out),dict(status='DIAGNOSTIC_ONLY_DECODED_POPUP_NAME',
        input_sha256=INPUT_SHA256,output_sha256=sha(out),size=len(out),writes=writes,
        stack_temporary_bytes=288,persistent_extra_ram=0,
        owner=dict(start=HELPER,end=OWNER_END,active_resource_end=start+used),
        scope='Both direct callers of native popup converter; source pointer identities unchanged')
