"use client";

import { X } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "@/lib/api";

function Dialog({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      className="m-auto w-[min(720px,calc(100vw-24px))] rounded-md border border-rule bg-sheet p-0 text-ink backdrop:bg-black/40"
    >
      <div className="flex items-center justify-between border-b border-rule px-5 py-3">
        <h2 className="text-[17px] font-semibold">{title}</h2>
        <button onClick={onClose} aria-label="Close" className="rounded p-1 text-ink-2 hover:bg-sheet-2">
          <X size={18} />
        </button>
      </div>
      <div className="max-h-[78vh] overflow-y-auto px-5 py-4 scroll-thin">{children}</div>
    </dialog>
  );
}

const EXAMPLES = [
  {
    name: "A fake: function that never existed",
    title: "Buffer overflow in tp_parse_header() allows RCE",
    body: "tinyparse v1.2 has a critical overflow in tp_parse_header() in src/header.c line 88. Attackers can send a long header to execute code. CVSS 9.1.",
    attachments: {},
  },
  {
    name: "Real: the trailing-% over-read",
    title: "tp_url_decode over-reads when input ends in a truncated escape",
    body: "In tinyparse v1.2, tp_url_decode() in src/url.c reads past the end of its input when the input ends with '%4'.\n\nSteps:\n```sh\nmake SAN=1\nprintf 'id=%%4' | ./build/tp decode\n```",
    attachments: {},
  },
];

export function SubmitDialog({ open, onClose, onSubmitted }: { open: boolean; onClose: () => void; onSubmitted: (id: string) => void }) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [reporter, setReporter] = useState("");
  const [fileName, setFileName] = useState("");
  const [fileContent, setFileContent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const attachments: Record<string, string> = fileName.trim() ? { [fileName.trim()]: fileContent } : {};
      const { id } = await api.submit({ title, body, reporter: reporter || "anonymous", attachments });
      onSubmitted(id);
      setTitle("");
      setBody("");
      setFileName("");
      setFileContent("");
      onClose();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const field = "mt-1 w-full rounded border border-rule-strong bg-sheet px-3 py-2 text-[14px] text-ink placeholder:text-ink-3";
  return (
    <Dialog open={open} onClose={onClose} title="Paste a report">
      <p className="text-[14px] text-ink-2">
        It will be checked against tinyparse, the fictional demo project. Reproduction commands run in a sandbox with no network, after{" "}
        <code className="font-mono text-[12.5px]">make SAN=1</code>; the CLI is <code className="font-mono text-[12.5px]">./build/tp</code>{" "}
        (decode, encode, ini, get, trim, split).
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {EXAMPLES.map((ex) => (
          <button
            key={ex.name}
            type="button"
            onClick={() => {
              setTitle(ex.title);
              setBody(ex.body);
            }}
            className="rounded border border-rule px-2.5 py-1 text-[13px] text-ink-2 hover:bg-sheet-2"
          >
            Use example: {ex.name}
          </button>
        ))}
      </div>
      <form onSubmit={submit} className="mt-4 space-y-3">
        <label className="block text-[13.5px] font-medium">
          Title
          <input required minLength={3} maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} className={field} />
        </label>
        <label className="block text-[13.5px] font-medium">
          Report
          <textarea
            required
            minLength={10}
            maxLength={20000}
            rows={10}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            className={`${field} font-mono text-[12.5px]`}
            placeholder={"Version, file, function, and steps. Put commands in a ```sh block."}
          />
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-[13.5px] font-medium">
            Reporter <span className="font-normal text-ink-3">(optional)</span>
            <input maxLength={80} value={reporter} onChange={(e) => setReporter(e.target.value)} className={field} />
          </label>
          <label className="block text-[13.5px] font-medium">
            Attachment name <span className="font-normal text-ink-3">(optional)</span>
            <input value={fileName} onChange={(e) => setFileName(e.target.value)} placeholder="poc.txt" pattern="[\w.\-]{1,64}" className={field} />
          </label>
        </div>
        {fileName && (
          <label className="block text-[13.5px] font-medium">
            Attachment contents
            <textarea rows={3} value={fileContent} onChange={(e) => setFileContent(e.target.value)} className={`${field} font-mono text-[12.5px]`} />
          </label>
        )}
        {error && <p className="text-[13.5px] text-false">{error}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose} className="rounded border border-rule-strong px-3 py-2 text-[14px]">
            Cancel
          </button>
          <button type="submit" disabled={busy} className="rounded bg-ink px-4 py-2 text-[14px] font-semibold text-paper disabled:opacity-50">
            {busy ? "Submitting…" : "Check this report"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

export function LimitationsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const items: [string, string][] = [
    ["Languages", "the first version supports C (built with sanitizers) and pure Python projects. Other languages fall back to claim checking only, with no reproduction."],
    ["Complex setups", "bugs that need a live server, special hardware, a particular OS or a large dataset cannot be reproduced in the sandbox. They get Needs human, never Fabricated."],
    ["Not reproduced is not “false”", "some real bugs only trigger rarely or under timing conditions. Bouncer says what it tried, and does not call the report fake."],
    ["Fix quality", "a patch that passes all three checks can still be wrong in ways the tests do not cover. It is a draft for review, never a merge."],
    ["Logic and design flaws", "vulnerabilities with no crash (for example, an authorization mistake) are hard to verify automatically. Bouncer can ground the claims, but not prove them."],
    ["Duplicate detection", "relies on search and the model's comparison, and can miss rewritten duplicates."],
    ["Cost", "every reproduction uses paid CPU compute. The hosted demo has a daily cap."],
    ["Evaluation size", "results in the demo come from 10 designed reports and a small set of public examples, not a large benchmark."],
  ];
  return (
    <Dialog open={open} onClose={onClose} title="Limitations">
      <ul className="space-y-3 text-[14.5px] leading-relaxed">
        {items.map(([k, v]) => (
          <li key={k}>
            <span className="font-semibold">{k}:</span> <span className="text-ink-2">{v}</span>
          </li>
        ))}
      </ul>
      <p className="mt-5 border-t border-rule pt-3 text-[13px] text-ink-3">
        This build: the Python path is claim checking only, and the sandbox runs on local Docker, not Nebius Serverless Jobs. Without a
        Token Factory key, model steps run labelled rule-based fallbacks.
      </p>
    </Dialog>
  );
}
