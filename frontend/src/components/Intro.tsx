"use client";

export function Intro({ onLoad, onPaste, busy }: { onLoad: () => void; onPaste: () => void; busy: boolean }) {
  return (
    <div className="mx-auto max-w-[680px] px-6 pt-14 pb-16 sm:px-8">
      <h2 className="cut-narrow text-[44px] leading-[1.02] font-extrabold tracking-tight text-balance sm:text-[56px]">
        Prove a bug report is real before anyone spends an hour on it.
      </h2>
      <p className="mt-5 max-w-[60ch] text-[17px] leading-relaxed text-ink-2">
        A fake security report now takes seconds to write and still takes a maintainer an hour to disprove. Bouncer checks every
        claim against the real code, runs the reporter&apos;s proof in a locked-down sandbox, and drafts a fix for the bugs that are
        real. Every verdict comes with the evidence behind it.
      </p>
      <div className="mt-7 flex flex-wrap gap-3">
        <button
          onClick={onLoad}
          disabled={busy}
          className="rounded bg-ink px-4 py-2.5 text-[15px] font-semibold text-paper hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Loading test reports…" : "Run 10 test reports"}
        </button>
        <button onClick={onPaste} className="rounded border border-rule-strong px-4 py-2.5 text-[15px] font-medium hover:bg-sheet-2">
          Paste your own report
        </button>
      </div>
      <p className="mt-3 text-[13px] text-ink-3">
        The test reports target tinyparse, a fictional C library made for this demo, with two planted bugs and three releases.
      </p>

      <ol className="mt-12 space-y-4 border-t border-rule pt-6">
        {[
          ["Extract the claims", "Version, files, functions, line numbers, quoted code, CVE IDs and steps, as a checkable list."],
          ["Check them against the code", "git grep across every release, exact match of quoted code, git log -S for fixes."],
          ["Check the outside world", "Is the CVE real? Was this already reported? Fakes usually stop here, before any sandbox starts."],
          ["Reproduce in a sandbox", "Build the claimed version with AddressSanitizer, run the steps three times with no network."],
          ["Decide and explain", "Rules pick the verdict from the evidence; Nemotron explains it and drafts a reply. Nothing is auto-closed."],
        ].map(([t, d], i) => (
          <li key={t} className="grid grid-cols-[28px_1fr] gap-x-3">
            <span className="cut-narrow text-[22px] leading-none font-extrabold text-ink-3">{i + 1}</span>
            <div>
              <p className="text-[15px] font-semibold">{t}</p>
              <p className="text-[14px] text-ink-2">{d}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-6 text-[14px] text-ink-2">
        Bugs that reproduce go on to the fix loop. A patch is kept only if the crash is gone, every existing test passes, the change is
        small, and a new regression test fails on the old code. It then lands in a private advisory, never a public pull request.
      </p>
    </div>
  );
}
