"use client";

import { ShieldAlert, Wrench } from "lucide-react";
import { useLayoutEffect, useRef } from "react";
import type { Card } from "@/lib/api";
import { STAGES, VERDICTS } from "@/lib/verdicts";
import { PipelineTrack, Stamp } from "./ui";

/** The triage queue. Rows re-sort by verdict as evidence arrives; positions animate (FLIP). */
export function Queue({
  cards,
  selected,
  onSelect,
  freshVerdicts,
}: {
  cards: Card[];
  selected: string | null;
  onSelect: (id: string) => void;
  freshVerdicts: Set<string>;
}) {
  const rows = useRef(new Map<string, HTMLElement>());
  const last = useRef(new Map<string, number>());

  useLayoutEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const next = new Map<string, number>();
    rows.current.forEach((el, id) => {
      const top = el.offsetTop;
      next.set(id, top);
      const prev = last.current.get(id);
      if (!reduce && prev !== undefined && prev !== top) {
        el.animate([{ transform: `translateY(${prev - top}px)` }, { transform: "translateY(0)" }], {
          duration: 420,
          easing: "cubic-bezier(0.2, 0.8, 0.2, 1)",
        });
      }
    });
    last.current = next;
  }, [cards]);

  return (
    <ol className="relative" aria-label="Report queue, sorted with proven bugs first">
      {cards.map((c) => {
        const color = c.verdict ? VERDICTS[c.verdict].color : "var(--ink-2)";
        const active = selected === c.id;
        const stageLabel =
          c.status === "queued"
            ? "Waiting in line"
            : c.status === "processing"
              ? (STAGES.find((s) => s.key === c.stage)?.label ?? "Working") + "…"
              : c.status === "error"
                ? "Pipeline error"
                : null;
        return (
          <li
            key={c.id}
            ref={(el) => {
              if (el) rows.current.set(c.id, el);
              else rows.current.delete(c.id);
            }}
          >
            <button
              type="button"
              onClick={() => onSelect(c.id)}
              aria-current={active ? "true" : undefined}
              className={`group relative block w-full border-b border-rule px-4 py-3 text-left transition-colors ${
                active ? "bg-sheet" : "hover:bg-sheet/60"
              }`}
            >
              {active && <span className="absolute inset-y-0 left-0 w-[3px]" style={{ background: color }} />}
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-[12px] text-ink-3">
                    <span className="font-mono">{c.id}</span>
                    {c.version && <span>{c.version}</span>}
                    {c.is_test_data && <span>test data</span>}
                  </div>
                  <p className="mt-0.5 line-clamp-2 text-[14px] leading-snug font-medium text-ink">{c.title}</p>
                </div>
                <div className="shrink-0 pt-0.5">
                  {c.verdict ? (
                    <Stamp verdict={c.verdict} land={freshVerdicts.has(c.id)} />
                  ) : (
                    <span className="text-[12px] text-ink-3">{c.status === "error" ? "Error" : "…"}</span>
                  )}
                </div>
              </div>
              <div className="mt-2 flex items-center justify-between gap-2">
                <PipelineTrack card={c} color={color} />
                <div className="flex items-center gap-2 text-[12px] text-ink-3">
                  {stageLabel && <span>{stageLabel}</span>}
                  {c.injection && (
                    <span className="inline-flex items-center gap-1 text-warn" title="Hidden instructions found in the report">
                      <ShieldAlert size={13} /> injection
                    </span>
                  )}
                  {c.false_claims > 0 && c.verdict && (
                    <span className="text-false">
                      {c.false_claims} false claim{c.false_claims > 1 ? "s" : ""}
                    </span>
                  )}
                  {c.patch_status === "fixed" && (
                    <span className="inline-flex items-center gap-1 text-proof">
                      <Wrench size={12} /> fix ready
                    </span>
                  )}
                  {(c.patch_status === "running" || c.patch_status === "queued") && <span>drafting fix…</span>}
                  {c.patch_status === "could_not_fix" && <span className="text-warn">no safe fix</span>}
                </div>
              </div>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
