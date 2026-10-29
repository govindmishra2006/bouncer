"use client";

import { ArrowLeft, Box, ExternalLink, Lock, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { api, type Health, type ReportDetail } from "@/lib/api";
import { CHANNELS, STAGES, VERDICTS, sourceLabel } from "@/lib/verdicts";
import { CodeBlock, CopyButton, Pill, Rich, Section, Stamp, StatusMark, stageStates, timeAgo } from "./ui";
import { FixPanel, AdvisoryPanel } from "./FixPanel";
import { ModelsPanel } from "./ModelsPanel";

type Tab = "evidence" | "sandbox" | "fix" | "advisory" | "reply" | "models" | "report";

export function CaseFile({
  report,
  health,
  onBack,
  onChanged,
}: {
  report: ReportDetail;
  health: Health | null;
  onBack: () => void;
  onChanged: () => void;
}) {
  const [tab, setTab] = useState<Tab>("evidence");
  const ev = report.evidence || {};
  const v = report.verdict ? VERDICTS[report.verdict] : null;

  const tabs: { key: Tab; label: string; show: boolean }[] = [
    { key: "evidence", label: "Evidence", show: true },
    { key: "sandbox", label: "Sandbox", show: true },
    { key: "fix", label: "Fix", show: report.verdict === "reproduced" },
    { key: "advisory", label: "Private advisory", show: !!report.advisory },
    { key: "reply", label: "Reply to reporter", show: !!report.reply },
    { key: "models", label: "Models", show: true },
    { key: "report", label: "Original report", show: true },
  ];

  return (
    <article className="mx-auto max-w-[920px] px-5 pt-5 pb-16 sm:px-8">
      <button onClick={onBack} className="mb-4 inline-flex items-center gap-1 text-[13px] text-ink-2 lg:hidden">
        <ArrowLeft size={14} /> Queue
      </button>

      {/* Header */}
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12.5px] text-ink-3">
            <span className="font-mono">{report.id}</span>
            <span>{CHANNELS[report.channel] || report.channel}</span>
            <span>from {report.reporter}</span>
            <span>{timeAgo(report.received_at)}</span>
            {report.is_test_data && <Pill>labelled test data</Pill>}
          </div>
          <h2 className="mt-1.5 text-[24px] leading-tight font-semibold text-balance">{report.title}</h2>
        </div>
        <div className="shrink-0 sm:pt-6">{report.verdict ? <Stamp verdict={report.verdict} size="lg" /> : <Working report={report} />}</div>
      </header>

      {/* Verdict block */}
      {v && (
        <div className="mt-5 rounded-md border border-rule bg-sheet p-4">
          <p className="text-[15.5px] leading-relaxed text-pretty"><Rich text={report.summary} /></p>
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12.5px] text-ink-3">
            <span>
              <span className="text-ink-2">Rule applied:</span> <Rich text={report.verdict_rule} />
            </span>
            <span>Explanation: {sourceLabel(ev.explanation_source)}</span>
          </div>
          <Decision report={report} onChanged={onChanged} />
        </div>
      )}
      {report.status === "error" && (
        <div className="mt-5 rounded-md border border-false/40 bg-false-bg p-4 text-[14px] text-false">{report.summary}</div>
      )}

      {ev.injection && ev.injection.length > 0 && (
        <div className="mt-4 flex gap-3 rounded-md border border-warn/40 bg-warn-bg p-3.5 text-[13.5px]">
          <ShieldAlert size={18} className="mt-0.5 shrink-0 text-warn" />
          <div>
            <p className="font-semibold text-warn">Hidden instructions found in this report</p>
            <p className="mt-0.5 text-ink-2">
              They were treated as data. Models only read report text inside an untrusted-data wrapper, and the verdict is computed by
              rules, so this text could not change it.
            </p>
            <ul className="mt-2 space-y-1">
              {ev.injection.map((f, i) => (
                <li key={i} className="text-ink-2">
                  <span className="text-ink">{f.kind}:</span> <span className="font-mono text-[12px]">{f.excerpt}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      <Timeline report={report} />

      {/* Tabs */}
      <div role="tablist" aria-label="Case file sections" className="mt-6 flex gap-1 overflow-x-auto border-b border-rule scroll-thin">
        {tabs
          .filter((t) => t.show)
          .map((t) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={tab === t.key}
              onClick={() => setTab(t.key)}
              className={`-mb-px shrink-0 border-b-2 px-3 py-2 text-[14px] ${
                tab === t.key ? "border-ink font-semibold text-ink" : "border-transparent text-ink-2 hover:text-ink"
              }`}
            >
              {t.label}
            </button>
          ))}
      </div>
      <div role="tabpanel" className="pt-2">
        {tab === "evidence" && <EvidencePanel report={report} />}
        {tab === "sandbox" && <SandboxPanel report={report} />}
        {tab === "fix" && <FixPanel report={report} />}
        {tab === "advisory" && report.advisory && <AdvisoryPanel report={report} health={health} onChanged={onChanged} />}
        {tab === "reply" && <ReplyPanel report={report} />}
        {tab === "models" && <ModelsPanel report={report} health={health} />}
        {tab === "report" && <OriginalPanel report={report} />}
      </div>
    </article>
  );
}

function Working({ report }: { report: ReportDetail }) {
  const label = report.status === "queued" ? "Waiting in line" : STAGES.find((s) => s.key === report.stage)?.label ?? "Working";
  return (
    <span className="inline-flex items-center gap-2 text-[14px] text-ink-2">
      <span className="seg-active h-2 w-2 rounded-full bg-ink-2" />
      {label}…
    </span>
  );
}

function Timeline({ report }: { report: ReportDetail }) {
  const states = stageStates(report.card);
  const timings = report.evidence?.timings || {};
  const color = report.verdict ? VERDICTS[report.verdict].color : "var(--ink-2)";
  return (
    <ol className="mt-6 grid grid-cols-1 gap-2 sm:grid-cols-5 sm:gap-0" aria-label="Pipeline stages">
      {STAGES.map((s, i) => {
        const st = states[i];
        const skipped = st === "skipped";
        return (
          <li key={s.key} className="relative sm:pr-3">
            <div
              className={`h-[5px] rounded-[1px] ${st === "active" ? "seg-active" : ""} ${skipped ? "seg-skipped" : ""}`}
              style={{ background: st === "done" ? color : st === "active" ? "var(--ink-2)" : skipped ? undefined : "var(--rule)" }}
            />
            <p className="mt-1.5 text-[13px] font-medium">
              <span className="text-ink-3">{i + 1}</span> {s.label}
            </p>
            <p className="text-[12px] text-ink-3">
              {skipped
                ? "Not needed: stopped early"
                : st === "done" && timings[s.key] !== undefined
                  ? `${timings[s.key] < 1000 ? `${timings[s.key]} ms` : `${(timings[s.key] / 1000).toFixed(1)} s`}`
                  : st === "active"
                    ? "running"
                    : ""}
            </p>
          </li>
        );
      })}
    </ol>
  );
}

function Decision({ report, onChanged }: { report: ReportDetail; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const d = report.decision;
  const act = async (action: string) => {
    setBusy(true);
    try {
      await api.decide(report.id, action);
      onChanged();
    } finally {
      setBusy(false);
    }
  };
  const names: Record<string, string> = { approve: "Verdict accepted", reject: "Verdict rejected", escalate: "Escalated", reopen: "Reopened" };
  return (
    <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-rule pt-3">
      {d && d.action !== "reopen" ? (
        <>
          <span className="text-[13.5px] font-medium">{names[d.action]} by maintainer</span>
          <span className="text-[12.5px] text-ink-3">{timeAgo(d.at)}</span>
          <button disabled={busy} onClick={() => act("reopen")} className="ml-auto text-[13px] text-ink-2 underline underline-offset-2">
            Undo
          </button>
        </>
      ) : (
        <>
          <span className="mr-1 text-[13px] text-ink-3">Bouncer never closes a report on its own.</span>
          <button
            disabled={busy}
            onClick={() => act("approve")}
            className="rounded bg-ink px-3 py-1.5 text-[13px] font-medium text-paper hover:opacity-90 disabled:opacity-50"
          >
            Accept verdict
          </button>
          <button
            disabled={busy}
            onClick={() => act("reject")}
            className="rounded border border-rule-strong px-3 py-1.5 text-[13px] font-medium hover:bg-sheet-2 disabled:opacity-50"
          >
            Reject verdict
          </button>
          <button
            disabled={busy}
            onClick={() => act("escalate")}
            className="rounded border border-rule-strong px-3 py-1.5 text-[13px] font-medium hover:bg-sheet-2 disabled:opacity-50"
          >
            Escalate
          </button>
        </>
      )}
    </div>
  );
}

function EvidencePanel({ report }: { report: ReportDetail }) {
  const ev = report.evidence || {};
  const claims = (ev.claims || {}) as Record<string, unknown>;
  const g = ev.grounding;
  if (!ev.claims) return <p className="py-6 text-[14px] text-ink-3">Claims are being extracted…</p>;
  const list = (k: string) => ((claims[k] as string[]) || []).filter(Boolean);
  const rows: [string, string][] = [
    ["Version", (claims.version as string) || "not stated"],
    ["Files", list("files").join(", ") || "none named"],
    ["Functions", list("functions").map((f) => `${f}()`).join(", ") || "none named"],
    ["Lines", ((claims.lines as { file: string | null; line: number }[]) || []).map((l) => `${l.file ?? "?"}:${l.line}`).join(", ") || "none"],
    ["Quoted code", `${list("quoted_code").length} snippet(s)`],
    ["CVE IDs", list("cve_ids").join(", ") || "none"],
    ["Reproduction steps", claims.has_steps ? `${list("repro_commands").length} command(s)` : "none given"],
    ["Bug class", (claims.bug_class as string) || "not stated"],
    ["Claimed severity", (claims.claimed_severity as string) || "not stated"],
    ["Needs beyond a build", list("requires_environment").join(", ") || "nothing"],
  ];
  return (
    <div>
      <Section title="What the report claims" aside={`Extracted by ${sourceLabel(ev.claims_source)}`}>
        <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 text-[13.5px] sm:grid-cols-[170px_1fr]">
          {rows.map(([k, val]) => (
            <div key={k} className="contents">
              <dt className="text-ink-3">{k}</dt>
              <dd className="min-w-0 break-words">{val}</dd>
            </div>
          ))}
        </dl>
        {ev.claims_source !== "rules" && (
          <p className="mt-3 text-[12.5px] text-ink-3">
            Anything the model extracted that does not appear word for word in the report is discarded, so a model mistake can drop a
            claim but never invent one.
          </p>
        )}
      </Section>

      <Section title="Checked against the code" aside={g?.version_note}>
        {g && g.checks.length > 0 ? (
          <ul className="space-y-3">
            {g.checks.map((c, i) => (
              <li key={i} className="flex gap-3">
                <StatusMark status={c.status} />
                <div className="min-w-0 flex-1">
                  <p className="text-[14px]">
                    <span className="text-ink-3">{c.kind.replace("_", " ")}</span>{" "}
                    <span className="font-mono text-[12.5px]">{c.claim}</span>
                  </p>
                  <p className="text-[13.5px] text-ink-2"><Rich text={c.detail} /></p>
                  {c.command && c.command !== "-" && (
                    <div className="mt-1 flex items-center gap-2">
                      <code className="code block flex-1 px-2 py-1 text-[11.5px]">$ {c.command}</code>
                      <CopyButton text={c.command} />
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[13.5px] text-ink-3">Nothing in the report names code that could be checked.</p>
        )}
      </Section>

      <Section title="Checked against the outside world">
        <div className="space-y-4">
          {(ev.cves || []).map((c) => (
            <div key={c.cve_id} className="flex gap-3">
              <StatusMark status={c.status === "issued" ? "verified" : c.status === "unknown" || c.status === "reserved" ? "unverifiable" : "false"} />
              <div className="min-w-0">
                <p className="text-[14px] font-mono">{c.cve_id}</p>
                <p className="text-[13.5px] text-ink-2"><Rich text={c.detail} /></p>
                <a href={c.source} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[12.5px] text-ink-3 underline underline-offset-2">
                  CVE Program API <ExternalLink size={11} />
                </a>
              </div>
            </div>
          ))}
          {!ev.cves?.length && <p className="text-[13.5px] text-ink-3">The report cites no CVE IDs.</p>}

          {(ev.web || []).map((w, i) => (
            <div key={i} className="rounded border border-rule p-3">
              <p className="text-[13px]">
                <span className="text-ink-3">Tavily search:</span> <span className="font-mono text-[12.5px]">{w.query}</span>
              </p>
              {w.status === "ok" ? (
                w.results.length ? (
                  <ul className="mt-2 space-y-1.5">
                    {w.results.slice(0, 3).map((r) => (
                      <li key={r.url} className="text-[13px]">
                        <a href={r.url} target="_blank" rel="noreferrer" className="underline underline-offset-2">
                          {r.title || r.url}
                        </a>
                        <p className="line-clamp-2 text-[12.5px] text-ink-3">{r.snippet}</p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-1 text-[13px] text-ink-2">No public results.</p>
                )
              ) : (
                <p className="mt-1 text-[13px] text-ink-3">Not run: {w.note}</p>
              )}
            </div>
          ))}

          <div className="flex gap-3">
            <StatusMark status={ev.duplicate ? "moved" : "verified"} />
            <div>
              <p className="text-[14px]">Duplicate check against earlier reports</p>
              {ev.duplicate ? (
                <p className="text-[13.5px] text-ink-2">
                  Same bug as <span className="font-mono">{ev.duplicate.of}</span> “{ev.duplicate.title}”. Overlap score{" "}
                  {ev.duplicate.score.toFixed(2)} ({ev.duplicate.how}).
                </p>
              ) : (
                <p className="text-[13.5px] text-ink-2">No earlier report describes the same bug.</p>
              )}
            </div>
          </div>
        </div>
      </Section>
    </div>
  );
}

function SandboxPanel({ report }: { report: ReportDetail }) {
  const ev = report.evidence || {};
  const r = ev.reproduction;
  if (!r) {
    return (
      <div className="py-5">
        <div className="flex gap-3 rounded-md border border-rule bg-sheet p-4">
          <Box size={18} className="mt-0.5 shrink-0 text-ink-3" />
          <div className="text-[14px]">
            <p className="font-medium">{ev.sandbox_skipped ? "No sandbox was started for this report." : "The sandbox has not run yet."}</p>
            {ev.sandbox_skipped && <p className="mt-1 text-ink-2">{ev.sandbox_skipped}</p>}
            {ev.plan && <p className="mt-1 text-ink-2">Reproduction plan: {ev.plan.reason}</p>}
          </div>
        </div>
      </div>
    );
  }
  if (r.error) return <p className="py-5 text-[14px] text-false">Sandbox unavailable: {r.error}</p>;
  return (
    <div>
      <Section title="Isolation" aside={`${r.backend}, ${r.image}, ${r.duration_s}s`}>
        <div className="flex flex-wrap gap-1.5">
          {r.isolation.map((f) => (
            <Pill key={f} tone="proof">
              <Lock size={11} /> {f}
            </Pill>
          ))}
        </div>
        <p className="mt-3 text-[13px] text-ink-2">
          A fresh container built {r.ref} with AddressSanitizer and UBSan, ran the steps three times, and was destroyed. No API keys or
          tokens are passed in.
        </p>
        <CodeBlock className="mt-2 text-[11.5px]">{r.container_command}</CodeBlock>
      </Section>
      <Section title="What ran" aside={sourceLabel(r.script_source)}>
        <CodeBlock>{r.script}</CodeBlock>
        {r.attachments.length > 0 && <p className="mt-2 text-[13px] text-ink-2">Attached files placed in the working directory: {r.attachments.join(", ")}</p>}
        <p className="mt-2 text-[13px] text-ink-2">Build: {r.build_ok ? "succeeded with sanitizers" : "failed"}</p>
      </Section>
      <Section title="Three attempts" aside={ev.match ? ev.match.detail : undefined}>
        <div className="space-y-4">
          {r.attempts.map((a) => (
            <div key={a.attempt}>
              <div className="flex flex-wrap items-center gap-2 text-[13.5px]">
                <span className="font-medium">Attempt {a.attempt}</span>
                <span className="text-ink-3">exit {a.exit_code}</span>
                {a.sanitizer ? <Pill tone="false">{a.sanitizer.tool}: {a.sanitizer.kind}</Pill> : <Pill>no crash</Pill>}
              </div>
              {a.sanitizer && a.attempt === r.attempts.find((x) => x.sanitizer)?.attempt && (
                <>
                  <ol className="mt-2 space-y-0.5 font-mono text-[12px]">
                    {a.sanitizer.frames.slice(0, 5).map((f, i) => (
                      <li key={i}>
                        <span className="text-ink-3">#{i}</span> {f.function} <span className="text-ink-3">{f.file}:{f.line}</span>
                      </li>
                    ))}
                  </ol>
                  <details className="mt-2">
                    <summary className="cursor-pointer text-[13px] text-ink-2">Full sanitizer output</summary>
                    <CodeBlock className="mt-2" maxH="max-h-80">{a.output}</CodeBlock>
                  </details>
                </>
              )}
              {!a.sanitizer && a.output.trim() && (
                <CodeBlock className="mt-2" maxH="max-h-40">{a.output}</CodeBlock>
              )}
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}

function ReplyPanel({ report }: { report: ReportDetail }) {
  return (
    <Section
      title="Draft reply"
      aside={report.verdict === "reproduced" ? "Fixed template: no details of an unreleased bug go out" : sourceLabel(report.evidence?.explanation_source)}
    >
      <div className="rounded-md border border-rule bg-sheet p-4 text-[14.5px] leading-relaxed whitespace-pre-wrap">{report.reply}</div>
      <div className="mt-2 flex items-center gap-3">
        <CopyButton text={report.reply || ""} label="Copy reply" />
        <span className="text-[12.5px] text-ink-3">Bouncer drafts replies; it never sends them.</span>
      </div>
    </Section>
  );
}

function OriginalPanel({ report }: { report: ReportDetail }) {
  return (
    <Section title="As received" aside="Untrusted input, shown verbatim">
      <CodeBlock className="whitespace-pre-wrap" maxH="max-h-[480px]">{report.body}</CodeBlock>
      {Object.entries(report.attachments || {}).map(([name, content]) => (
        <div key={name} className="mt-3">
          <p className="text-[13px] text-ink-2">Attachment {name}</p>
          <CodeBlock>{content}</CodeBlock>
        </div>
      ))}
    </Section>
  );
}
