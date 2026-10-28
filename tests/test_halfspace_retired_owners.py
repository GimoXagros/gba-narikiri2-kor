import sys
import unittest
import json
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from halfspace_retired_owners import checked_writes,check_preimages,check_text_slots,manifest,sha


class RetiredOwnerGuards(unittest.TestCase):
    def test_fixed_even_owners_never_grant_prefix_or_boundary_writes(self):
        owners=manifest()['owners']
        self.assertEqual(len(owners),45)
        for owner in owners:
            lo,hi=owner['reclaim_start'],owner['reclaim_end']
            good={'start':lo,'end':hi&~1}
            self.assertEqual(checked_writes([good]),[(lo,hi&~1)])
            invalid=[{'start':lo-2,'end':lo+2},{'start':lo,'end':hi+1},
                     {'start':lo+1,'end':lo+3}]
            if hi&1:invalid.append({'start':lo,'end':hi})
            for row in invalid:
                with self.assertRaises(ValueError):checked_writes([row])
            with self.assertRaises(ValueError):checked_writes([good,good])

    def test_unrelated_ranges_do_not_become_retired_owners(self):
        self.assertEqual(checked_writes([{'start':0x7fe000,'end':0x800000}]),[])
        with self.assertRaises(ValueError):check_preimages(b'wrong')
        with self.assertRaises(ValueError):check_preimages(bytes(0x800000))

    def test_actual_input_live_prefix_and_undeclared_suffix_are_protected(self):
        root=Path(__file__).resolve().parents[1]
        candidate=root/'private_validation/halfspace-graphics-20261025/v11b-build-g-reproduction/Xagros_Narikiri2_KOR_v1.1b.gba'
        corpus=root.parent/'narikiri2-v09d-graphics-test/private_validation/kr-patch-qa-20261019/reviewed-dialogue-data.json'
        if not candidate.exists() or not corpus.exists():self.skipTest('Private exact input unavailable')
        before=candidate.read_bytes();rows=json.loads(corpus.read_text(encoding='utf-8'))
        owner=check_preimages(before)[0];lo=owner['reclaim_start']
        after=bytearray(before);after[lo:lo+2]=bytes(v^255 for v in before[lo:lo+2])
        write={'start':lo,'end':lo+2,'before_sha256':sha(before[lo:lo+2]),'after_sha256':sha(after[lo:lo+2])}
        self.assertEqual(check_text_slots(before,after,rows,[write]),[(lo,lo+2)])
        with self.assertRaises(ValueError):check_text_slots(before,after,rows,[])
        after[lo-1]^=255
        with self.assertRaises(ValueError):check_text_slots(before,after,rows,[write])
        after[lo-1]^=255;after[lo+2]^=255
        with self.assertRaises(ValueError):check_text_slots(before,after,rows,[write])


if __name__=='__main__':unittest.main()
