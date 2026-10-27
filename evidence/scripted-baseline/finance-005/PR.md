# Repair: finance-005

Change sign is reversed. Return paid minus total, including negative balances.

## Result

Status: **resolved**. Hidden contracts and public checks passed.

## Change

Uses evaluator-provided reference code; measures the harness only.

## Validation

Baseline: 1 passed, 2 failed.

Final public checks: 3 passed, 0 failed.

Hidden checks: 2 passed, 0 failed.

Patch attempts: 1. Backend: bounded-ast. Provider: scripted-oracle.

Review final.patch and trace.jsonl before merging. This is a local PR draft; nothing was pushed or published.
