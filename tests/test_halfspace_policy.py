"""Space classification does not rewrite layout edges or control boundaries."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from audit_halfspace import classify
from strict_unit_codec import units
from narikiri2_text_spec import hangul_to_game_code,glyph_code_to_text
from confirmed_text_edits import encode_full


class SpacePolicyTests(unittest.TestCase):
    def categories(self,text):
        raw=b''.join(b'\x81\x40' if c==' ' else hangul_to_game_code(c).to_bytes(2,'big') if '\uac00'<=c<='\ud7a3' else c.encode('ascii') for c in text)
        tokens=units(raw,'full_text')
        return [classify(tokens,i) for i,t in enumerate(tokens) if t==b'\x81\x40']

    def test_words_and_layout(self):
        self.assertEqual(self.categories('가 나'),['WORD_SEPARATOR'])
        self.assertEqual(self.categories(' 가 '),['INDENT','TRAILING_ERASE'])
        self.assertEqual(self.categories('가  나'),['COLUMN_ALIGNMENT']*2)
        self.assertEqual(self.categories('가\n 나'),['INDENT'])

    def test_visible_variables_and_neutral_waits_are_word_boundaries(self):
        for text in ('%l 가','%k 가','@L 가'):
            self.assertEqual(self.categories(text),['INDENT'])
        for text in ('%s 가','가 %s','@C1 가','%03d 가','가%k 나','가%0t 나','가@S 나','@I 나','가 @E','@L@B 나'):
            self.assertEqual(self.categories(text),['WORD_SEPARATOR'])
        for text in ('@P 가','@L 가','%0t 가','@L @B'):
            self.assertEqual(self.categories(text),['INDENT'])
        self.assertEqual(self.categories('가 @P'),['TRAILING_ERASE'])

    def test_true_control_flag_space_and_layout_runs_stay_full(self):
        self.assertEqual(self.categories('가% 나'),['CONTROL_ARGUMENT'])
        self.assertEqual(self.categories('%s  가'),['COLUMN_ALIGNMENT']*2)

    def test_reserved_space_has_explicit_text_mapping(self):
        self.assertEqual(glyph_code_to_text(0x8040),' ')
        self.assertEqual(glyph_code_to_text(0x8140),'\u3000')

    def test_candidate_encoder_preserves_half_and_full_space_distinction(self):
        self.assertEqual(encode_full(' ',halfwidth_spaces=True),b'\x80\x40')
        self.assertEqual(encode_full('\u3000',halfwidth_spaces=True),b'\x81\x40')
        self.assertEqual(encode_full(' '),b'\x81\x40')
        encoded=encode_full('가 나',halfwidth_spaces=True)
        self.assertEqual(encoded[2:4],b'\x80\x40')


if __name__=='__main__':unittest.main()
