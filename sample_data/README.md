# Sample data

Synthetic demonstration inputs and the reports the engine produces for them. No real
company is represented; see `DISCLAIMER.md`.

| Path | Contents |
|---|---|
| `companies/<scenario>/company_data.json` | Synthetic `CompanyData` inputs (manual-entry provenance). |
| `reports/<scenario>.{json,txt,html}` | Reports from the current ruleset (2.0.0). |
| `reports/ruleset-1.0.0/` | Historical reports from the superseded ruleset 1.0.0, kept so the change in outcomes can be compared. Do not rely on them. |
| `benchmark_results.md` | Engine timing (not extraction accuracy — that is in `docs/BENCHMARK_RESULTS.md`). |

Regenerate with:

```bash
.venv/bin/python scripts/demo.py --write-inputs --write-reports
.venv/bin/python scripts/benchmark.py
```

Real-document extraction is measured separately on public SEBI DRHPs (`benchmark/`).
