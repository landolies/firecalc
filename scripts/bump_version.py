#!/usr/bin/env python3
"""Bump the version + updated-on date in web/index.html.

Decides patch/minor/major from the staged file list and the in-progress
commit message, taking the higher of the two signals.

Message signals (Conventional Commits style, case-insensitive):
  - "BREAKING CHANGE" anywhere, or "<type>!:" prefix      -> major
  - "feat(...):" or "feat:"                               -> minor
  - "fix:", "chore:", "docs:", "refactor:", "test:",
    "style:", "perf:", "build:", "ci:"                    -> patch

Path signals (taken from `git diff --cached --name-only`):
  - SPEC.md changed                                       -> minor
  - engine_py/*.py (non-test) changed                     -> minor
  - everything else                                       -> patch

Run automatically by .githooks/pre-commit, or by hand:
  python3 scripts/bump_version.py [--dry-run] [--force=patch|minor|major]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INDEX = REPO / "web" / "index.html"

VERSION_RE = re.compile(
    r'(v)(\d+)\.(\d+)\.(\d+)( · updated )(\d{4}-\d{2}-\d{2})'
)

_RANK = {"patch": 0, "minor": 1, "major": 2}


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True)


def staged_files() -> list[str]:
    out = _git("diff", "--cached", "--name-only")
    return [line for line in out.splitlines() if line]


def commit_message() -> str:
    # Populated by `git commit -m` before pre-commit fires; absent for some
    # GUI clients. When missing we fall back to path-based heuristics only.
    p = REPO / ".git" / "COMMIT_EDITMSG"
    if not p.exists():
        return ""
    return p.read_text(errors="ignore")


def _msg_level(msg: str) -> str | None:
    m = msg.lower()
    if "breaking change" in m or re.search(r'^\w+!\s*:', m, re.MULTILINE):
        return "major"
    if re.search(r'^\s*feat\s*(\(|:)', m, re.MULTILINE):
        return "minor"
    if re.search(
        r'^\s*(fix|chore|docs|refactor|test|style|perf|build|ci)\s*(\(|:)',
        m, re.MULTILINE,
    ):
        return "patch"
    return None


def _path_level(files: list[str]) -> str:
    level = "patch"
    for f in files:
        if f == "SPEC.md":
            level = "minor"
        elif f.startswith("engine_py/") and "/tests/" not in f and f.endswith(".py"):
            level = "minor"
    return level


def decide_bump(files: list[str], msg: str, force: str | None) -> str:
    if force:
        return force
    msg_lvl = _msg_level(msg)
    path_lvl = _path_level(files)
    if msg_lvl is None:
        return path_lvl
    return msg_lvl if _RANK[msg_lvl] >= _RANK[path_lvl] else path_lvl


def bump(version: tuple[int, int, int], level: str) -> tuple[int, int, int]:
    major, minor, patch = version
    if level == "major":
        return (major + 1, 0, 0)
    if level == "minor":
        return (major, minor + 1, 0)
    return (major, minor, patch + 1)


def _is_substantive(files: list[str]) -> bool:
    # Bumping the version on a commit that *only* edits the bumper or the
    # version line itself would be circular noise.
    ignore_prefixes = (".githooks/", "scripts/bump_version")
    for f in files:
        if f == "web/index.html":
            continue
        if any(f.startswith(p) for p in ignore_prefixes):
            continue
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the decision without modifying the file.")
    ap.add_argument("--force", choices=["patch", "minor", "major"],
                    help="Override the auto-decided severity.")
    args = ap.parse_args()

    text = INDEX.read_text()
    m = VERSION_RE.search(text)
    if not m:
        print("bump_version: version pattern not found in web/index.html",
              file=sys.stderr)
        return 1

    cur = (int(m.group(2)), int(m.group(3)), int(m.group(4)))
    files = staged_files()

    if not args.force and not _is_substantive(files):
        print("bump_version: no substantive staged changes; skipping")
        return 0

    level = decide_bump(files, commit_message(), args.force)
    new = bump(cur, level)
    today = _dt.date.today().isoformat()

    new_text = VERSION_RE.sub(
        lambda mm: f"{mm.group(1)}{new[0]}.{new[1]}.{new[2]}{mm.group(5)}{today}",
        text, count=1,
    )

    cur_str = ".".join(map(str, cur))
    new_str = ".".join(map(str, new))
    print(f"bump_version: {cur_str} -> {new_str} ({level}), {today}")

    if args.dry_run or new_text == text:
        return 0

    INDEX.write_text(new_text)

    # When invoked from the pre-commit hook, re-stage so the bump rides along
    # with the user's commit. BUMP_RESTAGE is set by .githooks/pre-commit.
    if os.environ.get("BUMP_RESTAGE") == "1":
        subprocess.run(["git", "add", "web/index.html"], cwd=REPO, check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
