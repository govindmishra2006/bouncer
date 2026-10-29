# Project state (checkpoint 2026-10-23)

**Architecture:** FastAPI backend (`backend/bouncer`), SQLite, local Docker sandbox (`bouncer-sandbox:1`), Next.js 16 dashboard (`frontend`). All model calls go through `gateway.py` to Nebius Token Factory; without a key, labelled fallbacks are used.

**Implemented and verified:** the five-stage pipeline, verdict rules, patch loop with anti-cheat and the 3+1 sandbox checks, advisory draft, API + SSE, the dashboard (queue, case file, all tabs, demo mode, paste form, limitations), responsive layout and dark mode. All 10 test reports give the expected verdicts.

**Key decisions**
- Sandbox = local Docker `--network none` (Nebius Jobs lacks a network-off flag per the CLI reference).
- Quoted-code matching is whitespace-insensitive but otherwise exact.
- Model extractions are filtered to text present in the report.
- CVE existence comes from the CVE Program API (works without keys); Tavily is optional context.
- Offline patch candidates exist only for demo bug A and are labelled "not model output".

**Known issues / not verified**
- No live Nemotron calls (no `NEBIUS_API_KEY` in the build environment). Model IDs are unconfirmed; run `make check-models`.
- Tavily path untested (no key). GitHub advisory publish path untested.
- Not deployed. The single-project setup (tinyparse) is hard-wired in `pipeline.PROJECT`.

**Tests:** `make test` runs 28 pytest tests (unit, API, 10-report e2e with the real sandbox), plus eslint and tsc. `npm run build` passes. Browser checks done via the in-app browser and Playwright (`scripts/capture_screenshots.js`).

**Run:** `make setup`, then `make api` (port 8000) and `make web` (port 3000).

**Remaining:** add keys and do a live run; record the video; host (Vercel + Nebius VM); fill in the Devpost TODOs (closest competitor, maintainer quotes, feedback).
