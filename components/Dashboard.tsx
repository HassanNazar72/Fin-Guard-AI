"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { analyzeStatement, askAnalyst, fetchHealth, fetchQuota, type StatementInput } from "@/lib/api";
import { longDate } from "@/lib/format";
import type { AnalyzeResponse, Quota, SecurityEvent } from "@/lib/types";
import { AnalystPanel, type ChatTurn } from "./AnalystPanel";
import { CategoryBarChart, CumulativeSpendChart } from "./Charts";
import { ControlBar } from "./ControlBar";
import { FindingsPanel } from "./FindingsPanel";
import { AlertIcon, BanIcon, FileIcon, InfoIcon, LockIcon, ShieldIcon, SparkIcon } from "./icons";
import { KpiCards } from "./KpiCards";
import { TransactionsTable } from "./TransactionsTable";

interface LoadedStatement extends StatementInput {
  fileName: string | null;
}

function EmptyState({ onLoadSample, loading }: { onLoadSample: () => void; loading: boolean }) {
  const features = [
    {
      Icon: LockIcon,
      title: "PII firewall",
      body: "Sort codes, account numbers, IBANs and card digits are hashed before any AI call.",
    },
    {
      Icon: BanIcon,
      title: "Injection defence",
      body: "Malicious merchant text is detected and cut out - try the sample's hidden attack.",
    },
    {
      Icon: SparkIcon,
      title: "Grounded agent",
      body: "Gemini chooses deterministic Python tools; it never does the arithmetic itself.",
    },
  ];
  return (
    <section className="rounded-3xl border border-line bg-card px-6 py-12 text-center sm:px-12">
      <p className="mx-auto mb-3 inline-flex items-center gap-1.5 rounded-full bg-card-2 px-3 py-1 text-xs font-medium text-ink-2">
        <ShieldIcon className="text-good" /> Security-hardened AI statement analyst
      </p>
      <h2 className="mx-auto max-w-2xl text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
        Find subscription creep, duplicate charges and hidden attacks in a bank statement - in seconds.
      </h2>
      <p className="mx-auto mt-3 max-w-xl text-sm text-ink-2">
        Load 60 realistic UK transactions with three planted anomalies, or upload your own CSV (up to 200 rows).
        Nothing is stored.
      </p>
      <button
        type="button"
        onClick={onLoadSample}
        disabled={loading}
        className="mt-6 inline-flex h-11 items-center gap-2 rounded-full bg-accent px-6 text-sm font-semibold text-accent-ink transition hover:opacity-90 disabled:opacity-50"
      >
        <FileIcon />
        {loading ? "Analysing…" : "Load Sample UK Statement"}
      </button>
      <div className="mx-auto mt-10 grid max-w-3xl gap-3 text-left sm:grid-cols-3">
        {features.map(({ Icon, title, body }) => (
          <div key={title} className="rounded-2xl border border-line bg-card-2 p-4">
            <Icon className="mb-2 text-ink" />
            <p className="text-sm font-semibold text-ink">{title}</p>
            <p className="mt-1 text-xs text-ink-2">{body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export function Dashboard() {
  const [statement, setStatement] = useState<LoadedStatement | null>(null);
  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [pending, setPending] = useState(false);
  const [quota, setQuota] = useState<Quota | null>(null);
  const [liveAi, setLiveAi] = useState<boolean | null>(null);
  const [chatEvents, setChatEvents] = useState<SecurityEvent[]>([]);
  const nextId = useRef(1);

  useEffect(() => {
    fetchHealth()
      .then((h) => setLiveAi(h.live_ai_enabled))
      .catch(() => setLiveAi(null));
    fetchQuota()
      .then(setQuota)
      .catch(() => setQuota(null));
  }, []);

  const load = useCallback(async (input: LoadedStatement) => {
    setLoading(true);
    setError(null);
    try {
      const result = await analyzeStatement(input);
      setStatement(input);
      setAnalysis(result);
      setQuota(result.quota);
      setLiveAi(result.live_ai_enabled);
      setTurns([]);
      setChatEvents([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not analyse that statement.");
    } finally {
      setLoading(false);
    }
  }, []);

  const ask = useCallback(
    async (prompt: string) => {
      if (!statement) return;
      const id = nextId.current++;
      setTurns((prev) => [...prev, { id, prompt, response: null, error: null }]);
      setPending(true);
      try {
        const response = await askAnalyst(prompt, statement);
        setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, response } : t)));
        setQuota(response.quota);
        const newEvents = response.security.events.filter(
          (e) => e.type === "prompt_rejected" || e.type === "rate_limited",
        );
        if (newEvents.length) setChatEvents((prev) => [...prev, ...newEvents]);
      } catch (err) {
        const message = err instanceof Error ? err.message : "The analyst could not answer.";
        setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, error: message } : t)));
      } finally {
        setPending(false);
      }
    },
    [statement],
  );

  const blockedPrompts = chatEvents.filter((e) => e.type === "prompt_rejected").length;
  const currency = analysis?.summary.currency ?? "GBP";

  return (
    <div className="space-y-4">
      <ControlBar
        loading={loading}
        source={analysis?.source ?? null}
        fileName={statement?.fileName ?? null}
        piiScrubbed={analysis?.security.pii_fields_scrubbed ?? 0}
        injectionsBlocked={(analysis?.security.injections_blocked ?? 0) + blockedPrompts}
        liveAiEnabled={liveAi}
        onLoadSample={() => load({ csvText: null, useSample: true, fileName: "sample_uk_statement.csv" })}
        onUpload={(csvText, fileName) => load({ csvText, useSample: false, fileName })}
        onError={setError}
      />

      {error && (
        <div
          role="alert"
          className="flex items-start justify-between gap-3 rounded-2xl border border-bad/30 bg-bad-soft px-4 py-3 text-sm text-bad"
        >
          <span className="flex items-start gap-2">
            <AlertIcon className="mt-0.5 shrink-0" />
            {error}
          </span>
          <button type="button" onClick={() => setError(null)} className="text-xs font-semibold underline">
            Dismiss
          </button>
        </div>
      )}

      {!analysis ? (
        <EmptyState onLoadSample={() => load({ csvText: null, useSample: true, fileName: null })} loading={loading} />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-1 text-xs text-muted">
            <span>
              {longDate(analysis.summary.period_start)} – {longDate(analysis.summary.period_end)}
            </span>
            <span>{analysis.summary.rows_analyzed} transactions analysed</span>
            {analysis.summary.warnings.map((w) => (
              <span key={w} className="inline-flex items-center gap-1 text-warn">
                <InfoIcon width={12} height={12} />
                {w}
              </span>
            ))}
          </div>

          <KpiCards kpis={analysis.kpis} currency={currency} />

          <div className="grid gap-4 lg:grid-cols-2">
            <CategoryBarChart
              categories={analysis.charts.monthly_category.categories}
              rows={analysis.charts.monthly_category.rows}
              currency={currency}
            />
            <CumulativeSpendChart points={analysis.charts.daily_cumulative} currency={currency} />
          </div>

          <div className="grid gap-4 lg:grid-cols-5">
            <div className="lg:col-span-3">
              <AnalystPanel enabled={!loading} turns={turns} pending={pending} quota={quota} onAsk={ask} />
            </div>
            <div className="lg:col-span-2">
              <FindingsPanel analysis={analysis} extraEvents={chatEvents} />
            </div>
          </div>

          <TransactionsTable transactions={analysis.transactions} currency={currency} />
        </>
      )}
    </div>
  );
}
