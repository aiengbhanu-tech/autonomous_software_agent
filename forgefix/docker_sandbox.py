"""Host subprocess access is confined to fixed Docker commands, never a shell."""
import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

from .types import TestResult


class SandboxUnavailable(RuntimeError):
    pass


class DockerSandbox:
    name = "docker"

    def __init__(self, image="forgefix-sandbox:local", timeout=20, runtime=None):
        self.executable = shutil.which("docker")
        if not self.executable:
            raise SandboxUnavailable("Docker CLI unavailable; host execution is never a fallback")
        if not 1 <= timeout <= 120:
            raise ValueError("Timeout must be between 1 and 120 seconds")
        self.timeout, self.runtime = timeout, runtime
        self.env = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "SystemRoot"}}
        try:
            probe = subprocess.run([self.executable, "image", "inspect", "--format", "{{.Id}}", image],
                                   env=self.env, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SandboxUnavailable("Docker image inspection failed") from exc
        if probe.returncode or not probe.stdout.strip().startswith("sha256:"):
            raise SandboxUnavailable("Prebuild the trusted sandbox image; automatic pulls are disabled")
        self.image_id = probe.stdout.strip()

    def command(self, root: Path, name: str) -> list[str]:
        runner = Path(__file__).with_name("docker_runner.py").resolve()
        # Paths are operator-owned; commas are separators in Docker's mount grammar.
        if any(c in str(root) + str(runner) for c in (",", "\n", "\r")):
            raise ValueError("Unsupported mount path")
        cmd = [self.executable, "run", "--pull=never", "--rm", "--name", name,
               "--network=none", "--read-only", "--cap-drop=ALL",
               "--security-opt=no-new-privileges", "--user=65534:65534",
               "--pids-limit=64", "--memory=256m", "--memory-swap=256m", "--cpus=1",
               "--ulimit=nofile=128:128", "--ulimit=fsize=1048576:1048576",
               "--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777",
               "--mount", f"type=bind,source={root.resolve()},target=/repo,readonly",
               "--mount", f"type=bind,source={runner},target=/runner.py,readonly",
               "--workdir=/tmp", "--env=PYTHONDONTWRITEBYTECODE=1", "--env=HOME=/tmp",
               "--entrypoint=python"]
        if self.runtime:
            cmd.append(f"--runtime={self.runtime}")
        return cmd + [self.image_id, "-I", "-B", "/runner.py"]

    def run(self, root: Path, hidden=False) -> TestResult:
        if hidden:
            raise ValueError("General repositories have no independent hidden-contract grader")
        started, name = time.monotonic(), "forgefix-" + uuid.uuid4().hex
        output, overflow = bytearray(), threading.Event()
        proc = None
        status = "error"
        try:
            proc = subprocess.Popen(self.command(root, name), env=self.env, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

            def drain():
                while True:
                    chunk = proc.stdout.read1(4096)
                    if not chunk:
                        return
                    room = 32_768 - len(output)
                    output.extend(chunk[:max(0, room)])
                    if len(chunk) > room:
                        overflow.set()
                        return

            reader = threading.Thread(target=drain, daemon=True)
            reader.start()
            while proc.poll() is None and time.monotonic() - started < self.timeout and not overflow.is_set():
                time.sleep(0.02)
            if overflow.is_set():
                status = "output_limit"
            elif proc.poll() is None:
                status = "timeout"
            else:
                status = "finished"
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=5)
            reader.join(timeout=1)
            if overflow.is_set():
                status = "output_limit"
        except (OSError, subprocess.TimeoutExpired) as exc:
            output.extend(str(exc).encode()[:1000])
        finally:
            if proc and proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
            # Killing only the Docker CLI does not guarantee container termination.
            try:
                cleanup = subprocess.run([self.executable, "rm", "--force", name], env=self.env,
                                         capture_output=True, timeout=10)
                if cleanup.returncode and b"No such container" not in cleanup.stderr:
                    status = "cleanup_error"
            except (OSError, subprocess.TimeoutExpired):
                status = "cleanup_error"
        text = output.decode("utf-8", errors="replace")
        if status == "finished":
            try:
                marker = [line for line in text.splitlines() if line.startswith("FORGEFIX_RESULT=")][-1]
                record = json.loads(marker.split("=", 1)[1])
                passed, failed = int(record["passed"]), int(record["failed"])
                if passed < 0 or failed < 0 or passed + failed == 0:
                    raise ValueError("No valid tests collected")
                status = "passed" if proc.returncode == 0 and failed == 0 else "failed"
                return TestResult(status, passed, failed, text, time.monotonic() - started, self.name)
            except (IndexError, KeyError, ValueError, TypeError):
                status = "error"
        return TestResult(status, output=text, duration_s=time.monotonic() - started, backend=self.name)

