"""Run the same adversarial boundary contract against dictionary ABI v2."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]
import test_strict_decoder_contract as contract
from strict_packed_tree import pack_tree
from test_strict_packed_tree import PackedThumbDecoder


class PackedContractHarness(contract.ContractHarness):
    def __init__(self):
        super().__init__()
        self.code = PackedThumbDecoder().code
        self.uc.mem_write(0x100000, self.code)

    def prepare(self, stream, book, capacity, **kwargs):
        return super().prepare(stream, None if book is None else pack_tree(book),
                               capacity, **kwargs)


class PackedDecoderContractTests(contract.DecoderContractTests):
    def setUp(self):
        super().setUp()
        self.vm = PackedContractHarness()


if __name__ == '__main__':
    unittest.main()
