# Repair: validation-004

Leap year rule ignores centuries. Gregorian years divide by 4, except centuries unless divisible by 400.

## Result

Status: **resolved**. Hidden contracts and public checks passed.

## Change

Uses evaluator-provided reference code; measures the harness only.

## Validation

Baseline: 2 passed, 1 failed.

Final public checks: 3 passed, 0 failed.

Hidden checks: 2 passed, 0 failed.

Patch attempts: 1. Backend: bounded-ast. Provider: scripted-oracle.

Review final.patch and trace.jsonl before merging. This is a local PR draft; nothing was pushed or published.
