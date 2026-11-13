import type { ReactNode } from "react";
import { money } from "@/lib/format";
import type { AnalyzeResponse } from "@/lib/types";
import { AlertIcon, CheckIcon } from "./icons";

interface Props {
  kpis: AnalyzeResponse["kpis"];
  currency: string;
}

function Card({
  label,
  value,
  footnote,
  tone = "neutral",
}: {
  label: string;
  value: string;
  footnote: ReactNode;
  tone?: "neutral" | "good" | "bad";
}) {
  const valueColor = tone === "good" ? "text-good" : tone === "bad" ? "text-bad" : "text-ink";
  return (
    <div className="rounded-2xl border border-line bg-card p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <p className={`mt-2 text-2xl font-semibold tracking-tight sm:text-[1.75rem] ${valueColor}`}>
        {value}
      </p>
      <div className="mt-1 text-xs text-ink-2">{footnote}</div>
    </div>
  );
}

export function KpiCards({ kpis, currency }: Props) {
  const net = kpis.net_cashflow;
  const anomalies = kpis.anomalies_detected;
  return (
    <section aria-label="Key figures" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Card label="Total Income" value={money(kpis.total_income, currency)} footnote="All money in" />
      <Card label="Total Spend" value={money(kpis.total_spend, currency)} footnote="All money out" />
      <Card
        label="Net Cashflow"
        value={money(net, currency, { sign: true })}
        tone={net >= 0 ? "good" : "bad"}
        footnote={
          kpis.savings_rate_pct === null ? "No income recorded" : `Savings rate ${kpis.savings_rate_pct}%`
        }
      />
      <Card
        label="Detected Anomalies"
        value={String(anomalies)}
        tone={anomalies ? "bad" : "good"}
        footnote={
          anomalies ? (
            <span className="inline-flex items-center gap-1">
              <AlertIcon width={12} height={12} className="text-bad" />
              {kpis.duplicates} duplicate · {kpis.outliers} outlier · {kpis.subscription_increases} price rise
            </span>
          ) : (
            <span className="inline-flex items-center gap-1">
              <CheckIcon width={12} height={12} className="text-good" />
              Nothing unusual found
            </span>
          )
        }
      />
    </section>
  );
}
