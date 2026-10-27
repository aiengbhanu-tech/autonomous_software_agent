import argparse
import json
import sys
from pathlib import Path

from .benchmark import load_tasks, run_benchmark, verify_tasks
from .docker_sandbox import DockerSandbox, SandboxUnavailable
from .engine import RepairAgent
from .providers import LLMProvider, ProviderError
from .repository import PolicyError


def main(argv=None):
    parser = argparse.ArgumentParser(prog="forgefix", description="Permission-limited issue repair and benchmarks")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("demo", "benchmark", "verify-benchmark"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--manifest", type=Path, default=Path("benchmarks/tasks.json"))
        if name != "verify-benchmark":
            cmd.add_argument("--out", type=Path, required=True)
            cmd.add_argument("--provider", choices=["scripted", "llm"], default="scripted")
            cmd.add_argument("--model")
            cmd.add_argument("--max-iterations", type=int, default=3)
            cmd.add_argument("--max-tokens", type=int, default=30_000)
        if name == "benchmark":
            cmd.add_argument("--limit", type=int)
    repair = sub.add_parser("repair")
    repair.add_argument("--repo", type=Path, required=True)
    repair.add_argument("--issue", type=Path, required=True)
    repair.add_argument("--out", type=Path, required=True)
    repair.add_argument("--model")
    repair.add_argument("--image", default="forgefix-sandbox:local")
    repair.add_argument("--runtime", help="Operator-selected Docker runtime, e.g. runsc")
    repair.add_argument("--max-iterations", type=int, default=3)
    repair.add_argument("--max-tokens", type=int, default=30_000)
    repair.add_argument("--test-timeout", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify-benchmark":
            tasks, _ = load_tasks(args.manifest)
            result = verify_tasks(tasks)
            print(json.dumps(result, indent=2))
            return 0 if not result["problems"] else 1
        if args.command in ("demo", "benchmark"):
            result = run_benchmark(args.manifest, args.out, args.provider,
                                   limit=getattr(args, "limit", None), max_iterations=args.max_iterations,
                                   task_id="auth-001" if args.command == "demo" else None,
                                   model=args.model, max_tokens=args.max_tokens)
            print(json.dumps(result["summary"], indent=2))
            return 0 if result["summary"]["resolved"] == result["summary"]["issues"] else 1
        # Probe execution prerequisites before sending any repository code to the LLM.
        sandbox = DockerSandbox(args.image, args.test_timeout, args.runtime)
        provider = LLMProvider(model=args.model, max_tokens=args.max_tokens)
        result = RepairAgent(provider, sandbox, args.max_iterations).run(
            args.repo, args.issue.read_text(encoding="utf-8"), args.out)
        print(json.dumps({k: result[k] for k in ("status", "reason", "iterations", "usage")}, indent=2))
        return 0 if result["status"] == "tests_passed" else 1
    except (PolicyError, ProviderError, SandboxUnavailable, ValueError, OSError) as exc:
        print(f"ForgeFix stopped: {exc}", file=sys.stderr)
        return 2

