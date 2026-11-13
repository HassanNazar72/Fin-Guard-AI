import { longDate, money } from "@/lib/format";
import type { AnalyzeResponse, SecurityEvent } from "@/lib/types";
import { AlertIcon, BanIcon, CheckIcon, LockIcon, ShieldIcon } from "./icons";

const EVENT_META: Record<SecurityEvent["type"], { label: string; tone: string; Icon: typeof ShieldIcon }> = {
  pii_redacted: { label: "PII redacted", tone: "text-good", Icon: LockIcon },
  injection_blocked: { label: "Injection neutralised", tone: "text-bad", Icon: BanIcon },
  prompt_rejected: { label: "Prompt blocked", tone: "text-bad", Icon: BanIcon },
  rate_limited: { label: "Rate limited", tone: "text-warn", Icon: AlertIcon },
};

interface Props {
  analysis: AnalyzeResponse;
  extraEvents: SecurityEvent[];
}

export function FindingsPanel({ analysis, extraEvents }: Props) {
  const currency = analysis.summary.currency;
  const { duplicates, outliers } = analysis.insights.anomalies;
  const increases = analysis.insights.subscriptions.flagged_increases;
  const events = [...analysis.security.events, ...extraEvents];

  return (
    <div className="flex flex-col gap-3">
      <section aria-label="Detected anomalies" className="rounded-2xl border border-line bg-card p-4">
        <h2 className="text-sm font-semibold text-ink">Detected Anomalies</h2>
        <p className="mb-3 text-xs text-muted">Computed deterministically in Python - no LLM involved.</p>
        {duplicates.length + outliers.length + increases.length === 0 ? (
          <p className="flex items-center gap-1.5 text-sm text-ink-2">
            <CheckIcon className="text-good" /> No anomalies found.
          </p>
        ) : (
          <ul className="space-y-2.5 text-sm">
            {increases.map((s) => (
              <li key={`sub-${s.merchant}`} className="flex gap-2">
                <AlertIcon className="mt-0.5 shrink-0 text-warn" />
                <div>
                  <p className="font-medium text-ink">Subscription creep · {s.merchant}</p>
                  <p className="text-xs text-ink-2">
                    {money(s.previous_amount, currency)} → {money(s.latest_amount, currency)} (+{s.price_change_pct}
                    %), {money(s.annualised_increase, currency)} more per year
                  </p>
                </div>
              </li>
            ))}
            {duplicates.map((d) => (
              <li key={`dup-${d.second_txn_id}`} className="flex gap-2">
                <AlertIcon className="mt-0.5 shrink-0 text-bad" />
                <div>
                  <p className="font-medium text-ink">Possible duplicate · {d.merchant}</p>
                  <p className="text-xs text-ink-2">
                    {money(d.amount, currency)} charged twice, {d.hours_apart}h apart ({d.first_at.slice(11)} &amp;{" "}
                    {d.second_at.slice(11)} on {longDate(d.first_at.slice(0, 10))})
                  </p>
                </div>
              </li>
            ))}
            {outliers.map((o) => (
              <li key={`out-${o.txn_id}`} className="flex gap-2">
                <AlertIcon className="mt-0.5 shrink-0 text-bad" />
                <div>
                  <p className="font-medium text-ink">Unusually large · {o.merchant}</p>
                  <p className="text-xs text-ink-2">
                    {money(o.amount, currency)} on {longDate(o.date)}, z-score {o.z_score} (typical spend{" "}
                    {money(analysis.insights.anomalies.mean_spend, currency)})
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Security events" className="rounded-2xl border border-line bg-card p-4">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold text-ink">
          <ShieldIcon className="text-good" /> Security Event Log
        </h2>
        <p className="mb-3 text-xs text-muted">Firewall actions taken before data reached the AI.</p>
        {events.length === 0 ? (
          <p className="text-sm text-ink-2">No PII or injection attempts detected.</p>
        ) : (
          <ul className="max-h-60 space-y-2 overflow-y-auto pr-1 text-xs">
            {events.map((e, i) => {
              const meta = EVENT_META[e.type];
              return (
                <li key={`${e.type}-${e.txn_id ?? "chat"}-${i}`} className="flex gap-2">
                  <meta.Icon width={14} height={14} className={`mt-px shrink-0 ${meta.tone}`} />
                  <div>
                    <p className="font-semibold text-ink">
                      {meta.label}
                      {e.txn_id ? <span className="font-mono font-normal text-muted"> · {e.txn_id}</span> : null}
                    </p>
                    <p className="text-ink-2">{e.detail}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
