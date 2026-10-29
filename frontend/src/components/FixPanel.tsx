"use client";

import { GitPullRequestDraft, Lock } from "lucide-react";
import { useState } from "react";
import { api, type Health, type ReportDetail } from "@/lib/api";
import { CodeBlock, DiffView, Pill, Rich, Section, StatusMark } from "./ui";

const CHECK_NAMES: Record<string, string> = {
  regression_fails_on_old: "New regression test fails on the unfixed code",
  bug_gone: "The bug is gone",
  tests_pass: "Nothing else broke",
  small: "The change is small",
};

export function FixPanel({ report }: { report: ReportDetail }) {
  const p = report.patch;
  if (!p || p.status === "queued" || (p.status === "running" && !p.attempts)) {
    return (
      <p className="py-6 text-[14px] text-ink-2">
        <span className="seg-active mr-2 inline-block h-2 w-2 rounded-full bg-ink-2" />
        Drafting a fix: root cause first, then up to 5 patch attempts, each checked in a fresh sandbox.
      </p>
    );
  }
  if (p.status === "error") return <p className="py-6 text-[14px] text-false">The patch loop failed: {p.reason}</p>;
  const attempts = p.attempts || [];
  return (
    <div>
      <div
        className={`mt-3 rounded-md border p-4 ${p.status === "fixed" ? "border-proof/40 bg-proof-bg" : "border-warn/40 bg-warn-bg"}`}
      >
        <p className={`text-[15px] font-semibold ${p.status === "fixed" ? "text-proof" : "text-warn"}`}>
          {p.status === "fixed"
            ? `Fix verified on attempt ${attempts.length} of up to ${p.max_attempts}`
            : "Could not fix safely"}
        </p>
        <p className="mt-1 text-[13.5px] text-ink-2">
          {p.status === "fixed"
            ? "It is a draft for review, never a merge. It goes into a private advisory, not a public pull request."
            : p.reason}
        </p>
      </div>

      {p.root_cause && (
        <Section title="Root cause" aside={p.root_cause.source === "nemotron-ultra" ? "Nemotron 3 Ultra" : p.root_cause.source}>
          <p className="text-[14.5px] leading-relaxed"><Rich text={p.root_cause.root_cause} /></p>
          {p.root_cause.fix_strategy && !p.root_cause.fix_strategy.startsWith("Model unavailable") && (
            <p className="mt-2 text-[13.5px] text-ink-2">Strategy: {p.root_cause.fix_strategy}</p>
          )}
        </Section>
      )}

      {attempts.map((a) => (
        <Section
          key={a.n}
          title={`Attempt ${a.n}`}
          aside={
            <span className="inline-flex items-center gap-2">
              <span>{a.source}</span>
              <Pill tone={a.outcome === "passed" ? "proof" : a.outcome === "rejected" ? "false" : "warn"}>
                {a.outcome === "passed" ? "Passed all checks" : a.outcome === "rejected" ? "Rejected before sandbox" : a.outcome === "failed" ? "Failed in sandbox" : "Stopped"}
              </Pill>
            </span>
          }
        >
          {a.rationale && <p className="text-[14px] text-ink-2">{a.rationale}</p>}
          {a.anticheat && a.anticheat.length > 0 && (
            <ul className="mt-3 space-y-1.5">
              {a.anticheat.map((v, i) => (
                <li key={i} className="flex gap-2 text-[13.5px]">
                  <StatusMark status="false" />
                  <span>
                    <span className="font-semibold text-false">Anti-cheat: {v.rule.replace(/-/g, " ")}.</span> <Rich text={v.detail} />
                  </span>
                </li>
              ))}
            </ul>
          )}
          {a.checks && (
            <ul className="mt-3 space-y-1.5">
              {Object.entries(a.checks).map(([k, c]) => (
                <li key={k} className="flex gap-2 text-[13.5px]">
                  <StatusMark status={c.pass ? "pass" : "fail"} />
                  <span>
                    <span className="font-medium">{CHECK_NAMES[k] || k}.</span> <span className="text-ink-2"><Rich text={c.detail} /></span>
                  </span>
                </li>
              ))}
            </ul>
          )}
          {a.diff && (
            <div className="mt-3">
              <DiffView diff={a.diff} />
            </div>
          )}
          {a.test_diff && a.outcome === "passed" && (
            <details className="mt-2">
              <summary className="cursor-pointer text-[13px] text-ink-2">Regression test added by this attempt</summary>
              <div className="mt-2">
                <DiffView diff={a.test_diff} />
              </div>
            </details>
          )}
          {a.feedback && a.outcome !== "passed" && (
            <p className="mt-3 text-[13px] text-ink-3">
              Fed back to the next attempt ({a.feedback_source}): <Rich text={a.feedback} />
            </p>
          )}
          {a.logs?.regress_on_old && a.outcome !== "rejected" && (
            <details className="mt-2">
              <summary className="cursor-pointer text-[13px] text-ink-2">Sandbox logs</summary>
              <CodeBlock className="mt-2" maxH="max-h-72">
                {`# regression test on the unfixed code\n${a.logs.regress_on_old}\n# full test suite on the fixed code\n${a.logs.fixed_tests}`}
              </CodeBlock>
            </details>
          )}
        </Section>
      ))}
    </div>
  );
}

export function AdvisoryPanel({ report, health, onChanged }: { report: ReportDetail; health: Health | null; onChanged: () => void }) {
  const a = report.advisory!;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(a.error || null);
  const canSend = !!health?.github && !a.sent;
  return (
    <div>
      <div className="mt-3 flex gap-3 rounded-md border border-rule bg-sheet p-4">
        <Lock size={18} className="mt-0.5 shrink-0 text-ink-2" />
        <div className="text-[14px]">
          <p className="font-semibold">{a.sent ? "Draft advisory created on GitHub" : "Draft private security advisory"}</p>
          <p className="mt-1 text-ink-2">
            A public pull request would show attackers where the hole is before users can update. Bouncer puts the patch, regression
            test and root cause in a draft GitHub security advisory with a temporary private fork, visible only to maintainers.
          </p>
          {a.sent && a.html_url && (
            <a href={a.html_url} className="mt-2 inline-block underline" target="_blank" rel="noreferrer">
              Open {a.ghsa_id}
            </a>
          )}
        </div>
      </div>

      <Section title={a.payload.summary} aside={`${a.payload.cwe_ids.join(", ")}, severity ${a.payload.severity}`}>
        <div className="prose-sm max-w-none text-[13.5px] whitespace-pre-wrap text-ink-2">{a.payload.description.split("### Patch")[0]}</div>
      </Section>

      <Section title="GitHub API calls" aside="Sent only when you click below">
        <ol className="space-y-1.5 text-[13.5px]">
          {a.steps.map((s, i) => (
            <li key={i}>
              <span className="text-ink-3">{i + 1}.</span> <span className="font-mono text-[12.5px]">{s.call}</span>{" "}
              <span className="text-ink-3">{s.body}</span>
            </li>
          ))}
        </ol>
        <details className="mt-3">
          <summary className="cursor-pointer text-[13px] text-ink-2">Request body</summary>
          <CodeBlock className="mt-2" maxH="max-h-96">{JSON.stringify(a.payload, null, 2)}</CodeBlock>
        </details>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            disabled={!canSend || busy}
            onClick={async () => {
              setBusy(true);
              setError(null);
              try {
                const res = await api.publishAdvisory(report.id);
                if (res.error) setError(res.error);
                onChanged();
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
            className="inline-flex items-center gap-2 rounded bg-ink px-3 py-1.5 text-[13.5px] font-medium text-paper disabled:cursor-not-allowed disabled:opacity-40"
          >
            <GitPullRequestDraft size={15} /> {busy ? "Creating draft advisory…" : "Create draft advisory on GitHub"}
          </button>
          {!health?.github && (
            <span className="text-[12.5px] text-ink-3">
              Unavailable here: tinyparse is a local demo repo. Set GITHUB_TOKEN and GITHUB_REPO to use it on a real repository.
            </span>
          )}
        </div>
        {error && <p className="mt-2 text-[13px] text-false">{error}</p>}
      </Section>
    </div>
  );
}
