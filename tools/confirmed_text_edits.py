"""Individually reviewed, exact-source full-text edits for the development build.

These do not constitute a whole-script translation or approval of the remaining
dialogue. Source controls and numeric effects are protected, and every payload
is relocated. ASCII-looking bytes are never searched/replaced across the ROM.
"""
import json
import re
import struct
import hashlib

from narikiri2_text_spec import (ITEM_RECORD_SIZE,ITEM_TABLE_OFFSET,decode_game_text,
                                hangul_to_game_code,read_c_string,read_pointer)


def normalized(text):
    return text.replace('\u3000',' ')


def encode_full(text, *, halfwidth_spaces=False):
    result=bytearray()
    for character in text:
        if '\uac00'<=character<='\ud7a3':
            result.extend(hangul_to_game_code(character).to_bytes(2,'big'))
        elif character=='\n':
            result.append(10)
        elif character==' ':
            result.extend(b'\x80\x40' if halfwidth_spaces else b'\x81\x40')
        elif 0x21<=ord(character)<=0x7e:
            result.append(ord(character))
        else:
            encoded=character.encode('cp932')
            if len(encoded)!=2 or not 0x81<=encoded[0]<=0x87:
                raise ValueError(f'Unapproved non-Hangul character: {character!r}')
            result.extend(encoded)
    return bytes(result)


def plans(source,root):
    decisions=json.loads((root/'translation/confirmed_description_edits.json').read_text(encoding='utf-8'))
    bindings=json.loads((root/'config/description_source_bindings.json').read_text(encoding='utf-8'))
    result=[]
    seen=set()
    for row in decisions:
        index=row['item']
        if index in seen or not 0<=index<157:
            raise ValueError('Repeated or invalid description decision')
        seen.add(index)
        original=bindings[str(index)]
        storage=ITEM_TABLE_OFFSET+index*ITEM_RECORD_SIZE+0x10
        _,old=read_pointer(source,storage)
        expected=read_c_string(source,old,len(source))
        if old+0x08000000!=int(original['pointer'],16) or hashlib.sha256(expected).hexdigest()!=original['sha256']:
            raise ValueError('Catalog/source byte mismatch')
        previous=normalized(decode_game_text(source,expected))
        final=row['final']
        if previous.count('\n')!=final.count('\n'):
            raise ValueError('Description line-count change requires a separate reviewed layout')
        if max(map(len,final.split('\n')))>max(map(len,previous.split('\n'))):
            raise ValueError(f'Item {index}: new maximum line length exceeds the existing layout bound')
        numbers=lambda text:re.findall('[0-9０-９]+',text)
        if numbers(previous)!=numbers(final):
            raise ValueError('Gameplay numbers changed')
        if '@' in final or '%' in final or '\x12' in final:
            raise ValueError('Description control extension is not supported')
        payload=encode_full(final)
        if normalized(decode_game_text(source,payload))!=final:
            raise ValueError('Full-text encode/decode mismatch')
        result.append({'id':f'ITEM_{index:03d}_DESCRIPTION','item':index,'storage':storage,
                       'old_offset':old,'expected':expected,'payload':payload,**row})
    # This is a single adopted terminology correction, not a global prose rule.
    # The unchanged menu already calls this section 커스텀, as does the monster
    # encyclopedia tutorial. Keep all page/voice tokens, spaces and byte length.
    storage=0x3470e0
    _,old=read_pointer(source,storage)
    if old!=0x835783:
        raise ValueError('Character-book tutorial source pointer mismatch')
    raw=read_c_string(source,old,len(source))
    before,after=encode_full('코스츔'),encode_full('커스텀')
    if raw.count(before)!=1 or len(before)!=len(after):
        raise ValueError('Tutorial expected term is not uniquely bound')
    payload=raw.replace(before,after)
    previous=decode_game_text(source,raw)
    final=decode_game_text(source,payload)
    tokens=lambda text:re.findall(r'@[A-Za-z]|%[0-9]*[A-Za-z]|\n',text)
    if tokens(previous)!=tokens(final):
        raise ValueError('Tutorial control-token mismatch')
    result.append({'id':'CHARACTER_BOOK_TUTORIAL_CUSTOM','item':None,'storage':storage,
                   'old_offset':old,'expected':raw,'payload':payload,'previous':previous,'final':final,
                   'reason':'The reachable menu is 커스텀; preserve every other script byte/control'})
    return result
