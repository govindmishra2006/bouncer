# Video storyboard

Target: under 3:00, 1080p, browser zoom 125%. Waiting time is sped up and labelled on screen ("sped up 4×"). All data is the fictional tinyparse project and labelled test reports.

| # | Time | Screen / visual | Narration | User action | Expected result | Transition |
|---|---|---|---|---|---|---|
| 1 | 0:00–0:08 | Black title card: "curl stops reading security reports for five weeks (2026)" | "In 2026, AI made fake bug reports free to write." | none | n/a | Hard cut |
| 2 | 0:08–0:20 | Title card: "GitHub adds a switch to disable pull requests", then Bouncer first-run page | "Maintainers still pay hours to disprove each one. Some projects stopped reading reports altogether." | none | First-run page visible with "Run 10 test reports" | Cursor moves to button |
| 3 | 0:20–0:35 | Queue fills; stamps land; rows re-sort | "This is Bouncer. It checks every report against the real code, before a human reads it." | Click **Run 10 test reports** | 10/10 decided in a few seconds offline (longer with live models; speed up and label it) | Click T04 |
| 4 | 0:35–0:52 | T04 case file: Fabricated stamp, summary, red ✕ checks with `git` commands | "This report claims a critical overflow. The function doesn't exist in any release…" | Scroll to "Checked against the code" | Three hard falsehoods; hatched sandbox bar, "Not needed: stopped early" | Click T05 |
| 5 | 0:52–1:05 | T05: CVE check | "…and the CVE it cites was never issued. Evidence, not opinion." | Point at CVE row | "The CVE Program has no record of CVE-2026-9381742" | Click T01 |
| 6 | 1:05–1:22 | T01 Sandbox tab: isolation chips, command, ASan frames | "This one is real. Bouncer rebuilt v1.2 with AddressSanitizer in a network-less sandbox; it crashed 3 times out of 3." | Click **Sandbox** | `heap-buffer-overflow`, `#0 tp_url_decode src/url.c:42` | Click Models |
| 7 | 1:22–1:40 | Models tab: per-step model, tokens, latency, cost | "Nemotron 3 Nano extracted the claims, Super writes code, Ultra does root cause, all via Nebius Token Factory." | Click **Models** | With a key: Token Factory rows with tokens and latency. Without: "Rule-based fallback" rows, and the narration must say so | Click Fix |
| 8 | 1:40–2:00 | Fix tab: attempt 1 rejected | "It drafts a fix. Attempt one tried to disable the function; Bouncer rejected it." | Click **Fix** | Red "Anti-cheat: disabled function" | Scroll |
| 9 | 2:00–2:15 | Attempt 2: four green checks, 2-line diff | "Attempt two passes: crash gone, all tests pass, tiny diff, and the new test fails on the old code." | Scroll to attempt 2 | All four checks green | Click Private advisory |
| 10 | 2:15–2:35 | Private advisory tab | "The fix never goes public. It lands in a private security advisory." | Click **Private advisory** | Draft, CWE-125, API calls listed, nothing sent | Zoom out to tally |
| 11 | 2:35–2:50 | Tally strip, then Limitations dialog | "Ten reports, one real bug, a verified fix, about nine hours saved. Bouncer never closes a report on its own. When it can't be sure, it says so." | Click **Limitations** | Dialog with the published limitations; small on-screen text: "assumes 1 h per report checked by hand" | Fade |
| 12 | 2:50–3:00 | Wordmark + repo URL + "Built with Nemotron on Nebius Token Factory" | "Bouncer: let maintainers spend their time on real bugs." | none | n/a | End |

## Capture procedure
1. `make clean && make api` and `make web`; in the browser, click **Clear**.
2. Start screen recording (QuickTime: File → New Screen Recording, or OBS at 1080p30).
3. Follow the table. Keep the cursor still while narrating.
4. In the editor, speed up any model wait and label it, then add the two title cards. Use no copyrighted music or third-party logos.
5. Export under 3:00 and upload to YouTube as **Public**.

Still frames for each scene are in `submission/screenshots/` (captured from the running app by `scripts/capture_screenshots.js`).
