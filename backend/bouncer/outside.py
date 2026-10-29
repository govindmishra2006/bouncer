"""Stage 3: check the outside world.

* CVE IDs: the CVE Program's public API (cveawg.mitre.org) is the authority on whether
  an ID was ever issued; Tavily web search adds what the wider web says about it.
* Duplicates: compare against earlier reports for the same project (claims overlap),
  confirmed by Nemotron Nano for borderline cases, plus a Tavily search for public advisories.
"""
from __future__ import annotations

import re

import httpx
from pydantic import BaseModel

from .config import Settings
from .extract import Claims
from .gateway import Gateway, ModelUnavailable
from .untrusted import wrap

CVE_API = "https://cveawg.mitre.org/api"
TAVILY_URL = "https://api.tavily.com/search"


class DuplicateJudgement(BaseModel):
    same_bug: bool
    reason: str


async def tavily_search(settings: Settings, query: str, max_results: int = 5) -> dict:
    if not settings.tavily_api_key:
        return {"query": query, "status": "skipped", "note": "TAVILY_API_KEY not set", "results": []}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                TAVILY_URL,
                headers={"Authorization": f"Bearer {settings.tavily_api_key}"},
                json={"query": query, "max_results": max_results, "search_depth": "basic"},
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        return {"query": query, "status": "error", "note": str(exc)[:200], "results": []}
    results = [
        {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": (r.get("content") or "")[:280]}
        for r in data.get("results", [])
    ]
    return {"query": query, "status": "ok", "results": results, "response_time": data.get("response_time")}


async def lookup_cve(settings: Settings, cve_id: str, project: str) -> dict:
    """Returns {"status": issued|reserved|not_issued|unknown, ...} with the evidence."""
    out: dict = {"cve_id": cve_id, "source": f"{CVE_API}/cve-id/{cve_id}"}
    if not settings.cve_lookup:
        return {**out, "status": "unknown", "detail": "CVE lookup disabled (BOUNCER_CVE_LOOKUP=0)."}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            id_resp = await client.get(f"{CVE_API}/cve-id/{cve_id}")
            if id_resp.status_code == 404:
                return {
                    **out,
                    "status": "not_issued",
                    "detail": f"The CVE Program has no record of {cve_id}: it was never issued or reserved "
                    f"(API answered {id_resp.json().get('error', '404')}).",
                }
            id_resp.raise_for_status()
            state = id_resp.json().get("state", "UNKNOWN")
            if state != "PUBLISHED":
                return {**out, "status": "reserved", "detail": f"{cve_id} exists with state {state}; no public record yet."}
            rec = (await client.get(f"{CVE_API}/cve/{cve_id}")).json()
    except (httpx.HTTPError, ValueError) as exc:
        return {**out, "status": "unknown", "detail": f"CVE lookup failed: {str(exc)[:160]}"}
    cna = rec.get("containers", {}).get("cna", {})
    products = [a.get("product", "") for a in cna.get("affected", [])]
    desc = " ".join(d.get("value", "") for d in cna.get("descriptions", []))
    mentions = project.lower() in (desc + " " + " ".join(products)).lower()
    return {
        **out,
        "status": "issued" if mentions else "issued_other_product",
        "products": products[:5],
        "detail": (
            f"{cve_id} is published and concerns {project}."
            if mentions
            else f"{cve_id} is published but concerns {', '.join(p for p in products if p) or 'another product'}, not {project}."
        ),
    }


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z_][a-z0-9_]{2,}", text.lower())}


def similarity(a: dict, b: dict) -> tuple[float, dict]:
    ca, cb = a["claims"], b["claims"]
    fa, fb = set(ca.get("functions", [])), set(cb.get("functions", []))
    func = len(fa & fb) / len(fa | fb) if fa | fb else 0.0
    files = 1.0 if set(ca.get("files", [])) & set(cb.get("files", [])) else 0.0
    cls = 1.0 if ca.get("bug_class") and ca.get("bug_class") == cb.get("bug_class") else 0.0
    ta, tb = _tokens(a["title"] + " " + a["body"]), _tokens(b["title"] + " " + b["body"])
    text = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    score = 0.4 * func + 0.15 * files + 0.25 * cls + 0.2 * text
    return round(score, 3), {"functions": round(func, 2), "files": files, "bug_class": cls, "text": round(text, 2)}


async def find_duplicate(gateway: Gateway, report: dict, claims: Claims, earlier: list[dict]) -> dict | None:
    """Returns {"of": id, "score", "parts", "how"} for the best duplicate among earlier reports, or None."""
    me = {"title": report["title"], "body": report["body"], "claims": claims.model_dump()}
    best = None
    for other in earlier:
        if not other.get("claims") or other.get("verdict") in ("fabricated", "needs_info"):
            continue
        score, parts = similarity(me, other)
        if parts["functions"] > 0 and (best is None or score > best["score"]):
            best = {"of": other["id"], "title": other["title"], "score": score, "parts": parts, "other": other}
    if best is None or best["score"] < 0.5:
        return None
    if best["score"] >= 0.7 and best["parts"]["bug_class"] == 1.0:
        best["how"] = "claims overlap: same function, same file, same bug class"
        best.pop("other")
        return best
    try:
        judgement = await gateway.json(
            report_id=report["id"],
            stage="duplicate_check",
            tier="nano",
            system="You decide whether two bug reports describe the same underlying bug in the same code. "
            "Different symptoms of one root cause count as the same bug. Return {\"same_bug\": bool, \"reason\": str}.",
            user="Earlier report:\n" + wrap(best["other"]["title"], best["other"]["body"])
            + "\n\nNew report:\n" + wrap(report["title"], report["body"]),
            schema=DuplicateJudgement,
            max_tokens=400,
        )
    except ModelUnavailable as exc:
        gateway.record_offline(report["id"], "duplicate_check", "nano", f"overlap score only ({exc})")
        return None
    if judgement.same_bug:
        best["how"] = f"Nemotron Nano: {judgement.reason}"
        best.pop("other")
        return best
    return None
