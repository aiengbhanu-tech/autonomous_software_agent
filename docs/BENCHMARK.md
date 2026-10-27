# Benchmark protocol

The suite contains **50 manually controlled microbugs**, five per category:
auth, pagination, numeric, text, collections, validation, finance, units, logic,
and strings. There are 251 fixed assertions across public and withheld contracts.
Tasks are short expression-level repairs, not SWE-bench or real production issues.

`benchmarks/build_tasks.py` deterministically creates `benchmarks/tasks.json`.
Each task includes a broken source, issue description, expected outputs, and a
reference solution. `verify-benchmark` confirms that every broken version fails
at least one contract and that every reference passes all contracts. Expected
outputs were specified in the generator, not inferred by a model during a run.

The controlled interpreter is used for both initial and repaired sources. This
gives repeatability and avoids executing model-generated Python on the host.
It also means interpreter implementation defects could affect evaluation; unit
tests cover boundaries and unsupported operations, but external evaluation is
still needed for broad claims.

## Two provider conditions

**Scripted oracle:** the provider is deliberately given the reference solution.
The authentication task deliberately receives an incorrect character-count patch
first. This validates iteration, failures, traces, and measurement plumbing. It
does not estimate coding competence or model latency. Model calls/tokens/cost are
zero by construction.

**Live LLM:** the provider gets the issue, selected source, map, public contracts,
and feedback. It never receives the reference or withheld contract data. The
orchestrator retains those outside the copied repository. Hidden expected values
are not sent back on failure, though the model can observe a generic pass/fail
signal. Models can still overfit the stated contract; the benchmark is small and
published, with no contamination guarantees.

Use a fixed model snapshot when the provider offers one. Retain rates, timestamps,
manifest/source/patch hashes, budgets, response model identifiers, and all traces.
Use all 50 tasks for a reported full-suite result; `--limit` always reports its
smaller denominator. For meaningful comparisons, repeat each configuration at
least three times and publish variance. ForgeFix currently runs tasks sequentially.

## Metric definitions

| Metric | Definition |
|---|---|
| Percent resolved | Public and hidden contracts pass / selected tasks × 100 |
| Tests passed | Final passing assertions / all configured final assertions |
| Tests not run | Configured assertions not reached, including hidden checks gated by public failure |
| Iterations/problem | Mean patch attempts, including policy-rejected attempts; baseline/planning are not attempts |
| Tokens/problem | Mean reported input + completion tokens across planning and all patch calls |
| Model USD/resolved issue | Total modeled spend across successful and failed problems / number resolved |
| Latency | Monotonic wall time from per-problem engine entry through final checks, including snapshotting, planning, calls, patches and tests |
| p95 latency | Nearest-rank 95th percentile of problem latencies |

Source fixture materialization, suite setup, final report serialization, and image
building are outside per-problem latency. Token reservation conservatively uses
input bytes plus overhead and the requested completion limit; accounting uses
actual provider usage. Token/call limits are per problem, not a suite-wide dollar
cap. The default maximum is three patch attempts plus one planning call.

Costs are **flat-rate estimates** from configured input/output rates. They exclude
infrastructure, cache/batch discounts, and other provider-specific billing. Missing
rates or unknown usage yield `null` cost, never a misleading zero. A timeout or
missing usage blocks further provider calls for that problem; no automatic HTTP
retry is performed because it could duplicate billing.

Earlier failed assertions remain in traces but are not added to final test counts.
Already-green baselines are `not_reproduced` and get no resolution credit. Empty,
skipped-only, or malformed check results cannot establish success. General Docker
test runs are `tests_passed`, not independently verified `resolved` results.

## Evidence supplied

The included scripted run reports 50/50 issues, 251/251 assertions, and 1.02 mean
attempts. Read `evidence/scripted-baseline/REPORT.md` and `benchmark.json` for
actual measured timings and metadata. The authentication trace contains an
observable failed attempt followed by a revision.

The live adapter is tested with mocked HTTPS responses, not a real model.
Docker tests are present but were skipped during authoring because Docker is
unavailable. No model-quality score or general-repository resolution rate is
claimed. Publish a live-model run and Docker CI results before presenting those
capabilities as empirically validated.

