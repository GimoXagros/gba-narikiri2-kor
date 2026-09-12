"""Synthetic input, integrity and non-overwrite checks; no game bytes required."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import apply_japanese_patch as tool
from bps import create_bps
from build_graphics_test import repair


class JapaneseApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = b'example Japanese input for synthetic tests'
        self.result = b'example translated result' * 7
        self.delta = create_bps(self.original, self.result)
        self.source = self.root/'original.gba'; self.source.write_bytes(self.original)
        self.delta_path = self.root/'patch.bps'; self.delta_path.write_bytes(self.delta)
        self.output = self.root/'new.gba'
        for name,value in dict(SOURCE_SIZE=len(self.original),TARGET_SIZE=len(self.result),
                SOURCE_SHA256=tool.sha(self.original),TARGET_SHA256=tool.sha(self.result),
                PATCH_SHA256=tool.sha(self.delta)).items():
            p=patch.object(tool,name,value);p.start();self.addCleanup(p.stop)

    def test_verified_apply_preserves_source(self):
        tool.apply(self.source,self.delta_path,self.output)
        self.assertEqual(self.output.read_bytes(),self.result)
        self.assertEqual(self.source.read_bytes(),self.original)

    def test_modified_same_size_source_rejected_without_output(self):
        self.source.write_bytes(b'!'+self.original[1:])
        with self.assertRaisesRegex(ValueError,'Input must'):
            tool.apply(self.source,self.delta_path,self.output)
        self.assertFalse(self.output.exists())

    def test_modified_patch_rejected_without_output(self):
        self.delta_path.write_bytes(self.delta[:-1]+bytes([self.delta[-1]^1]))
        with self.assertRaisesRegex(ValueError,'Patch SHA'):
            tool.apply(self.source,self.delta_path,self.output)
        self.assertFalse(self.output.exists())

    def test_wrong_expected_output_does_not_publish(self):
        with patch.object(tool,'TARGET_SHA256','0'*64),self.assertRaisesRegex(ValueError,'Output identity'):
            tool.apply(self.source,self.delta_path,self.output)
        self.assertFalse(self.output.exists())

    def test_existing_destination_preserved(self):
        self.output.write_bytes(b'personal file')
        with self.assertRaises(FileExistsError):tool.apply(self.source,self.delta_path,self.output)
        self.assertEqual(self.output.read_bytes(),b'personal file')

    def test_source_cannot_be_overwritten(self):
        with self.assertRaises(FileExistsError):tool.apply(self.source,self.delta_path,self.source)
        self.assertEqual(self.source.read_bytes(),self.original)

    def test_graphics_repair_rejects_unbound_input(self):
        with self.assertRaisesRegex(ValueError,'exact v0.9c'):
            repair(b'unknown base',b'unknown reference')


if __name__=='__main__':unittest.main()
