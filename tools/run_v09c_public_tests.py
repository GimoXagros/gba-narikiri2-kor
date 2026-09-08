"""The historical 43 public contracts plus six new storage-failure contracts."""
import sys
import unittest
from run_public_tests import NAMES

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromNames(NAMES + ['test_v09c_io'])
    collected = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f'Collected {collected}; executed {result.testsRun}; failures {len(result.failures)}; '
          f'errors {len(result.errors)}; skipped {len(result.skipped)}')
    sys.exit(0 if result.wasSuccessful() and not result.skipped else 1)
