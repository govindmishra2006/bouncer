# Demo script (2:50)

Setup before recording: `make api` and `make web` running, `.env` with `NEBIUS_API_KEY` (and ideally `TAVILY_API_KEY`), browser at 125% zoom, 1080p, queue cleared (**Clear** button). Use no music, or royalty-free music only. Show no real project logos.

> If you record without a Token Factory key, the Models tab will say "Rule-based fallback". In that case, do not say "Nemotron did X" on camera. Say "this step routes to Nemotron Nano / Super / Ultra on Token Factory; this recording uses the offline fallback". Don't fake it.

## 1. Hook (0:00–0:20)
**Screen:** title cards. "curl stops reading bug reports for five weeks." "GitHub adds a switch to disable pull requests." Then the empty Bouncer first-run screen.
**Say:** "In 2026, AI made fake bug reports free to write. Open-source maintainers still pay hours to disprove each one. Some projects stopped reading reports altogether."

## 2. The product (0:20–0:35)
**Action:** click **Run 10 test reports**.
**Screen:** 10 reports arrive; the five-segment tracks fill and stamps land; the queue re-sorts itself, Reproduced to the top and Fabricated to the bottom.
**Say:** "This is Bouncer. It checks every report against the real code, before a human reads it."

## 3. A fake, disproved with evidence (0:35–1:05)
**Action:** open **T04 "CRITICAL: Heap overflow in url_decode_safe()…"**, then scroll to "Checked against the code"; then open **T05** to show the CVE check.
**Screen:** red ✕ marks: "`url_decode_safe()` does not exist at v1.2, in any release, and the name never appears in git history", each with its `git` command. On T05: "The CVE Program has no record of CVE-2026-9381742". Point at the hatched fourth bar: no sandbox was started.
**Say:** "This report claims a critical overflow. Bouncer searched every release: the function doesn't exist, and the CVE it cites was never issued. Every check comes with the command that proves it. Evidence, not opinion, and no sandbox was needed."

## 4. A real bug, reproduced (1:05–1:40)
**Action:** open **T01**, then the **Sandbox** tab, then the **Models** tab.
**Screen:** isolation chips (`--network none`, read-only rootfs, cap-drop ALL…), the reporter's command, AddressSanitizer `heap-buffer-overflow` in `tp_url_decode src/url.c:42` in 3 of 3 attempts. Then the model table.
**Say:** "This one is real. Bouncer rebuilt the claimed version with AddressSanitizer in an isolated, network-less sandbox, and the crash reproduced three times out of three. Nemotron 3 Nano extracted the claims, and Ultra explained the result, all through Nebius Token Factory." *(Adjust to what the Models tab actually shows.)*

## 5. The fix, and the anti-cheat (1:40–2:15)
**Action:** **Fix** tab. Show attempt 1, then scroll to attempt 2.
**Screen:** Attempt 1: "Anti-cheat: disabled function. Adds an unconditional return to tp_url_decode()". Attempt 2: four green checks and the 2-line diff `i + 2 < len`.
**Say:** "Then it drafts a fix. Attempt one tried to just disable the function, and Bouncer rejected it. Attempt two passes: the crash is gone, all existing tests pass, the change is two lines, and the new regression test fails on the old code, so it really tests this bug."

## 6. Responsible disclosure (2:15–2:35)
**Action:** **Private advisory** tab.
**Screen:** draft advisory, CWE-125, the two GitHub API calls, "Sent only when you click below".
**Say:** "The fix never goes public. It lands in a draft private security advisory, so the maintainer decides when to release."

## 7. Impact and honesty (2:35–2:50)
**Action:** point at the tally strip ("10/10 decided · 1 proven real · 1 fix verified · 2 sandboxes for 10 reports · 9 h saved"), then open **Limitations**.
**Say:** "Ten reports, one real bug, a verified fix, and about nine maintainer hours saved, assuming an hour per report checked by hand. Bouncer never closes a report on its own and never merges code. When it can't be sure, it says so."

## 8. Close (2:50–3:00)
**Screen:** wordmark, repo link, "Built with Nemotron on Nebius Token Factory".
**Say:** "Bouncer: let maintainers spend their time on real bugs."
