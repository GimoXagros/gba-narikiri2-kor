import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from fix_skill_title_margin import AFTER, BEFORE, CONTEXT, CONTEXT_START, OFFSET, apply_title_margin


class SkillTitleMarginTests(unittest.TestCase):
    def image(self):
        image = bytearray(b'\x5a' * 0x800000)
        image[CONTEXT_START:CONTEXT_START + len(CONTEXT)] = CONTEXT
        return bytes(image)

    def test_only_y_immediate_changes_without_size_or_other_bytes(self):
        before = self.image()
        after, report = apply_title_margin(before)
        self.assertEqual(len(after), 0x800000)
        self.assertEqual(after[:OFFSET], before[:OFFSET])
        self.assertEqual(after[OFFSET + 2:], before[OFFSET + 2:])
        self.assertEqual(before[OFFSET:OFFSET + 2], BEFORE)
        self.assertEqual(after[OFFSET:OFFSET + 2], AFTER)
        self.assertEqual(report['new_y'], 4)

    def test_rejects_wrong_context_repeated_application_and_size(self):
        source = self.image()
        for at in range(CONTEXT_START, CONTEXT_START + len(CONTEXT)):
            damaged = bytearray(source)
            damaged[at] ^= 1
            with self.assertRaises(ValueError):
                apply_title_margin(bytes(damaged))
        with self.assertRaises(ValueError):
            apply_title_margin(source[:-1])
        with self.assertRaises(ValueError):
            apply_title_margin(apply_title_margin(source)[0])


if __name__ == '__main__':
    unittest.main()
