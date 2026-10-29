# Bouncer: working notes
- Requirements: `Bouncer — Project Plan.pdf`; analysis in docs/REQUIREMENTS_ANALYSIS.md; current state in docs/PROJECT_STATE.md.
- Run: `make api` + `make web`; tests: `make test`; 10-report check: `make demo`.
- Verdicts are computed in backend/bouncer/verdict.py only; models never choose them.
- Never label fallback output as Nemotron; offline steps log provider "offline-rules".
- Docker job dirs must live under $HOME (colima mount); data/ is gitignored.
