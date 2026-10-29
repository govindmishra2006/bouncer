"""Runs the 10 demo reports through the full pipeline without the HTTP layer and prints a table.

Usage: .venv/bin/python tests/run_demo.py
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bouncer.config import ROOT, settings  # noqa: E402
from bouncer.db import Store  # noqa: E402
from bouncer.pipeline import Pipeline  # noqa: E402


async def main() -> int:
    store = Store(settings.data_dir / "e2e.sqlite3")
    p = Pipeline(store, settings)
    p.start()
    started = time.perf_counter()
    await p.load_demo()
    while any(r["status"] not in ("done", "error") for r in store.list_reports()):
        await asyncio.sleep(1)
    expected = {r["id"]: r["expected"] for r in json.loads((ROOT / "demo/reports/reports.json").read_text())["reports"]}
    ok = 0
    for r in store.list_reports():
        good = r["verdict"] == expected[r["id"]]
        ok += good
        patch = (r.get("patch") or {}).get("status", "")
        print(f"{'PASS' if good else 'FAIL'} {r['id']} expected={expected[r['id']]:<15} got={str(r['verdict']):<15} {patch:<14} {r['verdict_rule']}")
    print(f"{ok}/10 verdicts as expected in {time.perf_counter() - started:.0f}s")
    await p.stop()
    return 0 if ok == 10 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
