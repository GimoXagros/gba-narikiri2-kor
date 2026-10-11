"""Source-only builder rejects invalid inputs before creating output."""
import sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from build_strict_8m_diagnostic import build
from strict_packed_tree import assemble_decoder


class StrictSourceBuildTests(unittest.TestCase):
    def test_invalid_source_has_no_partial_output(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);jp=p/'jp';ko=p/'ko';jp.write_bytes(b'bad');ko.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'size'):
                build(jp,ko,p/'catalog',p/'audit',p/'output')
            self.assertFalse((p/'output').exists())

    def test_existing_directory_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);(p/'keep').write_bytes(b'unchanged')
            with self.assertRaises(FileExistsError):build(p/'x',p/'y',p/'c',p/'a',p)
            self.assertEqual((p/'keep').read_bytes(),b'unchanged')

    def test_decoder_is_position_independent_without_test_runtime(self):
        self.assertEqual(assemble_decoder(0x0837E1F0),assemble_decoder(0x08C91800))
        with self.assertRaises(ValueError):assemble_decoder(0x0837E1F1)


if __name__=='__main__':unittest.main()
