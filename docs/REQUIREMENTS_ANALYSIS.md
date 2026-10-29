# Requirements analysis

**Source of truth:** `Bouncer — Project Plan.pdf` (24 pages, dated Oct 23, 2026, by @Govind). The folder holds no DOCX; this PDF is the only requirements document. All three embedded diagrams were inspected: the report pipeline, the architecture, and the 7-day build plan.

Labels used below:
- **[DOC]** stated in the plan.
- **[RULES via DOC]** the plan's own summary of the hackathon's Official Rules/FAQ. We have not read the official rules directly.
- **[ASSUMPTION]** our own decision.

## 1. Problem statement [DOC]

> Bouncer is an AI agent that checks every incoming bug or security report against the real code, reproduces the real ones in a sandbox, and drafts a verified fix, so open-source maintainers only spend time on reports that are proven true.

- **Audience:** maintainers of open-source projects who receive security and bug reports from the public.
- **The problem:** AI made a convincing fake report cost seconds to write, while disproving one still costs a human hours. In 2026, curl, Jazzband, HackerOne IBB, GitHub and Godot all restricted intake because of this.
- **Track:** Coding and Agentic Engineering.
- **Core rule:** every verdict rests on something Bouncer checked or ran, never on an AI opinion. Bouncer never auto-closes a report and never auto-merges a fix.

## 2. Mandatory requirements

| # | Requirement | Source |
|---|---|---|
| M1 | Runtime calls to **Nebius Token Factory**, or deployment on Nebius AI Cloud | RULES via DOC |
| M2 | Use at least one **NVIDIA open-source model**; the plan uses **Nemotron 3 Nano, Super and Ultra** | RULES via DOC |
| M3 | Models must not be reached through another provider (HuggingFace, OpenRouter) | RULES via DOC |
| M4 | Fit one track (Coding & Agentic Engineering) and make a genuine attempt at its goal | RULES via DOC |
| M5 | Five-stage pipeline: extract claims → ground in code → check outside world → reproduce in sandbox → decide and explain | DOC |
| M6 | Seven verdicts with the plan's exact rules and queue order (Reproduced top … Fabricated bottom) | DOC |
| M7 | Verdict computed by **code** from evidence; the model only explains it | DOC |
| M8 | "Fabricated" requires at least one hard, checkable falsehood; mixed evidence becomes "Needs human" | DOC |
| M9 | Cheap checks (stages 2–3) run first; fabricated reports never start a sandbox | DOC |
| M10 | Sandbox: one fresh container per run, no network, CPU/memory/disk limits, no secrets, non-root, read-only base | DOC |
| M11 | Reproduction with ASan + UBSan for C; record exit code, crash log and stack trace; 3 attempts | DOC |
| M12 | Patch loop for Reproduced reports only: Ultra root cause → Super patch + regression test → three checks → Nano failure summary; up to 5 attempts | DOC |
| M13 | Three checks: bug gone, full test suite passes, small diff (≤ ~40 lines, stack-trace files only) | DOC |
| M14 | Anti-cheat: reject disabling the function, catch-all hiding, sanitizers/warnings/tests turned off, edited tests, special-casing the input; the regression test must fail on the unfixed code | DOC |
| M15 | Security fixes go to a **draft GitHub security advisory with a temporary private fork**, never a public PR | DOC |
| M16 | Report text is untrusted: wrapped in prompts; injection attempts flagged (test report #10) | DOC |
| M17 | Structured JSON model output validated against a schema, rejected and retried if malformed | DOC |
| M18 | A model gateway that logs model, tokens, latency and cost per stage, with a per-card panel showing which model did what | DOC |
| M19 | Tavily search for CVE/advisory checks and duplicates | DOC |
| M20 | Demo project `tinyparse`: fictional C library of about 600 lines with URL decoder, INI parser and string utils; tags v1.0/v1.1/v1.2; about 40 tests; planted bugs A (one-byte heap overflow on trailing `%`, v1.2) and B (INI off-by-one in v1.0, fixed in v1.1) | DOC |
| M21 | 10 labelled test reports with the expected verdicts from the plan | DOC |
| M22 | Dashboard: queue sorted by verdict, evidence cards, model panel, patch review, guided demo mode, paste-your-own-report | DOC |
| M23 | Public repo with MIT licence, README (with NVIDIA/Nebius section and model-routing table), `.env.example`, no keys | RULES via DOC |
| M24 | Demo video under 3 minutes (script provided in the plan); no third-party trademarks | RULES via DOC |
| M25 | Published limitations, word for word from the plan, in README and write-up | DOC |
| M26 | Feedback log on Token Factory, Nebius services and each Nemotron model | RULES via DOC |

## 3. Optional / stretch requirements [DOC]

- Orchestrator deployed as a Nebius Serverless Endpoint.
- Sandbox on Nebius Serverless Jobs, with a Docker `--network none` fallback on a Nebius VM.
- A second repo for credibility: read-only claim checking of public fake reports against a real project.
- GitHub App intake (issues with a `security` label, private vulnerability reports).
- Replay mode serving recorded runs, plus a rate-limited live mode with a daily budget cap.
- Hosted dashboard on Vercel.

## 4. Judging criteria [RULES via DOC]

Four criteria, each scored 1–5 and weighted equally:
1. **Technological implementation:** closed loop, three Nemotron models with distinct jobs, sandboxes central.
2. **Design:** a complete product; queue sorted by verdict, evidence on every card, one-click advisory review, guided demo.
3. **Potential impact:** a specific problem for a specific audience, with "maintainer hours saved" shown.
4. **Quality of the idea:** verdicts from evidence (not "AI detection"), never auto-closing, private disclosure, anti-cheat rules.

Judges' advice reflected in the product: aha within 30 s; action first; show which model does what; publish limitations.

## 5. Technical constraints

- **[DOC]** Every model call goes to Token Factory through an OpenAI-compatible client.
- **[DOC]** The sandbox has no secrets and no network.
- **[DOC]** First version supports C (sanitizers) and pure Python; other languages get claim checking only.
- **[ASSUMPTION]** Local dev runs on macOS with Docker via colima (verified on this machine: arm64 Linux VM).
- **[VERIFIED]** Nebius `ai job create` has no flag to disable networking, its minimum timeout is 1 h, and it defaults to GPU platforms (CLI reference, docs.nebius.com). This is why we use the plan's documented fallback: a Docker `--network none` sandbox, which can run on a Nebius VM.

## 6. Expected submission artifacts

Devpost form (name, track, description, "built with", demo URL, repo URL, YouTube link, feedback), public GitHub repo with MIT licence, README, `.env.example`, demo repo and test reports, video under 3 minutes.

## 7. External dependencies

| Dependency | Needed for | Status in this environment |
|---|---|---|
| Nebius Token Factory API key (`NEBIUS_API_KEY`) | Nemotron calls | **Not available**; rule-based fallbacks, clearly labelled |
| Tavily API key (`TAVILY_API_KEY`) | Web search for CVEs/advisories | **Not available**; CVE existence is still checked against the public CVE Program API |
| Docker | Sandbox | Available (colima), verified |
| GitHub token + repo | Creating the draft advisory | Not configured; the payload is drafted and shown, never sent |
| Nebius Serverless Jobs / VM | Hosted sandbox | Not available (no credentials) |

## 8. Risks

- No Token Factory key in this environment, so live Nemotron output cannot be verified here. Mitigation: gateway plus fallbacks, `scripts/check_models.py`, and model IDs overridable by env.
- Model IDs come from third-party catalogue listings (Nebius docs are not public without login). Mitigation: env overrides and a `/v1/models` check script.
- LLM-written C patches may be weak. Mitigation: the plan's 5-attempt loop with real checks, and an honest "could not fix safely".
- Prompt injection. Mitigation: wrapping, detection, and code-computed verdicts.

## 9. Acceptance criteria

1. All 10 test reports get the expected verdict end to end (`backend/tests/run_demo.py`).
2. The Reproduced report shows a real ASan crash from a `--network none` container; Fabricated reports never start a sandbox.
3. The patch loop rejects a cheating patch, keeps a fix only when all checks pass in a fresh sandbox, and produces a draft private advisory.
4. Every card shows the evidence, the git/API command that proves each check, and a model panel distinguishing Nemotron calls from offline fallbacks.
5. The dashboard runs a guided demo, accepts pasted reports, and streams progress live.
6. README, limitations, architecture, demo script and storyboard are complete, with no secrets in the repo.
