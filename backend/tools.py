"""Deterministic financial math tools.

The LLM never does arithmetic. It *chooses* which of these functions to call
(Gemini Function Calling), receives their exact JSON output, and writes prose
around numbers it was handed. Every figure in an answer is traceable to one of
the four functions below.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from backend.config import (
    DUPLICATE_WINDOW_HOURS,
    OUTLIER_EXCLUDED_CATEGORIES,
    OUTLIER_Z_THRESHOLD,
    SUBSCRIPTION_CREEP_MIN_PCT,
    SUBSCRIPTION_MAX_GAP_DAYS,
    SUBSCRIPTION_MIN_GAP_DAYS,
)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str


TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "get_cashflow_summary",
        "Exact total income, total spend, net cashflow and savings rate (%) for the "
        "loaded statement, plus the statement period and transaction count.",
    ),
    ToolSpec(
        "get_category_breakdown",
        "Total spend grouped by category (Groceries, Bills, Eating Out, ...) sorted "
        "from largest to smallest, with each category's share of total spend.",
    ),
    ToolSpec(
        "detect_subscription_creep",
        "Finds recurring monthly merchants (subscriptions, bills, rent) and flags any "
        "whose latest charge increased versus the previous one, with the % change.",
    ),
    ToolSpec(
        "detect_anomalies_and_duplicates",
        "Flags duplicate charges (same merchant and amount within 48 hours) and "
        "unusually large transactions more than 2.5 standard deviations above mean spend.",
    ),
)
TOOL_NAMES: tuple[str, ...] = tuple(spec.name for spec in TOOL_SPECS)


def _money(value: float) -> float:
    return round(float(value) + 0.0, 2)


def merchant_key(merchant: str) -> str:
    """Stable grouping key: ``"AMAZON.CO.UK*2K4H71"`` -> ``"AMAZONCOUK"``."""
    base = str(merchant).split("*", 1)[0]
    base = re.sub(r"\[[^\]]*\]", " ", base)  # drop redaction tokens
    base = re.sub(r"[^A-Za-z ]+", "", base).upper()
    return re.sub(r"\s+", " ", base).strip() or str(merchant).upper()


def _timestamps(frame: pd.DataFrame) -> pd.Series:
    times = frame["time"].where(frame["time"].astype(str).str.len() > 0, "12:00")
    return pd.to_datetime(frame["date"] + " " + times, format="%Y-%m-%d %H:%M")


class FinancialToolbox:
    """Binds the four deterministic tools to one sanitised statement."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.df["amount"] = self.df["amount"].astype(float)
        self.currency = (
            str(self.df["currency"].mode().iloc[0]) if len(self.df) else "GBP"
        )
        self._registry: dict[str, Callable[[], dict[str, Any]]] = {
            "get_cashflow_summary": self.get_cashflow_summary,
            "get_category_breakdown": self.get_category_breakdown,
            "detect_subscription_creep": self.detect_subscription_creep,
            "detect_anomalies_and_duplicates": self.detect_anomalies_and_duplicates,
        }

    # ------------------------------------------------------------------ helpers
    @property
    def spend(self) -> pd.DataFrame:
        return self.df[self.df["amount"] < 0]

    def execute(self, name: str) -> dict[str, Any]:
        """Run a tool by name. Unknown names return an error payload, never raise."""
        func = self._registry.get(name)
        if func is None:
            return {"error": f"Unknown tool '{name}'. Available: {', '.join(TOOL_NAMES)}"}
        return func()

    # -------------------------------------------------------------------- tools
    def get_cashflow_summary(self) -> dict[str, Any]:
        income = self.df.loc[self.df["amount"] > 0, "amount"].sum()
        spend = -self.spend["amount"].sum()
        net = income - spend
        savings_rate = (net / income * 100) if income > 0 else None
        return {
            "currency": self.currency,
            "period_start": str(self.df["date"].min()),
            "period_end": str(self.df["date"].max()),
            "months_covered": int(self.df["date"].str[:7].nunique()),
            "transaction_count": int(len(self.df)),
            "total_income": _money(income),
            "total_spend": _money(spend),
            "net_cashflow": _money(net),
            "savings_rate_pct": None if savings_rate is None else round(float(savings_rate), 1),
        }

    def get_category_breakdown(self) -> dict[str, Any]:
        spend = self.spend.assign(abs_amount=lambda f: -f["amount"])
        total = spend["abs_amount"].sum()
        grouped = (
            spend.groupby("category")
            .agg(total=("abs_amount", "sum"), transaction_count=("abs_amount", "size"))
            .sort_values("total", ascending=False)
        )
        categories = [
            {
                "category": str(category),
                "total": _money(row["total"]),
                "pct_of_spend": round(float(row["total"] / total * 100), 1) if total else 0.0,
                "transaction_count": int(row["transaction_count"]),
            }
            for category, row in grouped.iterrows()
        ]
        return {"currency": self.currency, "total_spend": _money(total), "categories": categories}

    def detect_subscription_creep(self) -> dict[str, Any]:
        spend = self.spend.assign(key=lambda f: f["merchant"].map(merchant_key))
        recurring: list[dict[str, Any]] = []
        for _, group in spend.groupby("key"):
            if len(group) < 2:
                continue
            group = group.sort_values(["date", "time"])
            dates = pd.to_datetime(group["date"])
            gaps = dates.diff().dt.days.dropna()
            if not gaps.between(SUBSCRIPTION_MIN_GAP_DAYS, SUBSCRIPTION_MAX_GAP_DAYS).all():
                continue
            amounts = (-group["amount"]).tolist()
            previous, latest = amounts[-2], amounts[-1]
            change_pct = (latest - previous) / previous * 100 if previous else 0.0
            recurring.append(
                {
                    "merchant": str(group["merchant"].iloc[-1]),
                    "category": str(group["category"].iloc[-1]),
                    "charges": len(group),
                    "first_charge_date": str(group["date"].iloc[0]),
                    "latest_charge_date": str(group["date"].iloc[-1]),
                    "previous_amount": _money(previous),
                    "latest_amount": _money(latest),
                    "price_change_pct": round(float(change_pct), 1),
                    "flagged_increase": bool(change_pct >= SUBSCRIPTION_CREEP_MIN_PCT),
                    "annualised_increase": _money((latest - previous) * 12)
                    if change_pct >= SUBSCRIPTION_CREEP_MIN_PCT
                    else 0.0,
                }
            )
        recurring.sort(key=lambda r: r["latest_amount"], reverse=True)
        flagged = [r for r in recurring if r["flagged_increase"]]
        return {
            "currency": self.currency,
            "recurring_merchants": recurring,
            "flagged_increases": flagged,
            "recurring_count": len(recurring),
            "total_monthly_recurring": _money(sum(r["latest_amount"] for r in recurring)),
        }

    def detect_anomalies_and_duplicates(self) -> dict[str, Any]:
        spend = self.spend.copy()
        spend["key"] = spend["merchant"].map(merchant_key)
        spend["ts"] = _timestamps(spend)

        duplicates: list[dict[str, Any]] = []
        for _, group in spend.groupby(["key", "amount"]):
            if len(group) < 2:
                continue
            group = group.sort_values("ts")
            rows = list(group.itertuples())
            for first, second in zip(rows, rows[1:]):
                hours = (second.ts - first.ts).total_seconds() / 3600
                if hours <= DUPLICATE_WINDOW_HOURS:
                    duplicates.append(
                        {
                            "merchant": str(second.merchant),
                            "amount": _money(-second.amount),
                            "first_txn_id": str(first.txn_id),
                            "second_txn_id": str(second.txn_id),
                            "first_at": first.ts.strftime("%Y-%m-%d %H:%M"),
                            "second_at": second.ts.strftime("%Y-%m-%d %H:%M"),
                            "hours_apart": round(hours, 2),
                        }
                    )

        base = spend[~spend["category"].isin(OUTLIER_EXCLUDED_CATEGORIES)]
        values = -base["amount"]
        mean = float(values.mean()) if len(values) else 0.0
        std = float(values.std()) if len(values) > 1 else 0.0
        threshold = mean + OUTLIER_Z_THRESHOLD * std
        outliers: list[dict[str, Any]] = []
        if std > 0:
            for row in base[values > threshold].itertuples():
                outliers.append(
                    {
                        "txn_id": str(row.txn_id),
                        "date": str(row.date),
                        "merchant": str(row.merchant),
                        "category": str(row.category),
                        "amount": _money(-row.amount),
                        "z_score": round((-row.amount - mean) / std, 2),
                    }
                )
        outliers.sort(key=lambda o: o["amount"], reverse=True)
        return {
            "currency": self.currency,
            "duplicates": duplicates,
            "outliers": outliers,
            "duplicate_window_hours": DUPLICATE_WINDOW_HOURS,
            "outlier_rule": f"> mean + {OUTLIER_Z_THRESHOLD} std (excluding "
            + ", ".join(sorted(OUTLIER_EXCLUDED_CATEGORIES))
            + ")",
            "mean_spend": _money(mean),
            "std_spend": _money(std),
            "outlier_threshold": _money(threshold),
            "duplicate_count": len(duplicates),
            "outlier_count": len(outliers),
        }


# ------------------------------------------------------------- dashboard data
def monthly_category_spend(df: pd.DataFrame) -> dict[str, Any]:
    """Rows for a stacked bar chart: one row per month, one key per category."""
    spend = df[df["amount"] < 0].assign(
        month=lambda f: f["date"].str[:7], abs_amount=lambda f: -f["amount"]
    )
    if spend.empty:
        return {"categories": [], "rows": []}
    pivot = spend.pivot_table(
        index="month", columns="category", values="abs_amount", aggfunc="sum", fill_value=0.0
    )
    order = pivot.sum().sort_values(ascending=False).index.tolist()
    rows = [
        {"month": str(month), **{str(c): _money(pivot.loc[month, c]) for c in order}}
        for month in pivot.index
    ]
    return {"categories": [str(c) for c in order], "rows": rows}


def daily_cumulative_spend(df: pd.DataFrame) -> list[dict[str, Any]]:
    """One point per calendar day across the statement, with running spend."""
    if df.empty:
        return []
    spend = df[df["amount"] < 0].assign(abs_amount=lambda f: -f["amount"])
    daily = spend.groupby("date")["abs_amount"].sum()
    days = pd.date_range(df["date"].min(), df["date"].max(), freq="D").strftime("%Y-%m-%d")
    daily = daily.reindex(days, fill_value=0.0)
    cumulative = daily.cumsum()
    return [
        {"date": day, "spend": _money(daily[day]), "cumulative": _money(cumulative[day])}
        for day in days
    ]
