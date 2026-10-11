"""Later adapters must not leave an apparently free component-layout tail."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from strict_runtime_linker import Ledger,final_arena_tail


class FinalArenaTest(unittest.TestCase):
    def test_all_late_writers_consume_tail_even_when_bytes_are_unchanged(self):
        ledger=Ledger(bytes(64));plan=dict(arena=[8,64],used=8,free=48)
        for name,lo,hi in [('menu',16,40),('dialogue',40,48),('arte',48,64)]:
            ledger.put(name,lo,bytes(hi-lo),bytes(hi-lo),stage=3,evidence='Synthetic exact owner')
        got=final_arena_tail(ledger,plan)
        self.assertEqual(got['component_layout_free_bytes'],48)
        self.assertEqual(got['final_tail_occupied_bytes'],48)
        self.assertEqual(got['final_tail_unassigned_bytes'],0)
        self.assertEqual(got['final_tail_unassigned_intervals'],[])

    def test_holes_are_union_based_and_stage1_is_not_an_allocation(self):
        ledger=Ledger(bytes(64));plan=dict(arena=[8,64],used=8,free=48)
        for name,lo,hi,stage in [('inherited',16,64,1),('left',8,24,2),
                                ('rewrite',20,28,3),('right',36,48,3)]:
            ledger.put(name,lo,bytes(hi-lo),bytes(hi-lo),stage=stage,evidence='Synthetic exact owner')
        got=final_arena_tail(ledger,plan)
        self.assertEqual(got['final_tail_unassigned_intervals'],[[28,36],[48,64]])
        self.assertEqual(got['final_tail_unassigned_bytes'],24)
        self.assertEqual(got['final_tail_occupied_bytes'],24)
        self.assertEqual([w['name'] for w in got['later_writers']],['left','rewrite','right'])

    def test_stale_or_outside_snapshot_is_rejected(self):
        for plan in [dict(arena=[8,64],used=8,free=49),
                     dict(arena=[8,65],used=8,free=49),
                     dict(arena=[8,64],used=57,free=-1)]:
            with self.subTest(plan=plan),self.assertRaises(ValueError):
                final_arena_tail(Ledger(bytes(64)),plan)


if __name__=='__main__':unittest.main()
