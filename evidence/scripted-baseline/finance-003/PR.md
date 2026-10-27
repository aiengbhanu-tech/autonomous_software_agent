# Repair: finance-003

Fee cap acts as a minimum. Return the smaller of amount * rate and cap.

## Result

Status: **resolved**. Hidden contracts and public checks passed.

## Change

Uses evaluator-provided reference code; measures the harness only.

## Validation

Baseline: 0 passed, 3 failed.

Final public checks: 3 passed, 0 failed.

Hidden checks: 2 passed, 0 failed.

Patch attempts: 1. Backend: bounded-ast. Provider: scripted-oracle.

Review final.patch and trace.jsonl before merging. This is a local PR draft; nothing was pushed or published.
