"""Fail-closed integration checks without private game inputs."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import build_v11c as build
from fix_skill_title_margin import CONTEXT, CONTEXT_START, apply_title_margin


class BuildTests(unittest.TestCase):
    def setUp(self):
        image=bytearray(0x800000)
        image[CONTEXT_START:CONTEXT_START+len(CONTEXT)]=CONTEXT
        image[0x100:0x104]=(0x08000200).to_bytes(4,'little')
        self.base=bytes(image)
        self.corpus={'rows':[{'pointer_storage':'0x100','original_start':'0x200','current_start':'0x200'}]}
        self.result=apply_title_margin(self.base)[0]

    def test_explicit_inputs_reach_previous_builder_and_roundtrip(self):
        with patch.object(build,'rebuild_v11b',return_value=(self.base,b'',{},None,None,None)) as old, patch.object(build,'TARGET',build.sha(self.result)):
            image,bps,report=build.rebuild(self.base,b'patch',{'layout':1},{'components':2},self.corpus)
        old.assert_called_once_with(self.base,b'patch',link={'layout':1},components={'components':2},corpus=self.corpus,expected_target=build.BASE)
        self.assertEqual(build.apply_bps(self.base,bps),image)
        self.assertFalse(report['audio_rom_changes'])

    def test_undeclared_write_rejected_even_if_target_matches(self):
        bad=bytearray(self.result);bad[123]=1;bad=bytes(bad)
        with patch.object(build,'rebuild_v11b',return_value=(self.base,b'',{},None,None,None)), patch.object(build,'apply_title_margin',return_value=(bad,{})), patch.object(build,'TARGET',build.sha(bad)):
            with self.assertRaisesRegex(ValueError,'Undeclared'):
                build.rebuild(self.base,b'',{}, {},self.corpus)

    def test_bad_pointer_rejected(self):
        self.corpus['rows'][0]['original_start']='0x201'
        with patch.object(build,'rebuild_v11b',return_value=(self.base,b'',{},None,None,None)), patch.object(build,'TARGET',build.sha(self.result)):
            with self.assertRaisesRegex(ValueError,'pointer'):
                build.rebuild(self.base,b'',{}, {},self.corpus)


if __name__=='__main__':unittest.main()
