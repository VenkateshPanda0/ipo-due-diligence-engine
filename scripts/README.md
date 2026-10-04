# Scripts

| Script | What it does |
|---|---|
| `benchmark_extraction.py` | Real-DRHP extraction benchmark: `--download` fetches and verifies the PDFs in `benchmark/manifest.json`; `--run [--split all\|development\|holdout] [--ocr on\|off] [--no-write]` scores the pipeline against `benchmark/ground_truth/` and writes `docs/BENCHMARK_RESULTS.md`. See `docs/BENCHMARK.md`. |
| `demo.py` | Runs synthetic sample companies through the rules engine. `--write-inputs --write-reports` regenerates `sample_data/`. |
| `benchmark.py` | Times the deterministic engine (CompanyData → report) and writes `sample_data/benchmark_results.md`. |

Run them from the repository root with the project virtualenv, e.g.
`.venv/bin/python scripts/demo.py --write-reports`.

The UI screenshots in `docs/images/` are produced by
`frontend/scripts/screenshots.mjs` (needs both servers running; see the README).
