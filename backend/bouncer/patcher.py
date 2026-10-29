"""Patch module: draft a fix for reproduced bugs and keep it only if it is proven.

Loop (max 5 attempts):
  1. Root cause   — Nemotron 3 Ultra reads the sanitizer report and the code.
  2. Patch        — Nemotron 3 Super proposes minimal search/replace edits + a regression test.
  3. Checks       — anti-cheat scan, then a fresh sandbox:
                    * regression test FAILS on the unfixed code (otherwise it proves nothing)
                    * the original reproduction no longer crashes (sanitizers still on, 3 runs)
                    * the full existing test suite passes
                    * the diff is small (<= 40 changed lines) and only touches files in the stack trace
  4. Feedback     — Nemotron 3 Nano summarises what failed; back to step 2.
A failure after 5 attempts is reported honestly as "could not fix safely" with the root cause.
"""
from __future__ import annotations

import difflib
import re
import shutil
from collections.abc import Awaitable, Callable
from pathlib import Path

from pydantic import BaseModel, Field

from . import anticheat
from .extract import Claims
from .gateway import Gateway, ModelUnavailable
from .grounding import Repo, function_definition
from .offline_patches import candidates_for
from .repro import _write_attachments
from .sandbox import SAN_ENV, DockerSandbox, export_tree, parse_sanitizer, split_sections

MAX_ATTEMPTS = 5
MAX_CHANGED_LINES = 40

Emit = Callable[[str, dict], Awaitable[None]]


class RootCause(BaseModel):
    root_cause: str
    faulty_lines: list[int] = Field(default_factory=list)
    fix_strategy: str


class Edit(BaseModel):
    file: str
    find: str
    replace: str


class PatchProposal(BaseModel):
    rationale: str
    edits: list[Edit]
    test_code: str


class FailureSummary(BaseModel):
    summary: str


ROOT_CAUSE_SYSTEM = """You are the root-cause analyst in Bouncer. You get a sanitizer crash report from a
sandboxed reproduction and the source code around the crash. Explain the defect precisely and briefly,
e.g. "The loop copies len bytes but the buffer holds len - 1; the terminating byte overflows."
Return {"root_cause": str, "faulty_lines": [int], "fix_strategy": str}. The fix strategy must fix the
cause, not hide the symptom (no disabling the function, no special-casing the input)."""

PATCH_SYSTEM = f"""You write the smallest correct C patch for a reproduced bug, plus a regression test.
Return {{"rationale": str, "edits": [{{"file": str, "find": str, "replace": str}}], "test_code": str}}.
- Each edit replaces one exact, unique snippet ("find" must be copied verbatim from the shown source,
  including indentation) with "replace". Only edit the files listed as editable.
- Change at most {MAX_CHANGED_LINES} lines. Fix the root cause. Rejected automatically: disabling or
  deleting the function, early returns that skip its logic, catch-all error hiding, touching sanitizer or
  build flags, editing existing tests, or special-casing the exact reproduction input.
- test_code is a complete C file with its own main(), using:
    #include "tinyparse.h"
    #include "tp_test.h"   /* provides CHECK(cond), CHECK_STR(a,b), RUN(fn), TEST_SUMMARY() */
  Each test is `static void name(void)`; main calls RUN(name) for each and returns TEST_SUMMARY().
  The test must trigger the original bug through the public API (e.g. heap buffers of exact size so
  AddressSanitizer catches over-reads) so that it FAILS on the unfixed code and passes once fixed."""


def _numbered(src: str, start: int, end: int) -> str:
    lines = src.splitlines()
    return "\n".join(f"{i + 1:4d}  {lines[i]}" for i in range(max(0, start - 1), min(len(lines), end)))


def crash_context(repo: Repo, ref: str, san: dict) -> tuple[list[str], str, str | None, str | None]:
    """Returns (editable files, code context, top project function, its file)."""
    tree_files = set(repo.files_at(ref))
    editable, chunks = [], []
    top_fn = top_file = None
    for frame in san.get("frames", []):
        path = frame["file"]
        if path not in tree_files:
            continue
        if top_fn is None:
            top_fn, top_file = frame["function"], path
        if path not in editable:
            editable.append(path)
        src = repo.show(ref, path) or ""
        span = function_definition(src, frame["function"]) or (max(1, frame["line"] - 15), frame["line"] + 15)
        chunks.append(f"--- {path} ({frame['function']}, crash frame at line {frame['line']}) ---\n"
                      + _numbered(src, span[0], span[1]))
        if len(chunks) >= 3:
            break
    # Only the library files are editable; the CLI front end in the trace is context.
    lib = [f for f in editable if not f.startswith("tools/")] or editable
    return lib, "\n\n".join(chunks), top_fn, top_file


def unified_diff(path: str, before: str, after: str) -> str:
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True), f"a/{path}", f"b/{path}"))


def changed_lines(diff: str) -> int:
    return sum(1 for l in diff.splitlines() if (l.startswith("+") or l.startswith("-")) and not l.startswith(("+++", "---")))


def apply_edits(originals: dict[str, str], edits: list[dict]) -> tuple[dict[str, str], str | None]:
    patched = dict(originals)
    for e in edits:
        src = patched.get(e["file"])
        if src is None:
            return patched, f"{e['file']} is not an editable file."
        count = src.count(e["find"])
        if count != 1:
            return patched, f"Edit for {e['file']} did not apply: the 'find' snippet occurs {count} times (must be exactly once)."
        patched[e["file"]] = src.replace(e["find"], e["replace"], 1)
    return patched, None


def check_script(test_name: str) -> str:
    return (
        SAN_ENV
        + "cd /work/orig\necho '::regress_on_old::'\n"
        + f"if make -s CC=clang SAN=1 build/{test_name} > /tmp/ob.log 2>&1; then\n"
        + f"  timeout 30 ./build/{test_name} > /tmp/or.log 2>&1; echo \"EXIT=$?\"; head -c 6000 /tmp/or.log\n"
        + "else echo 'EXIT=build-failed'; tail -c 3000 /tmp/ob.log; fi\n"
        + "cd /work/fixed\necho '::fixed_build::'\n"
        + "make -s CC=clang SAN=1 > /tmp/fb.log 2>&1; echo \"EXIT=$?\"; tail -c 3000 /tmp/fb.log\n"
        + "for i in 1 2 3; do echo \"::fixed_run$i::\"; timeout 30 bash .bouncer/repro.sh > /tmp/r.log 2>&1; "
        + "echo \"EXIT=$?\"; head -c 6000 /tmp/r.log; done\n"
        + "echo '::fixed_tests::'\n"
        + "timeout 120 make -s CC=clang SAN=1 test > /tmp/t.log 2>&1; echo \"EXIT=$?\"; tail -c 8000 /tmp/t.log\n"
    )


def _exit(section: str) -> str:
    m = re.search(r"^EXIT=(\S+)", section or "", re.M)
    return m.group(1) if m else "missing"


async def run_checks(sandbox: DockerSandbox, repo_path: Path, ref: str, report: dict, repro_script: str,
                     patched: dict[str, str], test_path: str, test_code: str) -> dict:
    run_id, job = sandbox.new_job_dir()
    for tree in ("orig", "fixed"):
        export_tree(repo_path, ref, job / tree)
        _write_attachments(job / tree, report.get("attachments") or {})
        (job / tree / test_path).write_text(test_code)
        (job / tree / ".bouncer").mkdir(exist_ok=True)
        (job / tree / ".bouncer" / "repro.sh").write_text(repro_script.replace("cd /work\n", ""))
    for path, content in patched.items():
        (job / "fixed" / path).write_text(content)
    test_name = Path(test_path).stem
    run = await sandbox.run(run_id, job, check_script(test_name), timeout_s=sandbox.settings.sandbox_timeout_s + 120)
    sec = split_sections(run.output)
    old = sec.get("regress_on_old", "")
    fixed_runs = [sec.get(f"fixed_run{i}", "") for i in (1, 2, 3)]
    crashes = [parse_sanitizer(r) for r in fixed_runs]
    tests = sec.get("fixed_tests", "")
    totals = re.findall(r"(\d+) tests, (\d+) failed", tests)
    old_exit = _exit(old)
    old_san = parse_sanitizer(old)
    if old_exit == "build-failed":
        regress_detail = "Regression test did not compile against the unfixed code."
    elif old_exit == "0":
        regress_detail = "Regression test PASSES on the unfixed code, so it proves nothing."
    else:
        regress_detail = "Regression test fails on the unfixed code (" + (old_san.summary if old_san else f"exit {old_exit}") + ")."
    checks = {
        "regression_fails_on_old": {"pass": old_exit not in ("0", "build-failed", "missing"), "detail": regress_detail},
        "bug_gone": {
            "pass": _exit(sec.get("fixed_build", "")) == "0" and all(c is None for c in crashes) and all(_exit(r) != "missing" for r in fixed_runs),
            "detail": ("Fixed build failed to compile." if _exit(sec.get("fixed_build", "")) != "0" else
                       "Original reproduction ran 3× with sanitizers on: no crash." if all(c is None for c in crashes) else
                       f"Still crashes: {next(c for c in crashes if c).summary}"),
        },
        "tests_pass": {
            "pass": _exit(tests) == "0",
            "detail": ("All test binaries pass (" + ", ".join(f"{t} tests, {f} failed" for t, f in totals) + ")."
                       if _exit(tests) == "0" else "Test suite failed: " + (tests.strip().splitlines() or ["no output"])[-1][:200]),
        },
    }
    return {"run_id": run_id, "duration_s": run.duration_s, "timed_out": run.timed_out, "checks": checks,
            "logs": {"regress_on_old": old[-3000:], "fixed_build": sec.get("fixed_build", "")[-2000:],
                     "fixed_run1": fixed_runs[0][-2000:], "fixed_tests": tests[-4000:]}}


async def patch_loop(gateway: Gateway, sandbox: DockerSandbox, repo_path: Path, ref: str, report: dict,
                     claims: Claims, repro: dict, emit: Emit) -> dict:
    repo = Repo(repo_path)
    crash = next(a["sanitizer"] for a in repro["attempts"] if a.get("sanitizer"))
    editable, context, top_fn, top_file = crash_context(repo, ref, crash)
    result: dict = {"status": "running", "attempts": [], "editable_files": editable, "function": top_fn,
                    "max_attempts": MAX_ATTEMPTS, "max_changed_lines": MAX_CHANGED_LINES}
    if not editable:
        result.update(status="could_not_fix", reason="No project source file appears in the crash stack.")
        return result
    originals = {f: repo.show(ref, f) or "" for f in editable}
    crash_text = next(a["output"] for a in repro["attempts"] if a.get("sanitizer"))[-4000:]

    # ---- 1. root cause (Ultra) ----
    await emit("patch_stage", {"step": "root_cause"})
    try:
        rc = await gateway.json(
            report_id=report["id"], stage="root_cause", tier="ultra", system=ROOT_CAUSE_SYSTEM,
            user=f"Sanitizer output:\n{crash_text}\n\nSource:\n{context}", schema=RootCause, max_tokens=1200)
        result["root_cause"] = {**rc.model_dump(), "source": "nemotron-ultra"}
    except ModelUnavailable as exc:
        gateway.record_offline(report["id"], "root_cause", "ultra", f"sanitizer-derived summary ({exc})")
        f0 = crash["frames"][0] if crash.get("frames") else {}
        line = (repo.show(ref, f0.get("file", "")) or "").splitlines()
        code = line[f0["line"] - 1].strip() if f0 and f0.get("line", 0) <= len(line) else ""
        result["root_cause"] = {
            "root_cause": f"{crash['tool']} reports {crash['kind']}. The faulting access is in {top_fn}() at "
                          f"{f0.get('file')}:{f0.get('line')}: `{code}`.",
            "faulty_lines": [f0.get("line")] if f0 else [],
            "fix_strategy": "Model unavailable; strategy not generated.",
            "source": "sanitizer report (offline, no model)",
        }

    payloads = anticheat.payloads_from(report, repro.get("script", ""))
    test_path = f"tests/test_regress_{report['id'].lower()}.c"
    feedback = ""
    offline = candidates_for(top_file or "", top_fn or "")

    for n in range(1, MAX_ATTEMPTS + 1):
        await emit("patch_stage", {"step": "propose", "attempt": n})
        attempt: dict = {"n": n}
        # ---- 2. patch (Super) ----
        try:
            prop = await gateway.json(
                report_id=report["id"], stage="write_patch", tier="super", system=PATCH_SYSTEM,
                user=(f"Root cause: {result['root_cause']['root_cause']}\nStrategy: {result['root_cause']['fix_strategy']}\n"
                      f"Editable files: {', '.join(editable)}\nRegression test path: {test_path}\n\n"
                      f"Sanitizer output:\n{crash_text[-2500:]}\n\nSource:\n{context}\n\n"
                      + "\n\n".join(f"=== full file {p} ===\n{originals[p]}" for p in editable)
                      + (f"\n\nYour previous attempt failed. What went wrong:\n{feedback}" if feedback else "")),
                schema=PatchProposal, max_tokens=4000, temperature=0.2 if n == 1 else 0.5)
            proposal = prop.model_dump()
            attempt["source"] = "nemotron-super"
        except ModelUnavailable as exc:
            if n > len(offline):
                gateway.record_offline(report["id"], "write_patch", "super", f"no candidate left ({exc})")
                result["attempts"].append({**attempt, "source": "none", "outcome": "stopped",
                                           "failure": "No model configured and no offline candidate for this crash."})
                break
            gateway.record_offline(report["id"], "write_patch", "super", f"offline scripted candidate {n} ({exc})")
            proposal = offline[n - 1]
            attempt["source"] = "offline scripted candidate (not model output)"
        attempt["rationale"] = proposal["rationale"]

        patched, apply_error = apply_edits(originals, proposal["edits"])
        diff = "".join(unified_diff(p, originals[p], patched[p]) for p in editable if patched[p] != originals[p])
        test_diff = unified_diff(test_path, "", proposal["test_code"])
        attempt.update(diff=diff, test_diff=test_diff, changed_lines=changed_lines(diff))

        problems: list[str] = []
        if apply_error:
            problems.append(apply_error)
        violations = anticheat.scan(edits=proposal["edits"], originals=originals, patched=patched,
                                    diff=diff, function=top_fn, payloads=payloads)
        attempt["anticheat"] = violations
        if violations:
            problems += [f"anti-cheat ({v['rule']}): {v['detail']}" for v in violations]
        small = {"pass": 0 < attempt["changed_lines"] <= MAX_CHANGED_LINES,
                 "detail": f"{attempt['changed_lines']} changed lines in {', '.join(p for p in editable if patched[p] != originals[p]) or 'no files'} (limit {MAX_CHANGED_LINES}, stack-trace files only)."}
        if not small["pass"] and not apply_error:
            problems.append(small["detail"])

        if problems:
            attempt.update(outcome="rejected", checks={"small": small}, failure=" ".join(problems))
        else:
            await emit("patch_stage", {"step": "sandbox", "attempt": n})
            run = await run_checks(sandbox, repo_path, ref, report, repro["script"], patched, test_path, proposal["test_code"])
            checks = {**run["checks"], "small": small}
            attempt.update(sandbox_run=run["run_id"], duration_s=run["duration_s"], checks=checks, logs=run["logs"])
            failed = [k for k, v in checks.items() if not v["pass"]]
            if not failed:
                attempt["outcome"] = "passed"
                result["attempts"].append(attempt)
                result.update(status="fixed", final_diff=diff, final_test=proposal["test_code"], test_path=test_path)
                await emit("patch_attempt", {"attempt": n, "outcome": "passed"})
                return result
            attempt.update(outcome="failed", failure="; ".join(checks[k]["detail"] for k in failed))

        # ---- 4. failure summary (Nano) ----
        try:
            fs = await gateway.json(
                report_id=report["id"], stage="summarize_failure", tier="nano",
                system="Summarise in 1-3 sentences why this patch attempt failed and what the next attempt must do differently. "
                       "Return {\"summary\": str}.",
                user=f"Failure: {attempt['failure']}\n\nDiff:\n{diff[:3000]}\n\nLogs:\n{str(attempt.get('logs', ''))[:3000]}",
                schema=FailureSummary, max_tokens=300)
            feedback = fs.summary
            attempt["feedback_source"] = "nemotron-nano"
        except ModelUnavailable as exc:
            gateway.record_offline(report["id"], "summarize_failure", "nano", f"raw failure text ({exc})")
            feedback = attempt["failure"]
            attempt["feedback_source"] = "raw check output"
        attempt["feedback"] = feedback
        result["attempts"].append(attempt)
        await emit("patch_attempt", {"attempt": n, "outcome": attempt["outcome"]})

    result.update(status="could_not_fix",
                  reason=f"No attempt passed all checks after {len(result['attempts'])} attempt(s). Root-cause analysis attached.")
    return result


def cleanup_runs(runs_dir: Path, keep: int = 200) -> None:
    runs = sorted(p for p in runs_dir.glob("*") if p.is_dir())
    for p in runs[: max(0, len(runs) - keep)]:
        shutil.rmtree(p, ignore_errors=True)
