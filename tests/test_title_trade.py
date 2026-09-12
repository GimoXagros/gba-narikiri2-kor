"""Independently reconstruct the observed three-sprite title consumer."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import build_v09d as title


class TradeTitleTests(unittest.TestCase):
    def test_observed_oam_pieces_reconstruct_centered_native_word(self):
        _,raw=title.trade_stream()
        frame=[[0]*48 for _ in range(16)]
        # OAM at x96/tile238, x128/tile234, x112/tile230; base tile230.
        for x0,tile in [(0,8),(32,4),(16,0)]:
            for y in range(16):
                for x in range(16):
                    offset=(tile+(y//8)*2+x//8)*32+(y%8)*4+(x%8)//2
                    frame[y][x0+x]=(raw[offset]>>(4*(x%2)))&15
        self.assertEqual(frame,title.trade_pixels())
        ink={(x,y) for y,row in enumerate(frame) for x,v in enumerate(row) if v==1}
        self.assertEqual((min(x for x,y in ink),max(x for x,y in ink)),(16,31))
        self.assertEqual((min(y for x,y in ink),max(y for x,y in ink)),(4,11))
        self.assertEqual({v for row in frame for v in row},{0,1,9})

    def test_font_geometry_mismatch_fails_before_build(self):
        invalid={'source_commit':'897f0e71224d9964a84b888f2596b2bfd7f98def',
                 'glyphs':{'교':{'rows':['#'*9]*8}}}
        with patch.object(title.json,'loads',return_value=invalid),self.assertRaisesRegex(ValueError,'geometry'):
            title.trade_stream()

    def test_font_provenance_change_is_rejected(self):
        with patch.object(title.json,'loads',return_value={'source_commit':'unknown'}),self.assertRaisesRegex(ValueError,'provenance'):
            title.trade_stream()


if __name__=='__main__':unittest.main()
