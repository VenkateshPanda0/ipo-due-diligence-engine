# Deterministic Engine Benchmark

Iterations per company: 100

| Company | Mean ms | Median ms | Max ms |
|---|---:|---:|---:|
| eligible-mainboard | 0.469 | 0.446 | 0.758 |
| not-eligible-profitability | 0.535 | 0.510 | 0.850 |
| needs-review-low-confidence | 0.429 | 0.409 | 0.698 |
| young-company | 0.501 | 0.480 | 1.017 |
| large-cap-float | 0.486 | 0.458 | 0.899 |
| low-public-float | 0.491 | 0.499 | 0.826 |
| high-issue-size | 0.504 | 0.483 | 1.288 |
| low-market-cap | 0.416 | 0.442 | 0.746 |
| capex-lock-in | 0.383 | 0.364 | 1.102 |
| advisory-warnings | 0.494 | 0.472 | 0.970 |

Target: < 100 ms per evaluation. Slowest observed run: 1.288 ms.
