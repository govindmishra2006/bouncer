"""Orchestrator: runs the five stages for each report in arrival order, then the patch loop.

Reports are processed one at a time by a single worker so duplicate detection always
sees every earlier report. Reproduced reports are handed to a separate patch worker so
the queue keeps moving while fixes are drafted. Every step emits an event that the
dashboard streams live.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

from . import advisory
from .config import ROOT, Settings
from .db import Store
from .explain import explain
from .extract import Claims, extract_claims
from .gateway import Gateway
from .grounding import Repo, ground
from .outside import find_duplicate, lookup_cve, tavily_search
from .patcher import cleanup_runs, patch_loop
from .repro import matches_claim, plan_script, reproduce
from .sandbox import DockerSandbox
from .untrusted import detect_injection
from .verdict import VERDICTS, post_sandbox, pre_sandbox

log = logging.getLogger("bouncer")
PROJECT = "tinyparse"


def ensure_demo_repo(settings: Settings) -> Path:
    path = settings.repos_dir / PROJECT
    if not (path / ".git").exists():
        import importlib.util

        spec = importlib.util.spec_from_file_location("build_tinyparse", ROOT / "demo" / "build_tinyparse.py")
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(mod)
        mod.build(path)
    return path


def load_demo_reports() -> list[dict]:
    data = json.loads((ROOT / "demo" / "reports" / "reports.json").read_text())
    return data["reports"]


class Pipeline:
    def __init__(self, store: Store, settings: Settings):
        self.store = store
        self.settings = settings
        self.gateway = Gateway(store, settings)
        self.sandbox = DockerSandbox(settings)
        self.repo_path = ensure_demo_repo(settings)
        self.repo = Repo(self.repo_path)
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.patch_queue: asyncio.Queue[str] = asyncio.Queue()
        self.subscribers: set[asyncio.Queue] = set()
        self.generation = 0
        self._tasks: list[asyncio.Task] = []

    # ---- lifecycle ------------------------------------------------------
    def start(self) -> None:
        self._tasks = [asyncio.create_task(self._worker()), asyncio.create_task(self._patch_worker())]
        for r in self.store.list_reports():
            if r["status"] in ("queued", "processing"):
                self.store.update_report(r["id"], status="queued", stage=None)
                self.queue.put_nowait(r["id"])
            elif r["status"] == "patching":
                self.patch_queue.put_nowait(r["id"])

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()

    # ---- events ---------------------------------------------------------
    async def emit(self, report_id: str | None, type_: str, payload: dict[str, Any] | None = None) -> None:
        event = self.store.add_event(report_id, type_, payload or {})
        for q in list(self.subscribers):
            q.put_nowait(event)

    # ---- intake ---------------------------------------------------------
    def submit(self, *, title: str, body: str, reporter: str, channel: str, attachments: dict[str, str] | None = None,
               is_test_data: bool = False, report_id: str | None = None) -> str:
        seq = self.store.next_seq()
        rid = report_id or f"R{seq:03d}-{uuid.uuid4().hex[:4]}"
        self.store.insert_report({
            "id": rid, "seq": seq, "project": PROJECT, "title": title, "body": body, "reporter": reporter,
            "channel": channel, "attachments": attachments or {}, "is_test_data": 1 if is_test_data else 0,
            "received_at": time.time(), "status": "queued", "evidence": {},
        })
        self.queue.put_nowait(rid)
        return rid

    def reset(self) -> None:
        self.generation += 1
        for q in (self.queue, self.patch_queue):
            while not q.empty():
                q.get_nowait()
        self.store.delete_all()
        cleanup_runs(self.settings.runs_dir, keep=0) if self.settings.runs_dir.exists() else None

    async def load_demo(self) -> list[str]:
        self.reset()
        await self.emit(None, "demo_loaded", {})
        ids = []
        for r in load_demo_reports():
            ids.append(self.submit(title=r["title"], body=r["body"], reporter=r["reporter"], channel=r["channel"],
                                   attachments=r.get("attachments"), is_test_data=True, report_id=r["id"]))
            await self.emit(ids[-1], "received", {"title": r["title"]})
        return ids

    # ---- workers ----------------------------------------------------------
    async def _worker(self) -> None:
        while True:
            rid = await self.queue.get()
            gen = self.generation
            try:
                await self.process(rid, gen)
            except Exception as exc:  # keep the queue alive; record the failure on the card
                log.exception("pipeline failed for %s", rid)
                if gen == self.generation and self.store.get_report(rid):
                    self.store.update_report(rid, status="error", stage=None,
                                             summary=f"Pipeline error: {exc}", verdict_rule=traceback.format_exc()[-1500:])
                    await self.emit(rid, "error", {"message": str(exc)})

    async def _patch_worker(self) -> None:
        while True:
            rid = await self.patch_queue.get()
            gen = self.generation
            try:
                await self.patch(rid, gen)
            except Exception as exc:
                log.exception("patch loop failed for %s", rid)
                if gen == self.generation and self.store.get_report(rid):
                    self.store.update_report(rid, status="done", patch={"status": "error", "reason": str(exc)})
                    await self.emit(rid, "patch_done", {"status": "error"})

    # ---- the five stages -------------------------------------------------
    async def process(self, rid: str, gen: int) -> None:
        report = self.store.get_report(rid)
        if not report:
            return
        evidence: dict[str, Any] = {"timings": {}}

        def alive() -> bool:
            return gen == self.generation

        async def stage(name: str) -> float:
            self.store.update_report(rid, status="processing", stage=name)
            await self.emit(rid, "stage", {"stage": name})
            return time.perf_counter()

        def done(name: str, started: float) -> None:
            evidence["timings"][name] = int((time.perf_counter() - started) * 1000)
            self.store.update_report(rid, evidence=evidence)

        # 1. extract
        t = await stage("extract")
        evidence["injection"] = detect_injection(report["title"], report["body"])
        claims, source = await extract_claims(self.gateway, rid, report["title"], report["body"])
        evidence["claims_source"] = source
        self.store.update_report(rid, claims=claims.model_dump())
        evidence["claims"] = claims.model_dump()
        done("extract", t)
        if not alive():
            return

        # 2. ground in the code
        t = await stage("ground")
        g = await asyncio.to_thread(ground, self.repo, claims)
        evidence["grounding"] = g.as_dict()
        done("ground", t)

        # 3. outside world
        t = await stage("outside")
        cves = await asyncio.gather(*(lookup_cve(self.settings, c, PROJECT) for c in claims.cve_ids))
        evidence["cves"] = list(cves)
        searches = [tavily_search(self.settings, c) for c in claims.cve_ids]
        if claims.functions:
            searches.append(tavily_search(self.settings, f"{PROJECT} {claims.functions[0]} vulnerability advisory"))
        evidence["web"] = list(await asyncio.gather(*searches)) if searches else []
        earlier = [r for r in self.store.list_reports() if r["seq"] < report["seq"]]
        evidence["duplicate"] = await find_duplicate(self.gateway, report, claims, earlier)
        done("outside", t)
        if not alive():
            return

        # Decide whether the sandbox is needed.
        plan = await plan_script(self.gateway, report, claims)
        evidence["plan"] = plan
        decision = pre_sandbox(evidence["claims"], evidence["grounding"], evidence["cves"], evidence["duplicate"], plan)

        # 4. sandbox
        if decision is None:
            t = await stage("sandbox")
            ok, why = await asyncio.to_thread(self.sandbox.available)
            if not ok:
                evidence["reproduction"] = {"error": why}
                from .verdict import Decision

                decision = Decision("needs_human", f"Sandbox unavailable: {why}")
            else:
                ref = g.resolved_version or (self.repo.tags() or ["HEAD"])[-1]
                repro = await reproduce(self.sandbox, self.repo_path, ref, report, plan)
                evidence["reproduction"] = repro
                crash = next((a["sanitizer"] for a in repro["attempts"] if a.get("sanitizer")), None)
                match = matches_claim(crash, claims) if crash else None
                evidence["match"] = {"ok": match[0], "detail": match[1]} if match else None
                decision = post_sandbox(evidence["claims"], evidence["grounding"], evidence["cves"], repro, match)
            done("sandbox", t)
        else:
            evidence["sandbox_skipped"] = "Stopped early: cheap checks were decisive, no sandbox started."
        if not alive():
            return

        # 5. decide and explain
        t = await stage("verdict")
        expl, expl_source = await explain(self.gateway, report, decision.verdict, decision.rule, evidence)
        evidence["explanation_source"] = expl_source
        done("verdict", t)
        if not alive():
            return
        reproduced = decision.verdict == "reproduced"
        self.store.update_report(
            rid, verdict=decision.verdict, verdict_rule=decision.rule, summary=expl.summary, reply=expl.reporter_reply,
            evidence=evidence, status="patching" if reproduced else "done", stage=None,
            finished_at=None if reproduced else time.time(),
            patch={"status": "queued"} if reproduced else None,
        )
        await self.emit(rid, "verdict", {"verdict": decision.verdict, "label": VERDICTS[decision.verdict]["label"]})
        if reproduced:
            self.patch_queue.put_nowait(rid)

    async def patch(self, rid: str, gen: int) -> None:
        report = self.store.get_report(rid)
        if not report or report.get("verdict") != "reproduced":
            return
        ev = report["evidence"]
        claims = Claims.model_validate(report["claims"])
        ref = ev["reproduction"]["ref"]
        self.store.update_report(rid, stage="patch", patch={"status": "running"})
        await self.emit(rid, "stage", {"stage": "patch"})

        async def emit(type_: str, payload: dict) -> None:
            if gen == self.generation:
                await self.emit(rid, type_, payload)

        result = await patch_loop(self.gateway, self.sandbox, self.repo_path, ref, report, claims, ev["reproduction"], emit)
        if gen != self.generation:
            return
        adv = None
        if result["status"] == "fixed":
            adv = advisory.build_draft(report, ev["reproduction"], result, PROJECT, ref, self.repo.tags())
        self.store.update_report(rid, patch=result, advisory=adv, status="done", stage=None, finished_at=time.time())
        await self.emit(rid, "patch_done", {"status": result["status"]})
