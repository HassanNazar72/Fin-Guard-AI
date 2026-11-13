"use client";

import { useMemo, useState } from "react";
import { money, shortDate } from "@/lib/format";
import type { Transaction, TransactionFlag } from "@/lib/types";

const FLAG_META: Record<TransactionFlag, { label: string; className: string }> = {
  injection_blocked: { label: "Injection blocked", className: "bg-bad-soft text-bad" },
  pii_redacted: { label: "PII redacted", className: "bg-good-soft text-good" },
  duplicate: { label: "Duplicate?", className: "bg-bad-soft text-bad" },
  outlier: { label: "Outlier", className: "bg-bad-soft text-bad" },
  price_increase: { label: "Price rise", className: "bg-warn-soft text-warn" },
};

export function TransactionsTable({ transactions, currency }: { transactions: Transaction[]; currency: string }) {
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const rows = useMemo(
    () => (flaggedOnly ? transactions.filter((t) => t.flags.length > 0) : transactions),
    [transactions, flaggedOnly],
  );
  const flaggedCount = transactions.filter((t) => t.flags.length > 0).length;

  return (
    <section aria-label="Sanitised transactions" className="rounded-2xl border border-line bg-card p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-ink">Sanitised Transactions</h2>
          <p className="text-xs text-muted">
            Exactly what the agent&apos;s tools see - PII hashed, injections cut out.
          </p>
        </div>
        <label className="inline-flex cursor-pointer items-center gap-2 text-xs text-ink-2">
          <input
            type="checkbox"
            checked={flaggedOnly}
            onChange={(e) => setFlaggedOnly(e.target.checked)}
            className="h-3.5 w-3.5 accent-[var(--series-1)]"
          />
          Flagged only ({flaggedCount})
        </label>
      </div>
      <div className="max-h-96 overflow-auto">
        <table className="w-full min-w-[40rem] text-left text-xs">
          <thead className="sticky top-0 z-10 bg-card text-muted">
            <tr>
              <th className="py-2 pr-3 font-medium">ID</th>
              <th className="py-2 pr-3 font-medium">Date</th>
              <th className="py-2 pr-3 font-medium">Merchant</th>
              <th className="py-2 pr-3 font-medium">Category</th>
              <th className="py-2 pr-3 text-right font-medium">Amount</th>
              <th className="py-2 font-medium">Flags</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.txn_id} className="border-t border-line align-top">
                <td className="py-2 pr-3 font-mono text-muted">{t.txn_id}</td>
                <td className="whitespace-nowrap py-2 pr-3 text-ink-2">
                  {shortDate(t.date)}
                  {t.time ? <span className="text-muted"> {t.time}</span> : null}
                </td>
                <td className="max-w-[18rem] break-words py-2 pr-3 font-mono text-[11px] text-ink">{t.merchant}</td>
                <td className="py-2 pr-3 text-ink-2">{t.category}</td>
                <td
                  className={`whitespace-nowrap py-2 pr-3 text-right tabular-nums ${
                    t.amount > 0 ? "text-good" : "text-ink"
                  }`}
                >
                  {money(t.amount, currency, { sign: true })}
                </td>
                <td className="py-2">
                  <div className="flex flex-wrap gap-1">
                    {t.flags.map((f) => (
                      <span
                        key={f}
                        className={`whitespace-nowrap rounded-full px-2 py-0.5 text-[10px] font-semibold ${FLAG_META[f].className}`}
                      >
                        {FLAG_META[f].label}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
