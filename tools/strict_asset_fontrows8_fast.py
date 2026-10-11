"""Same font format and ABI, fewer operations per decoded row.

The symbol base and zero value live in caller-scratch registers for one call.
The mask shift supplies the branch carry. No persistent RAM/cache is added.
"""
from strict_asset_fontrows8 import DECODER_SOURCE, DECODER, WRAPPER_14E0
from strict_asset_fontpages import _assemble


def decoder_source():
    source=DECODER_SOURCE
    replacements=(
        ('offset_loop:\ncmp r7, #0\nbeq offset_done\nldrb r2, [r1]',
         'cmp r7, #0\nbeq offset_done\noffset_loop:\nldrb r2, [r1]'),
        ('subs r7, #1\nb offset_loop','subs r7, #1\nbne offset_loop'),
        ('movs r7, #16\nrow_loop:\nmovs r1, #1\ntst r6, r1\nbne nonzero\nmovs r1, #0\nstrh r1, [r5]',
         'ldr r3, symbols\nmovs r0, #0\nmovs r7, #16\nrow_loop:\nlsrs r6, r6, #1\nbcs nonzero\nstrh r0, [r5]'),
        ('ldr r1, symbols\nlsls r2, r2, #1\nldrh r2, [r1,r2]',
         'lsls r2, r2, #1\nldrh r2, [r3,r2]'),
        ('adds r5, #2\nlsrs r6, r6, #1\nsubs r7, #1','adds r5, #2\nsubs r7, #1'),
    )
    for old,new in replacements:
        if source.count(old)!=1:raise ValueError('Baseline font decoder derivation changed')
        source=source.replace(old,new)
    return source


def code_pair():
    before=_assemble(DECODER_SOURCE,DECODER,WRAPPER_14E0-DECODER)
    after=_assemble(decoder_source(),DECODER,len(before))
    if (len(before)-len(after))%2:raise ValueError('Thumb padding alignment')
    after+=b'\xc0\x46'*((len(before)-len(after))//2)
    return before,after


def apply(image):
    before,after=code_pair()
    if len(image)!=0x800000 or image[DECODER:DECODER+len(before)]!=before:
        raise ValueError('Exact linked original font decoder required')
    result=bytearray(image);result[DECODER:DECODER+len(before)]=after
    return bytes(result)
