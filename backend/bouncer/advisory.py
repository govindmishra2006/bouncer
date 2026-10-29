"""Responsible disclosure: drafts a private GitHub security advisory, never a public PR.

The draft follows GitHub's REST API "Create a repository security advisory"
(POST /repos/{owner}/{repo}/security-advisories) followed by
"Create a temporary private fork" (POST .../security-advisories/{ghsa_id}/forks).
Nothing is sent unless GITHUB_TOKEN and GITHUB_REPO are set AND a maintainer
clicks "Create draft advisory". The demo project is local, so the demo shows the
exact payload instead.
"""
from __future__ import annotations

import httpx

from .config import Settings

CWE = {
    "heap-buffer-overflow": ("CWE-125", "Out-of-bounds Read"),
    "stack-buffer-overflow": ("CWE-121", "Stack-based Buffer Overflow"),
    "heap-use-after-free": ("CWE-416", "Use After Free"),
    "use-after-free": ("CWE-416", "Use After Free"),
    "double-free": ("CWE-415", "Double Free"),
    "undefined-behavior": ("CWE-758", "Reliance on Undefined Behavior"),
    "segmentation-fault": ("CWE-119", "Improper Restriction of Operations within the Bounds of a Memory Buffer"),
}


def build_draft(report: dict, repro: dict, patch: dict, project: str, ref: str, tags: list[str]) -> dict:
    crash = next(a["sanitizer"] for a in repro["attempts"] if a.get("sanitizer"))
    kind = crash["kind"]
    if kind == "heap-buffer-overflow" and "WRITE" in "".join(a["output"] for a in repro["attempts"]):
        cwe = ("CWE-787", "Out-of-bounds Write")
    else:
        cwe = CWE.get(kind, ("CWE-119", "Improper Restriction of Operations within the Bounds of a Memory Buffer"))
    fn = patch.get("function") or crash.get("top_function")
    later = [t for t in tags if tags.index(t) > tags.index(ref)] if ref in tags else []
    description = "\n".join([
        f"### Impact\n{crash['tool']} reports `{kind}` in `{fn}()` when processing attacker-controlled input.",
        f"\n### Root cause\n{patch.get('root_cause', {}).get('root_cause', '')}",
        f"\n### Reproduction (verified by Bouncer in a network-less sandbox, {ref}, sanitizers on)\n```sh\n{repro['script'].strip()}\n```",
        f"\n### Patch\nDrafted by Bouncer and verified: crash gone with sanitizers on, full test suite passes, "
        f"regression test fails on the unfixed code.\n```diff\n{patch.get('final_diff', '').strip()}\n```",
        "\n### Credit\nReported by " + report["reporter"] + ".",
    ])
    payload = {
        "summary": f"{cwe[1]} in {fn}() ({project})",
        "description": description,
        "cwe_ids": [cwe[0]],
        "severity": "high" if kind in ("heap-buffer-overflow", "stack-buffer-overflow", "use-after-free") else "medium",
        "vulnerabilities": [{
            "package": {"ecosystem": "other", "name": project},
            "vulnerable_version_range": f"= {ref.lstrip('v')}",
            "patched_versions": later[0].lstrip("v") if later else None,
            "vulnerable_functions": [fn] if fn else [],
        }],
    }
    return {
        "status": "draft",
        "sent": False,
        "visibility": "private draft (maintainers only)",
        "steps": [
            {"call": "POST /repos/{owner}/{repo}/security-advisories", "body": "payload below"},
            {"call": "POST /repos/{owner}/{repo}/security-advisories/{ghsa_id}/forks", "body": "creates a temporary private fork"},
            {"call": "git push <private fork> bouncer/fix-" + report["id"].lower(), "body": "patch + regression test commit"},
        ],
        "payload": payload,
        "patch_files": {"diff": patch.get("final_diff", ""), "test_path": patch.get("test_path"), "test": patch.get("final_test", "")},
    }


async def publish(settings: Settings, draft: dict) -> dict:
    """Creates the draft advisory and its private fork. Only called on explicit maintainer action."""
    if not (settings.github_token and settings.github_repo):
        return {**draft, "sent": False, "error": "GITHUB_TOKEN and GITHUB_REPO must be set to create the advisory."}
    headers = {"Authorization": f"Bearer {settings.github_token}", "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    base = f"https://api.github.com/repos/{settings.github_repo}/security-advisories"
    payload = {k: v for k, v in draft["payload"].items()}
    payload["vulnerabilities"] = [{k: v for k, v in vuln.items() if v is not None} for vuln in payload["vulnerabilities"]]
    async with httpx.AsyncClient(timeout=30, headers=headers) as client:
        resp = await client.post(base, json=payload)
        if resp.status_code >= 300:
            return {**draft, "sent": False, "error": f"GitHub answered {resp.status_code}: {resp.text[:300]}"}
        adv = resp.json()
        fork = await client.post(f"{base}/{adv['ghsa_id']}/forks")
    return {**draft, "sent": True, "ghsa_id": adv["ghsa_id"], "html_url": adv.get("html_url"),
            "private_fork": fork.json().get("html_url") if fork.status_code < 300 else None,
            "fork_error": None if fork.status_code < 300 else fork.text[:300]}
