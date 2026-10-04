# Deterministic Engine Benchmark

Iterations per company: 100

| Company | Mean ms | Median ms | Max ms |
|---|---:|---:|---:|
| eligible-mainboard | 1.268 | 1.253 | 2.263 |
| not-eligible-profitability | 1.296 | 1.281 | 1.552 |
| needs-review-low-confidence | 1.131 | 1.122 | 1.248 |
| young-company | 1.271 | 1.254 | 2.123 |
| large-cap-float | 1.292 | 1.280 | 1.565 |
| low-public-float | 1.269 | 1.260 | 1.485 |
| high-issue-size | 1.271 | 1.259 | 1.862 |
| low-market-cap | 1.275 | 1.268 | 1.544 |
| capex-lock-in | 1.275 | 1.257 | 2.692 |
| advisory-warnings | 1.265 | 1.259 | 1.370 |

Target: < 100 ms per evaluation. Slowest observed run: 2.692 ms.
