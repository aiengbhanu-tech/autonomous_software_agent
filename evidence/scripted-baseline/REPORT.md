# ForgeFix benchmark

Provider: **scripted-oracle**. Backend: **bounded AST interpreter**.

**Scripted oracle harness validation. Reference patches were supplied to the provider. These results do not measure autonomous model ability.**

| Metric | Measured value |
|---|---:|
| Issues resolved | 50/50 (100.0%) |
| Final assertions passed | 251/251 |
| Final assertions failed / not run | 0 / 0 |
| Mean patch attempts/problem | 1.02 |
| Mean model tokens/problem | 0.0 |
| Model USD/resolved issue | 0.000000 |
| Mean latency/problem (seconds) | 0.002685 |
| p95 latency/problem (seconds) | 0.003950 |

Model cost uses configured flat input/output rates and reported tokens, including failed attempts and planning. It excludes infrastructure and does not account for cache/batch discounts. Unknown usage or rates produce unknown cost. Scripted mode makes zero model calls. Final assertion totals exclude earlier failed attempts, which remain in traces.

| Category | Issues | Resolved |
|---|---:|---:|
| auth | 5 | 5 |
| collections | 5 | 5 |
| finance | 5 | 5 |
| logic | 5 | 5 |
| numeric | 5 | 5 |
| pagination | 5 | 5 |
| strings | 5 | 5 |
| text | 5 | 5 |
| units | 5 | 5 |
| validation | 5 | 5 |

Manifest SHA-256: `62216d3149f2fefccd4aa19c491bcc481ce9599e22a7e37caa29c29642da16a5`. Each issue has its own patch, PR draft, worktree, and trace.
