import sys
import unittest
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import issue25_graphics as graphics


class Issue25GraphicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Synthetic tiles keep these checks runnable without private game assets.
        japanese = bytearray(graphics.ROM_SIZE)
        baseline = bytearray(japanese)
        labels = []
        for index, label in enumerate(graphics.LABELS, start=1):
            before = bytes([index]) * (label.end - label.start)
            original = bytes([0x10 + index]) * len(before)
            baseline[label.start:label.end] = before
            japanese[label.start:label.end] = original
            labels.append(replace(label, v11c_sha256=sha256(before).hexdigest(),
                                  japanese_sha256=sha256(original).hexdigest()))

        # Model an unrelated runtime change and preserve a byte immediately after both spans.
        baseline[0x134C6] = 0x04
        baseline[0x6D645C] = 0xA1
        baseline[0x6D6FFC] = 0xB1
        cls.japanese, cls.baseline = bytes(japanese), bytes(baseline)
        cls.labels = tuple(labels)

    def setUp(self):
        self.enterContext(patch.multiple(
            graphics, LABELS=self.labels, JAPANESE_SHA256=sha256(self.japanese).hexdigest()))

    def test_only_the_four_exact_tile_ranges_are_restored(self):
        result, records = graphics.restore_battle_graphics(self.japanese, self.baseline)
        expected = bytearray(self.baseline)
        bounds = [(0x6D63BC, 0x6D645C), (0x6D6C3C, 0x6D6DBC),
                  (0x6D6DBC, 0x6D6EFC), (0x6D6EFC, 0x6D6FFC)]
        self.assertEqual([(row['offset'], row['end']) for row in records], bounds)
        for row, (start, end) in zip(records, bounds, strict=True):
            expected[start:end] = self.japanese[start:end]
            self.assertEqual(row['before_sha256'], sha256(self.baseline[start:end]).hexdigest())
            self.assertEqual(row['after_sha256'], sha256(self.japanese[start:end]).hexdigest())
            self.assertEqual(row['changed_bytes'], end - start)
        self.assertEqual(result, expected)

    def test_rejects_changed_donor_layout_or_tiles(self):
        wrong_donor = self.japanese[:-1] + b'\x01'
        with self.assertRaisesRegex(ValueError, 'exact Japanese AN9J'):
            graphics.restore_battle_graphics(wrong_donor, self.baseline)
        for description, offset, _ in graphics.LAYOUT_GUARDS:
            with self.subTest(description=description):
                changed = bytearray(self.baseline)
                changed[offset] ^= 1
                with self.assertRaisesRegex(ValueError, description):
                    graphics.restore_battle_graphics(self.japanese, bytes(changed))
        for label in self.labels:
            with self.subTest(label=label.name):
                changed = bytearray(self.baseline)
                changed[label.end-1] ^= 1
                with self.assertRaisesRegex(ValueError, label.name):
                    graphics.restore_battle_graphics(self.japanese, bytes(changed))

    def test_rejects_wrong_rom_length(self):
        with self.assertRaisesRegex(ValueError, 'two 8 MiB ROMs'):
            graphics.restore_battle_graphics(self.japanese[:-1], self.baseline)
        with self.assertRaisesRegex(ValueError, 'two 8 MiB ROMs'):
            graphics.restore_battle_graphics(self.japanese, self.baseline[:-1])


if __name__ == '__main__':
    unittest.main()
