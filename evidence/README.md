# Included validation evidence

- `unit-tests.txt`: 36 executed checks passed; four Docker integration checks skipped.
- `validation.json`: machine-readable validation summary.
- `scripted-baseline/REPORT.md`: measured 50-issue scripted oracle report.
- `scripted-baseline/benchmark.json`: full per-issue results and aggregate metrics.
- `scripted-baseline/auth-001/trace.jsonl`: failed character-count patch, Unicode
  feedback, byte-length revision, green checks, and PR draft.

These are **scripted oracle** results. The provider was supplied reference fixes.
No live model was called. Docker was unavailable, so full Python containment and
endpoint integration remain unverified in this environment. The Docker workflow
is included for execution on a suitable machine or GitHub Actions runner.

