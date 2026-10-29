"""Stage 4 runner: build and run untrusted code in a throwaway, network-less container.

Every job gets a fresh container that is destroyed afterwards:
  --network none, read-only root filesystem, non-root user (uid 10001),
  all capabilities dropped, no-new-privileges, memory / CPU / pids limits,
  a wall-clock timeout, and no secrets (no environment is passed through).

The backend is local Docker. The same image and script can be submitted as a
Nebius Serverless Job or run on a Nebius VM (see docs/ARCHITECTURE.md); this code
only claims what it runs.
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .config import Settings

ASAN_RE = re.compile(r"ERROR: (AddressSanitizer|LeakSanitizer|MemorySanitizer): ([\w-]+)")
UBSAN_RE = re.compile(r"([\w./-]+):(\d+):(\d+): runtime error: (.+)")
FRAME_RE = re.compile(r"#(\d+) 0x[0-9a-f]+ in (\S+) (?:/work/(?:fixed/|orig/)?)?([\w./-]+):(\d+)")
SEGV_RE = re.compile(r"Segmentation fault|SIGSEGV|core dumped", re.I)


@dataclass
class SanitizerReport:
    tool: str
    kind: str
    summary: str
    frames: list[dict] = field(default_factory=list)

    @property
    def top_function(self) -> str | None:
        return self.frames[0]["function"] if self.frames else None

    def as_dict(self) -> dict:
        return {**self.__dict__, "top_function": self.top_function}


def parse_sanitizer(output: str) -> SanitizerReport | None:
    m = ASAN_RE.search(output)
    if m:
        frames = []
        tail = output[m.start():]
        first = tail.find("#0 ")
        # Only the crashing stack: it ends at the first blank line (allocation/free stacks follow).
        stack = tail[first:].split("\n\n", 1)[0] if first != -1 else ""
        for fm in FRAME_RE.finditer(stack):
            frames.append({"function": fm.group(2), "file": fm.group(3), "line": int(fm.group(4))})
        summary = next((l.strip() for l in tail.splitlines() if l.startswith("SUMMARY:")), m.group(0))
        return SanitizerReport(m.group(1), m.group(2), summary, frames)
    u = UBSAN_RE.search(output)
    if u:
        frames = [{"function": fm.group(2), "file": fm.group(3), "line": int(fm.group(4))}
                  for fm in FRAME_RE.finditer(output[u.start():])]
        file = u.group(1).replace("/work/fixed/", "").replace("/work/orig/", "").replace("/work/", "")
        if not frames:
            frames = [{"function": "?", "file": file, "line": int(u.group(2))}]
        return SanitizerReport("UndefinedBehaviorSanitizer", "undefined-behavior", f"{file}:{u.group(2)}: {u.group(4)}", frames)
    if SEGV_RE.search(output):
        return SanitizerReport("kernel", "segmentation-fault", "Process crashed with SIGSEGV", [])
    return None


def split_sections(output: str) -> dict[str, str]:
    """Splits output on lines like '::name::' into {name: text}."""
    sections: dict[str, str] = {}
    current = "_"
    for line in output.splitlines(keepends=True):
        m = re.match(r"^::([\w.:-]+)::\s*$", line)
        if m:
            current = m.group(1)
            sections.setdefault(current, "")
        else:
            sections[current] = sections.get(current, "") + line
    return sections


@dataclass
class ContainerRun:
    run_id: str
    exit_code: int
    timed_out: bool
    duration_s: float
    output: str
    command: str


class DockerSandbox:
    name = "docker-local"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.env = dict(os.environ)
        colima = Path.home() / ".colima/default/docker.sock"
        if "DOCKER_HOST" not in self.env and colima.exists():
            self.env["DOCKER_HOST"] = f"unix://{colima}"
        if os.environ.get("BOUNCER_DOCKER_CONFIG"):
            self.env["DOCKER_CONFIG"] = os.environ["BOUNCER_DOCKER_CONFIG"]
        self.env["DOCKER_CLI_HINTS"] = "false"

    def available(self) -> tuple[bool, str]:
        if shutil.which("docker") is None:
            return False, "docker CLI not found"
        res = subprocess.run(
            ["docker", "image", "inspect", self.settings.sandbox_image, "--format", "{{.Id}}"],
            capture_output=True, text=True, env=self.env,
        )
        if res.returncode != 0:
            return False, f"sandbox image {self.settings.sandbox_image} not available: {res.stderr.strip()[:200]}"
        return True, f"{self.settings.sandbox_image} ready"

    def new_job_dir(self) -> tuple[str, Path]:
        run_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        path = self.settings.runs_dir / run_id
        path.mkdir(parents=True)
        return run_id, path

    async def run(self, run_id: str, job_dir: Path, script: str, *, timeout_s: int | None = None) -> ContainerRun:
        timeout_s = timeout_s or self.settings.sandbox_timeout_s
        (job_dir / ".bouncer").mkdir(exist_ok=True)
        (job_dir / ".bouncer" / "job.sh").write_text(script)
        name = f"bouncer-{run_id}"
        cmd = [
            "docker", "run", "--rm", "--name", name,
            "--network", "none",
            "--read-only",
            "--tmpfs", "/work:rw,exec,size=256m,uid=10001,gid=10001",
            "--tmpfs", "/tmp:rw,exec,size=64m,uid=10001,gid=10001",
            "--user", "10001:10001",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--memory", "768m", "--memory-swap", "768m",
            "--cpus", "1.5",
            "--pids-limit", "256",
            "-v", f"{job_dir}:/src:ro",
            self.settings.sandbox_image,
            "bash", "-c", "cp -r /src/. /work/ && cd /work && exec bash /work/.bouncer/job.sh",
        ]
        shown = " ".join(c if " " not in c else f"'{c}'" for c in cmd[:-3]) + " bash job.sh"
        started = time.perf_counter()
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, env=self.env
        )
        timed_out = False
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except asyncio.TimeoutError:
            timed_out = True
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, env=self.env)
            out, _ = await proc.communicate()
        text = (out or b"").decode("utf-8", "replace")
        (job_dir / ".bouncer" / "output.log").write_text(text)
        return ContainerRun(run_id, proc.returncode if proc.returncode is not None else -1, timed_out,
                            round(time.perf_counter() - started, 2), text, shown)


def export_tree(repo_path: Path, ref: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(["git", "-C", str(repo_path), "archive", ref], capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive.stdout, check=True)


SAN_ENV = (
    "export ASAN_OPTIONS=detect_leaks=0:symbolize=1:abort_on_error=0 "
    "UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1\n"
)
