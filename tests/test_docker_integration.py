"""Opt in only on a host with the prebuilt trusted sandbox image."""
import os
import tempfile
import unittest
from pathlib import Path

from forgefix.docker_sandbox import DockerSandbox
from forgefix.engine import RepairAgent
from forgefix.providers import ScriptedProvider

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get("FORGEFIX_DOCKER_TESTS") == "1", "requires Docker sandbox image")
class DockerIntegrationTests(unittest.TestCase):
    def test_real_endpoint_fail_patch_pass(self):
        repo = ROOT / "examples/auth-service"
        original = (repo / "src/auth.py").read_text()
        fixed = original.replace("    # BUG: overlong input reaches verifier and raises ValueError.\n",
                                 "    if len(password.encode('utf-8')) > MAX_PASSWORD_BYTES:\n"
                                 "        return 422, {'error': 'password exceeds supported length'}\n")
        with tempfile.TemporaryDirectory() as temp:
            result = RepairAgent(ScriptedProvider(fixed, path="src/auth.py"), DockerSandbox()).run(
                repo, "Reject passwords above 72 UTF-8 bytes without changing verification", Path(temp) / "run")
            self.assertEqual(result["status"], "tests_passed")
            self.assertGreater(result["baseline"]["failed"], 0)
            self.assertEqual(result["public_tests"]["passed"], 9)

    def test_readonly_mount_network_and_secret_isolation(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "src").mkdir()
            (repo / "tests").mkdir()
            (repo / "src/probe.py").write_text("MARKER = 1\n")
            (repo / "tests/test_isolation.py").write_text('''import os, socket, unittest
class IsolationTests(unittest.TestCase):
    def test_repo_readonly(self):
        with self.assertRaises(OSError):
            open('/repo/src/marker', 'w')
    def test_no_host_secret(self):
        self.assertNotIn('FORGEFIX_API_KEY', os.environ)
        self.assertFalse(os.path.exists('/var/run/docker.sock'))
    def test_no_external_network(self):
        with self.assertRaises(OSError):
            socket.create_connection(('203.0.113.1', 443), timeout=0.5)
''')
            result = DockerSandbox().run(repo)
            self.assertTrue(result.green, result.output)
            self.assertFalse((repo / "src/marker").exists())

    def test_timeout_kills_container(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "src").mkdir()
            (repo / "tests").mkdir()
            (repo / "tests/test_timeout.py").write_text("import unittest, time\nclass T(unittest.TestCase):\n def test_hang(self):\n  time.sleep(30)\n")
            self.assertEqual(DockerSandbox(timeout=1).run(repo).status, "timeout")

    def test_output_flood_stopped(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "src").mkdir()
            (repo / "tests").mkdir()
            (repo / "tests/test_flood.py").write_text("import unittest\nclass T(unittest.TestCase):\n def test_flood(self):\n  while True: print('x'*4096, flush=True)\n")
            result = DockerSandbox(timeout=5).run(repo)
            self.assertEqual(result.status, "output_limit")
            self.assertLessEqual(len(result.output.encode()), 32768)

