import json
import platform
import statistics
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .ast_sandbox import ContractSandbox, run_contract
from .engine import RepairAgent
from .providers import LLMProvider, ScriptedProvider
from .repository import digest


def load_tasks(manifest: Path) -> tuple[list[dict], str]:
    raw = manifest.read_text(encoding="utf-8")
    data = json.loads(raw)
    tasks = data["tasks"]
    if not isinstance(tasks, list) or len({t["id"] for t in tasks}) != len(tasks):
        raise ValueError("Task IDs must be unique")
    for t in tasks:
        if not t["public_cases"] or not t["hidden_cases"]:
            raise ValueError("Every task needs public and hidden contracts")
    return tasks, digest(raw)


def verify_tasks(tasks: list[dict]) -> dict:
    problems = []
    for task in tasks:
        cases = task["public_cases"] + task["hidden_cases"]
        before = run_contract(task["initial_source"], task["function"], cases)
        after = run_contract(task["reference_source"], task["function"], cases)
        if before.green or not after.green:
            problems.append({"id": task["id"], "baseline": before.output, "reference": after.output})
    return {"tasks": len(tasks), "valid": len(tasks) - len(problems), "problems": problems}


def summarize(results: list[dict], task_count: int, expected_tests: int) -> dict:
    resolved = sum(r["status"] == "resolved" for r in results)
    tests = [x for r in results for x in [r["public_tests"], r["hidden_tests"]] if x is not None]
    passed = sum(t["passed"] for t in tests)
    failed = sum(t["failed"] for t in tests)
    costs = [r["usage"]["cost_usd"] for r in results]
    known = all(c is not None for c in costs)
    total_cost = sum(costs) if known else None
    usage_complete = all(r["usage"]["complete"] for r in results)
    latencies = sorted(r["latency_s"] for r in results)
    return {"issues": task_count, "attempted": len(results), "resolved": resolved,
            "resolved_percent": 100 * resolved / task_count if task_count else 0,
            "tests_passed": passed, "tests_failed": failed,
            "tests_not_run": expected_tests - passed - failed,
            "tests_expected": expected_tests,
            "tests_passed_percent": 100 * passed / expected_tests if expected_tests else 0,
            "iterations_per_problem": statistics.mean(r["iterations"] for r in results) if results else 0,
            "tokens_per_problem": (statistics.mean(r["usage"]["total_tokens"] for r in results) if results else 0) if usage_complete else None,
            "token_usage_complete": usage_complete,
            "total_model_cost_usd": total_cost,
            "model_usd_per_resolved_issue": total_cost / resolved if known and resolved else None,
            "mean_latency_s": statistics.mean(latencies) if latencies else 0,
            "p95_latency_s": latencies[max(0, (95 * len(latencies) + 99) // 100 - 1)] if latencies else 0,
            "statuses": dict(Counter(r["status"] for r in results))}


def run_benchmark(manifest: Path, out: Path, provider="scripted", limit=None, max_iterations=3,
                  task_id=None, model=None, max_tokens=30_000) -> dict:
    tasks, manifest_hash = load_tasks(manifest)
    if task_id:
        tasks = [t for t in tasks if t["id"] == task_id]
        if not tasks:
            raise ValueError("Unknown task ID")
    if limit is not None:
        if not 1 <= limit <= len(tasks):
            raise ValueError("Limit outside available task range")
        tasks = tasks[:limit]
    validation = verify_tasks(tasks)
    if validation["problems"]:
        raise ValueError("Invalid fixture contracts: " + json.dumps(validation))
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    results = []
    for task in tasks:
        with tempfile.TemporaryDirectory(prefix="forgefix-fixture-") as temporary:
            root = Path(temporary)
            (root / "src").mkdir()
            (root / "src/solution.py").write_text(task["initial_source"], encoding="utf-8")
            agent_provider = (ScriptedProvider(task["reference_source"], unicode_retry=task["id"] == "auth-001")
                              if provider == "scripted" else LLMProvider(model=model, max_tokens=max_tokens))
            result = RepairAgent(agent_provider, ContractSandbox(task), max_iterations).run(
                root, task["issue"], out / task["id"], task["id"])
            result["category"] = task["category"]
            results.append(result)
            # Checkpoint each completed problem before proceeding to the next.
            with (out / "results.jsonl").open("a", encoding="utf-8") as checkpoint:
                checkpoint.write(json.dumps(result) + "\n")
            print(f"{task['id']}: {result['status']} ({result['iterations']} attempts)", flush=True)
    summary = summarize(results, len(tasks), sum(len(t["public_cases"]) + len(t["hidden_cases"]) for t in tasks))
    report = {"suite": "controlled-microbugs-v1", "manifest_sha256": manifest_hash,
              "provider": "scripted-oracle" if provider == "scripted" else "llm",
              "quality_claim": "harness-validation-only" if provider == "scripted" else "controlled-microbug-performance-only",
              "backend": "bounded-ast", "max_iterations": max_iterations,
              "max_tokens_per_problem": max_tokens if provider != "scripted" else 0,
              "model": model or ("none" if provider == "scripted" else results[0]["model"]),
              "created_at": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
              "fixture_validation": validation, "summary": summary, "results": results}
    (out / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    categories = []
    for category in sorted({t["category"] for t in tasks}):
        subset = [r for r in results if r["category"] == category]
        categories.append(f"| {category} | {len(subset)} | {sum(r['status'] == 'resolved' for r in subset)} |")
    cost = summary["model_usd_per_resolved_issue"]
    token_display = "unknown" if summary["tokens_per_problem"] is None else format(summary["tokens_per_problem"], ".1f")
    md = ("# ForgeFix benchmark\n\n"
          f"Provider: **{report['provider']}**. Backend: **bounded AST interpreter**.\n\n"
          + ("**Scripted oracle harness validation. Reference patches were supplied to the provider. These results do not measure autonomous model ability.**\n\n" if provider == "scripted" else
             "Controlled expression-level issues only; these results do not establish general repository repair performance.\n\n")
          + "| Metric | Measured value |\n|---|---:|\n"
          f"| Issues resolved | {summary['resolved']}/{summary['issues']} ({summary['resolved_percent']:.1f}%) |\n"
          f"| Final assertions passed | {summary['tests_passed']}/{summary['tests_expected']} |\n"
          f"| Final assertions failed / not run | {summary['tests_failed']} / {summary['tests_not_run']} |\n"
          f"| Mean patch attempts/problem | {summary['iterations_per_problem']:.2f} |\n"
          f"| Mean model tokens/problem | {token_display} |\n"
          f"| Model USD/resolved issue | {'unknown' if cost is None else format(cost, '.6f')} |\n"
          f"| Mean latency/problem (seconds) | {summary['mean_latency_s']:.6f} |\n"
          f"| p95 latency/problem (seconds) | {summary['p95_latency_s']:.6f} |\n\n"
          "Model cost uses configured flat input/output rates and reported tokens, including failed attempts and planning. "
          "It excludes infrastructure and does not account for cache/batch discounts. Unknown usage or rates produce unknown cost. "
          "Scripted mode makes zero model calls. Final assertion totals exclude earlier failed attempts, which remain in traces.\n\n"
          "| Category | Issues | Resolved |\n|---|---:|---:|\n" + "\n".join(categories)
          + f"\n\nManifest SHA-256: `{manifest_hash}`. Each issue has its own patch, PR draft, worktree, and trace.\n")
    (out / "REPORT.md").write_text(md, encoding="utf-8")
    return report

