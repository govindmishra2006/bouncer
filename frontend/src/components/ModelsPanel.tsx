"use client";

import type { Health, ReportDetail } from "@/lib/api";
import { tierLabel } from "@/lib/verdicts";
import { Section } from "./ui";

const STAGE_NAMES: Record<string, string> = {
  extract_claims: "Extract claims",
  duplicate_check: "Compare with earlier report",
  write_repro_script: "Write reproduction script",
  explain_verdict: "Explain verdict, draft reply",
  root_cause: "Root-cause analysis",
  write_patch: "Write patch + regression test",
  summarize_failure: "Summarise failed attempt",
};

const ROUTING = [
  { tier: "nano", job: "Claim extraction, duplicate comparison, failure summaries, clear-cut explanations", why: "Runs on every report; fast and cheap" },
  { tier: "super", job: "Reproduction scripts, patches and regression tests", why: "Everyday coding work, retried in a loop" },
  { tier: "ultra", job: "Root cause from crash + code; explanations for judgement calls", why: "Serious reasoning across code and logs" },
];

export function ModelsPanel({ report, health }: { report: ReportDetail; health: Health | null }) {
  const calls = report.model_calls;
  const live = calls.filter((c) => c.provider === "nebius-token-factory");
  const tokens = live.reduce((s, c) => s + c.tokens_in + c.tokens_out, 0);
  const cost = live.reduce((s, c) => s + c.cost_usd, 0);
  return (
    <div>
      {!health?.models.live && (
        <div className="mt-3 rounded-md border border-warn/40 bg-warn-bg p-3.5 text-[13.5px]">
          <p className="font-semibold text-warn">No Nemotron calls in this run</p>
          <p className="mt-0.5 text-ink-2">
            NEBIUS_API_KEY is not set, so each model step below ran a deterministic fallback (regex extraction, templates, pre-written
            patch candidates). Verdicts are unchanged: they are computed by rules from git, CVE and sandbox evidence either way.
          </p>
        </div>
      )}
      <Section title="Who did what for this report" aside={live.length ? `${live.length} Token Factory calls, ${tokens.toLocaleString()} tokens, $${cost.toFixed(4)}` : undefined}>
        {calls.length === 0 ? (
          <p className="text-[13.5px] text-ink-3">No model steps yet.</p>
        ) : (
          <div className="overflow-x-auto scroll-thin">
            <table className="w-full min-w-[620px] text-left text-[13px]">
              <thead className="text-ink-3">
                <tr className="border-b border-rule">
                  <th className="py-1.5 pr-3 font-medium">Step</th>
                  <th className="py-1.5 pr-3 font-medium">Model</th>
                  <th className="py-1.5 pr-3 text-right font-medium">Tokens in / out</th>
                  <th className="py-1.5 pr-3 text-right font-medium">Latency</th>
                  <th className="py-1.5 text-right font-medium">Cost</th>
                </tr>
              </thead>
              <tbody>
                {calls.map((c) => (
                  <tr key={c.id} className="border-b border-rule/70 align-top">
                    <td className="py-1.5 pr-3">{STAGE_NAMES[c.stage] || c.stage}</td>
                    <td className="py-1.5 pr-3">
                      <span className={c.provider === "offline-rules" ? "text-ink-3" : "font-medium"}>{tierLabel(c.tier, c.provider)}</span>
                      <span className="block font-mono text-[11px] text-ink-3">
                        {c.provider === "offline-rules" ? `in place of ${tierLabel(c.tier, "")}: ${c.error ?? ""}` : c.model}
                      </span>
                      {c.provider !== "offline-rules" && !c.ok && <span className="block text-[12px] text-false">{c.error}</span>}
                    </td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{c.provider === "offline-rules" ? "–" : `${c.tokens_in} / ${c.tokens_out}`}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{c.provider === "offline-rules" ? "–" : `${c.latency_ms} ms`}</td>
                    <td className="py-1.5 text-right tabular-nums">{c.provider === "offline-rules" ? "–" : `$${c.cost_usd.toFixed(5)}`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
      <Section title="Model routing" aside="All calls go to Nebius Token Factory">
        <ul className="space-y-2 text-[13.5px]">
          {ROUTING.map((r) => (
            <li key={r.tier} className="grid gap-x-4 sm:grid-cols-[150px_1fr]">
              <span className="font-medium">{tierLabel(r.tier, "")}</span>
              <span>
                {r.job}. <span className="text-ink-3">{r.why}.</span>
                <span className="block font-mono text-[11px] text-ink-3">{health?.models.tiers[r.tier]}</span>
              </span>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}
