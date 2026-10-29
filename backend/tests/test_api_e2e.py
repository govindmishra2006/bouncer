"""API and end-to-end tests. The e2e test needs Docker and the sandbox image (skipped otherwise)."""
import json
import time

import pytest
from fastapi.testclient import TestClient

from bouncer.api import app
from bouncer.config import ROOT, settings
from bouncer.sandbox import DockerSandbox

EXPECTED = {r["id"]: r["expected"] for r in json.loads((ROOT / "demo/reports/reports.json").read_text())["reports"]}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    h = client.get("/api/health").json()
    assert h["models"]["live"] is False
    assert h["project"]["tags"] == ["v1.0", "v1.1", "v1.2"]


def test_submit_validation(client):
    assert client.post("/api/reports", json={"title": "x", "body": "short"}).status_code == 422
    bad = {"title": "ok title", "body": "long enough body", "attachments": {"../etc/passwd": "x"}}
    assert client.post("/api/reports", json=bad).status_code == 422
    assert client.get("/api/reports/nope").status_code == 404
    assert client.get("/api/repo/file", params={"ref": "v1.2", "path": "../x"}).status_code == 400


def test_repo_file(client):
    r = client.get("/api/repo/file", params={"ref": "v1.1", "path": "src/url.c"})
    assert r.status_code == 200 and "i + 2 < len" in r.json()["content"]


@pytest.mark.skipif(not DockerSandbox(settings).available()[0], reason="Docker sandbox image not available")
def test_demo_queue_end_to_end(client):
    client.post("/api/demo/load")
    deadline = time.time() + 300
    while time.time() < deadline:
        data = client.get("/api/reports").json()
        if data["stats"]["in_progress"] == 0 and data["stats"]["decided"] == 10:
            break
        time.sleep(1)
    cards = {c["id"]: c for c in data["reports"]}
    assert {i: cards[i]["verdict"] for i in EXPECTED} == EXPECTED
    # Queue order: reproduced first, fabricated last.
    assert data["reports"][0]["verdict"] == "reproduced" and data["reports"][-1]["verdict"] == "fabricated"
    # Fabricated reports never started a sandbox.
    assert not any(c["sandbox_used"] for c in data["reports"] if c["verdict"] == "fabricated")
    t01 = client.get("/api/reports/T01").json()
    assert t01["patch"]["status"] == "fixed"
    outcomes = [a["outcome"] for a in t01["patch"]["attempts"]]
    assert outcomes == ["rejected", "passed"]
    passed = t01["patch"]["attempts"][-1]["checks"]
    assert all(c["pass"] for c in passed.values())
    assert t01["advisory"]["sent"] is False and t01["advisory"]["payload"]["cwe_ids"] == ["CWE-125"]
    assert t01["reply"].startswith("Thank you for your report. We have received it and it is under review")
    t10 = client.get("/api/reports/T10").json()
    assert t10["evidence"]["injection"]
    assert data["stats"]["hours_saved"] == 9
