import difflib
import json
import platform
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .critic import review
from .patching import apply_edits
from .providers import ProviderError
from .repository import PolicyError, code_map, digest, search, snapshot


class RepairAgent:
    def __init__(self, provider, sandbox, max_iterations=3):
        if not 1 <= max_iterations <= 10:
            raise ValueError("Iterations must be between 1 and 10")
        self.provider, self.sandbox, self.max_iterations = provider, sandbox, max_iterations

    def run(self, repo: Path, issue: str, out: Path, task_id="external") -> dict:
        started = time.monotonic()
        repo, out = repo.resolve(), out.resolve()
        if out.is_relative_to(repo):
            raise PolicyError("Output directory must be outside the input repository")
        if len(issue.encode()) > 16_000:
            raise PolicyError("Issue exceeds byte limit")
        out.mkdir(parents=True, exist_ok=False)
        # Snapshot is private operator-owned storage; untrusted code never runs here.
        root = out / "worktree"
        snapshot(repo, root)
        events, iterations, history = [], 0, []

        def emit(stage, **data):
            event = {"sequence": len(events) + 1, "stage": stage,
                     "elapsed_s": round(time.monotonic() - started, 6), **data}
            events.append(event)
            with (out / "trace.jsonl").open("a", encoding="utf-8") as file:
                file.write(json.dumps(event, ensure_ascii=False) + "\n")

        mapping = code_map(root)
        initial = {x["path"]: (root / x["path"]).read_text(encoding="utf-8") for x in mapping}
        repository_hash = digest(json.dumps({p: digest(s) for p, s in initial.items()}, sort_keys=True))
        emit("repo_analyzer", code_map=mapping, repository_sha256=repository_hash)
        (out / "code-map.json").write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
        baseline = self.sandbox.run(root)
        emit("baseline_tests", result=asdict(baseline))
        status, reason, plan, last_proposal = "unresolved", "Iteration limit reached", None, None
        public, hidden = baseline, None
        if baseline.green:
            status, reason = "not_reproduced", "Baseline is already green; no resolution claimed"
        elif baseline.passed + baseline.failed == 0 or baseline.status in {"error", "timeout", "output_limit", "blocked", "cleanup_error"}:
            status, reason = "blocked", "Baseline execution failed; no host fallback"
        else:
            try:
                files = search(root, issue, mapping)
                if not files:
                    raise PolicyError("No editable Python source found under src/")
                context = {"issue": issue, "backend": self.sandbox.name, "code_map": mapping,
                           "files": files, "failure": baseline.output[:16_000],
                           "public_contract": getattr(self.sandbox, "task", {}).get("public_cases", [])}
                plan = self.provider.plan(context)
                emit("planner", plan=plan)
                feedback = baseline.output[:16_000]
                for iterations in range(1, self.max_iterations + 1):
                    current_map = code_map(root)
                    files = search(root, issue, current_map)
                    emit("code_search", paths=[x["path"] for x in files])
                    context = {"issue": issue, "backend": self.sandbox.name, "plan": plan,
                               "files": files, "feedback": feedback, "history": history[-2:],
                               "public_contract": getattr(self.sandbox, "task", {}).get("public_cases", [])}
                    try:
                        proposal = self.provider.propose(context, iterations)
                        emit("hypothesis", text=proposal.hypothesis, iteration=iterations)
                        diff = apply_edits(root, proposal.edits)
                        last_proposal = proposal
                        (out / f"iteration-{iterations}.patch").write_text(diff, encoding="utf-8")
                        emit("patch_generator", iteration=iterations, paths=[x.path for x in proposal.edits])
                    except PolicyError as exc:
                        feedback = str(exc)
                        history.append({"iteration": iterations, "decision": "policy_rejected", "feedback": feedback})
                        emit("permission_denied", iteration=iterations, reason=feedback)
                        continue
                    public = self.sandbox.run(root)
                    emit("sandbox_tests", iteration=iterations, result=asdict(public))
                    hidden = self.sandbox.run(root, hidden=True) if public.green and self.sandbox.name == "bounded-ast" else None
                    if hidden is not None:
                        emit("hidden_grader", iteration=iterations, result=asdict(hidden))
                    critique = review(public, hidden)
                    emit("critic", iteration=iterations, **critique)
                    feedback = critique["feedback"]
                    history.append({"iteration": iterations, **critique})
                    if critique["decision"] == "accept":
                        status = "resolved" if hidden is not None else "tests_passed"
                        reason = "Hidden contracts and public checks passed" if hidden is not None else "Repository tests passed; human review still required"
                        break
                    if public.status in {"error", "timeout", "output_limit", "blocked", "cleanup_error"}:
                        status, reason = "blocked", "Sandbox failed; iteration stopped"
                        break
            except (ProviderError, PolicyError, ValueError) as exc:
                status, reason = "blocked", str(exc)
                emit("blocked", reason=reason)
        final_diff = "".join("".join(difflib.unified_diff(before.splitlines(True),
                            (root / path).read_text(encoding="utf-8").splitlines(True),
                            fromfile=f"a/{path}", tofile=f"b/{path}")) for path, before in initial.items())
        (out / "final.patch").write_text(final_diff, encoding="utf-8")
        result = {"task_id": task_id, "status": status, "reason": reason,
                  "provider": self.provider.name, "model": self.provider.model,
                  "response_models": getattr(self.provider, "response_models", []),
                  "backend": self.sandbox.name, "iterations": iterations,
                  "latency_s": time.monotonic() - started, "usage": self.provider.usage.to_dict(),
                  "baseline": asdict(baseline), "public_tests": asdict(public),
                  "hidden_tests": asdict(hidden) if hidden else None,
                  "repository_sha256": repository_hash, "patch_sha256": digest(final_diff),
                  "issue_sha256": digest(issue), "created_at": datetime.now(timezone.utc).isoformat(),
                  "python": platform.python_version()}
        (out / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        explanation = last_proposal.explanation if last_proposal else "No patch was accepted for testing."
        pr = (f"# Repair: {task_id}\n\n{issue}\n\n## Result\n\n"
              f"Status: **{status}**. {reason}.\n\n## Change\n\n{explanation}\n\n"
              f"## Validation\n\nBaseline: {baseline.passed} passed, {baseline.failed} failed.\n\n"
              f"Final public checks: {public.passed} passed, {public.failed} failed.\n\n"
              + (f"Hidden checks: {hidden.passed} passed, {hidden.failed} failed.\n\n" if hidden else "")
              + f"Patch attempts: {iterations}. Backend: {self.sandbox.name}. Provider: {self.provider.name}.\n\n"
              "Review final.patch and trace.jsonl before merging. This is a local PR draft; nothing was pushed or published.\n")
        (out / "PR.md").write_text(pr, encoding="utf-8")
        emit("pr_draft", status=status, patch_sha256=result["patch_sha256"])
        return result

