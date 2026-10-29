"""Stage 5b: plain-English explanation for the maintainer and a draft reply to the reporter.

The verdict is already fixed by code; the model only explains it. Nemotron 3 Ultra writes
explanations where judgement matters (reproduced, not reproduced, needs human); Nano writes
the clear-cut ones. For reproduced bugs the reporter reply is a fixed template so no detail
of an unreleased security bug is ever drafted for an outside party.
"""
from __future__ import annotations

import json

from pydantic import BaseModel

from .gateway import Gateway, ModelUnavailable
from .verdict import VERDICTS

ULTRA_VERDICTS = {"reproduced", "not_reproduced", "needs_human"}

UNDER_REVIEW_REPLY = (
    "Thank you for your report. We have received it and it is under review by the maintainers. "
    "Please keep the details private while we investigate; we will follow up through this channel."
)


class Explanation(BaseModel):
    summary: str
    reporter_reply: str


EXPLAIN_SYSTEM = """You write for Bouncer, which verifies bug reports for open-source maintainers.
You are given a verdict that was ALREADY DECIDED by rules over evidence, plus that evidence.
Do not dispute or change the verdict. Write:
- summary: 2-4 plain sentences for the maintainer explaining why the evidence supports the verdict,
  citing the specific checks (function names, commands, commit hashes, CVE IDs). No hype.
- reporter_reply: a short, polite, factual reply to the reporter. List what was checked and, if they
  can fix the report (wrong version, missing steps), exactly what to send. Never insult or accuse;
  never say the report was AI-generated. Do not promise a fix date.
Return {"summary": str, "reporter_reply": str}."""


def _evidence_digest(report: dict, verdict: str, rule: str, evidence: dict) -> str:
    keep = {
        "verdict": VERDICTS[verdict]["label"],
        "rule": rule,
        "claims": evidence.get("claims"),
        "grounding_checks": [
            {k: c[k] for k in ("kind", "claim", "status", "detail")} for c in evidence.get("grounding", {}).get("checks", [])
        ],
        "fixed_in": evidence.get("grounding", {}).get("fixed_in"),
        "cves": [{k: c.get(k) for k in ("cve_id", "status", "detail")} for c in evidence.get("cves", [])],
        "duplicate": evidence.get("duplicate"),
        "reproduction": None,
        "injection_flags": evidence.get("injection"),
    }
    repro = evidence.get("reproduction")
    if repro:
        keep["reproduction"] = {
            "script": repro.get("script"),
            "build_ok": repro.get("build_ok"),
            "attempts": [{"exit_code": a["exit_code"], "sanitizer": (a.get("sanitizer") or {}).get("summary")}
                         for a in repro.get("attempts", [])],
        }
    return f"Report title (untrusted): {report['title']!r}\n\nEvidence:\n{json.dumps(keep, indent=1)[:9000]}"


def template(report: dict, verdict: str, rule: str, evidence: dict) -> Explanation:
    g = evidence.get("grounding", {})
    checks = g.get("checks", [])
    false = [c["detail"] for c in checks if c.get("hard_falsehood")]
    false += [c["detail"] for c in evidence.get("cves", []) if c.get("status") in ("not_issued", "issued_other_product")]
    verified = [c["claim"] for c in checks if c.get("status") == "verified"]
    if verdict == "fabricated":
        summary = "The report cites things that do not exist: " + " ".join(false[:3])
        reply = ("Thanks for reaching out. We checked the specific details in your report against the repository "
                 "and could not match them:\n- " + "\n- ".join(false[:4]) +
                 "\nIf you believe this is still a real issue, please reply with the exact version, file and function, "
                 "and a reproduction we can run.")
    elif verdict == "duplicate":
        d = evidence.get("duplicate") or {}
        summary = f"This describes the same bug as {d.get('of')} ({d.get('title')}). {d.get('how', '')}."
        reply = "Thank you for the report. This issue has already been reported and is being tracked; we'll link your report to it."
    elif verdict == "already_fixed":
        f = g.get("fixed_in") or {}
        summary = (f"The quoted code no longer exists at {g.get('resolved_version')}; it was changed by commit {f.get('commit')} "
                   f"(\"{f.get('subject')}\"), first released in {f.get('tag')}.")
        reply = (f"Thank you for the report. This was fixed in {f.get('tag')} (commit {f.get('commit')}). "
                 f"The code you quoted is from an earlier release. If you can reproduce the problem on "
                 f"{g.get('resolved_version')} or later, please send the exact steps.")
    elif verdict == "needs_info":
        summary = ("There is nothing concrete to verify yet. Without a version, an affected file or function, and steps, "
                   "no claim can be checked against the code, so Bouncer asks for them instead of guessing.")
        reply = ("Thank you for writing in. To investigate we need: the affected version, the file and function involved, "
                 "and exact steps or an input file that triggers the problem.")
    elif verdict == "not_reproduced":
        summary = (f"The claims are grounded ({', '.join(verified[:3])}), and the reporter's steps were run 3 times "
                   "against a sanitizer build without any crash. This does not mean the report is false.")
        reply = ("Thank you for the detailed report. We ran your steps three times against a build with AddressSanitizer "
                 "and UBSan and did not see a crash. Could you check the exact commands, version and input, "
                 "and send any sanitizer output you saw?")
    elif verdict == "needs_human":
        summary = f"The claims check out against the code ({', '.join(verified[:3])}), but: {rule}"
        reply = ("Thank you for the report. The details check out against our code, and a maintainer will review "
                 "the parts we could not test automatically.")
    else:
        repro = evidence.get("reproduction") or {}
        crash = next((a["sanitizer"] for a in repro.get("attempts", []) if a.get("sanitizer")), {}) or {}
        frame = (crash.get("frames") or [{}])[0]
        crashed = sum(1 for a in repro.get("attempts", []) if a.get("sanitizer"))
        summary = (f"Real bug. Bouncer built {repro.get('ref')} with AddressSanitizer and UBSan in a network-less container and "
                   f"ran the reporter's own steps: {crash.get('tool')} reported `{crash.get('kind')}` in "
                   f"`{frame.get('function')}()` at {frame.get('file')}:{frame.get('line')}, in {crashed} of "
                   f"{len(repro.get('attempts', []))} attempts. A fix is being drafted.")
        reply = UNDER_REVIEW_REPLY
    return Explanation(summary=summary, reporter_reply=reply)


async def explain(gateway: Gateway, report: dict, verdict: str, rule: str, evidence: dict) -> tuple[Explanation, str]:
    tier = "ultra" if verdict in ULTRA_VERDICTS else "nano"
    try:
        out = await gateway.json(
            report_id=report["id"], stage="explain_verdict", tier=tier, system=EXPLAIN_SYSTEM,
            user=_evidence_digest(report, verdict, rule, evidence), schema=Explanation, max_tokens=900,
        )
        source = f"nemotron-{tier}"
    except ModelUnavailable as exc:
        gateway.record_offline(report["id"], "explain_verdict", tier, f"template explanation ({exc})")
        out, source = template(report, verdict, rule, evidence), "template"
    if verdict == "reproduced":
        out.reporter_reply = UNDER_REVIEW_REPLY
    return out, source
