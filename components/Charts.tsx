"use client";

import { useMemo, useState, type ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { compactMoney, money, monthLabel, shortDate } from "@/lib/format";
import type { DailyPoint, MonthlyCategoryRow } from "@/lib/types";

// Categorical slots are assigned in fixed order and never cycled; anything past
// slot 7 folds into a neutral "Other" so no hue is ever generated.
const SERIES = Array.from({ length: 7 }, (_, i) => `var(--series-${i + 1})`);
const OTHER = "Other";
const AXIS_TICK = { fill: "var(--muted)", fontSize: 11 };

interface TooltipRow {
  name?: string | number;
  value?: unknown;
  color?: string;
  fill?: string;
  dataKey?: unknown;
  payload?: unknown;
}

function TooltipShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="min-w-44 rounded-xl border border-line bg-card px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-semibold text-ink">{title}</p>
      {children}
    </div>
  );
}

function ChartCard({
  title,
  subtitle,
  chart,
  table,
}: {
  title: string;
  subtitle: string;
  chart: ReactNode;
  table: ReactNode;
}) {
  const [view, setView] = useState<"chart" | "table">("chart");
  return (
    <section className="rounded-2xl border border-line bg-card p-4" aria-label={title}>
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          <p className="text-xs text-muted">{subtitle}</p>
        </div>
        <div className="inline-flex rounded-full border border-line p-0.5 text-xs" role="group" aria-label="View">
          {(["chart", "table"] as const).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setView(v)}
              aria-pressed={view === v}
              className={`rounded-full px-2.5 py-1 font-medium capitalize transition ${
                view === v ? "bg-accent text-accent-ink" : "text-ink-2 hover:text-ink"
              }`}
            >
              {v}
            </button>
          ))}
        </div>
      </div>
      {view === "chart" ? chart : <div className="max-h-72 overflow-auto">{table}</div>}
    </section>
  );
}

function foldCategories(categories: string[], rows: MonthlyCategoryRow[]) {
  if (categories.length <= SERIES.length) return { keys: categories, rows };
  const keep = categories.slice(0, SERIES.length - 1);
  const rest = categories.slice(SERIES.length - 1);
  const folded = rows.map((row) => {
    const next: MonthlyCategoryRow = { month: row.month };
    keep.forEach((k) => (next[k] = Number(row[k] ?? 0)));
    next[OTHER] = Math.round(rest.reduce((sum, k) => sum + Number(row[k] ?? 0), 0) * 100) / 100;
    return next;
  });
  return { keys: [...keep, OTHER], rows: folded };
}

export function CategoryBarChart({
  categories,
  rows,
  currency,
}: {
  categories: string[];
  rows: MonthlyCategoryRow[];
  currency: string;
}) {
  const { keys, rows: data } = useMemo(() => foldCategories(categories, rows), [categories, rows]);
  const colorFor = (key: string, i: number) => (key === OTHER ? "var(--series-other)" : SERIES[i]);

  const chart = (
    <>
      <ul className="mb-3 flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink-2" aria-label="Legend">
        {keys.map((key, i) => (
          <li key={key} className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: colorFor(key, i) }} aria-hidden="true" />
            {key}
          </li>
        ))}
      </ul>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }} barCategoryGap="28%">
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <XAxis dataKey="month" tickFormatter={monthLabel} tick={AXIS_TICK} axisLine={false} tickLine={false} />
            <YAxis
              tickFormatter={(v: number) => compactMoney(v, currency)}
              tick={AXIS_TICK}
              axisLine={false}
              tickLine={false}
              width={52}
            />
            <Tooltip
              cursor={{ fill: "var(--grid)", opacity: 0.6 }}
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                const items = (payload as readonly TooltipRow[]).filter((p) => Number(p.value) > 0);
                const total = items.reduce((sum, p) => sum + Number(p.value), 0);
                return (
                  <TooltipShell title={monthLabel(String(label))}>
                    <ul className="space-y-0.5">
                      {[...items].reverse().map((p) => (
                        <li key={String(p.dataKey)} className="flex items-center justify-between gap-4 text-ink-2">
                          <span className="inline-flex items-center gap-1.5">
                            <span className="h-2 w-2 rounded-sm" style={{ background: p.fill ?? p.color }} />
                            {String(p.name)}
                          </span>
                          <span className="tabular-nums text-ink">{money(Number(p.value), currency)}</span>
                        </li>
                      ))}
                    </ul>
                    <p className="mt-1 flex justify-between border-t border-line pt-1 font-semibold text-ink">
                      <span>Total</span>
                      <span className="tabular-nums">{money(total, currency)}</span>
                    </p>
                  </TooltipShell>
                );
              }}
            />
            {keys.map((key, i) => (
              <Bar
                key={key}
                dataKey={key}
                name={key}
                stackId="spend"
                fill={colorFor(key, i)}
                stroke="var(--card)"
                strokeWidth={2}
                radius={i === keys.length - 1 ? [4, 4, 0, 0] : 0}
                maxBarSize={72}
                isAnimationActive={false}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </>
  );

  const table = (
    <table className="w-full text-left text-xs">
      <thead className="sticky top-0 bg-card text-muted">
        <tr>
          <th className="py-1.5 pr-3 font-medium">Category</th>
          {rows.map((r) => (
            <th key={r.month} className="py-1.5 pr-3 text-right font-medium">
              {monthLabel(r.month)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="text-ink-2">
        {categories.map((c) => (
          <tr key={c} className="border-t border-line">
            <td className="py-1.5 pr-3 text-ink">{c}</td>
            {rows.map((r) => (
              <td key={r.month} className="py-1.5 pr-3 text-right tabular-nums">
                {money(Number(r[c] ?? 0), currency)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );

  return (
    <ChartCard
      title="Monthly Spend by Category"
      subtitle="Money out per month, stacked by category"
      chart={chart}
      table={table}
    />
  );
}

export function CumulativeSpendChart({ points, currency }: { points: DailyPoint[]; currency: string }) {
  const chart = (
    <div className="h-[18.5rem]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis
            dataKey="date"
            tickFormatter={shortDate}
            tick={AXIS_TICK}
            axisLine={false}
            tickLine={false}
            minTickGap={32}
          />
          <YAxis
            tickFormatter={(v: number) => compactMoney(v, currency)}
            tick={AXIS_TICK}
            axisLine={false}
            tickLine={false}
            width={52}
          />
          <Tooltip
            cursor={{ stroke: "var(--muted)", strokeWidth: 1, strokeDasharray: "3 3" }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const point = (payload as readonly TooltipRow[])[0].payload as DailyPoint;
              return (
                <TooltipShell title={shortDate(point.date)}>
                  <p className="flex justify-between gap-4 text-ink-2">
                    <span>Cumulative spend</span>
                    <span className="font-semibold tabular-nums text-ink">{money(point.cumulative, currency)}</span>
                  </p>
                  <p className="flex justify-between gap-4 text-ink-2">
                    <span>Spent that day</span>
                    <span className="tabular-nums text-ink">{money(point.spend, currency)}</span>
                  </p>
                </TooltipShell>
              );
            }}
          />
          <Line
            type="monotone"
            dataKey="cumulative"
            name="Cumulative spend"
            stroke="var(--series-1)"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 5, fill: "var(--series-1)", stroke: "var(--card)", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );

  const table = (
    <table className="w-full text-left text-xs">
      <thead className="sticky top-0 bg-card text-muted">
        <tr>
          <th className="py-1.5 pr-3 font-medium">Date</th>
          <th className="py-1.5 pr-3 text-right font-medium">Spent</th>
          <th className="py-1.5 text-right font-medium">Cumulative</th>
        </tr>
      </thead>
      <tbody className="text-ink-2">
        {points
          .filter((p) => p.spend > 0)
          .map((p) => (
            <tr key={p.date} className="border-t border-line">
              <td className="py-1.5 pr-3 text-ink">{shortDate(p.date)}</td>
              <td className="py-1.5 pr-3 text-right tabular-nums">{money(p.spend, currency)}</td>
              <td className="py-1.5 text-right tabular-nums">{money(p.cumulative, currency)}</td>
            </tr>
          ))}
      </tbody>
    </table>
  );

  return (
    <ChartCard
      title="Daily Cumulative Spend"
      subtitle="Running total of money out across the statement"
      chart={chart}
      table={table}
    />
  );
}
