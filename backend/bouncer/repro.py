"""Stage 4: reproduce the reported bug in the sandbox, three attempts, sanitizers on.

Bouncer only runs the reproduction the reporter supplied (or a script written
from their own steps). It never searches for new bugs or writes exploits.
"""
from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel

from .extract import Claims
from .gateway import Gateway, ModelUnavailable
from .sandbox import SAN_ENV, DockerSandbox, export_tree, parse_sanitizer, split_sections
from .untrusted import wrap

ATTEMPTS = 3
NETWORK_RE = re.compile(r"\b(curl|wget|nc|ncat|ssh|telnet)\b|https?://", re.I)
BUILD_RE = re.compile(r"^\s*(make|cmake|\./configure|gcc|clang|cc)\b")
SAFE_NAME_RE = re.compile(r"^[\w.-]{1,64}$")


class ReproScript(BaseModel):
    runnable: bool
    script: str
    reason: str


REPRO_SYSTEM = """You turn a bug reporter's written reproduction steps into a bash script for Bouncer's sandbox.
The sandbox has the project source in the current directory, ALREADY BUILT with sanitizers
(`make SAN=1` has run; binaries are in ./build/). It has NO network access, no servers and no root.
Write only what the reporter described: do not invent new attack inputs or search for other bugs.
If the steps need anything the sandbox cannot provide (network, a server, special hardware, missing
details), set runnable=false and explain why. Return {"runnable": bool, "script": str, "reason": str}."""


def build_script(commands: list[str]) -> str:
    body = [c for c in commands if not BUILD_RE.match(c) and not c.startswith("cd ")]
    return "set -o pipefail\ncd /work\n" + "\n".join(body) + "\n"


def job_script() -> str:
    return (
        SAN_ENV
        + "echo '::build::'\n"
        + "make -s CC=clang SAN=1 > /tmp/build.log 2>&1; b=$?; tail -c 4000 /tmp/build.log\n"
        + "echo '::build_exit::'; echo $b\n"
        + "[ $b -eq 0 ] || exit 0\n"
        + f"for i in $(seq 1 {ATTEMPTS}); do\n"
        + "  echo \"::run$i::\"\n"
        + "  timeout 30 bash .bouncer/repro.sh > /tmp/run.log 2>&1; rc=$?\n"
        + "  head -c 20000 /tmp/run.log\n"
        + "  echo \"::run${i}_exit::\"; echo $rc\n"
        + "done\n"
    )


def _write_attachments(dest: Path, attachments: dict[str, str]) -> list[str]:
    written = []
    for name, content in (attachments or {}).items():
        base = Path(name).name
        if SAFE_NAME_RE.match(base):
            (dest / base).write_text(content)
            written.append(base)
    return written


async def plan_script(gateway: Gateway, report: dict, claims: Claims) -> dict:
    """Decides what, if anything, can be run. Returns {"runnable", "script", "source", "reason"}."""
    if claims.requires_environment:
        return {"runnable": False, "script": "", "source": "rules",
                "reason": "The reproduction needs " + ", ".join(claims.requires_environment)
                + ", which the network-less sandbox cannot provide."}
    commands = [c for c in claims.repro_commands if not BUILD_RE.match(c)]
    if commands:
        if any(NETWORK_RE.search(c) for c in commands):
            return {"runnable": False, "script": "", "source": "rules",
                    "reason": "The reproduction steps make network requests; the sandbox has no network."}
        return {"runnable": True, "script": build_script(claims.repro_commands), "source": "reporter",
                "reason": "Running the reporter's own commands verbatim."}
    if not claims.has_steps:
        return {"runnable": False, "script": "", "source": "rules", "reason": "The report gives no reproduction steps."}
    try:
        plan = await gateway.json(
            report_id=report["id"], stage="write_repro_script", tier="super", system=REPRO_SYSTEM,
            user=wrap(report["title"], report["body"]) + "\n\nAttached files (in the working directory): "
            + ", ".join(report.get("attachments", {}) or ["none"]),
            schema=ReproScript, max_tokens=1200,
        )
    except ModelUnavailable as exc:
        gateway.record_offline(report["id"], "write_repro_script", "super", f"no script writer ({exc})")
        return {"runnable": False, "script": "", "source": "rules",
                "reason": "Steps are written in prose and no model is configured to turn them into a script."}
    if not plan.runnable or NETWORK_RE.search(plan.script):
        return {"runnable": False, "script": "", "source": "nemotron-super", "reason": plan.reason}
    return {"runnable": True, "script": "set -o pipefail\ncd /work\n" + plan.script, "source": "nemotron-super",
            "reason": plan.reason}


def matches_claim(san: dict, claims: Claims) -> tuple[bool, str]:
    frames = [f["function"] for f in san.get("frames", [])[:6]]
    files = [f["file"] for f in san.get("frames", [])[:6]]
    if claims.functions:
        hit = [fn for fn in claims.functions if fn in frames]
        if not hit:
            return False, f"Crashed, but in {san.get('top_function') or 'unknown code'}, not in the claimed {', '.join(claims.functions)}()."
        where = f"in {hit[0]}()"
    elif claims.files:
        if not any(any(f.endswith(c) or c.endswith(f) for c in claims.files) for f in files):
            return False, "Crashed, but not in the claimed file."
        where = "in the claimed file"
    else:
        where = "(no location was claimed)"
    note = ""
    if claims.bug_class and claims.bug_class not in ("other", san["kind"]):
        note = f" Sanitizer class {san['kind']} differs from the claimed {claims.bug_class}."
    return True, f"{san['tool']} reported {san['kind']} {where}.{note}"


async def reproduce(sandbox: DockerSandbox, repo_path: Path, ref: str, report: dict, plan: dict) -> dict:
    run_id, job_dir = sandbox.new_job_dir()
    export_tree(repo_path, ref, job_dir)
    files = _write_attachments(job_dir, report.get("attachments") or {})
    (job_dir / ".bouncer").mkdir(exist_ok=True)
    (job_dir / ".bouncer" / "repro.sh").write_text(plan["script"])
    run = await sandbox.run(run_id, job_dir, job_script())
    sections = split_sections(run.output)
    infra_error = None
    if "build" not in sections:
        infra_error = ("The sandbox did not start the job (is the run directory shared with Docker?): "
                       + run.output.strip()[-300:])
    build_exit = int((sections.get("build_exit") or "1").strip() or 1)
    attempts = []
    for i in range(1, ATTEMPTS + 1):
        if f"run{i}" not in sections:
            continue
        out = sections[f"run{i}"]
        san = parse_sanitizer(out)
        attempts.append({
            "attempt": i,
            "exit_code": int((sections.get(f"run{i}_exit") or "-1").strip() or -1),
            "output": out[-6000:],
            "sanitizer": san.as_dict() if san else None,
        })
    return {
        "run_id": run_id,
        "backend": sandbox.name,
        "ref": ref,
        "image": sandbox.settings.sandbox_image,
        "container_command": run.command,
        "isolation": ["--network none", "read-only rootfs", "uid 10001", "cap-drop ALL", "no-new-privileges",
                      "768 MB RAM", "1.5 CPU", "256 pids", f"{sandbox.settings.sandbox_timeout_s}s timeout"],
        "attachments": files,
        "script": plan["script"],
        "script_source": plan["source"],
        "build_ok": build_exit == 0,
        "build_log": (sections.get("build") or "")[-3000:],
        "attempts": attempts,
        "timed_out": run.timed_out,
        "duration_s": run.duration_s,
        "infra_error": infra_error,
    }
