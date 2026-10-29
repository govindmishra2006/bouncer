"""SQLite storage for reports, evidence, model calls and pipeline events."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    seq INTEGER NOT NULL,
    project TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    reporter TEXT NOT NULL,
    channel TEXT NOT NULL,
    attachments TEXT NOT NULL DEFAULT '{}',
    is_test_data INTEGER NOT NULL DEFAULT 0,
    received_at REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    stage TEXT,
    verdict TEXT,
    verdict_rule TEXT,
    summary TEXT,
    reply TEXT,
    claims TEXT,
    evidence TEXT NOT NULL DEFAULT '{}',
    patch TEXT,
    advisory TEXT,
    decision TEXT,
    finished_at REAL
);
CREATE TABLE IF NOT EXISTS model_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT,
    stage TEXT NOT NULL,
    tier TEXT NOT NULL,
    model TEXT NOT NULL,
    provider TEXT NOT NULL,
    tokens_in INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0,
    ok INTEGER NOT NULL DEFAULT 1,
    error TEXT,
    ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT,
    ts REAL NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}'
);
"""

JSON_COLUMNS = {"attachments", "claims", "evidence", "patch", "advisory", "decision"}


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    # ---- reports --------------------------------------------------------
    def next_seq(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM reports").fetchone()
        return int(row[0])

    def insert_report(self, report: dict[str, Any]) -> None:
        cols = list(report)
        values = [json.dumps(report[c]) if c in JSON_COLUMNS else report[c] for c in cols]
        with self._lock:
            self._conn.execute(
                f"INSERT INTO reports ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})", values
            )
            self._conn.commit()

    def update_report(self, report_id: str, **fields: Any) -> None:
        if not fields:
            return
        sets = ", ".join(f"{k} = ?" for k in fields)
        values = [json.dumps(v) if k in JSON_COLUMNS and v is not None else v for k, v in fields.items()]
        with self._lock:
            self._conn.execute(f"UPDATE reports SET {sets} WHERE id = ?", [*values, report_id])
            self._conn.commit()

    def get_report(self, report_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        return _decode(row) if row else None

    def list_reports(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM reports ORDER BY seq").fetchall()
        return [_decode(r) for r in rows]

    def delete_all(self) -> None:
        with self._lock:
            self._conn.executescript("DELETE FROM reports; DELETE FROM model_calls; DELETE FROM events;")
            self._conn.commit()

    # ---- model calls ----------------------------------------------------
    def log_model_call(self, **call: Any) -> int:
        call.setdefault("ts", time.time())
        cols = list(call)
        with self._lock:
            cur = self._conn.execute(
                f"INSERT INTO model_calls ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                [call[c] for c in cols],
            )
            self._conn.commit()
        return int(cur.lastrowid)

    def model_calls(self, report_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if report_id:
                rows = self._conn.execute(
                    "SELECT * FROM model_calls WHERE report_id = ? ORDER BY id", (report_id,)
                ).fetchall()
            else:
                rows = self._conn.execute("SELECT * FROM model_calls ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def spend_since(self, since_ts: float) -> float:
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) FROM model_calls WHERE ts >= ?", (since_ts,)
            ).fetchone()
        return float(row[0])

    # ---- events ---------------------------------------------------------
    def add_event(self, report_id: str | None, type_: str, payload: dict[str, Any]) -> dict[str, Any]:
        ts = time.time()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO events (report_id, ts, type, payload) VALUES (?, ?, ?, ?)",
                (report_id, ts, type_, json.dumps(payload)),
            )
            self._conn.commit()
        return {"id": cur.lastrowid, "report_id": report_id, "ts": ts, "type": type_, "payload": payload}

    def events(self, report_id: str | None = None, after_id: int = 0) -> list[dict[str, Any]]:
        with self._lock:
            if report_id:
                rows = self._conn.execute(
                    "SELECT * FROM events WHERE report_id = ? AND id > ? ORDER BY id", (report_id, after_id)
                ).fetchall()
            else:
                rows = self._conn.execute("SELECT * FROM events WHERE id > ? ORDER BY id", (after_id,)).fetchall()
        return [{**dict(r), "payload": json.loads(r["payload"])} for r in rows]


def _decode(row: sqlite3.Row) -> dict[str, Any]:
    out = dict(row)
    for col in JSON_COLUMNS:
        if out.get(col) is not None:
            out[col] = json.loads(out[col])
    out["is_test_data"] = bool(out.get("is_test_data"))
    return out
