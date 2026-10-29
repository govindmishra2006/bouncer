# Devpost write-up (draft)

**Name:** Bouncer
**Tagline:** Filters the fake bug reports, proves the real ones, and drafts the fix.
**Track:** Coding and Agentic Engineering
**Built with:** NVIDIA Nemotron 3 Nano, Super and Ultra · Nebius Token Factory · Docker sandbox (AddressSanitizer, UBSan) · CVE Program API · Tavily · FastAPI · Next.js

## What it does
AI made convincing fake security reports free to write, and disproving one still costs a volunteer maintainer an hour. Bouncer verifies every report before a human reads it:
1. extracts the concrete claims (Nemotron 3 Nano);
2. checks them against the real repository with git, across every release;
3. checks whether cited CVEs were ever issued and whether the bug was already reported;
4. builds the claimed version with sanitizers in a network-less sandbox and runs the reporter's own steps three times;
5. computes the verdict with rules over that evidence. Nemotron only explains it.

For reproduced bugs, a patch loop drafts a fix. Ultra writes the root cause, Super writes the patch and a regression test, and Nano summarises failures. Bouncer keeps a fix only if the crash is gone, all tests pass, the diff is small, it passes an anti-cheat scan, and the regression test fails on the old code. The fix goes into a draft private GitHub security advisory, never a public PR.

## How it uses Nemotron and Nebius
Every model call goes through one gateway to Nebius Token Factory, with schema-validated JSON, retries, and per-call logging of model, tokens, latency and cost, shown on each card. See the routing table in the README.

## What makes it different
- Verdicts come from evidence, not "AI detection". Each check shows the command that proves it.
- "Fabricated" needs a hard, checkable falsehood; mixed evidence becomes "Needs human".
- Model output can drop a claim but never invent one (extractions are filtered to the report's own words).
- Never auto-closes, never auto-merges, never publishes a security fix.

## Closest existing tool
TODO before submitting: spend 30 minutes searching GitHub and Product Hunt for 2026 "AI security report triage" tools and name the closest one here, with how Bouncer differs (per the project plan).

## Maintainer input
TODO: quote the three maintainers contacted on day 1 (per the project plan), or remove this section.

## Limitations
(Paste the README "Limitations" section verbatim.)

## Feedback
(Paste from `docs/FEEDBACK_LOG.md` after the live run.)
