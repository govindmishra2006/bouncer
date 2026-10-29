"""Stage 5a: the verdict, computed by code from evidence. Models never choose it.

Order of rules (first match wins):
  needs_info     no target named (no file, function or quoted code), or no version and no steps
  fabricated     at least one hard, checkable falsehood (non-existent function / file / quoted code,
                 or a CVE that was never issued) AND no runnable reproduction to settle it
  duplicate      matches an earlier report for the same bug
  already_fixed  the quoted code was changed by a commit released before/at the claimed version
  needs_human    grounded, but the reproduction needs something the sandbox cannot provide
  needs_info     grounded, but no steps or proof of concept were given
  reproduced     sanitizer crash in the claimed location, in at least one of 3 attempts
  needs_human    crashed somewhere else, the build failed, or the evidence is mixed
  not_reproduced ran 3 times with no crash

A falsehood alongside a runnable reproduction is "mixed evidence": the sandbox runs, and
anything short of a matching crash becomes needs_human, never fabricated.
"""
from __future__ import annotations

from dataclasses import dataclass

VERDICTS = {
    "reproduced": {"label": "Reproduced", "rank": 0},
    "needs_human": {"label": "Needs human", "rank": 1},
    "not_reproduced": {"label": "Not reproduced", "rank": 2},
    "needs_info": {"label": "Needs info", "rank": 3},
    "duplicate": {"label": "Duplicate", "rank": 4},
    "already_fixed": {"label": "Already fixed", "rank": 5},
    "fabricated": {"label": "Fabricated", "rank": 6},
}


@dataclass
class Decision:
    verdict: str
    rule: str
    stop_before_sandbox: bool = False


def falsehoods(grounding: dict, cves: list[dict]) -> list[str]:
    out = [c["detail"] for c in grounding.get("checks", []) if c.get("hard_falsehood")]
    out += [c["detail"] for c in cves if c.get("status") in ("not_issued", "issued_other_product")]
    return out


def has_target(claims: dict) -> bool:
    return bool(claims.get("files") or claims.get("functions") or claims.get("quoted_code"))


def pre_sandbox(claims: dict, grounding: dict, cves: list[dict], duplicate: dict | None, plan: dict) -> Decision | None:
    """Decides early when cheap evidence is enough. Returns None when the sandbox must run."""
    if not has_target(claims) or (not claims.get("version") and not claims.get("has_steps")):
        missing = [n for n, ok in (("version", claims.get("version")), ("affected file or function", has_target(claims)),
                                   ("steps to reproduce", claims.get("has_steps"))) if not ok]
        return Decision("needs_info", "Missing: " + ", ".join(missing) + ".", True)

    lies = falsehoods(grounding, cves)
    if lies and not plan.get("runnable"):
        return Decision("fabricated", f"{len(lies)} hard, checkable falsehood(s) and no runnable reproduction.", True)

    if duplicate:
        return Decision("duplicate", f"Same bug as {duplicate['of']} ({duplicate['how']}).", True)

    fixed = grounding.get("fixed_in")
    if fixed and fixed.get("tag"):
        return Decision("already_fixed", f"The quoted code was changed in {fixed['commit']} and released in {fixed['tag']}.", True)

    if not plan.get("runnable"):
        if claims.get("has_steps"):
            return Decision("needs_human", plan.get("reason", "Reproduction cannot run in the sandbox."), True)
        return Decision("needs_info", "Claims are grounded, but no steps or proof of concept were given.", True)
    return None


def post_sandbox(claims: dict, grounding: dict, cves: list[dict], repro: dict, match: tuple[bool, str] | None) -> Decision:
    lies = falsehoods(grounding, cves)
    if repro.get("infra_error"):
        return Decision("needs_human", f"Sandbox failure, not a verdict on the report: {repro['infra_error']}")
    if not repro.get("build_ok"):
        return Decision("needs_human", "The claimed version did not build in the sandbox.")
    if repro.get("timed_out"):
        return Decision("needs_human", "The reproduction timed out.")
    crashes = [a for a in repro.get("attempts", []) if a.get("sanitizer")]
    if crashes:
        ok, why = match if match else (False, "Crash could not be matched to the claim.")
        if ok:
            note = f" (Report also contains {len(lies)} false detail(s); see evidence.)" if lies else ""
            return Decision("reproduced", f"{why} Crashed in {len(crashes)} of {len(repro['attempts'])} attempts.{note}")
        return Decision("needs_human", why)
    if lies:
        return Decision("needs_human", "Mixed evidence: the report contains false details, and its reproduction did not crash.")
    return Decision("not_reproduced", f"Ran the reporter's steps {len(repro.get('attempts', []))} times with sanitizers on; no crash.")
