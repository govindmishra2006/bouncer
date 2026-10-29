# Implementation plan

Critical path: demo repo → claims + grounding → sandbox + verdict rules → dashboard → patch loop (cut line) → packaging. Status reflects this build.

| # | Task | Outcome | Files | Depends on | Tests | Done when | Status |
|---|---|---|---|---|---|---|---|
| 1 | Demo project | tinyparse with v1.0/v1.1/v1.2 tags, 48 tests, bugs A and B | `demo/tinyparse`, `demo/build_tinyparse.py` | – | `make test` inside the repo under ASan | Bug A crashes under ASan; suite passes | Done |
| 2 | Sandbox image + runner | Network-less, read-only, non-root container builds with sanitizers | `sandbox/Dockerfile`, `sandbox.py` | 1 | e2e | ASan trace captured from a `--network none` run | Done |
| 3 | Claim extraction | Regex + Nano, filtered to the report's own words | `extract.py`, `untrusted.py` | – | unit | 10 reports extract expected claims; hallucinations dropped | Done |
| 4 | Grounding | git checks with re-runnable commands | `grounding.py` | 1, 3 | unit | Fabricated / already-fixed / real cases detected | Done |
| 5 | Outside world | CVE Program API, Tavily, duplicates | `outside.py` | 3 | e2e | Fake CVE flagged; T02 marked duplicate of T01 | Done (Tavily path untested: no key) |
| 6 | Verdict rules | Code-only verdicts, mixed → Needs human | `verdict.py` | 4, 5, 2 | unit | All rule branches tested | Done |
| 7 | Explanations | Nano/Ultra with templates offline; fixed reply for reproduced | `explain.py` | 6 | e2e | No bug details in reproduced reply | Done |
| 8 | Gateway | Token Factory client, schema validation, retries, cost log, budget cap | `gateway.py` | – | unit (fake client) | Malformed output retried; calls logged | Done (live endpoint unverified) |
| 9 | Orchestrator + API + SSE | Ordered worker, patch worker, events | `pipeline.py`, `api.py` | 3–8 | API tests | 10/10 end-to-end | Done |
| 10 | Dashboard | Queue, case file, tabs, demo mode, paste form, limitations | `frontend/src` | 9 | lint, tsc, build, browser checks | Journey verified at 1440 px and 375 px, light and dark | Done |
| 11 | Patch loop | Root cause → patch → anti-cheat → 3 checks + regression-fails-on-old | `patcher.py`, `anticheat.py`, `offline_patches.py` | 2, 8 | unit + e2e | Cheat rejected; real fix passes | Done |
| 12 | Advisory | GitHub draft advisory payload + private fork, explicit click only | `advisory.py` | 11 | e2e (draft only) | Draft shown, never auto-sent | Done (publish path untested) |
| 13 | Packaging | README, docs, demo script, storyboard, screenshots | `README.md`, `docs/`, `submission/` | all | – | Files complete | Done |
| 14 | Hosting | Vercel dashboard + Nebius VM API | – | 13 | – | Public URL works logged out | Not done: needs accounts and credentials |
