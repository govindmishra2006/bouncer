"use client";

import { Box, Cpu, Globe, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { CaseFile } from "@/components/CaseFile";
import { LimitationsDialog, SubmitDialog } from "@/components/Dialogs";
import { Intro } from "@/components/Intro";
import { Queue } from "@/components/Queue";
import { API_URL, api, type Card, type Health, type ReportDetail, type Stats } from "@/lib/api";

export default function Console() {
  const [cards, setCards] = useState<Card[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<ReportDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [submitOpen, setSubmitOpen] = useState(false);
  const [limitsOpen, setLimitsOpen] = useState(false);
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  const selectedRef = useRef<string | null>(null);

  const refreshList = useCallback(
    () =>
      api
        .reports()
        .then((data) => {
          setCards(data.reports);
          setStats(data.stats);
          setError(null);
        })
        .catch((e: Error) => setError(e.message))
        .finally(() => setLoaded(true)),
    [],
  );

  const refreshDetail = useCallback((id: string | null) => {
    if (!id) return;
    api
      .report(id)
      .then((d) => {
        if (selectedRef.current === id) setDetail(d);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    refreshList();
    api.health().then(setHealth).catch(() => {});
  }, [refreshList]);

  useEffect(() => {
    selectedRef.current = selected;
    refreshDetail(selected);
  }, [selected, refreshDetail]);

  // Live updates: every pipeline event triggers a (debounced) refresh.
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    let lastId = 0;
    let es: EventSource | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    const connect = () => {
      es = new EventSource(`${API_URL}/api/events?after=${lastId || 1e12}`);
      // After a reconnect (e.g. API restart) events may have been missed: resync once.
      es.onopen = () => refreshList();
      es.onmessage = (msg) => {
        const ev = JSON.parse(msg.data);
        lastId = Math.max(lastId, ev.id);
        if (ev.type === "verdict") {
          setFresh((s) => new Set(s).add(ev.report_id));
        }
        if (ev.type === "demo_loaded" || ev.type === "reset") setFresh(new Set());
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => {
          refreshList();
          if (!ev.report_id || ev.report_id === selectedRef.current) refreshDetail(selectedRef.current);
        }, 120);
      };
      es.onerror = () => {
        es?.close();
        retry = setTimeout(connect, 3000);
      };
    };
    connect();
    return () => {
      es?.close();
      if (timer) clearTimeout(timer);
      if (retry) clearTimeout(retry);
    };
  }, [refreshList, refreshDetail]);

  const loadDemo = async () => {
    setBusy(true);
    try {
      const { ids } = await api.loadDemo();
      setSelected(null);
      setDetail(null);
      await refreshList();
      api.health().then(setHealth).catch(() => {});
      return ids;
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const reset = async () => {
    await api.reset();
    setSelected(null);
    setDetail(null);
    refreshList();
  };

  const showCase = selected && detail && detail.id === selected;

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-rule bg-sheet px-4 py-2.5 sm:px-5">
        <div className="flex items-baseline gap-3">
          <h1 className="cut-wide text-[21px] leading-none font-extrabold tracking-tight">Bouncer</h1>
          <span className="hidden text-[13px] text-ink-3 2xl:inline">Report queue for tinyparse (fictional demo project)</span>
        </div>
        <Status health={health} />
        <div className="ml-auto flex items-center gap-2">
          <button onClick={() => setLimitsOpen(true)} className="hidden rounded px-2.5 py-1.5 text-[13.5px] text-ink-2 hover:bg-sheet-2 sm:block">
            Limitations
          </button>
          {cards.length > 0 && (
            <button onClick={reset} className="rounded px-2.5 py-1.5 text-[13.5px] text-ink-2 hover:bg-sheet-2" title="Clear the queue">
              <RotateCcw size={14} className="inline" /> <span className="hidden sm:inline">Clear</span>
            </button>
          )}
          <button
            onClick={() => setSubmitOpen(true)}
            className="rounded border border-rule-strong px-3 py-1.5 text-[13.5px] font-medium whitespace-nowrap hover:bg-sheet-2"
          >
            Paste<span className="hidden sm:inline"> a report</span>
          </button>
          <button
            onClick={loadDemo}
            disabled={busy}
            className="rounded bg-ink px-3 py-1.5 text-[13.5px] font-semibold whitespace-nowrap text-paper hover:opacity-90 disabled:opacity-50"
          >
            {cards.length ? "Rerun" : "Run"} test reports
          </button>
        </div>
      </header>

      {error && (
        <div role="alert" className="border-b border-false/30 bg-false-bg px-5 py-2 text-[13.5px] text-false">
          {error}
        </div>
      )}

      {cards.length > 0 && stats && <Tally stats={stats} />}

      <div className="flex min-h-0 flex-1">
        {cards.length > 0 && (
          <aside
            className={`${showCase ? "hidden lg:block" : "block"} w-full shrink-0 overflow-y-auto border-r border-rule scroll-thin lg:w-[400px]`}
          >
            <p className="sr-only" aria-live="polite">
              {stats ? `${stats.decided} of ${stats.total} reports decided` : ""}
            </p>
            <Queue cards={cards} selected={selected} onSelect={setSelected} freshVerdicts={fresh} />
            <p className="px-4 py-3 text-[12px] leading-relaxed text-ink-3">
              Sorted so proven bugs come first. The five bars are the pipeline stages; a hatched fourth bar means the report was
              settled by cheap checks and no sandbox was started.
            </p>
          </aside>
        )}
        <main className={`${cards.length > 0 && !showCase ? "hidden lg:block" : "block"} min-w-0 flex-1 overflow-y-auto scroll-thin`}>
          {showCase ? (
            <CaseFile
              key={detail.id}
              report={detail}
              health={health}
              onBack={() => setSelected(null)}
              onChanged={() => {
                refreshDetail(selected);
                refreshList();
              }}
            />
          ) : cards.length === 0 ? (
            loaded && <Intro onLoad={loadDemo} onPaste={() => setSubmitOpen(true)} busy={busy} />
          ) : (
            <Pick stats={stats} />
          )}
        </main>
      </div>

      <SubmitDialog open={submitOpen} onClose={() => setSubmitOpen(false)} onSubmitted={(id) => setSelected(id)} />
      <LimitationsDialog open={limitsOpen} onClose={() => setLimitsOpen(false)} />
    </div>
  );
}

function Status({ health }: { health: Health | null }) {
  if (!health) return null;
  const items = [
    {
      icon: <Cpu size={13} />,
      ok: health.models.live,
      text: health.models.live ? "Nemotron via Nebius Token Factory" : "Nemotron offline: rule-based fallbacks",
      title: health.models.live ? health.models.base_url : "Set NEBIUS_API_KEY to route model steps to Nemotron on Token Factory",
    },
    {
      icon: <Box size={13} />,
      ok: health.sandbox.ok,
      text: health.sandbox.ok ? "Sandbox ready, network off" : "Sandbox unavailable",
      title: health.sandbox.detail,
    },
    {
      icon: <Globe size={13} />,
      ok: health.tavily,
      text: health.tavily ? "Tavily search on" : "Tavily off, CVE Program API on",
      title: health.tavily ? "Web search for CVEs and advisories" : "Set TAVILY_API_KEY for web search; CVE IDs are still checked against the CVE Program",
    },
  ];
  return (
    <ul className="hidden items-center gap-4 text-[12.5px] md:flex">
      {items.map((i) => (
        <li key={i.text} title={i.title} className={`inline-flex items-center gap-1.5 ${i.ok ? "text-ink-2" : "text-warn"}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${i.ok ? "bg-proof" : "bg-warn"}`} />
          {i.icon}
          {i.text}
        </li>
      ))}
    </ul>
  );
}

function Tally({ stats }: { stats: Stats }) {
  const figs: [string, string, string?][] = [
    [`${stats.decided}/${stats.total}`, "reports decided"],
    [`${stats.by_verdict.reproduced}`, "proven real"],
    [`${stats.by_verdict.fabricated}`, "fabricated"],
    [`${stats.patches_ready}`, "fixes verified"],
    [`${stats.sandboxes_started}`, `sandboxes for ${stats.total} reports`],
    [`${stats.hours_saved.toFixed(0)} h`, "maintainer time saved", stats.hours_assumption],
  ];
  return (
    <div className="grid grid-cols-3 items-end gap-x-4 gap-y-2 border-b border-rule px-4 py-2.5 sm:flex sm:flex-wrap sm:gap-x-8 sm:px-5 sm:py-3">
      {figs.map(([n, label, title]) => (
        <div key={label} title={title} className="min-w-0">
          <p className="cut-narrow text-[20px] leading-none font-extrabold tabular-nums sm:text-[26px]">{n}</p>
          <p className="mt-1 truncate text-[11.5px] text-ink-3 sm:text-[12px]">{label}</p>
        </div>
      ))}
      <p className="ml-auto hidden max-w-[36ch] text-right sm:block text-[11.5px] leading-snug text-ink-3">
        Time saved assumes {stats.hours_assumption.replace(";", ", and")}
        {stats.in_progress > 0 && <span className="block text-ink-2">{stats.in_progress} still in progress</span>}
      </p>
    </div>
  );
}

function Pick({ stats }: { stats: Stats | null }) {
  return (
    <div className="mx-auto max-w-[560px] px-8 pt-20">
      <p className="cut-narrow text-[32px] leading-tight font-extrabold">Open a report to see its evidence.</p>
      <p className="mt-3 text-[15px] text-ink-2">
        Each card shows what the report claims, every check Bouncer ran with the command to re-run it, the sandbox output, which model
        did which step, and for real bugs, the verified fix.
      </p>
      {stats && stats.in_progress > 0 && <p className="mt-4 text-[14px] text-ink-3">{stats.in_progress} reports are still moving through the pipeline.</p>}
    </div>
  );
}
