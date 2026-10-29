"""Anti-cheat scan: reject patches that make the crash disappear without fixing the bug.

Rules (any violation rejects the attempt before it reaches the sandbox):
  disabled-function   the vulnerable function is disabled (#if 0, an unconditional early
                      return that leaves dead code, or most of its body deleted)
  catch-all           errors are hidden (signal handlers, setjmp/longjmp, try/catch-all)
  sanitizers-off      sanitizer, warning or build/test configuration is changed
  tests-modified      existing tests are edited or deleted
  input-special-case  the exact reproduction input appears in the fix
The sandbox adds the final rule: the new regression test must FAIL on the unfixed code.
"""
from __future__ import annotations

import re

from .grounding import function_definition

BUILD_FILES = re.compile(r"(^|/)(Makefile|GNUmakefile|CMakeLists\.txt|[\w.-]+\.mk|configure(\.ac)?|meson\.build)$")
SAN_OFF = re.compile(r"no_sanitize|-fno-sanitize|__asan_|__ubsan|ASAN_OPTIONS|UBSAN_OPTIONS|#\s*pragma\s+(GCC|clang)\s+diagnostic")
CATCH_ALL = re.compile(r"\bsignal\s*\(|\bsigaction\s*\(|\bsetjmp\s*\(|\blongjmp\s*\(|__try\b|catch\s*\(\s*\.\.\.\s*\)|except\s*:|except\s+Exception\s*:")
RETURN_RE = re.compile(r"^\s*return\b[^;]*;")


def _added_lines(diff: str, *, include_tests: bool) -> list[str]:
    lines, current = [], ""
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[4:].strip()
            continue
        if line.startswith("+") and not line.startswith("+++"):
            if include_tests or not current.split("/", 1)[-1].startswith("tests/"):
                lines.append(line[1:])
    return lines


def _body(source: str, fn: str) -> list[str] | None:
    span = function_definition(source, fn)
    if not span:
        return None
    return source.splitlines()[span[0] - 1 : span[1]]


def _dead_code_after_return(body: list[str]) -> bool:
    depth = 0
    for i, line in enumerate(body):
        before = depth
        depth += line.count("{") - line.count("}")
        if before == 1 and RETURN_RE.match(line):
            prev = body[i - 1].strip() if i else ""
            conditional = prev.startswith(("if", "else", "} else")) or prev.endswith(")") and not prev.endswith(";")
            rest = [l for l in body[i + 1 :] if l.strip() and l.strip() != "}"]
            if not conditional and rest:
                return True
    return False


def payloads_from(report: dict, script: str) -> list[str]:
    out = [v for v in (report.get("attachments") or {}).values() if len(v.strip()) >= 3]
    out += [m for m in re.findall(r"'([^']{3,})'", script)]
    out += [m for m in re.findall(r'"([^"]{3,})"', script)]
    cleaned = []
    for p in out:
        p = p.replace("%%", "%").replace("\\n", "").replace("\\t", "\t").strip()
        if len(p) >= 3 and p not in cleaned:
            cleaned.append(p)
    return cleaned


def scan(
    *,
    edits: list[dict],
    originals: dict[str, str],
    patched: dict[str, str],
    diff: str,
    function: str | None,
    payloads: list[str],
) -> list[dict]:
    violations: list[dict] = []

    for e in edits:
        path = e["file"]
        if path.startswith("tests/") and path in originals:
            violations.append({"rule": "tests-modified", "detail": f"Edits the existing test file {path}."})
        if BUILD_FILES.search(path):
            violations.append({"rule": "sanitizers-off", "detail": f"Changes build configuration in {path}."})

    added = _added_lines(diff, include_tests=False)
    for line in added:
        if SAN_OFF.search(line):
            violations.append({"rule": "sanitizers-off", "detail": f"Adds `{line.strip()[:90]}`."})
        if CATCH_ALL.search(line):
            violations.append({"rule": "catch-all", "detail": f"Hides errors with `{line.strip()[:90]}`."})
        if re.match(r"^\s*#\s*if\s+0\b", line):
            violations.append({"rule": "disabled-function", "detail": "Wraps code in `#if 0`."})
        for p in payloads:
            if p in line or (len(p) >= 4 and p.strip("%") and f'"{p}"' in line):
                violations.append({"rule": "input-special-case",
                                   "detail": f"Special-cases the reproduction input {p!r}: `{line.strip()[:90]}`."})

    if function:
        for path, before in originals.items():
            after = patched.get(path)
            if after is None or before == after:
                continue
            old_body, new_body = _body(before, function), _body(after, function)
            if old_body is None:
                continue
            if new_body is None:
                violations.append({"rule": "disabled-function", "detail": f"Removes {function}() from {path}."})
                continue
            if _dead_code_after_return(new_body) and not _dead_code_after_return(old_body):
                violations.append({"rule": "disabled-function",
                                   "detail": f"Adds an unconditional return to {function}(), leaving the rest of its body unreachable."})
            old_n = len([l for l in old_body if l.strip()])
            new_n = len([l for l in new_body if l.strip()])
            if new_n < old_n * 0.5:
                violations.append({"rule": "disabled-function",
                                   "detail": f"Deletes {old_n - new_n} of {old_n} lines of {function}()."})

    unique, seen = [], set()
    for v in violations:
        key = (v["rule"], v["detail"])
        if key not in seen:
            seen.add(key)
            unique.append(v)
    return unique
