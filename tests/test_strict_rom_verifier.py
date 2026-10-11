"""Exercise ROM-backed decoding and assembly with independent synthetic bytes."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from build_jp8mib_strict import assemble_text_slots
from strict_layout_core import Binding, ROM_SIZE
from strict_text_codec import BOOK_SIZE, build_codebook, encode
from verify_jp8mib_strict import phrase_decoder_from_image, unit_decoder_from_image, read_native
from strict_inline_layout import encode_inline, assemble_inline_slots


class RomVerifierTests(unittest.TestCase):
    def setUp(self):
        self.jp = bytearray(b'\xff' * ROM_SIZE)
        self.jp[0x100:0x104] = (0x08000200).to_bytes(4, 'little')
        self.jp[0x104:0x108] = (0x08000200).to_bytes(4, 'little')
        self.jp[0x200:0x210] = b'original source\0'
        self.jp = bytes(self.jp)
        self.book = build_codebook([b'ABCD', b'ABCE'])
        self.audit = [{'kind':'compact', 'storage':'00000100'}]
        self.offsets = {'compact':0x1000, 'full_text':0x2000}

    def target(self, stream):
        target = bytearray(self.jp)
        target[0x200:0x200+len(stream)] = stream
        for address in self.offsets.values():
            target[address:address+BOOK_SIZE] = self.book
        return bytes(target)

    def test_rom_backed_book_and_original_slot_bound(self):
        target = self.target(encode(b'ABCD', self.book))
        decoder = phrase_decoder_from_image(self.jp, target, self.audit, self.offsets)
        self.assertEqual(decoder(target, 0x200, 0x210, 5), b'ABCD\0')
        with self.assertRaises(ValueError):
            decoder(target, 0x200, 0x204, 5)
        with self.assertRaises(ValueError):
            decoder(target, 0x200, 0x210, 4)

    def test_corrupt_or_out_of_rom_codebook_rejected(self):
        target = bytearray(self.target(b'ABCD\0'))
        target[0x1000] = 0
        with self.assertRaises(ValueError):
            phrase_decoder_from_image(self.jp, bytes(target), self.audit, self.offsets)
        with self.assertRaises(ValueError):
            phrase_decoder_from_image(self.jp, self.target(b'ABCD\0'), self.audit,
                                      dict(compact=ROM_SIZE-BOOK_SIZE+1, full_text=0x2000))

    def test_mixed_category_alias_rejected(self):
        audit = self.audit + [{'kind':'full_text', 'storage':'00000104'}]
        with self.assertRaisesRegex(ValueError, 'Mixed-category'):
            phrase_decoder_from_image(self.jp, self.target(b'A\0'), audit, self.offsets)

    def test_assembler_actual_bytes_and_missing_stream(self):
        row = Binding('synthetic', 0x100, self.jp[0x100:0x104], 0x200, 0x210, b'ABCD\0')
        def native(image, start, end, capacity):
            result = read_native(image, start, end-start)
            if len(result) > capacity:
                raise ValueError('output overflow')
            return result
        image, writes = assemble_text_slots(self.jp, [row], [b'ABCD\0'], 'native', native)
        self.assertEqual(len(image), ROM_SIZE)
        self.assertEqual(image[0x200:0x205], b'ABCD\0')
        self.assertEqual(len(writes), 1)
        with self.assertRaisesRegex(ValueError, 'Missing'):
            assemble_text_slots(self.jp, [row], [], 'native', native)
        with self.assertRaisesRegex(ValueError, 'translation mismatch'):
            assemble_text_slots(self.jp, [row], [b'ABCE\0'], 'native', native)

    def test_inline_alias_assembly_and_rom_backed_context_verifier(self):
        raws=[b'ABXDE',b'ABYYDE']
        rows=[dict(jp_text_start=0x200,slot_capacity=16,category='compact',jp_pointer_storage=s)
              for s in (0x100,0x104)]
        streams,books,selections,_=encode_inline(rows,raws)
        self.assertEqual(streams[0],streams[1])
        bindings=[Binding(str(i),s,self.jp[s:s+4],0x200,0x210,raw+b'\0')
                  for i,(s,raw) in enumerate(zip((0x100,0x104),raws))]
        details=[dict(category='compact',**selected) for selected in selections]
        image,writes=assemble_inline_slots(self.jp,bindings,streams,books,details)
        self.assertEqual(len(writes),1)
        target=bytearray(image)
        for offset in self.offsets.values():
            target[offset:offset+len(books['compact'])]=books['compact']
        baseline=bytearray(self.jp)
        for storage,start,raw in zip((0x100,0x104),(0x300,0x400),raws):
            baseline[storage:storage+4]=(0x08000000+start).to_bytes(4,'little')
            baseline[start:start+len(raw)+1]=raw+b'\0'
        audit=self.audit+[dict(kind='compact',storage='00000104')]
        decoder=unit_decoder_from_image(self.jp,bytes(target),audit,self.offsets,bytes(baseline))
        for storage,raw in zip((0x100,0x104),raws):
            self.assertEqual(decoder(bytes(target),0x200,0x210,len(raw)+1,storage),raw+b'\0')
        with self.assertRaisesRegex(ValueError,'identity'):
            decoder(bytes(target),0x200,0x210,100)
        corrupt=bytearray(target);corrupt[0x1000:0x1002]=b'\xff\xff'
        with self.assertRaises(ValueError):
            unit_decoder_from_image(self.jp,bytes(corrupt),audit,self.offsets,bytes(baseline))


if __name__ == '__main__':
    unittest.main()
