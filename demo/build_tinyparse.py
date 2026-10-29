"""Builds the fictional `tinyparse` demo repository as a real git repo.

History (all fictional test data):
  v1.0  initial release; INI parser has an off-by-one in the key copy (bug B)
  v1.1  fixes bug B
  v1.2  "fast path" refactor of the URL decoder drops a bounds check (bug A)

Usage: python demo/build_tinyparse.py <output_dir>
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent / "tinyparse"
AUTHOR = {
    "GIT_AUTHOR_NAME": "tinyparse maintainers",
    "GIT_AUTHOR_EMAIL": "maintainers@tinyparse.invalid",
    "GIT_COMMITTER_NAME": "tinyparse maintainers",
    "GIT_COMMITTER_EMAIL": "maintainers@tinyparse.invalid",
}
LONG_KEY_TEST = "test_ini_long_key_truncated"


def git(repo: Path, *args: str, date: str | None = None) -> str:
    env = {**os.environ, **AUTHOR}
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env
    ).stdout


def write_tree(repo: Path, version: str) -> None:
    """Writes base files, then version overrides (v1.0 also gets v1.1's)."""
    for path in repo.iterdir():
        if path.name != ".git":
            shutil.rmtree(path) if path.is_dir() else path.unlink()
    shutil.copytree(HERE / "base", repo, dirs_exist_ok=True)
    layers = {"v1.0": ["v1.1", "v1.0"], "v1.1": ["v1.1"], "v1.2": []}[version]
    for layer in layers:
        shutil.copytree(HERE / layer, repo, dirs_exist_ok=True)

    header = repo / "include/tinyparse.h"
    header.write_text(header.read_text().replace('"1.2.0"', f'"{version[1:]}.0"'))

    if version == "v1.0":
        # The long-key regression test arrived together with the v1.1 fix.
        tests = repo / "tests/test_main.c"
        lines = [l for l in tests.read_text().splitlines(keepends=True) if f"RUN({LONG_KEY_TEST})" not in l]
        text = "".join(lines)
        start = text.index(f"static void {LONG_KEY_TEST}")
        end = text.index("static void", start + 10)
        tests.write_text(text[:start] + text[end:])
    # v1.0 and v1.1 had no "+ as space" option docs in README; keep README identical for simplicity.


def commit(repo: Path, message: str, date: str) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message, date=date)


def build(out: Path) -> Path:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    git(out, "init", "-q", "-b", "main")

    write_tree(out, "v1.0")
    commit(out, "tinyparse 1.0: URL decoding, INI parsing, string helpers", "2026-03-02T10:00:00Z")
    git(out, "tag", "-a", "v1.0", "-m", "tinyparse 1.0", date="2026-03-02T10:00:00Z")

    write_tree(out, "v1.1")
    # Split v1.1 into the fix commit and a hardening commit for a realistic history.
    commit(
        out,
        "ini: fix off-by-one when truncating long keys (#12)\n\n"
        "A key of TP_INI_MAX_KEY or more bytes wrote the terminating NUL one byte\n"
        "past the end of the key buffer. Truncate to TP_INI_MAX_KEY - 1 instead and\n"
        "add a regression test. Also make the URL decoder bounds check explicit.",
        "2026-05-11T09:30:00Z",
    )
    git(out, "tag", "-a", "v1.1", "-m", "tinyparse 1.1\n\nSecurity: fixes INI key off-by-one (#12)", date="2026-05-11T09:30:00Z")

    write_tree(out, "v1.2")
    commit(
        out,
        "url: fast path for percent escapes\n\nDecode the escape in a single branch instead of two lookups.",
        "2026-08-19T14:15:00Z",
    )
    git(out, "tag", "-a", "v1.2", "-m", "tinyparse 1.2", date="2026-08-19T14:15:00Z")
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "data/repos/tinyparse").resolve()
    build(target)
    print(f"built {target}")
    print(git(target, "log", "--oneline", "--decorate"))
