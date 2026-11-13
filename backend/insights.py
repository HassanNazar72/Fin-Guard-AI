"""Deterministic insight engine.

Used whenever a live Gemini call is not possible or not wanted:

* no ``GEMINI_API_KEY`` configured,
* the caller's daily live quota is exhausted (zero-bill protection),
* Gemini errored or returned output that failed schema validation.

It mirrors the agent contract exactly: route the question to tools, run them,
and return a validated :class:`FinancialInsightReport`. The answers are
template-based but every number is still produced by ``backend.tools``.
"""

from __future__ import annotations

import re
from typing import Any

from backend.schemas import FinancialInsightReport
from backend.tools import TOOL_NAMES, FinancialToolbox

# Ordered keyword rules: (tool, regex). A question can match several tools.
INTENT_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "detect_subscription_creep",
        re.compile(
            r"subscri|recurring|netflix|spotify|creep|membership|direct debit|standing order"
            r"|price (?:rise|increase|hike)|went up|monthly bills?",
            re.I,
        ),
    ),
    (
        "detect_anomalies_and_duplicates",
        re.compile(
            r"duplicat|anomal|fraud|suspicious|unusual|outlier|double|twice|charged .*again"
            r"|odd|strange|weird|dispute|unexpected|large(?:st)? (?:transaction|purchase|charge|payment)"
            r"|biggest (?:transaction|purchase|charge|payment)|one-?off",
            re.I,
        ),
    ),
    (
        "get_cashflow_summary",
        re.compile(
            r"cash ?flow|income|earn|salary|sav(?:e|ed|ing|ings)|net\b|overall|in total"
            r"|total (?:spend|spending|spent|outgoings)|how much (?:did|have) i (?:spend|spent)(?! on)"
            r"|money (?:in|out)|budget|afford|surplus|deficit|summary|summari[sz]e|overview|health",
            re.I,
        ),
    ),
    (
        "get_category_breakdown",
        re.compile(
            r"categor|breakdown|break down|where (?:does|did|is|do) (?:most of |all of )?my money"
            r"|spend(?:ing)? on|spent on|spend the most|most of my money"
            r"|groceries|eating out|restaurants|takeaway|transport|travel|shopping|bills|housing|\brent\b|mortgage"
            r"|entertainment|health (?:&|and) care|gym|top (?:spend|categories)"
            r"|biggest (?:spend|categor|expense)|most money",
            re.I,
        ),
    ),
)

DEFAULT_TOOLS = ("get_cashflow_summary", "get_category_breakdown")

CATEGORY_ALIASES = {
    "rent": "Housing",
    "mortgage": "Housing",
    "takeaway": "Eating Out",
    "restaurant": "Eating Out",
    "food delivery": "Eating Out",
    "travel": "Transport",
    "commut": "Transport",
    "supermarket": "Groceries",
    "gym": "Health & Care",
    "utilities": "Bills",
}


def route_intent(question: str) -> list[str]:
    """Map a natural-language question to the tools needed to answer it."""
    matched = [tool for tool, pattern in INTENT_RULES if pattern.search(question or "")]
    return matched or list(DEFAULT_TOOLS)


def fmt_money(value: float, currency: str = "GBP") -> str:
    symbol = {"GBP": "£", "EUR": "€", "USD": "$"}.get(currency)
    sign = "-" if value < 0 else ""
    body = f"{abs(value):,.2f}"
    return f"{sign}{symbol}{body}" if symbol else f"{sign}{body} {currency}"


def _fmt_date(iso: str) -> str:
    year, month, day = iso.split("-")
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    return f"{int(day)} {months[int(month) - 1]} {year}"


def run_tools(toolbox: FinancialToolbox, tool_names: list[str]) -> dict[str, dict[str, Any]]:
    return {name: toolbox.execute(name) for name in tool_names if name in TOOL_NAMES}


def collect_risks(outputs: dict[str, dict[str, Any]]) -> list[str]:
    """Deterministic risk flags derived from tool outputs."""
    risks: list[str] = []
    subs = outputs.get("detect_subscription_creep")
    if subs:
        cur = subs["currency"]
        for item in subs["flagged_increases"]:
            risks.append(
                f"Subscription creep: {item['merchant']} rose {item['price_change_pct']}% "
                f"({fmt_money(item['previous_amount'], cur)} -> {fmt_money(item['latest_amount'], cur)})"
            )
    anomalies = outputs.get("detect_anomalies_and_duplicates")
    if anomalies:
        cur = anomalies["currency"]
        for dup in anomalies["duplicates"]:
            risks.append(
                f"Possible duplicate charge: {dup['merchant']} {fmt_money(dup['amount'], cur)} "
                f"twice within {dup['hours_apart']} hours"
            )
        for out in anomalies["outliers"]:
            risks.append(
                f"Unusually large transaction: {out['merchant']} {fmt_money(out['amount'], cur)} "
                f"(z-score {out['z_score']})"
            )
    cash = outputs.get("get_cashflow_summary")
    if cash:
        if cash["net_cashflow"] < 0:
            risks.append(f"Negative net cashflow of {fmt_money(cash['net_cashflow'], cash['currency'])}")
        elif cash["savings_rate_pct"] is not None and cash["savings_rate_pct"] < 10:
            risks.append(f"Low savings rate of {cash['savings_rate_pct']}%")
    return risks


def _cashflow_sentence(out: dict[str, Any]) -> str:
    cur = out["currency"]
    net = out["net_cashflow"]
    net_text = f"+{fmt_money(net, cur)}" if net >= 0 else fmt_money(net, cur)
    rate = (
        f", a savings rate of {out['savings_rate_pct']}%"
        if out["savings_rate_pct"] is not None
        else ""
    )
    return (
        f"Between {_fmt_date(out['period_start'])} and {_fmt_date(out['period_end'])} you received "
        f"{fmt_money(out['total_income'], cur)} and spent {fmt_money(out['total_spend'], cur)}, "
        f"leaving net cashflow of {net_text}{rate}."
    )


def _category_sentence(out: dict[str, Any], question: str) -> str:
    cur = out["currency"]
    cats = out["categories"]
    if not cats:
        return "There is no spending in this statement."
    lowered = (question or "").lower()
    wanted = {cat for alias, cat in CATEGORY_ALIASES.items() if alias in lowered}
    asked = [
        c
        for c in cats
        if c["category"] in wanted or c["category"].lower().split(" ")[0] in lowered
    ]
    if asked:
        parts = [
            f"{c['category']}: {fmt_money(c['total'], cur)} across {c['transaction_count']} "
            f"transactions ({c['pct_of_spend']}% of spend)"
            for c in asked
        ]
        return "; ".join(parts) + "."
    top = ", ".join(
        f"{c['category']} ({fmt_money(c['total'], cur)}, {c['pct_of_spend']}%)" for c in cats[:3]
    )
    return f"Your largest spending categories were {top}."


def _subscription_sentence(out: dict[str, Any]) -> str:
    cur = out["currency"]
    if not out["recurring_merchants"]:
        return "I found no recurring monthly payments in this statement."
    text = (
        f"I found {out['recurring_count']} recurring monthly payments totalling "
        f"{fmt_money(out['total_monthly_recurring'], cur)} per month."
    )
    flagged = out["flagged_increases"]
    if not flagged:
        return text + " None of them changed price."
    for item in flagged:
        text += (
            f" {item['merchant']} increased from {fmt_money(item['previous_amount'], cur)} to "
            f"{fmt_money(item['latest_amount'], cur)} (+{item['price_change_pct']}%), an extra "
            f"{fmt_money(item['annualised_increase'], cur)} a year."
        )
    return text


def _anomaly_sentence(out: dict[str, Any]) -> str:
    cur = out["currency"]
    if not out["duplicates"] and not out["outliers"]:
        return "No duplicate charges or unusually large transactions were found."
    parts: list[str] = []
    for dup in out["duplicates"]:
        parts.append(
            f"Possible duplicate: {dup['merchant']} charged {fmt_money(dup['amount'], cur)} twice, "
            f"{dup['hours_apart']} hours apart ({dup['first_at']} and {dup['second_at']})."
        )
    for item in out["outliers"]:
        parts.append(
            f"Unusually large: {item['merchant']} {fmt_money(item['amount'], cur)} on "
            f"{_fmt_date(item['date'])}, {item['z_score']} standard deviations above your typical "
            f"spend of {fmt_money(out['mean_spend'], cur)}."
        )
    return " ".join(parts)


def compose_report(question: str, outputs: dict[str, dict[str, Any]]) -> FinancialInsightReport:
    """Build a schema-valid report from tool outputs, with zero LLM involvement."""
    sentences: list[str] = []
    if "get_cashflow_summary" in outputs:
        sentences.append(_cashflow_sentence(outputs["get_cashflow_summary"]))
    if "get_category_breakdown" in outputs:
        sentences.append(_category_sentence(outputs["get_category_breakdown"], question))
    if "detect_subscription_creep" in outputs:
        sentences.append(_subscription_sentence(outputs["detect_subscription_creep"]))
    if "detect_anomalies_and_duplicates" in outputs:
        sentences.append(_anomaly_sentence(outputs["detect_anomalies_and_duplicates"]))
    if not sentences:
        sentences.append("I could not find data in this statement to answer that question.")

    anomalies = outputs.get("detect_anomalies_and_duplicates") or {}
    needs_review = bool(anomalies.get("duplicates") or anomalies.get("outliers"))
    return FinancialInsightReport(
        answer=" ".join(sentences),
        tools_invoked=list(outputs.keys()),
        flagged_risks=collect_risks(outputs),
        confidence_score=0.95 if outputs else 0.3,
        requires_human_review=needs_review,
    )


def deterministic_answer(question: str, toolbox: FinancialToolbox) -> FinancialInsightReport:
    return compose_report(question, run_tools(toolbox, route_intent(question)))
