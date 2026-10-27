# ForgeFix

**A permission-limited software engineering agent: issue → code map → plan → patch → sandbox tests → critique → revision → PR draft.**

Give it a small Python repository and an issue. ForgeFix reads source as data,
proposes narrowly scoped edits, reproduces the failure, iterates against test
feedback, and produces a reviewable patch with an execution trace.

The included issue is: **“The authentication endpoint sometimes returns 500 when
passwords exceed the supported length. Diagnose and fix it.”**

## What is implemented

- Repository snapshotting, Python symbol/import maps, and ranked code search.
- Planner and patch generator using an OpenAI-compatible HTTPS Chat Completions endpoint.
- Source-only edits, preimage hashes, schema validation, and a fixed execution interface.
- A test-driven repair loop with iteration/call/token limits and a deterministic critic.
- An expression interpreter for controlled tasks, plus a hardened Docker runner for ordinary Python.
- Fifty controlled issues with public and withheld contracts, reproducible manifests, and benchmark metrics.
- Per-attempt diffs, JSONL traces, final patches, usage/cost records, and local PR explanations.
- Unit tests, mocked provider integration tests, and an opt-in Docker isolation suite wired into CI.

There are no runtime Python dependencies. Python 3.11+ is required. Commands below
work from the extracted repository root. Installing the package is optional;
`python -m forgefix` works directly.

## Try the complete repair loop without credentials

```powershell
python -m unittest discover -s tests -v
python -m forgefix verify-benchmark
python -m forgefix demo --provider scripted --out runs/auth-demo
python -m forgefix benchmark --provider scripted --out runs/scripted-baseline
```

Choose a fresh output directory for each run; existing runs are never overwritten.
Open `runs/auth-demo/auth-001/PR.md`, `final.patch`, and `trace.jsonl`.

The demo's first proposed patch uses character length and fails on Unicode.
Its second patch measures UTF-8 bytes and passes. These attempts are scripted to
exercise the revision path. They are **not autonomous model results**.

### Measured result included with this repository

| Metric | Scripted oracle harness run |
|---|---:|
| Controlled issues resolved | 50 / 50 |
| Final contract assertions passed | 251 / 251 |
| Mean patch attempts / problem | 1.02 |
| Model tokens / problem | 0 |
| Model USD / resolved issue | 0 |

Reference patches are supplied to the scripted provider. This is an upper-bound
harness check, not evidence of model quality. See
[the measured report](evidence/scripted-baseline/REPORT.md) for latency and
[benchmark methodology](docs/BENCHMARK.md) for definitions and limitations.

## Run a live model benchmark

Configure an API key, a model supported by your provider, and optionally the actual
flat input/output rates. API billing is separate from ChatGPT subscriptions.
ForgeFix does not auto-load `.env`; set environment variables in the shell.

```powershell
$env:FORGEFIX_API_KEY = "YOUR_API_KEY"
$env:FORGEFIX_MODEL = "YOUR_SUPPORTED_MODEL_ID"
# Optional: set FORGEFIX_INPUT_USD_PER_MILLION and FORGEFIX_OUTPUT_USD_PER_MILLION.
# Use current rates from your provider. Without both rates, cost remains unknown.
python -m forgefix benchmark --provider llm --limit 5 --out runs/llm-smoke
python -m forgefix benchmark --provider llm --out runs/llm-50 --max-iterations 3 --max-tokens 30000
```

The adapter defaults to `https://api.openai.com/v1/chat/completions`. An operator
can set `FORGEFIX_API_URL` to another compatible HTTPS endpoint. It must support
JSON-object responses, `max_completion_tokens`, and prompt/completion usage counts.
The model receives issue text, selected source, the map, public contracts, and
bounded failure feedback. It does not receive hidden contracts or reference fixes.
The orchestrator sends selected source to the configured provider; use repositories
you are authorized to send there.

No live model run was performed in the supplied evidence. Mocked API tests verify
request construction, response parsing, usage accounting, and revision behavior.

## Repair the authentication endpoint in Docker

The fixture at `examples/auth-service` is a real in-process WSGI endpoint backed by
a **fake** length-limited verifier. It intentionally returns 500 for long passwords.
It uses no actual password hashing and must not be deployed as authentication.

Start Docker Desktop on Windows, or a trusted local Docker engine on Linux.
Build the runner image yourself; repository Dockerfiles are never executed.

```powershell
docker build -f Dockerfile.sandbox -t forgefix-sandbox:local .
$env:FORGEFIX_DOCKER_TESTS = "1"
python -m unittest discover -s tests -p test_docker_integration.py -v
python -m forgefix repair --repo examples/auth-service --issue examples/issues/auth.md --out runs/auth-live
```

This command also requires the live-model environment variables above. On Linux,
an operator with gVisor installed can add `--runtime runsc`.

The Docker path was **not executed in the authoring environment**: Docker was
unavailable, and namespace creation was restricted. The fail-closed path was
verified. CI includes endpoint repair, network/secret isolation, read-only mounts,
timeout cleanup, and output-flood tests to execute on a Docker-capable runner.

Supported input layout:

```text
your-repository/
  src/       # existing Python source; the only editable files
  tests/     # unittest test_*.py files; immutable to the model
```

The trusted sandbox image contains the Python standard library only. Third-party
dependencies require an operator-built image and `--image`; the agent cannot run
pip, choose commands, change tests, execute hooks, or run repository setup scripts.
Input repositories are limited to 200 files, 64 KB/file, 2 MB total, 1,000 entries,
and 12 directory levels. Symlinks/devices are rejected; hidden paths are omitted.

## Outputs and result meanings

Each repair produces `code-map.json`, `trace.jsonl`, `iteration-N.patch`,
`final.patch`, `result.json`, `PR.md`, and a private copied `worktree/`.
The original repository is never patched. The complete diff is against its
original snapshot, even after multiple revisions.

| Status | Meaning |
|---|---|
| `resolved` | Controlled task passes public and independent hidden contracts |
| `tests_passed` | Docker repository tests are green; review required |
| `unresolved` | Patch budget exhausted with failing checks |
| `not_reproduced` | Baseline already green; no fix credit |
| `blocked` | Execution, policy, provider, or accounting prerequisite failed |

PRs are local Markdown drafts. ForgeFix does not push, merge, publish, or message
anyone. Inspect the patch and tests before adopting a change.

## Design and security

See [architecture](docs/ARCHITECTURE.md), [security boundaries](SECURITY.md), and
[benchmark methodology](docs/BENCHMARK.md).

The agent has no command tool. Docker receives a fixed command vector with no
shell, no network, no writable host mount, no host credentials, a non-root UID,
dropped capabilities, no new privileges, and CPU/memory/PID/time/output limits.
Missing isolation stops execution; it never falls back to running generated
Python on the host. Docker shares a kernel, so use a disposable VM or gVisor for
hostile repositories. Container hardening is not a proof against kernel exploits.

The controlled benchmark interpreter does not use Python `eval`, `exec`, or code
imports. It interprets a small bounded AST subset. This limits benchmark realism;
it is not an alternative Python runtime for arbitrary applications.

## Portfolio demonstration

1. Show the issue and the repository map.
2. Walk through the first failed patch and its Unicode failure.
3. Show the revision, green public/hidden checks, final diff, and PR draft.
4. Show a rejected test-file edit and the missing-Docker failure.
5. Run a live model on the controlled suite; publish its full trace and measured
   cost separately from the scripted harness baseline.

To make stronger real-world claims, add multi-file issues from independent repos,
dependency-specific trusted images, repeated model runs, and external evaluations.

License: [MIT](LICENSE).

New to publishing the repository? See [GitHub setup](GITHUB_SETUP.md).

