"""Bounded evidence for address-shaped payload words; never rewrites ROM data.

This supplements a census of aligned changed words. It is not a claim that
all game consumers or unaligned/relative references have been discovered.
"""
import struct
from strict_relative_assets import TABLES,read_resource


def word(data,at):
    return struct.unpack_from('<I',data,at)[0]


def preserved_graphic_owners(japanese,adopted,image):
    owners=[]
    for table,count in TABLES:
        starts=[table+word(japanese,table+4+4*i) for i in range(count)]
        for i,start in enumerate(starts):
            at=table+4+4*i
            if image[at:at+4]!=japanese[at:at+4]:continue
            # The adopted active map table replaced the old table.
            source_table=word(adopted,0xCAF0)-0x08000000 if table==0x380F08 else table
            target=(source_table+word(adopted,source_table+4+4*i))&0xFFFFFFFF
            if target!=start:continue
            if i+1<count:end=starts[i+1]
            else:
                try:end=start+read_resource(japanese,start)[1]
                except ValueError:continue
            if not start<end<=len(japanese):raise ValueError('Graphic owner boundary')
            if image[start:end]!=adopted[start:end]:continue
            if image[start]&0xF0 not in (0x10,0x30):continue
            owners.append(dict(start=start,end=end,kind='preserved_native_graphic_payload',
                table=table,index=i,qualification='exact adopted bytes; overlapping native RL runs are not reallocated'))
    return owners


def extra_classification(japanese,adopted,image,owners,at,writer):
    for owner in owners:
        if owner['start']<=at and at+4<=owner['end']:
            return owner
    if writer and writer['start']<=at and at+4<=writer['end']:
        name=writer['name']
        if name.startswith(('asset:map_resource_','asset:native_staff_font')):
            return dict(kind='encoded_native_graphic_payload',start=writer['start'],end=writer['end'])
        if name=='relocated:boot_notice_1bpp_wrapper':
            relative=at-writer['start']
            if relative==36 and word(image,at)==0x09053402:
                return dict(kind='thumb_instruction_pair',instructions='adds r4,#2; lsrs r5,r0,#4')
        if name=='menu:owned_adapter':
            from strict_menu_owned import descriptor_bytes
            begin=writer['start']+268;blob=descriptor_bytes()
            if begin<=at and at+4<=begin+len(blob) and (at-begin)%8==4 and image[begin:begin+len(blob)]==blob:
                return dict(kind='menu_count_length_halfwords',descriptor=(at-begin)//8,
                    count=word(image,at)&0xFFFF,native_bytes=word(image,at)>>16)
    # The new Korean font consumes exactly1564 bytes; the original consumed
    #1997. Only the retired suffix, not the adjacent resource, is classified.
    start=0xCA3F4
    if start+1564<=at and at+4<=start+1997:
        payload,used=read_resource(image,start)
        if used==1564 and len(payload)==8192 and image[start:start+used]==adopted[0xC18000:0xC18000+used]:
            return dict(kind='retired_small_font_stream_suffix',start=start+1564,end=start+1997)
    if at==0x188C38:
        header=0x188AD8;end=0x189C4D
        if (japanese[header:header+16]==struct.pack('<4I',0,0x7D0000,0,0x1165)
            and word(japanese,0xCC9E4)==0x08188AD8
            and image[0xCC9E4:0xCC9E8]==japanese[0xCC9E4:0xCC9E8]
            and image[header:end]==adopted[header:end]
            and adopted[header:at]==japanese[header:at]
            and adopted[at+4:end]==japanese[at+4:end]
            and word(adopted,at)==0x08951B48):
            return dict(kind='inherited_ffr_pcm_sample_word',header=header,
                sample=[header+16,end],reference=0xCC9E4,qualification='retained adopted sound bytes; not a text or code pointer')
    return None
