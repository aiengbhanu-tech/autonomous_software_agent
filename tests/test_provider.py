import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from forgefix.ast_sandbox import ContractSandbox
from forgefix.benchmark import load_tasks
from forgefix.engine import RepairAgent
from forgefix.providers import LLMProvider, NoRedirect, ProviderError
from forgefix.repository import digest

ROOT = Path(__file__).resolve().parents[1]
ENV = {"FORGEFIX_API_URL": "https://example.com/v1/chat/completions", "FORGEFIX_API_KEY": "fake-test-key",
       "FORGEFIX_MODEL": "test-model", "FORGEFIX_INPUT_USD_PER_MILLION": "2",
       "FORGEFIX_OUTPUT_USD_PER_MILLION": "4"}


def envelope(content, usage=None):
    return io.BytesIO(json.dumps({"model": "test-model-snapshot", "usage": usage if usage is not None else {"prompt_tokens": 100, "completion_tokens": 50},
                                  "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(content)}}]}).encode())


class ProviderTests(unittest.TestCase):
    def test_llm_adapter_plan_patch_failure_revision_accounting(self):
        task = load_tasks(ROOT / "benchmarks/tasks.json")[0][0]
        wrong = task["reference_source"].replace("len(password.encode('utf-8'))", "len(password)")
        def proposal(before, after):
            return {"hypothesis": "Measure supported bytes", "explanation": "Validate before verification",
                    "edits": [{"path": "src/solution.py", "before_sha256": digest(before), "content": after}]}
        responses = [envelope({"hypothesis": "Length error", "steps": ["Validate boundary"]}),
                     envelope(proposal(task["initial_source"], wrong)),
                     envelope(proposal(wrong, task["reference_source"]))]
        requests = []
        class FakeOpener:
            def open(self, request, timeout):
                requests.append(json.loads(request.data))
                return responses.pop(0)
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", ENV), patch("urllib.request.build_opener", return_value=FakeOpener()):
            repo = Path(tmp) / "input"
            (repo / "src").mkdir(parents=True)
            (repo / "src/solution.py").write_text(task["initial_source"])
            result = RepairAgent(LLMProvider(), ContractSandbox(task)).run(repo, task["issue"], Path(tmp) / "run")
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["iterations"], 2)
        self.assertEqual(result["usage"]["calls"], 3)
        self.assertEqual(result["usage"]["total_tokens"], 450)
        self.assertAlmostEqual(result["usage"]["cost_usd"], 0.0012)
        for request in requests:
            serialized = json.dumps(request)
            self.assertNotIn("fake-test-key", serialized)
            self.assertNotIn("hidden_cases", serialized)
            self.assertNotIn("reference_source", serialized)
            self.assertEqual(request["response_format"], {"type": "json_object"})

    def test_missing_usage_blocks_further_calls(self):
        class FakeOpener:
            def open(self, *args, **kwargs):
                return envelope({}, usage={})
        with patch.dict("os.environ", ENV), patch("urllib.request.build_opener", return_value=FakeOpener()):
            provider = LLMProvider()
            with self.assertRaises(ProviderError):
                provider.plan({})
            self.assertFalse(provider.usage.complete)
            self.assertIsNone(provider.usage.cost)
            with self.assertRaisesRegex(ProviderError, "budget"):
                provider.plan({})
            self.assertEqual(provider.usage.calls, 1)

    def test_redirects_rejected(self):
        with self.assertRaises(ProviderError):
            NoRedirect().redirect_request(None, None, None, None, None, "https://other.example/")

    def test_bad_output_still_records_billable_usage(self):
        class FakeOpener:
            def open(self, *args, **kwargs):
                return envelope({"unexpected": "shape"})
        with patch.dict("os.environ", ENV), patch("urllib.request.build_opener", return_value=FakeOpener()):
            provider = LLMProvider()
            with self.assertRaises(ValueError):
                provider.plan({})
            self.assertEqual(provider.usage.tokens, 150)
            self.assertIsNotNone(provider.usage.cost)

