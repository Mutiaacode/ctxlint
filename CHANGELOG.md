# Changelog

All notable changes to this project. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

First working release.

### Added
- Discovery for repo layouts: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `CONTEXT.md`,
  `.cursorrules`, `.windsurfrules`, `.clinerules`, `.rules`, `.aider.conf.yml`,
  `.github/copilot-instructions.md`, `.github/instructions/*.md`, `.cursor/rules/*`,
  `.claude/**/*.md`, `skills/**/SKILL.md`.
- Discovery for the Hermes layout via `--agent hermes` (also auto-detected).
- Checks: `broken-ref`, `duplicate`, `stale`, `cost`, `trigger`, `pruned`, `budget`, `secret`.
- Output formats: table (default), `--json`, `--format markdown`, `--format sarif` (2.1.0).
- `--ignore`, `--quiet`, `--max-tokens`, `--max-days`, `--memory-limit`, `--list-checks`.
- Inline suppression per line with `<!-- ctxlint-ignore -->`.
- Built-in assertions via `--selftest`.
- Installable as a console script: `ctxlint` on `PATH`, plus a pre-commit hook id.

### Notes
- Exit code `1` when at least one `error` is reported, `0` otherwise, `2` on usage error.
- Standard library only. No network, no telemetry, no model calls.
