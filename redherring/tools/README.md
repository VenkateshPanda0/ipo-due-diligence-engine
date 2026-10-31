# tools/

Labelling and release helpers (not part of the installed package).

| File | Use |
|---|---|
| `gate.sh` | format, lint, type-check, test; exit status is the result. Run `tools/gate.sh && git commit ...`; never pipe it. |
| `pg.py` | read a filing as poppler text: `page N`, and `grep REGEX` which prints every hit |
| `label_build.py` | build `labels/DOC.json` from a spec of printed values; `--audit-absent` lists every line that could contradict an "absent" label |
| `diff_eval.py` | after `rh analyze`, print only the misses: abstentions, wrong values, inventions |

Labelling procedure (D-021, D-034, D-037): commit the labels before running the extractor; read
every "absent" label against the `--audit-absent` output; keep a set held out unless a defect it
exposed was fixed.
