from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from issue25_names import build

WORKSPACE = ROOT.parent
V11C = WORKSPACE / "narikiri2-halfspace-graphics" / "private_validation" / "v11c-20261030"
INPUTS = V11C / "isolated-source" / "inputs"
BASE_ROM = Path(os.environ.get("ISSUE25_BASE_ROM", V11C / "build-a" / "Xagros_Narikiri2_KOR_v1.1c.gba"))
JP_ROM = Path(os.environ.get("ISSUE25_JP_ROM", INPUTS / "Japanese.gba"))
MASTER = Path(os.environ.get("ISSUE25_MASTER_CSV", V11C / "book-final" / "JP_KO_MASTER_UTF8.csv"))
LINK = Path(os.environ.get("ISSUE25_LINK_JSON", INPUTS / "LINK.json"))
BUILD = Path(os.environ.get("ISSUE25_BUILD_JSON", INPUTS / "BUILD.json"))
NAME_MAP = ROOT / "docs" / "issue25-names.csv"


class Issue25NameOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        missing = [str(path) for path in (BASE_ROM, JP_ROM, MASTER, LINK, BUILD) if not path.is_file()]
        if missing:
            raise unittest.SkipTest(
                "Pinned private v11c inputs are unavailable; set ISSUE25_BASE_ROM, ISSUE25_JP_ROM, "
                "ISSUE25_MASTER_CSV, ISSUE25_LINK_JSON, ISSUE25_BUILD_JSON to run integration checks"
            )
        cls.image, cls.records, cls.details = build(
            BASE_ROM.read_bytes(), JP_ROM.read_bytes(), MASTER, LINK, NAME_MAP, BUILD
        )
        cls.by_binding = {row["binding_id"]: row for row in cls.records}

    def test_all_24_full_and_compact_bindings_are_readback_verified(self):
        self.assertEqual(len(self.records), 24)
        self.assertEqual(self.details["full_name_binding_readbacks"], 12)
        self.assertEqual(self.details["compact_name_readbacks"], 12)
        self.assertEqual(self.details["full_population"]["fresh_readbacks"], 8945)
        self.assertEqual(self.details["full_population"]["unique_starts"], 8203)
        self.assertEqual(self.details["pointer_writes"], 0)
        self.assertTrue(self.details["reused_text_starts"])

    def test_issue25_names_have_exact_encoded_readback(self):
        expected = {
            "밀정": ["JOB_131:002B78D0", "SELECT_JOB_131:003AE2EC", "JOB_132:002B7910",
                     "SELECT_JOB_132:003AE2F0", "D00798:002B78CC", "D00798:002B790C",
                     "D00798:003A765C", "D00798:003A7660"],
            "인챈터": ["JOB_145:002B7C50", "SELECT_JOB_145:003AE324", "D00805:002B7C4C",
                       "D06243:003A769C"],
            "인챈트리스": ["JOB_146:002B7C90", "SELECT_JOB_146:003AE328", "D00806:002B7C8C",
                           "D06244:003A76A0"],
            "유랑 예술가": ["JOB_164:002B8110", "SELECT_JOB_164:003AE370", "D00817:002B810C",
                             "D06250:003A7700"],
            "물 곡예사": ["JOB_165:002B8150", "SELECT_JOB_165:003AE374", "D00818:002B814C",
                          "D06251:003A7704"],
        }
        self.assertEqual({name for row in self.records for name in [row["decoded_name"]]}, set(expected))
        for name, bindings in expected.items():
            for binding in bindings:
                with self.subTest(name=name, binding=binding):
                    self.assertEqual(self.by_binding[binding]["decoded_name"], name)
                    self.assertEqual(self.by_binding[binding]["status"], "OVERLAID_AND_READBACK_VERIFIED")

    def test_full_164_fits_exactly_without_borrowing_the_next_slot(self):
        for binding in ("D00817:002B810C", "D06250:003A7700"):
            row = self.by_binding[binding]
            self.assertEqual(row["slot_bytes"], 7)
            self.assertEqual(row["new_stream_bytes"], 7)
        swap = self.details["full_book_swap"]
        self.assertEqual(swap["target_164_full_bits_before"], 57)
        self.assertEqual(swap["target_164_full_bits_after"], 56)
        self.assertEqual(swap["slot_overflow_count"], 0)
        self.assertEqual(swap["packed_bytes_before_after"], [9312, 9312])
        self.assertEqual(swap["reencoded_unique_starts"], 144)
        self.assertEqual(self.details["full_stream_update_bytes"], 3976)
        self.assertEqual(self.details["borrowed_tail_bytes_written"], 0)
        owner = self.details["target_164_physical_owner"]
        self.assertEqual(owner["japanese_pointer"], "082B8CC0")
        self.assertEqual(owner["source_bytes_hex_including_nul"], "97B78C7C906C00")
        self.assertEqual(owner["slot_bytes_including_nul"], 7)
        self.assertEqual(owner["next_live_source_start"], "2B8CC8")
        self.assertEqual(owner["unused_gap_bytes_before_next_start"], 1)

    def test_job_prose_and_extra_ui_are_preserved(self):
        guards = {row["binding_id"] for row in self.details["job_prose_guards"]}
        self.assertEqual(guards, {"D02179:00325B70", "D07983:007F923C"})
        self.assertFalse(self.details["extra_ui_book_or_streams_changed"])


if __name__ == "__main__":
    unittest.main()
