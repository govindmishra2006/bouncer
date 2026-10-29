# Product strategy

## Format: a web dashboard backed by an agent API
The plan specifies a dashboard (Next.js + Tailwind), a FastAPI orchestrator and short-lived sandboxes. We kept that. A maintainer triages a *queue*, and a browser dashboard is the natural surface: shareable, recordable, and judges can open it without installing anything. The CLI runner (`backend/tests/run_demo.py`) is kept for reproducible evaluation.

## Target user
A volunteer maintainer of a small or mid-sized open-source C or Python project who receives security reports from strangers and cannot afford an hour per report.

## Core problem
Verifying a report (checking out the version, grepping for the function, looking up the CVE, running the PoC) is manual and slow. Generating a convincing fake is instant.

## Solution
Bouncer verifies claims mechanically, before a human reads anything:
1. Nemotron 3 Nano extracts claims. Anything the model extracts that is not literally in the report is dropped.
2. git grounds them across every release and the whole history.
3. The CVE Program API (and Tavily, when configured) checks the outside world, and earlier reports are compared for duplicates.
4. A network-less, read-only, non-root container builds the claimed version with ASan/UBSan and runs the reporter's own steps three times.
5. Code rules pick the verdict. Nemotron explains it and drafts a polite reply.

Reproduced bugs go into a patch loop that keeps a fix only if: the crash is gone, all tests pass, the diff is small, it passes anti-cheat, and a new regression test fails on the old code. The fix lands in a draft private advisory.

## Differentiators
- **Evidence, not "AI detection".** Every check on a card shows the exact `git` command or API URL that proves it. A judge can re-run any of them.
- **Asymmetric safety.** "Fabricated" requires a hard falsehood. Mixed evidence becomes "Needs human". A report can never talk its way to Reproduced, because only a sanitizer crash does that.
- **Model can't override code.** Models extract and explain; verdicts are rules. Prompt injections are flagged on the card.
- **Fixes are proven against the reported bug,** including a regression test that must fail on the unfixed code, and are never published.

## Major features (all implemented)
- Live queue that sorts itself by verdict as reports stream through the five stages.
- A verdict card with claims, grounding checks (with commands), CVE lookups, duplicate match, sandbox run (isolation flags, script, three attempts, sanitizer stack), explanation and reporter reply.
- Model panel per card: stage → model → tokens → latency → cost, with offline fallbacks labelled as such.
- Patch review: root cause, every attempt (rejected / failed / passed) with diff, anti-cheat findings and the three checks.
- Draft private GitHub advisory (exact REST payload, private-fork steps). Sent only on explicit click when a token is configured.
- Guided demo mode (10 labelled test reports) and "paste your own report".
- Maintainer actions (approve / reject / escalate). Nothing is auto-closed.

## Demonstration strategy
Open on the empty queue → one click loads 10 reports → cards flip to verdicts within seconds. Then open the Fabricated card ("`url_decode_safe()` never existed in any release"), the Reproduced card (real ASan trace from a `--network none` container), the patch loop (attempt 1 rejected by anti-cheat, attempt 2 passes), and the private advisory. Close on the hours-saved counter and the limitations panel.

## Honesty constraints we hold ourselves to
- Without `NEBIUS_API_KEY`, every model step runs a deterministic fallback, and the UI labels it "offline rules", never as Nemotron.
- Offline patch candidates are pre-written fixtures, labelled "offline scripted candidate (not model output)". The checks they go through are real.
- No GPU acceleration is claimed. Nemotron runs on Nebius-hosted infrastructure. Nothing runs on a local GPU.
