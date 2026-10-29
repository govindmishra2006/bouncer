"use client";

import { Check, Copy, Minus, X, CircleHelp, CornerDownRight } from "lucide-react";
import { useState, type ReactNode } from "react";
import type { Card, VerdictKey } from "@/lib/api";
import { STAGES, VERDICTS } from "@/lib/verdicts";

export function Stamp({
  verdict,
  size = "sm",
  land = false,
}: {
  verdict: VerdictKey;
  size?: "sm" | "lg";
  land?: boolean;
}) {
  const v = VERDICTS[verdict];
  return (
    <span
      data-verdict={verdict}
      className={`stamp ${land ? "stamp-land" : ""} ${size === "lg" ? "text-[22px]" : "text-[13px]"}`}
      style={{ color: v.color }}
    >
      {v.label}
    </span>
  );
}

type SegState = "done" | "active" | "skipped" | "pending" | "error";

export function stageStates(card: Pick<Card, "status" | "stage" | "verdict" | "sandbox_used">): SegState[] {
  const order = STAGES.map((s) => s.key as string);
  if (card.verdict) {
    return order.map((k) => (k === "sandbox" && !card.sandbox_used ? "skipped" : "done"));
  }
  if (card.status === "error") return order.map(() => "error");
  if (card.status === "queued" || !card.stage) return order.map(() => "pending");
  const idx = order.indexOf(card.stage);
  return order.map((_, i) => (i < idx ? "done" : i === idx ? "active" : "pending"));
}

/** Five segments, one per pipeline stage. Hatched sandbox = stopped early by cheap checks. */
export function PipelineTrack({ card, color }: { card: Card; color: string }) {
  const states = stageStates(card);
  return (
    <div className="flex items-center gap-[3px]" aria-hidden>
      {states.map((s, i) => (
        <span
          key={i}
          className={`h-[5px] w-[18px] rounded-[1px] ${s === "active" ? "seg-active" : ""} ${s === "skipped" ? "seg-skipped" : ""}`}
          style={{
            background:
              s === "done" ? color : s === "active" ? "var(--ink-2)" : s === "error" ? "var(--false)" : s === "skipped" ? undefined : "var(--rule)",
          }}
        />
      ))}
      {card.patch_status && (
        <span
          className={`ml-1 h-[7px] w-[7px] rounded-full ${card.patch_status === "running" || card.patch_status === "queued" ? "seg-active" : ""}`}
          style={{
            background:
              card.patch_status === "fixed" ? "var(--proof)" : card.patch_status === "could_not_fix" ? "var(--warn)" : "var(--ink-2)",
          }}
        />
      )}
    </div>
  );
}

export function StatusMark({ status }: { status: string }) {
  if (status === "verified" || status === "pass")
    return (
      <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-proof-bg text-proof" title="Checked: true">
        <Check size={13} strokeWidth={3} />
      </span>
    );
  if (status === "false" || status === "fail")
    return (
      <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-false-bg text-false" title="Checked: false">
        <X size={13} strokeWidth={3} />
      </span>
    );
  if (status === "moved")
    return (
      <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-warn-bg text-warn" title="Changed in another version">
        <CornerDownRight size={13} strokeWidth={3} />
      </span>
    );
  if (status === "unverifiable")
    return (
      <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-sheet-2 text-ink-3" title="Could not be checked">
        <CircleHelp size={13} strokeWidth={2.5} />
      </span>
    );
  return (
    <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-sheet-2 text-ink-3">
      <Minus size={13} />
    </span>
  );
}

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1400);
        } catch {}
      }}
      className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[12px] text-ink-3 hover:bg-sheet-2 hover:text-ink"
      aria-label={`${label} to clipboard`}
    >
      {copied ? <Check size={12} /> : <Copy size={12} />}
      {copied ? "Copied" : label}
    </button>
  );
}

export function CodeBlock({ children, className = "", maxH = "" }: { children: string; className?: string; maxH?: string }) {
  return <pre className={`code scroll-thin p-3 ${maxH} ${className}`}>{children}</pre>;
}

export function DiffView({ diff }: { diff: string }) {
  if (!diff) return <p className="text-[13px] text-ink-3">No diff.</p>;
  return (
    <pre className="code scroll-thin py-2">
      {diff.split("\n").map((line, i) => {
        const bg =
          line.startsWith("+") && !line.startsWith("+++")
            ? "var(--diff-add)"
            : line.startsWith("-") && !line.startsWith("---")
              ? "var(--diff-del)"
              : undefined;
        const color = line.startsWith("@@") ? "var(--ink-3)" : undefined;
        return (
          <div key={i} className="px-3" style={{ background: bg, color }}>
            {line || " "}
          </div>
        );
      })}
    </pre>
  );
}

export function Section({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="border-t border-rule pt-4 pb-5">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h3 className="text-[15px] font-semibold">{title}</h3>
        {aside && <div className="text-[12.5px] text-ink-3">{aside}</div>}
      </div>
      {children}
    </section>
  );
}

export function Pill({ tone = "neutral", children, title }: { tone?: "neutral" | "proof" | "false" | "warn"; children: ReactNode; title?: string }) {
  const tones = {
    neutral: "bg-sheet-2 text-ink-2 border-rule",
    proof: "bg-proof-bg text-proof border-transparent",
    false: "bg-false-bg text-false border-transparent",
    warn: "bg-warn-bg text-warn border-transparent",
  };
  return (
    <span title={title} className={`inline-flex items-center gap-1 rounded border px-1.5 py-[1px] text-[12px] ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function timeAgo(ts: number): string {
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(ts * 1000).toLocaleDateString();
}

/** Renders `backticked` spans in plain text as inline code. */
export function Rich({ text }: { text: string | null | undefined }) {
  if (!text) return null;
  return (
    <>
      {text.split(/(`[^`]+`)/g).map((part, i) =>
        part.startsWith("`") && part.endsWith("`") && part.length > 2 ? (
          <code key={i} className="rounded bg-code px-1 py-px font-mono text-[0.86em]">
            {part.slice(1, -1)}
          </code>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}
