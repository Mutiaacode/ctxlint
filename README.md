# ctxlint

**A checker for the instruction files your AI coding agent reads.**

[English](README.md) · [Bahasa Indonesia](README.id.md)

[![CI](https://github.com/Mutiaacode/ctxlint/actions/workflows/ctxlint.yml/badge.svg)](https://github.com/Mutiaacode/ctxlint/actions/workflows/ctxlint.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://github.com/Mutiaacode/ctxlint/blob/master/pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen)](https://github.com/Mutiaacode/ctxlint/blob/master/.pre-commit-hooks.yaml)
[![dependencies: none](https://img.shields.io/badge/dependencies-none-lightgrey)](pyproject.toml)

## In one minute

Before your agent writes any code, it reads instruction files: `AGENTS.md`, `CLAUDE.md`, `.cursor/rules`, `.clinerules`, `SKILL.md`. That is where you tell it "run tests with `npm test`" or "the API lives in `src/api/v2`".

Then the code moves on. A folder gets renamed, a script gets deleted, a rule gets copied into five files, one file grows to 7000 tokens. The instruction files do not get updated.

The agent has no way to know. It reads the old instruction and follows it exactly. You get a wrong result and blame the model.

`ctxlint` reads those files and tells you which ones are out of date, which point at things that no longer exist, which repeat each other, and which are too big. One command, a table of problems, a score.

```
$ ctxlint --agent hermes
skills/agent-visualization/SKILL.md:65   error  broken-ref  references `references/pixel-character-sprites.md` which does not exist
skills/office/SKILL.md:236               error  broken-ref  references `scripts/office/soffice.py` which does not exist
skills/market-analysis/SKILL.md:1        warn   cost        ~7110 tokens loaded every run (budget 4000)
skills/market-analysis/SKILL.md:129      warn   duplicate   same rule also in skills/xauusd-analysis/SKILL.md:41
skills/ui-ux-pro-max/SKILL.md:1          info   trigger     description should start with 'Use when ...'

context: 78 files, ~278950 tokens/run  ·  11 error, 31 warn  ·  score 36/100
```

If there is at least one error, the exit code is `1`, so CI can block a bad change.

## Why this exists

We did not guess where the problems are. We counted them. Open issues in popular agent tools:

| repo | `context` | `memory` | `token cost` | `observability` |
|---|---|---|---|---|
| Aider-AI/aider | 340 | 32 | 95 | 3 |
| cline/cline | 239 | 71 | 35 | 1 |
| langchain-ai/langchain | 225 | 53 | 37 | 26 |
| microsoft/autogen | 193 | 67 | 29 | 22 |

Problems about context and state are 10 to 100 times more common than problems about watching an agent run. Tools for watching already exist and are good. Nobody looks after what the agent is actually told.

More evidence:

- Stack Overflow Developer Survey 2025: **66%** of developers say their biggest AI frustration is output that is "almost right, but not quite", and **45%** say debugging AI-written code takes longer.
- A study of agent questions on Stack Overflow (arXiv 2510.25423) found observability is only **11.6%** of agent problems; tool coordination and configuration make up **23%**.
- Issue titles that keep coming back: *"Cline auto compacts context silently"*, *"Clinerules are completely ignored"*, *"Checkpoint restore fails after internal continuations"*.

A linter cannot make the model smarter. It can stop you from feeding it wrong information for free.

## Install

Needs Python 3.10 or newer. Nothing else — no dependencies, no internet, no API key.

```bash
# one command, isolated environment, no clone
uv tool install git+https://github.com/Mutiaacode/ctxlint
pipx install git+https://github.com/Mutiaacode/ctxlint

# or plain pip, inside a venv
python3 -m pip install git+https://github.com/Mutiaacode/ctxlint

# or skip installing entirely
python3 ctxlint.py --help
```

Verify:

```bash
ctxlint --version     # ctxlint 0.1.1
```

### As a pre-commit hook

```yaml
repos:
  - repo: https://github.com/Mutiaacode/ctxlint
    rev: v0.1.1
    hooks: [{ id: ctxlint }]
```

## Usage

```bash
ctxlint                          # check the repo you are in
ctxlint path/to/repo             # check another repo
ctxlint --agent hermes           # check ~/.hermes/skills and ~/.hermes/memories
ctxlint --quiet                  # errors only, best for CI
ctxlint --json                   # machine readable output
ctxlint --format sarif           # SARIF 2.1.0 for GitHub code scanning
ctxlint --format markdown        # table you can paste into a PR comment
ctxlint --ignore stale,cost      # skip checks that are too noisy for you
ctxlint --max-tokens 6000        # per-file token budget (default 4000)
ctxlint --max-days 90            # how old is "stale" (default 180)
ctxlint --selftest               # run the built-in tests
ctxlint --list-checks            # print every check and exit
```

To skip one line, add a comment at the end of it:

```markdown
- Config lives in `config/app.yaml` <!-- ctxlint-ignore -->
```

## What it checks

| code | level | what it means |
|---|---|---|
| `broken-ref` | error | the file points at something it claims to ship (`references/x.md`, `scripts/y.py`) and that thing is gone |
| `broken-ref` | info | a path mentioned in passing is not found — may just be an example |
| `duplicate` | warn | the same rule is written in more than one file |
| `stale` | warn | git says the file has not changed in N days, so it may no longer match the code |
| `cost` | warn | the file is larger than the token budget, and it is sent on every run |
| `trigger` | info | a skill description does not start with "Use when ...", so the trigger is unclear |
| `pruned` | error | a `[SKILL_PRUNED]` placeholder was left inside a skill body |
| `budget` | warn | a memory file is full, with no room left for new facts |
| `secret` | error | a token or private key is committed in a context file |

Why the same code has two levels: a path the file says it ships is a fact we can check, so it is an error. A `package.json` mentioned in the middle of a sentence might only be an example, so it is `info`.

## Works with

Repo layout: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `CONTEXT.md`, `.cursorrules`, `.windsurfrules`, `.clinerules`, `.rules`, `.aider.conf.yml`, `.github/copilot-instructions.md`, `.github/instructions/*.md`, `.cursor/rules/*`, `.claude/**/*.md`, `skills/**/SKILL.md`.

Hermes layout (`--agent hermes`): `~/.hermes/skills/**/SKILL.md`, `~/.hermes/memories/*.md`, `~/.hermes/AGENTS.md`, `~/.hermes/SOUL.md`.

Supporting another layout takes one function in `discover()`.

## CI

Copy [`.github/workflows/ctxlint.yml`](.github/workflows/ctxlint.yml), or start from the short version:

```yaml
name: ctxlint
on: [push, pull_request]
jobs:
  ctxlint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }   # the staleness check needs git history
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: python3 ctxlint.py --quiet .
```

`--format sarif` plus `github/codeql-action/upload-sarif` puts findings in the repo's Security → Code scanning tab instead of only the job log.

## What you get

- **Fewer wasted runs.** A broken reference is a wrong instruction the agent obeys instantly. Catching it in a linter is much cheaper than catching it after a failed task.
- **Lower token cost.** Context files are sent again with every request. Cutting 7000 tokens of stale rules from a five-request task saves real money, every day.
- **One repo, many agents.** Five agents read five different rule files. `duplicate` shows you which rules have already drifted apart, so you fix the source instead of the symptom.

## What it will not do

- It will not call a model. No network, no telemetry, no API key. It runs in CI and in a sandbox.
- It will not have dependencies. One file, standard library only.
- It will not guess. Checks report things that can be verified. Anything subjective is marked `info` and never fails a build.

## Roadmap

Planned: `--fix` for safe rewrites (move a duplicated rule into one file), a `ctxsync` mode that writes one shared rule file for every agent, checks for MCP configs (duplicate servers, dead commands), conflict detection (two skills giving opposite orders), MCP config checks, near-clone detection.

Not planned: another trace viewer, an eval platform, a dashboard, a framework.

## Contributing

Every check is one function in `ctxlint.py`: it takes a `CtxFile` and returns `Finding`s. Add it to `analyze()`, add a fixture to `--selftest`, then run:

```bash
python3 ctxlint.py --selftest
```

Test any new check against a big real collection of files first. A check that fires on healthy repos is worse than no check at all.

## License

MIT. Built by [mutiadev](https://github.com/Mutiaacode).
