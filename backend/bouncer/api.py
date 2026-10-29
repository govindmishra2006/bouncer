"""HTTP API for the Bouncer dashboard."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from . import advisory
from .config import settings
from .db import Store
from .pipeline import PROJECT, Pipeline
from .verdict import VERDICTS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

store = Store(settings.db_path)
pipeline: Pipeline | None = None
_submissions: deque[float] = deque(maxlen=200)
SUBMISSIONS_PER_HOUR = 40


@asynccontextmanager
async def lifespan(_: FastAPI):
    global pipeline
    pipeline = Pipeline(store, settings)
    pipeline.start()
    yield
    await pipeline.stop()


app = FastAPI(title="Bouncer API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _pipe() -> Pipeline:
    if pipeline is None:
        raise HTTPException(503, "pipeline not started")
    return pipeline


def _sort_key(r: dict) -> tuple:
    if r["status"] in ("queued", "processing") or not r.get("verdict"):
        return (-1 if r["status"] == "processing" else 7, r["seq"])
    return (VERDICTS[r["verdict"]]["rank"], r["seq"])


def _card(r: dict) -> dict:
    ev = r.get("evidence") or {}
    claims = r.get("claims") or {}
    patch = r.get("patch") or {}
    return {
        "id": r["id"], "seq": r["seq"], "title": r["title"], "reporter": r["reporter"], "channel": r["channel"],
        "is_test_data": r["is_test_data"], "received_at": r["received_at"], "status": r["status"], "stage": r["stage"],
        "verdict": r["verdict"], "verdict_label": VERDICTS[r["verdict"]]["label"] if r.get("verdict") else None,
        "verdict_rule": r["verdict_rule"], "version": claims.get("version"), "functions": claims.get("functions", [])[:3],
        "bug_class": claims.get("bug_class"), "injection": bool(ev.get("injection")),
        "false_claims": sum(1 for c in (ev.get("grounding") or {}).get("checks", []) if c.get("hard_falsehood"))
        + sum(1 for c in ev.get("cves", []) if c.get("status") in ("not_issued", "issued_other_product")),
        "patch_status": patch.get("status"), "sandbox_used": bool(ev.get("reproduction")),
    }


@app.get("/api/health")
async def health() -> dict:
    p = _pipe()
    ok, detail = await asyncio.to_thread(p.sandbox.available)
    return {
        "models": {
            "live": settings.models_live,
            "provider": "Nebius Token Factory" if settings.models_live else "offline rule-based fallbacks",
            "base_url": settings.nebius_base_url,
            "tiers": {k: v.model_id for k, v in settings.tiers.items()},
        },
        "tavily": bool(settings.tavily_api_key),
        "cve_lookup": settings.cve_lookup,
        "sandbox": {"ok": ok, "backend": p.sandbox.name, "detail": detail, "image": settings.sandbox_image},
        "github": bool(settings.github_token and settings.github_repo),
        "budget": {"daily_usd": settings.daily_budget_usd, "spent_24h_usd": round(store.spend_since(time.time() - 86400), 4)},
        "project": {"name": PROJECT, "tags": p.repo.tags(), "fictional": True},
    }


@app.get("/api/reports")
async def list_reports() -> dict:
    reports = sorted(store.list_reports(), key=_sort_key)
    return {"reports": [_card(r) for r in reports], "stats": _stats(reports)}


def _stats(reports: list[dict]) -> dict:
    by = {k: 0 for k in VERDICTS}
    for r in reports:
        if r.get("verdict"):
            by[r["verdict"]] += 1
    decided = sum(by.values())
    hours = (decided - by["needs_human"]) * settings.hours_per_report
    calls = store.model_calls()
    return {
        "total": len(reports), "decided": decided, "by_verdict": by,
        "in_progress": sum(1 for r in reports if r["status"] in ("queued", "processing", "patching")),
        "patches_ready": sum(1 for r in reports if (r.get("patch") or {}).get("status") == "fixed"),
        "sandboxes_started": sum(1 for r in reports if (r.get("evidence") or {}).get("reproduction")),
        "hours_saved": hours,
        "hours_assumption": f"{settings.hours_per_report:g} maintainer hour per report verified by hand; "
                            "counts every decided report except Needs human.",
        "model_calls": sum(1 for c in calls if c["provider"] == "nebius-token-factory"),
        "fallback_steps": sum(1 for c in calls if c["provider"] == "offline-rules"),
        "tokens": sum(c["tokens_in"] + c["tokens_out"] for c in calls),
        "cost_usd": round(sum(c["cost_usd"] for c in calls), 4),
    }


@app.get("/api/reports/{report_id}")
async def get_report(report_id: str) -> dict:
    r = store.get_report(report_id)
    if not r:
        raise HTTPException(404, "report not found")
    return {**r, "card": _card(r), "model_calls": store.model_calls(report_id), "events": store.events(report_id)}


class Submission(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=10, max_length=20000)
    reporter: str = Field(default="anonymous", max_length=80)
    attachments: dict[str, str] = Field(default_factory=dict)

    @field_validator("attachments")
    @classmethod
    def _check_attachments(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) > 3:
            raise ValueError("at most 3 attachments")
        for name, content in v.items():
            if not re.fullmatch(r"[\w.-]{1,64}", name):
                raise ValueError(f"invalid attachment name {name!r}")
            if len(content) > 65536:
                raise ValueError(f"attachment {name} is larger than 64 KB")
        return v


@app.post("/api/reports", status_code=201)
async def submit(sub: Submission) -> dict:
    now = time.time()
    if len([t for t in _submissions if now - t < 3600]) >= SUBMISSIONS_PER_HOUR:
        raise HTTPException(429, "submission limit reached for this hour")
    _submissions.append(now)
    rid = _pipe().submit(title=sub.title, body=sub.body, reporter=sub.reporter or "anonymous",
                         channel="bouncer_form", attachments=sub.attachments)
    await _pipe().emit(rid, "received", {"title": sub.title})
    return {"id": rid}


@app.post("/api/demo/load")
async def demo_load() -> dict:
    ids = await _pipe().load_demo()
    return {"ids": ids}


@app.post("/api/demo/reset")
async def demo_reset() -> dict:
    _pipe().reset()
    await _pipe().emit(None, "reset", {})
    return {"ok": True}


class DecisionIn(BaseModel):
    action: str = Field(pattern="^(approve|reject|escalate|reopen)$")
    note: str = Field(default="", max_length=2000)


@app.post("/api/reports/{report_id}/decision")
async def decide(report_id: str, d: DecisionIn) -> dict:
    if not store.get_report(report_id):
        raise HTTPException(404, "report not found")
    decision = {"action": d.action, "note": d.note, "at": time.time(), "by": "maintainer"}
    store.update_report(report_id, decision=decision)
    await _pipe().emit(report_id, "decision", decision)
    return decision


@app.post("/api/reports/{report_id}/advisory/publish")
async def publish_advisory(report_id: str) -> dict:
    r = store.get_report(report_id)
    if not r or not r.get("advisory"):
        raise HTTPException(404, "no advisory draft for this report")
    result = await advisory.publish(settings, r["advisory"])
    store.update_report(report_id, advisory=result)
    return result


@app.get("/api/repo/file")
async def repo_file(ref: str, path: str) -> dict:
    p = _pipe()
    if ref not in p.repo.tags() or not re.fullmatch(r"[\w./-]{1,200}", path) or ".." in path:
        raise HTTPException(400, "invalid ref or path")
    content = p.repo.show(ref, path)
    if content is None:
        raise HTTPException(404, "file not found at that ref")
    return {"ref": ref, "path": path, "content": content}


@app.get("/api/events")
async def events(request: Request, after: int = 0) -> StreamingResponse:
    p = _pipe()
    q: asyncio.Queue = asyncio.Queue()
    p.subscribers.add(q)

    async def stream():
        try:
            for ev in store.events(after_id=after):
                yield f"id: {ev['id']}\ndata: {json.dumps(ev)}\n\n"
            while not await request.is_disconnected():
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"id: {ev['id']}\ndata: {json.dumps(ev)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            p.subscribers.discard(q)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
