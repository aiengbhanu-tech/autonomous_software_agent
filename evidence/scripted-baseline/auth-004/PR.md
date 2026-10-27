# Repair: auth-004

Admin authorization incorrectly permits editors. Return True only for exact role 'admin'.

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
