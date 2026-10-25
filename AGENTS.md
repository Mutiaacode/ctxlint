# AGENTS.md

Instructions for AI coding agents working in this repo.

## Rules

- Python 3.10+ stdlib only. No new dependencies, no network calls, no telemetry.
- One file: `ctxlint.py`. Do not split it into a package.
- Every new rule needs a fixture in `--selftest`, and `python3 ctxlint.py --selftest` must pass.
- Calibrate new rules against a large real corpus before opening a PR. False positives are worse than missing features.
- Severity by confidence: only paths a file claims to ship (`references/`, `scripts/`, `assets/`, `templates/`) are errors. Everything contextual is `info`.
- Keep the CLI additive. Existing flags and exit codes are a contract.
- README numbers must stay verifiable; cite the source inline.
