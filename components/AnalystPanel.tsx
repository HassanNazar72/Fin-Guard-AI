"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatResponse, Mode, Quota } from "@/lib/types";
import { ExecutionTrace } from "./ExecutionTrace";
import { AlertIcon, BanIcon, InfoIcon, SendIcon, SparkIcon } from "./icons";

export const MAX_PROMPT_CHARS = 250;

export const QUICK_PROMPTS = [
  "Audit my recurring subscriptions",
  "Check for duplicate or anomalous charges",
  "Summarize my cash flow & savings rate",
];

export interface ChatTurn {
  id: number;
  prompt: string;
  response: ChatResponse | null;
  error: string | null;
}

interface Props {
  enabled: boolean;
  turns: ChatTurn[];
  pending: boolean;
  quota: Quota | null;
  onAsk: (prompt: string) => void;
}

const STATUS_STYLE: Record<Mode, string> = {
  live: "bg-good-soft text-good",
  cached: "bg-card-2 text-ink-2",
  fallback: "bg-warn-soft text-warn",
  blocked: "bg-bad-soft text-bad",
};

function StatusBanner({ mode, message }: { mode: Mode; message: string | null }) {
  if (!message) return null;
  const Icon = mode === "blocked" ? BanIcon : mode === "fallback" ? AlertIcon : InfoIcon;
  return (
    <p className={`mb-2 flex items-start gap-1.5 rounded-lg px-2.5 py-1.5 text-xs ${STATUS_STYLE[mode]}`}>
      <Icon width={14} height={14} className="mt-px shrink-0" />
      <span>{message}</span>
    </p>
  );
}

function Answer({ turn }: { turn: ChatTurn }) {
  if (turn.error) {
    return (
      <p className="flex items-start gap-1.5 rounded-xl bg-bad-soft px-3 py-2 text-sm text-bad">
        <AlertIcon className="mt-0.5 shrink-0" />
        {turn.error}
      </p>
    );
  }
  if (!turn.response) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-line px-3 py-3 text-sm text-muted">
        <span className="h-2 w-2 animate-pulse rounded-full bg-muted" aria-hidden="true" />
        Agent is selecting tools and analysing…
      </div>
    );
  }
  const { report, trace, status } = turn.response;
  return (
    <div className="rounded-xl border border-line bg-card p-3">
      <StatusBanner mode={status.mode} message={status.message} />
      <p className="whitespace-pre-line text-sm leading-relaxed text-ink">{report.answer}</p>
      {report.flagged_risks.length > 0 && (
        <ul className="mt-3 space-y-1" aria-label="Flagged risks">
          {report.flagged_risks.map((risk) => (
            <li key={risk} className="flex items-start gap-1.5 text-xs text-ink-2">
              <AlertIcon width={13} height={13} className="mt-px shrink-0 text-bad" />
              <span>
                <span className="font-semibold text-bad">Risk: </span>
                {risk}
              </span>
            </li>
          ))}
        </ul>
      )}
      {report.requires_human_review && (
        <p className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-warn-soft px-2.5 py-1 text-[11px] font-semibold text-warn">
          <AlertIcon width={12} height={12} />
          Human review recommended
        </p>
      )}
      <ExecutionTrace trace={trace} />
    </div>
  );
}

export function AnalystPanel({ enabled, turns, pending, quota, onAsk }: Props) {
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const tooLong = draft.length > MAX_PROMPT_CHARS;
  const canSend = enabled && !pending && draft.trim().length > 0 && !tooLong;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [turns]);

  function submit(prompt: string) {
    if (!enabled || pending || !prompt.trim() || prompt.length > MAX_PROMPT_CHARS) return;
    onAsk(prompt.trim());
    setDraft("");
  }

  return (
    <section
      aria-label="AI Financial and Security Analyst"
      className="flex min-h-[32rem] flex-col rounded-2xl border border-line bg-card p-4"
    >
      <header className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-1.5 text-sm font-semibold text-ink">
            <SparkIcon className="text-[var(--series-1)]" />
            AI Financial &amp; Security Analyst
          </h2>
          <p className="text-xs text-muted">
            Gemini picks the tools, Python does the maths, every answer is schema-validated.
          </p>
        </div>
        {quota && (
          <span className="shrink-0 rounded-full bg-card-2 px-2.5 py-1 text-[11px] font-medium text-ink-2">
            {quota.remaining}/{quota.limit} live AI queries left today
          </span>
        )}
      </header>

      <div className="mb-3 flex flex-wrap gap-2">
        {QUICK_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => submit(prompt)}
            disabled={!enabled || pending}
            className="rounded-full border border-line bg-card-2 px-3 py-1.5 text-xs font-medium text-ink transition hover:border-ink-2 disabled:opacity-50"
          >
            {prompt}
          </button>
        ))}
      </div>

      <div className="max-h-[40rem] flex-1 space-y-4 overflow-y-auto pr-1" aria-live="polite">
        {turns.length === 0 && (
          <p className="rounded-xl border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
            {enabled
              ? "Pick a starter prompt or ask your own question about this statement."
              : "Load the sample statement or upload a CSV to start the analyst."}
          </p>
        )}
        {turns.map((turn) => (
          <article key={turn.id} className="space-y-2">
            <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-accent px-3 py-2 text-sm text-accent-ink">
              {turn.prompt}
            </p>
            <Answer turn={turn} />
          </article>
        ))}
        <div ref={endRef} />
      </div>

      <form
        className="mt-3"
        onSubmit={(e) => {
          e.preventDefault();
          submit(draft);
        }}
      >
        <div
          className={`flex items-end gap-2 rounded-2xl border bg-card-2 p-2 ${
            tooLong ? "border-bad" : "border-line focus-within:border-ink-2"
          }`}
        >
          <label htmlFor="analyst-input" className="sr-only">
            Ask about your statement
          </label>
          <textarea
            id="analyst-input"
            rows={2}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit(draft);
              }
            }}
            disabled={!enabled}
            placeholder={enabled ? "e.g. How much did I spend on eating out?" : "Load a statement first"}
            className="max-h-32 min-h-10 flex-1 resize-none bg-transparent px-1 text-sm text-ink placeholder:text-muted focus:outline-none focus-visible:outline-none disabled:opacity-60"
            aria-describedby="analyst-counter"
          />
          <button
            type="submit"
            disabled={!canSend}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-accent-ink transition hover:opacity-90 disabled:opacity-40"
            aria-label="Send question"
          >
            <SendIcon />
          </button>
        </div>
        <div id="analyst-counter" className="mt-1.5 flex justify-between text-[11px] text-muted">
          <span>Statement data is PII-scrubbed and injection-filtered before the AI sees it.</span>
          <span className={`tabular-nums ${tooLong ? "font-semibold text-bad" : ""}`}>
            {draft.length}/{MAX_PROMPT_CHARS}
          </span>
        </div>
      </form>
    </section>
  );
}
