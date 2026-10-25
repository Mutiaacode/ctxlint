#!/usr/bin/env python3
"""ctxlint — ESLint for the context your AI agent reads.

Zero dependencies, no network, no model calls. Reads the rule/context files an
agent loads (AGENTS.md, CLAUDE.md, Cursor rules, Hermes skills, memory files)
and reports the ones that are broken, stale, duplicated or expensive.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

VERSION = "0.1.0"

# ---------------------------------------------------------------- file discovery

REPO_NAMES = [
    "AGENTS.md", "CLAUDE.md", "GEMINI.md", "CONTEXT.md", ".cursorrules",
    ".windsurfrules", ".clinerules", ".rules", ".aider.conf.yml",
    ".github/copilot-instructions.md",
]
REPO_GLOBS = [
    "skills/*/SKILL.md", "skills/*/*/SKILL.md", ".cursor/rules/*.mdc",
    ".cursor/rules/*.md", ".claude/**/*.md", ".github/instructions/*.md",
    "docs/agents/*.md", ".ai/**/*.md",
]

FILE_EXT = (r"py|sh|bash|md|json|ya?ml|js|mjs|cjs|ts|tsx|jsx|toml|db|sqlite|"
            r"csv|xlsx|xlsm|service|conf|cfg|ini|txt|html|css|scss|php|go|rs|"
            r"java|kt|swift|rb|ipynb|lock|env|sql")
BACKTICK_RE = re.compile(r"`([^`\n]+)`")
REF_RE = re.compile(r"^(?:~|\.{1,2}/|/)?[\w.@/-]*[\w-]\.(?:" + FILE_EXT + r")$")
SKIP_REF_CHARS = set("{}<>*$|%()[]\"'=,;")
BARE_REFS = {"py", "sh", "bash", "mjs", "cjs", "service", "sql", "db"}
# paths a skill/doc claims to ship with itself — checkable, so high confidence
SHIPPED_PREFIX = ("references/", "scripts/", "assets/", "templates/", "./", "../")

# ---------------------------------------------------------------- model

@dataclass
class CtxFile:
    path: Path
    root: Path          # resolution root for reference checks
    text: str
    kind: str = "context"   # context | skill | memory
    lines: list = field(default_factory=list)

@dataclass(order=True)
class Finding:
    path: str
    line: int
    level: str          # error | warn | info
    code: str
    msg: str
    sort_key: tuple = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        self.sort_key = (self.path, self.line, self.level)

STARS = {"error": "error", "warn": "warn ", "info": "info "}

def tok(text: str) -> int:
    return max(1, round(len(text) / 4))

# ---------------------------------------------------------------- discovery

DOT_DIRS = {".cursor", ".claude", ".github", ".ai"}  # legitimate context locations

def _hidden(p: Path, root: Path) -> bool:
    parts = p.relative_to(root).parts[:-1]
    return any(part.startswith(".") and part not in DOT_DIRS for part in parts)

def discover(target: Path, agent: str) -> list[CtxFile]:
    files: list[CtxFile] = []
    seen = set()

    def add(p: Path, root: Path, kind: str):
        try:
            rp = p.resolve()
        except OSError:
            return
        if rp in seen or not p.is_file():
            return
        seen.add(rp)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        files.append(CtxFile(p, root, text, kind, text.splitlines()))

    if agent == "hermes":
        home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
        skills = home / "skills"
        if skills.is_dir():
            for p in sorted(skills.rglob("SKILL.md")):
                if not _hidden(p, skills):
                    add(p, p.parent, "skill")
        mem = home / "memories"
        if mem.is_dir():
            for p in sorted(mem.glob("*.md")):
                add(p, mem, "memory")
        for name in ("AGENTS.md", "SOUL.md"):
            if (home / name).is_file():
                add(home / name, home, "context")
        return files

    for name in REPO_NAMES:
        add(target / name, target, "context")
    for pattern in REPO_GLOBS:
        for p in sorted(target.glob(pattern)):
            if _hidden(p, target):
                continue
            kind = "skill" if p.name == "SKILL.md" else "context"
            root = p.parent if kind == "skill" else target
            add(p, root, kind)
    return files

# ---------------------------------------------------------------- checks

def frontmatter(lines: list[str]) -> dict:
    if not lines or lines[0].strip() != "---":
        return {}
    out = {}
    for ln in lines[1:]:
        if ln.strip() == "---":
            break
        if ":" in ln and not ln.startswith((" ", "\t")):
            k, v = ln.split(":", 1)
            out[k.strip()] = v.strip().strip('"\'')
    return out

def check_refs(f: CtxFile, ignore: set[str]) -> list[Finding]:
    if "ref-mati" in ignore:
        return []
    found, seen = [], set()
    for i, line in enumerate(f.lines, 1):
        if "ctxlint-ignore" in line:
            continue
        for m in BACKTICK_RE.finditer(line):
            ref = m.group(1).strip()
            if (not REF_RE.match(ref) or any(c in ref for c in SKIP_REF_CHARS)
                    or "://" in ref or len(ref) < 4 or ref in seen):
                continue
            seen.add(ref)
            # ponytail: bare doc/data filenames are usually illustrative prose
            # (package.json, MASTER.md). Only executable-ish bare names are refs.
            if "/" not in ref and ref.rsplit(".", 1)[-1] not in BARE_REFS:
                continue
            if ref.startswith(("/tmp", "/var", "C:", "~/tmp")):
                continue
            p = Path(ref).expanduser()
            cands = [p, f.root / ref, f.root.parent / ref, Path.cwd() / ref]
            if any(c.exists() for c in cands):
                continue
            level = "error" if ref.startswith(SHIPPED_PREFIX) else "info"
            found.append(Finding(str(f.path), i, level, "ref-mati",
                                 f"references `{ref}` which does not exist"))
    return found

DUPE_MIN = 30
DUPE_SKIP = ("--", "==", "|", "```", "curl ", "http://", "https://", "$ ")

def norm_rule(line: str) -> str:
    s = line.strip().lstrip("#-*+0123456789. ").strip().lower()
    s = re.sub(r"[`*_\"']", "", s)
    s = re.sub(r"\s+", " ", s).rstrip(".:;")
    return s

def check_dupes(files: list[CtxFile], ignore: set[str]) -> list[Finding]:
    if "duplikat" in ignore:
        return []
    index: dict[str, list[tuple[str, int]]] = {}
    for f in files:
        for i, line in enumerate(f.lines, 1):
            if len(line.strip()) < DUPE_MIN or any(t in line for t in DUPE_SKIP):
                continue
            k = norm_rule(line)
            if len(k) < DUPE_MIN:
                continue
            index.setdefault(k, []).append((str(f.path), i))
    out = []
    for _, hits in index.items():
        paths = {p for p, _ in hits}
        if len(paths) < 2:
            continue
        out.append(Finding(hits[0][0], hits[0][1], "warn", "duplikat",
                           "same rule also in " + ", ".join(
                               f"{p}:{l}" for p, l in hits[1:4])))
    return out

def git_mtime_days(path: Path) -> int | None:
    try:
        r = subprocess.run(
            ["git", "-C", str(path.parent), "log", "-1", "--format=%ct", "--", str(path)],
            capture_output=True, text=True, timeout=5)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        import time
        return int((time.time() - int(r.stdout.strip())) / 86400)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None

def check_stale(f: CtxFile, ignore: set[str], max_days: int) -> list[Finding]:
    if "basi" in ignore:
        return []
    d = git_mtime_days(f.path)
    if d is not None and d > max_days:
        return [Finding(str(f.path), 1, "warn", "basi",
                        f"unchanged for {d} days — verify it still matches the code")]
    return []

def check_cost(f: CtxFile, ignore: set[str], budget: int) -> list[Finding]:
    if "biaya" in ignore:
        return []
    n = tok(f.text)
    if n > budget:
        return [Finding(str(f.path), 1, "warn", "biaya",
                        f"~{n} tokens loaded every run (budget {budget})")]
    return []

def check_skill(f: CtxFile, ignore: set[str]) -> list[Finding]:
    out = []
    if "[SKILL_PRUNED]" in f.text and "pruned" not in ignore:
        ln = next(i for i, l in enumerate(f.lines, 1) if "[SKILL_PRUNED]" in l)
        out.append(Finding(str(f.path), ln, "error", "pruned",
                           "[SKILL_PRUNED] placeholder — skill body was lost, reload needed"))
    fm = frontmatter(f.lines)
    if "pemicu" not in ignore:
        d = fm.get("description", "")
        if not d:
            out.append(Finding(str(f.path), 1, "error", "pemicu",
                               "frontmatter has no description — agent cannot know when to load it"))
        elif not re.match(r"(use when|use for|use this|load when|when the user)", d.lower()):
            out.append(Finding(str(f.path), 1, "info", "pemicu",
                               "description should start with 'Use when ...' so the trigger is unambiguous"))
    return out

def check_memory(f: CtxFile, ignore: set[str], limit: int) -> list[Finding]:
    if "budget" in ignore or len(f.text) <= limit:
        return []
    return [Finding(str(f.path), 1, "warn", "budget",
                    f"{len(f.text)} chars (soft limit {limit}) — no room left for new facts, consolidate")]

# ---------------------------------------------------------------- report

def analyze(target: Path, agent: str, ignore: set[str], max_tokens: int,
            max_days: int, memory_limit: int) -> tuple[list[Finding], list[CtxFile]]:
    files = discover(target, agent)
    out: list[Finding] = []
    for f in files:
        out += check_refs(f, ignore)
        out += check_cost(f, ignore, max_tokens)
        out += check_stale(f, ignore, max_days)
        if f.kind == "skill":
            out += check_skill(f, ignore)
        if f.kind == "memory":
            out += check_memory(f, ignore, memory_limit)
    out += check_dupes(files, ignore)
    order = {"error": 0, "warn": 1, "info": 2}
    return sorted(out, key=lambda f: (f.path, order[f.level], f.line)), files

def score(findings: list[Finding]) -> int:
    pen = sum(3 if f.level == "error" else 1 for f in findings if f.level != "info")
    return max(0, 100 - pen)

def report(findings, files, as_json, quiet, target) -> int:
    total_tok = sum(tok(f.text) for f in files)
    sc = score(findings)
    if as_json:
        print(json.dumps({
            "version": VERSION, "score": sc, "files": len(files),
            "tokens": total_tok,
            "findings": [{"path": p, "line": l, "level": lv, "code": c, "message": m}
                         for p, l, lv, c, m in
                         [(f.path, f.line, f.level, f.code, f.msg) for f in findings]],
        }, indent=2))
        return 1 if any(f.level == "error" for f in findings) else 0

    shown = [f for f in findings if not quiet or f.level == "error"]
    for f in shown:
        rel = os.path.relpath(f.path, Path.cwd())
        print(f"{rel}:{f.line}".ljust(44) + f" {STARS[f.level]}  {f.code:<9} {f.msg}")

    errs = sum(f.level == "error" for f in findings)
    warns = sum(f.level == "warn" for f in findings)
    if shown:
        print()
    print(f"context: {len(files)} files, ~{total_tok} tokens/run  ·  "
          f"{errs} error, {warns} warn  ·  score {sc}/100")
    if not findings:
        print("clean — nothing to fix")
    return 1 if errs else 0

# ---------------------------------------------------------------- selftest

def selftest() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "src").mkdir()
        (root / "AGENTS.md").write_text(
            "- Always run `npm test` before commit\n"
            "- API lives in `src/api/v2/routes.py`\n"
            "- Never use tabs, always two spaces for indentation\n")
        (root / "CLAUDE.md").write_text(
            "- Never use tabs, always two spaces for indentation\n")
        sk = root / "skills" / "demo"
        sk.mkdir(parents=True)
        (sk / "SKILL.md").write_text(
            "---\nname: demo\n---\nbody [SKILL_PRUNED]\nsee `scripts/run.py`\n"
            "and `references/deep.md`\n")
        findings, files = analyze(root, "repo", set(), 2000, 10_000, 2000)
        codes = {f.code for f in findings}
        assert "ref-mati" in codes, codes
        assert "duplikat" in codes, codes
        assert "pemicu" in codes, codes
        assert "pruned" in codes, codes
        hi = [f for f in findings if f.code == "ref-mati" and f.level == "error"]
        assert hi, "shipped-path refs must be errors, not info"
        assert score(findings) < 100
        assert len(files) == 3, len(files)
        # clean tree stays clean
        for p in root.rglob("*.md"):
            p.unlink()
        (root / "AGENTS.md").write_text("- Use pnpm, not npm\n")
        f2, _ = analyze(root, "repo", set(), 2000, 10_000, 2000)
        assert f2 == [], f2
    print("selftest ok")
    return 0

# ---------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="ctxlint", description="Lint the context your AI agent reads.")
    ap.add_argument("path", nargs="?", default=".", help="repo root (default: .)")
    ap.add_argument("--agent", default="auto", choices=["auto", "repo", "hermes"],
                    help="which context layout to scan (default: auto)")
    ap.add_argument("--json", action="store_true", help="machine readable output")
    ap.add_argument("--quiet", action="store_true", help="only errors")
    ap.add_argument("--ignore", default="", help="comma separated rule codes to skip")
    ap.add_argument("--max-tokens", type=int, default=4000,
                    help="per-file token budget (default: 4000)")
    ap.add_argument("--max-days", type=int, default=180,
                    help="flag context untouched for N days (default: 180)")
    ap.add_argument("--memory-limit", type=int, default=2000,
                    help="char soft limit for memory files (default: 2000)")
    ap.add_argument("--version", action="version", version=f"ctxlint {VERSION}")
    ap.add_argument("--selftest", action="store_true", help="run built-in assertions")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()

    target = Path(a.path).expanduser()
    if not target.is_dir():
        print(f"ctxlint: not a directory: {target}", file=sys.stderr)
        return 2

    agent = a.agent
    if agent == "auto":
        agent = "hermes" if (Path.home() / ".hermes" / "skills").is_dir() and \
            target.resolve() in ((Path.home() / ".hermes").resolve(),
                                 (Path.home() / ".hermes" / "skills").resolve()) else "repo"

    ignore = {c.strip() for c in a.ignore.split(",") if c.strip()}
    findings, files = analyze(target, agent, ignore, a.max_tokens, a.max_days, a.memory_limit)
    if not files:
        print(f"ctxlint: no context files found in {target} (agent={agent})", file=sys.stderr)
        return 0
    return report(findings, files, a.json, a.quiet, target)

if __name__ == "__main__":
    sys.exit(main())
