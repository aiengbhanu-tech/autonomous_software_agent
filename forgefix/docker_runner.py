"""Trusted runner mounted by the operator, never selected by the model."""
import json
import sys
import unittest

sys.path.insert(0, "/repo/src")
suite = unittest.defaultTestLoader.discover("/repo/tests", pattern="test_*.py")
result = unittest.TextTestRunner(verbosity=2).run(suite)
failed = len(result.failures) + len(result.errors) + len(result.unexpectedSuccesses)
# Skipped/expected-failure tests do not establish resolution.
passed = result.testsRun - failed - len(result.skipped) - len(result.expectedFailures)
print("FORGEFIX_RESULT=" + json.dumps({"passed": passed, "failed": failed}), flush=True)
sys.exit(0 if result.wasSuccessful() and passed > 0 else 1)

