import sys
import unittest
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENTS_DIR))

from routing import classify_worker_failure

class TestWorkerFailureClassification(unittest.TestCase):
    def test_classify_5xx_internal_error(self):
        stdout = 'Error 500: Internal Server Error while processing request.'
        classification = classify_worker_failure(stdout, '')
        self.assertEqual(classification, 'provider_failure')

    def test_classify_non_provider_failure(self):
        stdout = 'Compilation error: syntax error in source file.'
        classification = classify_worker_failure(stdout, '')
        self.assertEqual(classification, 'implementation_failure')

    def test_auth_failure_is_fallback_eligible(self):
        self.assertEqual(classify_worker_failure('', '401 Unauthorized'), 'credential_missing')

if __name__ == '__main__':
    unittest.main()
