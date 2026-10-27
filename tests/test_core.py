import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from forgefix.ast_sandbox import ContractSandbox, ExpressionVM, Unsupported, run_contract
from forgefix.benchmark import load_tasks, summarize, verify_tasks
from forgefix.critic import review
from forgefix.docker_sandbox import DockerSandbox, SandboxUnavailable
from forgefix.engine import RepairAgent
from forgefix.patching import apply_edits
from forgefix.providers import LLMProvider, ProviderError, ScriptedProvider, parse_proposal
from forgefix.repository import PolicyError, code_map, digest, snapshot
from forgefix.types import Edit, TestResult, Usage

ROOT = Path(__file__).resolve().parents[1]


class FixtureTests(unittest.TestCase):
    def test_all_fifty_reference_and_broken_contracts(self):
        tasks, _ = load_tasks(ROOT / "benchmarks/tasks.json")
        self.assertEqual(len(tasks), 50)
        self.assertEqual(verify_tasks(tasks)["valid"], 50)

    def test_generator_is_reproducible(self):
        # Load trusted generator as data definitions; do not invoke its write step.
        import runpy
        generated = runpy.run_path(str(ROOT / "benchmarks/build_tasks.py"))["tasks"]
        stored, _ = load_tasks(ROOT / "benchmarks/tasks.json")
        self.assertEqual(generated, stored)


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "src").mkdir()
        self.source = "def f(x):\n    return x + 1\n"
        (self.root / "src/a.py").write_text(self.source)

    def edit(self, path, content="def f(x):\n    return x + 2\n", sha=None):
        return Edit(path, sha or digest(self.source), content)

    def test_source_edit_and_diff(self):
        diff = apply_edits(self.root, [self.edit("src/a.py")])
        self.assertIn("+    return x + 2", diff)

    def test_denied_paths(self):
        for path in ("../a.py", "/tmp/a.py", "tests/test_a.py", ".github/a.py", "src/../a.py", "src\\a.py", "src/.hidden.py", "src/a.txt", "src/new.py"):
            with self.subTest(path=path), self.assertRaises(PolicyError):
                apply_edits(self.root, [self.edit(path)])

    def test_preimage_hash(self):
        with self.assertRaisesRegex(PolicyError, "Stale"):
            apply_edits(self.root, [self.edit("src/a.py", sha="0" * 64)])

    def test_all_validated_before_write(self):
        with self.assertRaises(PolicyError):
            apply_edits(self.root, [self.edit("src/a.py"), self.edit("tests/test_a.py")])
        self.assertEqual((self.root / "src/a.py").read_text(), self.source)

    def test_symlink_escape(self):
        (self.root / "src/link.py").symlink_to(self.root / "src/a.py")
        with self.assertRaises(PolicyError):
            apply_edits(self.root, [self.edit("src/link.py")])

    def test_invalid_python(self):
        with self.assertRaises(PolicyError):
            apply_edits(self.root, [self.edit("src/a.py", "def broken(")])

    def test_duplicate_edit(self):
        with self.assertRaises(PolicyError):
            apply_edits(self.root, [self.edit("src/a.py"), self.edit("src/a.py")])

    def test_snapshot_and_code_map_do_not_execute_top_level(self):
        text = "raise RuntimeError('must never execute')\n" + self.source
        (self.root / "src/a.py").write_text(text)
        target = self.root.parent / (self.root.name + "-copy")
        import shutil
        self.addCleanup(lambda: shutil.rmtree(target, ignore_errors=True))
        snapshot(self.root, target)
        self.assertEqual(code_map(target)[0]["symbols"][0]["name"], "f")

    def test_snapshot_rejects_links(self):
        (self.root / "src/link.py").symlink_to("/etc/passwd")
        with self.assertRaises(PolicyError):
            snapshot(self.root, self.root / "copy")

    def test_schema_does_not_allow_commands(self):
        with self.assertRaises(PolicyError):
            parse_proposal({"hypothesis": "x", "explanation": "x", "edits": [], "command": "sh"})


class InterpreterTests(unittest.TestCase):
    def test_host_access_and_code_execution_are_denied(self):
        expressions = ["__import__('os').system('id')", "open('/etc/passwd').read()",
                       "x.__class__.__mro__", "eval('1')", "getattr(x, '__class__')",
                       "(lambda: 1)()", "[v for v in x]", "2 ** 999999999",
                       "'x' * 999999999", "'%999999999s' % 'x'",
                       "'x'.replace('x', 'a' * 1000)", "x.encode('unicode_escape')",
                       "f(x)", "sorted(x, key=str)"]
        for expression in expressions:
            with self.subTest(expression=expression):
                result = run_contract(f"def f(x):\n    return {expression}\n", "f", [{"args": ["x"], "expected": None}])
                self.assertFalse(result.green)

    def test_imports_loops_assignments_and_defaults_denied(self):
        for source in ("import os\ndef f(x):\n return x\n", "def f(x):\n while True: pass\n",
                       "def f(x):\n y = x\n return y\n", "def f(x=open('/x')):\n return x\n"):
            with self.subTest(source=source), self.assertRaises(Unsupported):
                ExpressionVM(source, "f")

    def test_unicode_boundary(self):
        vm = ExpressionVM("def f(x):\n    return len(x.encode('utf-8'))\n", "f")
        self.assertEqual(vm.call(["🔐" * 19]), 76)

    def test_hidden_values_not_in_feedback(self):
        result = run_contract("def f(x):\n    return 0\n", "f", [{"args": [123], "expected": 98765}], hidden=True)
        self.assertNotIn("98765", result.output)

    def test_zero_tests_not_green(self):
        result = run_contract("def f(x):\n    return x\n", "f", [])
        self.assertFalse(result.green)
        self.assertEqual(review(result)["decision"], "revise")

    def test_depth_budget(self):
        source = "def f(x):\n    return " + ("1+" * 60) + "x\n"
        self.assertFalse(run_contract(source, "f", [{"args": [1], "expected": 61}]).green)

    def test_aggregate_nested_expansion_is_bounded(self):
        source = "def f(x):\n    return [[x] * 1024] * 1024\n"
        result = run_contract(source, "f", [{"args": [0], "expected": []}])
        self.assertFalse(result.green)
        self.assertIn("Aggregate value node limit", result.output)

    def test_aggregate_string_expansion_is_bounded(self):
        source = "def f(x):\n    return [x] * 100\n"
        result = run_contract(source, "f", [{"args": ["x" * 1000], "expected": []}])
        self.assertFalse(result.green)
        self.assertIn("Aggregate string size limit", result.output)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.task = load_tasks(ROOT / "benchmarks/tasks.json")[0][0]
        self.repo = self.root / "input"
        (self.repo / "src").mkdir(parents=True)
        (self.repo / "src/solution.py").write_text(self.task["initial_source"])

    def run_agent(self, limit=3, provider=None):
        return RepairAgent(provider or ScriptedProvider(self.task["reference_source"], unicode_retry=True),
                           ContractSandbox(self.task), limit).run(self.repo, self.task["issue"], self.root / "run", "auth-001")

    def test_failure_iteration_pass_and_pr(self):
        result = self.run_agent()
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["iterations"], 2)
        trace = [json.loads(x) for x in (self.root / "run/trace.jsonl").read_text().splitlines()]
        self.assertEqual([e["decision"] for e in trace if e["stage"] == "critic"], ["revise", "accept"])
        self.assertIn("Hidden checks: 3 passed", (self.root / "run/PR.md").read_text())
        self.assertEqual((self.repo / "src/solution.py").read_text(), self.task["initial_source"])

    def test_iteration_cap(self):
        result = self.run_agent(limit=1)
        self.assertEqual(result["status"], "unresolved")
        self.assertEqual(result["iterations"], 1)

    def test_oracles_never_in_provider_context(self):
        task = self.task
        outer = self
        class InspectProvider(ScriptedProvider):
            def plan(self, context):
                outer.assertNotIn("reference_source", json.dumps(context))
                outer.assertNotIn("hidden_cases", json.dumps(context))
                return super().plan(context)
            def propose(self, context, iteration):
                outer.assertNotIn("reference_source", json.dumps(context))
                outer.assertNotIn("hidden_cases", json.dumps(context))
                return super().propose(context, iteration)
        self.assertEqual(self.run_agent(provider=InspectProvider(task["reference_source"]))["status"], "resolved")

    def test_already_green_not_counted_as_resolved(self):
        (self.repo / "src/solution.py").write_text(self.task["reference_source"])
        self.assertEqual(self.run_agent()["status"], "not_reproduced")


class AccountingTests(unittest.TestCase):
    def test_unknown_rates_are_not_zero(self):
        self.assertIsNone(Usage(input_tokens=200).cost)

    def test_reported_usage_cost(self):
        usage = Usage(input_tokens=1000, output_tokens=200, input_rate=2, output_rate=10)
        self.assertAlmostEqual(usage.cost, 0.004)

    def test_unknown_usage_cost(self):
        self.assertIsNone(Usage(complete=False, input_rate=0, output_rate=0).cost)

    def test_total_spend_includes_failed_problems(self):
        def record(status, cost):
            return {"status": status, "iterations": 2, "latency_s": 1,
                    "usage": {"cost_usd": cost, "complete": True, "total_tokens": 100},
                    "public_tests": {"passed": 2, "failed": 1}, "hidden_tests": None}
        report = summarize([record("resolved", 0.1), record("unresolved", 0.2)], 2, 10)
        self.assertAlmostEqual(report["model_usd_per_resolved_issue"], 0.3)
        self.assertEqual(report["tests_not_run"], 4)


class DockerPolicyTests(unittest.TestCase):
    def test_no_host_execution_fallback(self):
        with patch("forgefix.docker_sandbox.shutil.which", return_value=None):
            with self.assertRaises(SandboxUnavailable):
                DockerSandbox()

    def test_command_has_hardening_and_fixed_runner(self):
        sandbox = DockerSandbox.__new__(DockerSandbox)
        sandbox.executable, sandbox.image_id, sandbox.runtime = "/usr/bin/docker", "sha256:test", None
        command = sandbox.command(ROOT / "examples/auth-service", "forgefix-test")
        for value in ("--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                      "--user=65534:65534", "--memory=256m", "--pids-limit=64", "--pull=never", "--entrypoint=python"):
            self.assertIn(value, command)
        self.assertEqual(command[-4:], ["sha256:test", "-I", "-B", "/runner.py"])
        self.assertTrue(all("readonly" in command[i+1] for i, part in enumerate(command) if part == "--mount"))
        self.assertNotIn("--privileged", command)
        self.assertNotIn("/var/run/docker.sock", " ".join(command))

    def test_non_https_provider_url_denied(self):
        with patch.dict("os.environ", {"FORGEFIX_API_URL": "http://example.com", "FORGEFIX_API_KEY": "test", "FORGEFIX_MODEL": "test"}):
            with self.assertRaises(ProviderError):
                LLMProvider()

    def test_token_reservation_stops_before_network(self):
        with patch.dict("os.environ", {"FORGEFIX_API_URL": "https://example.com", "FORGEFIX_API_KEY": "test", "FORGEFIX_MODEL": "test"}):
            provider = LLMProvider(max_tokens=1)
            with self.assertRaisesRegex(ProviderError, "budget"):
                provider.plan({"issue": "x"})
            self.assertEqual(provider.usage.calls, 0)


if __name__ == "__main__":
    unittest.main()

