# ctxlint

**ESLint for the context your AI agent reads.**

[English](README.md) · [Bahasa Indonesia](README.id.md)

Your coding agent loads rule files before it touches a line of code: `AGENTS.md`, `CLAUDE.md`, `.cursor/rules`, `.clinerules`, `SKILL.md`. Those files drift. Folders get renamed, scripts get deleted, the same rule ends up copy-pasted into five files, and one file grows to 7k tokens that get re-sent on every single run.

The agent does not know any of that is wrong. It reads the stale rule and confidently follows it.

`ctxlint` reads those files instead, and tells you what is broken, dead, duplicated or too expensive — before your agent wastes a run on it.

```
$ ctxlint --agent hermes
skills/agent-visualization/SKILL.md:65   error  broken-ref  references `references/pixel-character-sprites.md` which does not exist
skills/office/SKILL.md:236               error  broken-ref  references `scripts/office/soffice.py` which does not exist
skills/market-analysis/SKILL.md:1        warn   cost     ~7110 tokens loaded every run (budget 4000)
skills/market-analysis/SKILL.md:129      warn   duplicate  same rule also in skills/xauusd-analysis/SKILL.md:41
skills/ui-ux-pro-max/SKILL.md:1          info   trigger    description should start with 'Use when ...'

context: 78 files, ~278950 tokens/run  ·  11 error, 31 warn  ·  score 36/100
```

Exit code is `1` when there is at least one error, so it drops straight into CI.

## Why

Because this is where the bugs actually are, measured, not guessed. Open issue counts across popular agent tooling:

| repo | `context` | `memory` | `token cost` | `observability` |
|---|---|---|---|---|
| Aider-AI/aider | 340 | 32 | 95 | 3 |
| cline/cline | 239 | 71 | 35 | 1 |
| langchain-ai/langchain | 225 | 53 | 37 | 26 |
| microsoft/autogen | 193 | 67 | 29 | 22 |

Context/state issues outnumber observability issues by 10-100x. The trace-viewer market (LangSmith, Langfuse, Phoenix, Braintrust) is already well served; nobody owns "what the agent actually reads, and is it still true".

Supporting evidence:

- Stack Overflow Developer Survey 2025: **66%** of developers say the biggest AI frustration is output that is "almost right, but not quite"; **45%** say debugging AI-generated code takes longer.
- Empirical study of agent questions on Stack Overflow (arXiv 2510.25423): observability is only **11.6%** of agent problems, while tool-use coordination and configuration are **23%**.
- Recurring issue titles in the wild: *"Cline auto compacts context silently"*, *"Clinerules are completely ignored"*, *"Checkpoint restore fails after internal continuations"*, *"1M context capped at 128K"*.

A linter cannot fix the model. It can stop you from feeding it lies for free.

## Install

Not on PyPI yet — clone it:

```bash
git clone https://github.com/Mutiaacode/ctxlint
pipx install ./ctxlint          # or: uv tool install ./ctxlint
# no pipx? just run it directly:
python3 ctxlint/ctxlint.py --help
```

Python 3.10+. No dependencies. No network calls. No API key.

## Usage

```bash
ctxlint                          # lint the repo in the current directory
ctxlint path/to/repo             # lint another repo
ctxlint --agent hermes           # lint ~/.hermes/skills + ~/.hermes/memories
ctxlint --quiet                  # errors only (good for CI)
ctxlint --json                   # machine readable (good for scripts/editors)
ctxlint --ignore stale,cost      # skip noisy rules
ctxlint --max-tokens 6000        # per-file token budget (default 4000)
ctxlint --max-days 90            # staleness threshold via git (default 180)
ctxlint --selftest               # run the built-in assertions
```

Silence one specific line with a trailing comment:

```markdown
- Config lives in `config/app.yaml` <!-- ctxlint-ignore -->
```

## What it checks

| code | level | meaning |
|---|---|---|
| `broken-ref` | error | a shipped path (`references/x.md`, `scripts/y.py`) does not exist |
| `broken-ref` | info | a bare or contextual path is missing — may be illustrative prose |
| `duplicate` | warn | the same rule is written in more than one file |
| `stale` | warn | file untouched for N days according to git — verify it still matches |
| `cost` | warn | file exceeds the per-run token budget |
| `trigger` | info | skill `description` does not start with "Use when ..." — ambiguous trigger |
| `pruned` | error | `[SKILL_PRUNED]` placeholder left in a skill body |
| `budget` | warn | memory file over its char soft limit, no room left |

Severity is calibrated by confidence: only paths the file claims to *ship* are errors. A `package.json` mentioned mid-sentence is prose, not a defect.

## Works with

Repo layout: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `CONTEXT.md`, `.cursorrules`, `.windsurfrules`, `.clinerules`, `.rules`, `.aider.conf.yml`, `.github/copilot-instructions.md`, `.github/instructions/*.md`, `.cursor/rules/*`, `.claude/**/*.md`, `skills/**/SKILL.md`.

Hermes layout (`--agent hermes`): `~/.hermes/skills/**/SKILL.md`, `~/.hermes/memories/*.md`, `~/.hermes/AGENTS.md`, `~/.hermes/SOUL.md`.

Adding another layout is one function in `discover()`.

## CI

```yaml
name: ctxlint
on: [push, pull_request]
jobs:
  ctxlint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }   # stash depth needed for the staleness check
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: python3 ctxlint.py --quiet .
```

## Benefits

- **Fewer wasted runs.** A broken reference is a wrong instruction the agent obeys instantly. Cheapest possible fix: catch it in a linter instead of in a failed task.
- **Cheaper prompts.** Context files are re-sent on every request. Trimming 7k tokens of stale rules off a 5-request task is real money, every single day.
- **One repo, many agents.** Five agents read five different rule files. `duplicate` shows you which rules have already drifted apart, so you fix the source, not the symptom.

## Design principles

- No model calls, no network, no telemetry — it runs in a sandbox and in CI.
- No dependencies, one file, stdlib only.
- Familiar shape (like `eslint`/`ruff`): table output, rule codes, `--ignore`, exit codes.
- Rules must be checkable facts, not tastes. Anything subjective ships as `info`.

## Roadmap / non-goals

Planned: `--fix` for safe rewrites (move duplicated rules to one file), a `ctxsync` mode that generates one canonical rule file for every agent, MCP config checks (duplicate servers, dead commands), SARIF output, secret scanning, and conflict-polarity detection (two skills giving opposite orders).

Not planned: another trace viewer, an eval platform, a dashboard, a framework.

## Contributing

Each rule is one function in `ctxlint.py`: take a `CtxFile`, return `Finding`s. Add it to `analyze()`, add a fixture to `--selftest`, run:

```bash
python3 ctxlint.py --selftest
```

Calibrate every new rule against a big real corpus first. A rule that fires on healthy repos is worse than no rule.

## License

MIT. Built by [mutiadev](https://github.com/Mutiaacode).
