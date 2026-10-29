"""Stage 1: turn free-text reports into a structured list of checkable claims.

Nemotron 3 Nano does the reading. Its output is then filtered so that only claims
that literally appear in the report survive: a model mistake can drop a claim but
can never invent one, so a Fabricated verdict always rests on the reporter's words.
Deterministic regex extraction runs on every report and is merged in.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from .gateway import Gateway, ModelUnavailable
from .untrusted import ZERO_WIDTH_RE, wrap

BUG_CLASSES = [
    "heap-buffer-overflow",
    "stack-buffer-overflow",
    "use-after-free",
    "double-free",
    "integer-overflow",
    "null-dereference",
    "out-of-bounds-read",
    "path-traversal",
    "injection",
    "denial-of-service",
    "logic",
    "other",
]

C_STDLIB = {
    "memcpy", "memmove", "memset", "malloc", "realloc", "calloc", "free", "strlen", "strcpy", "strncpy",
    "strcmp", "strncmp", "printf", "sprintf", "snprintf", "fprintf", "puts", "fwrite", "fread", "sizeof",
    "main", "exit", "abort", "assert", "memchr", "strchr", "strdup", "strndup", "gets", "fgets",
}


class LineClaim(BaseModel):
    file: str | None = None
    line: int


class Claims(BaseModel):
    version: str | None = None
    files: list[str] = Field(default_factory=list)
    functions: list[str] = Field(default_factory=list)
    lines: list[LineClaim] = Field(default_factory=list)
    quoted_code: list[str] = Field(default_factory=list)
    cve_ids: list[str] = Field(default_factory=list)
    repro_commands: list[str] = Field(default_factory=list)
    has_steps: bool = False
    bug_class: str | None = None
    claimed_impact: str | None = None
    claimed_severity: str | None = None
    requires_environment: list[str] = Field(default_factory=list)


EXTRACT_SYSTEM = f"""You are the claim extractor in Bouncer, a tool that verifies bug and security reports
against real source code. Extract every concrete, checkable claim from the report.

Return JSON with these keys:
- version: the project version the reporter says is affected (e.g. "v1.2"), or null
- files: source file paths named in the prose (not inside quoted code)
- functions: function names the report says contain the bug (without parentheses)
- lines: list of {{"file": path or null, "line": number}} for every line number cited
- quoted_code: code snippets the reporter claims are in the project, copied verbatim
- cve_ids: every CVE identifier cited
- repro_commands: shell commands given as reproduction steps, verbatim, one per item
- has_steps: true if the report gives any reproduction steps or proof of concept
- bug_class: one of {BUG_CLASSES}
- claimed_impact: one short sentence
- claimed_severity: as stated (e.g. "CVSS 9.8", "High") or null
- requires_environment: things the reproduction needs beyond building the library and running
  a command (e.g. "live HTTP server", "nginx reverse proxy", "special hardware", "network access").
  Empty list if a plain build + command is enough.

Copy names, code and commands exactly as written. Never add claims the report does not make."""


FENCE_RE = re.compile(r"```([\w+-]*)\n(.*?)```", re.S)
CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.I)
VERSION_RES = [
    re.compile(r"\btinyparse\s+v?(\d+\.\d+(?:\.\d+)?)\b", re.I),
    re.compile(r"(?:affected(?:\s+version)?|version)\s*[:*]*\s*\**\s*(?:tinyparse\s+)?v?(\d+\.\d+(?:\.\d+)?)", re.I),
    re.compile(r"(?<![\w.])v(\d+\.\d+(?:\.\d+)?)\b"),
]
FUNC_CALL_RE = re.compile(r"`?\b([A-Za-z_][A-Za-z0-9_]{2,})\(\)`?")
FUNC_WORD_RE = re.compile(r"\bfunction\s+(?:`([A-Za-z_]\w{2,})`|([A-Za-z]\w*_\w+))", re.I)
FILE_RE = re.compile(r"(?<![\w/.-])((?:[\w-]+/)*[\w-]+\.(?:c|h|cc|cpp|py))\b")
LINE_RE = re.compile(r"\bline\s+(\d{1,6})\b", re.I)
SHELL_PREFIXES = ("./", "printf ", "echo ", "curl ", "make", "cat ", "python3 ", "python ", "nc ", "sh ", "bash ")
ENV_KEYWORDS = {
    "nginx": "nginx reverse proxy",
    "reverse proxy": "reverse proxy",
    "http server": "live HTTP server",
    "http application": "live HTTP server",
    "on port": "live network server",
    "curl http": "live network server",
    "http://localhost": "live network server",
    "kubernetes": "cluster deployment",
    "gpu": "special hardware",
    "fpga": "special hardware",
    "windows": "specific operating system",
    "database": "external database",
}


def _prose(body: str) -> str:
    return FENCE_RE.sub(" ", body)


def _looks_like_shell(lang: str, code: str) -> bool:
    if lang in ("sh", "bash", "shell", "console", "zsh"):
        return True
    if lang in ("c", "cpp", "c++", "h"):
        return False
    first = code.strip().splitlines()[0] if code.strip() else ""
    return first.startswith(SHELL_PREFIXES)


def rule_extract(title: str, body: str) -> Claims:
    """Deterministic extraction used on every report (and alone when offline)."""
    body = ZERO_WIDTH_RE.sub("", body)
    text = f"{title}\n{body}"
    prose = f"{title}\n{_prose(body)}"
    claims = Claims()

    for pattern in VERSION_RES:
        m = pattern.search(text)
        if m:
            claims.version = "v" + m.group(1)
            break

    claims.cve_ids = sorted({c.upper() for c in CVE_RE.findall(text)})

    funcs: list[str] = []
    for m in list(FUNC_CALL_RE.finditer(prose)) + list(FUNC_WORD_RE.finditer(prose)):
        name = next(g for g in m.groups() if g)
        if name not in C_STDLIB and name not in funcs:
            funcs.append(name)
    claims.functions = funcs

    files: list[str] = []
    for m in FILE_RE.finditer(prose):
        if m.group(1) not in files:
            files.append(m.group(1))
    claims.files = files

    for sentence in re.split(r"(?<=[.\n])\s", prose):
        for lm in LINE_RE.finditer(sentence):
            fm = FILE_RE.search(sentence)
            claim = LineClaim(file=fm.group(1) if fm else None, line=int(lm.group(1)))
            if claim not in claims.lines:
                claims.lines.append(claim)

    commands: list[str] = []
    for lang, code in FENCE_RE.findall(body):
        if _looks_like_shell(lang.lower(), code):
            commands += [l.strip() for l in code.strip().splitlines() if l.strip() and not l.strip().startswith("#")]
        elif code.strip():
            claims.quoted_code.append(code.rstrip("\n"))
    for inline in re.findall(r"`([^`\n]+)`", _prose(body)):
        if inline.strip().startswith(SHELL_PREFIXES) and inline.strip() not in commands:
            commands.append(inline.strip())
    claims.repro_commands = commands
    claims.has_steps = bool(commands) or bool(re.search(r"(steps to reproduce|^#+\s*reproduc|proof of concept)", body, re.I | re.M))

    lowered = text.lower()
    for key, cls in [
        ("heap-buffer-overflow", "heap-buffer-overflow"), ("heap buffer over", "heap-buffer-overflow"),
        ("heap overflow", "heap-buffer-overflow"), ("reads past the end", "heap-buffer-overflow"),
        ("read past", "heap-buffer-overflow"), ("stack buffer overflow", "stack-buffer-overflow"),
        ("stack-based buffer overflow", "stack-buffer-overflow"), ("use-after-free", "use-after-free"),
        ("double free", "double-free"), ("integer overflow", "integer-overflow"),
        ("null pointer", "null-dereference"), ("path traversal", "path-traversal"),
        ("underflow", "out-of-bounds-read"), ("before the start", "out-of-bounds-read"),
    ]:
        if key in lowered:
            claims.bug_class = cls
            break
    if claims.bug_class is None and any(w in lowered for w in ("insecure", "vulnerab", "exploit")):
        claims.bug_class = "other"

    sev = re.search(r"(CVSS[^\n)]{0,12}\d+(?:\.\d)?|severity:?\**\s*\w+)", text, re.I)
    claims.claimed_severity = sev.group(1).strip("* ") if sev else None
    impact = re.search(r"#+\s*impact\s*\n+(.+)", body, re.I)
    claims.claimed_impact = impact.group(1).strip()[:200] if impact else None

    envs: list[str] = []
    for key, label in ENV_KEYWORDS.items():
        if key in lowered and label not in envs:
            envs.append(label)
    claims.requires_environment = envs
    return claims


def _normalize(s: str) -> str:
    return " ".join(ZERO_WIDTH_RE.sub("", s).split())


def ground_to_text(model: Claims, title: str, body: str) -> Claims:
    """Drops any model-extracted item that does not literally appear in the report."""
    norm = _normalize(f"{title}\n{body}")
    raw = ZERO_WIDTH_RE.sub("", f"{title}\n{body}")
    model.functions = [f for f in model.functions if re.search(rf"\b{re.escape(f)}\b", raw)]
    model.files = [f for f in model.files if f in raw]
    model.cve_ids = [c.upper() for c in model.cve_ids if c.upper() in raw.upper()]
    model.quoted_code = [q for q in model.quoted_code if q.strip() and _normalize(q) in norm]
    model.repro_commands = [c for c in model.repro_commands if _normalize(c) in norm]
    model.lines = [l for l in model.lines if str(l.line) in raw]
    if model.bug_class not in BUG_CLASSES:
        model.bug_class = "other" if model.bug_class else None
    if model.version and not re.search(re.escape(model.version.lstrip("vV")), raw):
        model.version = None
    return model


def merge(rule: Claims, model: Claims) -> Claims:
    def union(a: list, b: list) -> list:
        out = list(a)
        for item in b:
            if item not in out:
                out.append(item)
        return out

    lines = list(rule.lines)
    for l in model.lines:
        if not any(x.line == l.line for x in lines):
            lines.append(l)
    return Claims(
        version=rule.version or model.version,
        files=union(rule.files, model.files),
        functions=union(rule.functions, [f for f in model.functions if f not in C_STDLIB]),
        lines=lines,
        quoted_code=rule.quoted_code or model.quoted_code,
        cve_ids=union(rule.cve_ids, model.cve_ids),
        repro_commands=rule.repro_commands or model.repro_commands,
        has_steps=rule.has_steps or model.has_steps,
        bug_class=model.bug_class or rule.bug_class,
        claimed_impact=model.claimed_impact or rule.claimed_impact,
        claimed_severity=rule.claimed_severity or model.claimed_severity,
        requires_environment=union(rule.requires_environment, model.requires_environment),
    )


async def extract_claims(gateway: Gateway, report_id: str, title: str, body: str) -> tuple[Claims, str]:
    """Returns the claims and the source ("nemotron-nano" or "rules")."""
    rule = rule_extract(title, body)
    try:
        model = await gateway.json(
            report_id=report_id,
            stage="extract_claims",
            tier="nano",
            system=EXTRACT_SYSTEM,
            user=wrap(title, body),
            schema=Claims,
            max_tokens=1500,
        )
    except ModelUnavailable as exc:
        gateway.record_offline(report_id, "extract_claims", "nano", f"regex claim extractor ({exc})")
        return rule, "rules"
    return merge(rule, ground_to_text(model, title, body)), "nemotron-nano"
