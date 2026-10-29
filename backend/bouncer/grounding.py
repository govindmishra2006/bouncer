"""Stage 2: ground every claim in the actual repository using git.

Checks, per claim:
  * files and functions exist at the claimed version, or at any tag / commit;
  * quoted code appears (fuzzy, whitespace-insensitive) at the claimed version or elsewhere;
  * cited line numbers fall inside the named function, and what is actually there;
  * if quoted code existed only in older versions, `git log -S` finds the commit that removed it.

Every result carries the exact git command that proves it, so a maintainer can re-run it.
"""
from __future__ import annotations

import difflib
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .extract import Claims

SOURCE_GLOBS = ("*.c", "*.h", "*.py", "*.cc", "*.cpp")


@dataclass
class Check:
    kind: str  # file | function | quoted_code | line | version
    claim: str
    status: str  # verified | false | moved | unverifiable
    detail: str
    command: str
    hard_falsehood: bool = False
    data: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class Grounding:
    resolved_version: str | None
    version_note: str
    checks: list[Check]
    fixed_in: dict | None  # {"commit", "tag", "subject"} when the claimed code was already changed

    @property
    def hard_falsehoods(self) -> list[Check]:
        return [c for c in self.checks if c.hard_falsehood]

    @property
    def grounded_targets(self) -> list[Check]:
        return [c for c in self.checks if c.kind in ("function", "file", "quoted_code") and c.status == "verified"]

    def as_dict(self) -> dict:
        return {
            "resolved_version": self.resolved_version,
            "version_note": self.version_note,
            "checks": [c.as_dict() for c in self.checks],
            "fixed_in": self.fixed_in,
        }


class Repo:
    def __init__(self, path: Path):
        self.path = path

    def git(self, *args: str, check: bool = False) -> str:
        res = subprocess.run(["git", "-C", str(self.path), *args], capture_output=True, text=True)
        if check and res.returncode != 0:
            raise RuntimeError(res.stderr.strip())
        return res.stdout

    def tags(self) -> list[str]:
        return [t for t in self.git("tag", "--sort=v:refname").split() if t]

    def files_at(self, ref: str) -> list[str]:
        return [f for f in self.git("ls-tree", "-r", "--name-only", ref).splitlines() if f]

    def show(self, ref: str, path: str) -> str | None:
        res = subprocess.run(["git", "-C", str(self.path), "show", f"{ref}:{path}"], capture_output=True, text=True)
        return res.stdout if res.returncode == 0 else None

    def grep_ok(self, pattern: str, ref: str) -> bool:
        res = subprocess.run(["git", "-C", str(self.path), "grep", "-qE", pattern, ref, "--", *SOURCE_GLOBS])
        return res.returncode == 0

    def head(self) -> str:
        return self.git("rev-parse", "--abbrev-ref", "HEAD").strip() or "HEAD"


def resolve_version(repo: Repo, claimed: str | None) -> tuple[str | None, str]:
    tags = repo.tags()
    if not claimed:
        return None, "The report does not name a version."
    want = claimed.lower().lstrip("v")
    for tag in tags:
        t = tag.lower().lstrip("v")
        if t == want or t == want.rstrip(".0") or f"{t}.0" == want:
            return tag, f"Claimed version {claimed} resolves to tag {tag}."
    return None, f"Claimed version {claimed} matches no release tag ({', '.join(tags)})."


def _function_regex(name: str) -> str:
    # POSIX ERE (git grep -E has no \\b or \\s).
    return rf"(^|[^A-Za-z0-9_]){re.escape(name)}[[:space:]]*\("


def function_definition(source: str, name: str) -> tuple[int, int] | None:
    """Returns the 1-based (start, end) line span of a C function definition, by brace matching."""
    lines = source.splitlines()
    pattern = re.compile(rf"^[A-Za-z_].*\b{re.escape(name)}\s*\(")
    for i, line in enumerate(lines):
        if not pattern.match(line) or line.rstrip().endswith(";"):
            continue
        depth, started = 0, False
        for j in range(i, len(lines)):
            # Signature may span lines; stop if we hit a ';' before any '{' (a prototype).
            if not started and ";" in lines[j] and "{" not in lines[j]:
                break
            depth += lines[j].count("{") - lines[j].count("}")
            if "{" in lines[j]:
                started = True
            if started and depth == 0:
                return i + 1, j + 1
    return None


def _normalize_lines(text: str) -> list[str]:
    return [" ".join(l.split()) for l in text.splitlines() if l.strip()]


def _squash(line: str) -> str:
    return "".join(line.split())


def fuzzy_find(snippet: str, source: str) -> tuple[float, int] | None:
    """Finds snippet in source ignoring all whitespace differences; returns (1.0, 1-based line).

    The match is deliberately strict about everything except whitespace: a changed
    operator (`>` vs `>=`) is a different program, so it must not count as present.
    Lines that are only an ellipsis are skipped.
    """
    want = [_squash(l) for l in snippet.splitlines() if l.strip() and _squash(l) not in ("...", "//...", "/*...*/", "…")]
    if not want:
        return None
    src = [(i + 1, _squash(l)) for i, l in enumerate(source.splitlines()) if l.strip()]
    if len(want) == 1:
        for lineno, text in src:
            if want[0] in text:
                return 1.0, lineno
        return None
    n = len(want)
    for k in range(0, len(src) - n + 1):
        window = [t for _, t in src[k : k + n]]
        if window[1:-1] == want[1:-1] and window[0].endswith(want[0]) and window[-1].startswith(want[-1]):
            return 1.0, src[k][0]
    return None


def _source_files(repo: Repo, ref: str) -> list[str]:
    return [f for f in repo.files_at(ref) if Path(f).suffix in {".c", ".h", ".py", ".cc", ".cpp"}]


def _distinctive_line(snippet: str) -> str | None:
    lines = [l.strip() for l in snippet.splitlines() if len(l.strip()) > 12]
    return max(lines, key=len) if lines else None


def ground(repo: Repo, claims: Claims) -> Grounding:
    tags = repo.tags()
    version, version_note = resolve_version(repo, claims.version)
    ref = version or (tags[-1] if tags else repo.head())
    if not version and claims.version is None and tags:
        version_note += f" Checks below use the latest release {ref}."
    checks: list[Check] = []
    fixed_in: dict | None = None

    if claims.version and not version:
        checks.append(Check("version", claims.version, "false", version_note, "git tag --list", hard_falsehood=False))

    files_at_ref = set(repo.files_at(ref))
    all_paths_ever = set(repo.git("log", "--all", "--pretty=format:", "--name-only").split())

    # ---- files ----
    for f in claims.files:
        matches = [p for p in files_at_ref if p == f or p.endswith("/" + f)]
        cmd = f"git ls-tree -r --name-only {ref} | grep -F '{f}'"
        if matches:
            checks.append(Check("file", f, "verified", f"{matches[0]} exists at {ref}.", cmd, data={"path": matches[0]}))
        elif any(p == f or p.endswith("/" + f) for p in all_paths_ever):
            checks.append(Check("file", f, "moved", f"{f} existed in history but not at {ref}.", f"git log --all -- '*{f}'"))
        else:
            checks.append(
                Check(
                    "file", f, "false",
                    f"No file named {f} exists at {ref}, in any release ({', '.join(tags)}), or anywhere in git history.",
                    f"git log --all --name-only | grep -F '{f}'", hard_falsehood=True,
                )
            )

    # ---- functions ----
    for fn in claims.functions:
        cmd = f"git grep -nE '{_function_regex(fn)}' {ref}"
        hits = repo.git("grep", "-nE", _function_regex(fn), ref, "--", *SOURCE_GLOBS).strip().splitlines()
        if hits:
            paths = [h.split(":")[1] for h in hits if h.count(":") >= 2]
            loc = next((p for p in paths if p.endswith(".c")), paths[0] if paths else None)
            checks.append(Check("function", fn, "verified", f"{fn}() is defined or used at {ref} ({len(hits)} hit(s)).", cmd,
                                data={"hits": hits[:5], "location": loc}))
            continue
        other = [t for t in tags if t != ref and repo.grep_ok(_function_regex(fn), t)]
        ever = repo.git("log", "--all", "-S", fn, "--oneline").strip()
        if other:
            checks.append(Check("function", fn, "moved", f"{fn}() is not at {ref} but exists at {', '.join(other)}.", cmd))
        elif ever:
            checks.append(Check("function", fn, "moved", f"{fn} appears in history ({ever.splitlines()[0]}) but not at {ref}.",
                                f"git log --all -S '{fn}' --oneline"))
        else:
            checks.append(
                Check(
                    "function", fn, "false",
                    f"{fn}() does not exist at {ref}, in any release ({', '.join(tags)}), and the name never appears in git history.",
                    f"git log --all -S '{fn}' --oneline  # no results", hard_falsehood=True,
                )
            )

    # ---- quoted code ----
    for snippet in claims.quoted_code:
        best = None
        for f in _source_files(repo, ref):
            src = repo.show(ref, f) or ""
            hit = fuzzy_find(snippet, src)
            if hit and (best is None or hit[0] > best[0]):
                best = (hit[0], f, hit[1])
        short = " / ".join(_normalize_lines(snippet))[:120]
        if best:
            checks.append(
                Check("quoted_code", short, "verified",
                      f"Quoted code found in {best[1]}:{best[2]} at {ref} (exact match, ignoring whitespace).",
                      f"git grep -nF '{(_distinctive_line(snippet) or '')[:60]}' {ref}",
                      data={"file": best[1], "line": best[2], "similarity": round(best[0], 3)})
            )
            continue
        # Not at the claimed version: was it there before?
        older = None
        for t in reversed(tags):
            if t == ref:
                continue
            for f in _source_files(repo, t):
                hit = fuzzy_find(snippet, repo.show(t, f) or "")
                if hit:
                    older = (t, f, hit[1], hit[0])
                    break
            if older:
                break
        if older:
            needle = _distinctive_line(snippet) or snippet.strip().splitlines()[0]
            log = repo.git("log", "--all", "-S", needle, "--format=%h%x09%s", "--", older[1]).strip().splitlines()
            removing = log[0].split("\t") if log else None
            fixed_tag = None
            if removing:
                contains = repo.git("tag", "--contains", removing[0], "--sort=v:refname").split()
                fixed_tag = contains[0] if contains else None
                fixed_in = {"commit": removing[0], "subject": removing[1] if len(removing) > 1 else "", "tag": fixed_tag,
                            "file": older[1], "last_seen": older[0]}
            checks.append(
                Check("quoted_code", short, "moved",
                      f"Quoted code is not at {ref}; it was in {older[1]}:{older[2]} at {older[0]}"
                      + (f" and was changed by commit {removing[0]} ({removing[1] if len(removing) > 1 else ''}), released in {fixed_tag}." if removing else "."),
                      f"git log --all -S '{needle[:60]}' --oneline -- {older[1]}",
                      data={"last_seen": older[0], "file": older[1], "line": older[2]})
            )
        else:
            checks.append(
                Check("quoted_code", short, "false",
                      f"The quoted code does not appear in any source file at {ref} or in any release ({', '.join(tags)}), even allowing for whitespace differences.",
                      f"git grep -nF '{(_distinctive_line(snippet) or short)[:60]}' $(git tag)  # no results",
                      hard_falsehood=True)
            )

    # ---- line numbers ----
    for lc in claims.lines:
        candidates = [c.data.get("path") for c in checks if c.kind == "file" and c.status == "verified"]
        path = lc.file if lc.file in files_at_ref else (candidates[0] if candidates else None)
        if path is None:
            for c in checks:
                if c.kind == "function" and c.status == "verified":
                    path = c.data.get("location")
                    break
        if path is None:
            checks.append(Check("line", f"line {lc.line}" + (f" of {lc.file}" if lc.file else ""), "unverifiable",
                                "The file the line refers to does not exist, so the line cannot be checked.", "-"))
            continue
        src = repo.show(ref, path) or ""
        lines = src.splitlines()
        cmd = f"git show {ref}:{path} | sed -n '{lc.line}p'"
        if lc.line > len(lines):
            checks.append(Check("line", f"{path}:{lc.line}", "false", f"{path} has only {len(lines)} lines at {ref}.", cmd, hard_falsehood=True))
            continue
        actual = lines[lc.line - 1].strip()
        inside = []
        for fn in claims.functions:
            span = function_definition(src, fn)
            if span and span[0] <= lc.line <= span[1]:
                inside.append(fn)
        detail = f"Line {lc.line} of {path} at {ref} is: `{actual or '(blank)'}`"
        if claims.functions and not inside:
            detail += f" — not inside {', '.join(claims.functions)}()."
        checks.append(Check("line", f"{path}:{lc.line}", "verified" if inside or not claims.functions else "false", detail, cmd))

    return Grounding(version, version_note, checks, fixed_in)
