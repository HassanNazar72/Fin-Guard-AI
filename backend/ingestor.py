"""Multi-bank CSV statement ingestion.

Turns heterogeneous bank exports (Monzo, Barclays, Starling, HSBC-style) into
one clean internal frame:

    txn_id | date (ISO) | time | merchant | amount | currency | raw_category | category

Conventions
-----------
* ``amount`` is signed: negative = money out (spend), positive = money in.
* Dates are UK-first: ``03/04/2026`` is 3 April, never 4 March.
* Exact duplicate rows (same date, time, merchant, amount, currency) are export
  artefacts and are dropped. Two *identical charges at different times* are
  kept on purpose - spotting those is the anomaly detector's job.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from backend.config import MAX_CSV_CHARS, MAX_ROWS

INTERNAL_COLUMNS = [
    "txn_id",
    "date",
    "time",
    "merchant",
    "amount",
    "currency",
    "raw_category",
    "category",
]

HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "date": (
        "date",
        "transaction date",
        "posted date",
        "posting date",
        "completed date",
        "booking date",
        "value date",
    ),
    "time": ("time", "transaction time"),
    "merchant": (
        "merchant",
        "name",
        "description",
        "transaction description",
        "payee",
        "memo",
        "details",
        "narrative",
        "counter party",
        "counterparty",
    ),
    "amount": ("amount", "value", "amount gbp", "transaction amount"),
    "money_in": ("money in", "paid in", "credit", "credit amount", "in"),
    "money_out": ("money out", "paid out", "debit", "debit amount", "out"),
    "currency": ("currency", "local currency", "ccy"),
    "raw_category": ("category", "spending category", "type", "transaction type"),
}

DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y/%m/%d",
    "%d/%m/%y",
    "%d %b %Y",
    "%d %B %Y",
    "%d-%b-%Y",
)

CURRENCY_SYMBOLS = {"£": "GBP", "€": "EUR", "$": "USD"}

# Monzo / Starling style category labels -> display categories.
RAW_CATEGORY_MAP = {
    "housing": "Housing",
    "rent": "Housing",
    "mortgage": "Housing",
    "bills": "Bills",
    "utilities": "Bills",
    "groceries": "Groceries",
    "transport": "Transport",
    "travel": "Transport",
    "entertainment": "Entertainment",
    "subscriptions": "Entertainment",
    "eating out": "Eating Out",
    "eating_out": "Eating Out",
    "restaurants": "Eating Out",
    "shopping": "Shopping",
    "personal care": "Health & Care",
    "personal_care": "Health & Care",
    "health": "Health & Care",
    "transfers": "Transfers",
    "transfer": "Transfers",
    "income": "Income",
    "general": "General",
}

# Fallback keyword categoriser for rows with no bank-provided category.
MERCHANT_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("rent", "Housing"),
    ("letting", "Housing"),
    ("mortgage", "Housing"),
    ("council tax", "Bills"),
    ("energy", "Bills"),
    ("water", "Bills"),
    ("ee limited", "Bills"),
    ("vodafone", "Bills"),
    ("tesco", "Groceries"),
    ("sainsbury", "Groceries"),
    ("lidl", "Groceries"),
    ("aldi", "Groceries"),
    ("waitrose", "Groceries"),
    ("asda", "Groceries"),
    ("tfl", "Transport"),
    ("trainline", "Transport"),
    ("uber eats", "Eating Out"),
    ("uber", "Transport"),
    ("deliveroo", "Eating Out"),
    ("pret", "Eating Out"),
    ("costa", "Eating Out"),
    ("starbucks", "Eating Out"),
    ("netflix", "Entertainment"),
    ("spotify", "Entertainment"),
    ("cinema", "Entertainment"),
    ("cineworld", "Entertainment"),
    ("odeon", "Entertainment"),
    ("amazon", "Shopping"),
    ("amzn", "Shopping"),
    ("asos", "Shopping"),
    ("currys", "Shopping"),
    ("boots", "Health & Care"),
    ("gym", "Health & Care"),
    ("transfer", "Transfers"),
)


class IngestionError(ValueError):
    """Raised when an uploaded statement cannot be safely ingested."""


@dataclass
class IngestResult:
    df: pd.DataFrame
    rows_in: int
    duplicates_dropped: int = 0
    invalid_rows_dropped: int = 0
    warnings: list[str] = field(default_factory=list)


def _normalize_header(header: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", str(header).lower().replace("﻿", ""))
    return re.sub(r"\s+", " ", cleaned).strip()


def map_columns(columns: list[str]) -> dict[str, str]:
    """Return ``{internal_name: source_column}`` for every recognised header."""
    normalized = {_normalize_header(c): c for c in columns}
    mapping: dict[str, str] = {}
    for internal, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            if alias in normalized and normalized[alias] not in mapping.values():
                mapping[internal] = normalized[alias]
                break
    return mapping


def parse_date(value: object) -> str | None:
    """Coerce mixed UK date formats into ISO ``YYYY-MM-DD``."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    # Drop a trailing time component ("2026-08-01 09:00:00", "01/08/2026T09:00").
    text = re.split(r"[ T](?=\d{1,2}:\d{2})", text, maxsplit=1)[0].strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_time(value: object) -> str:
    """Return ``HH:MM`` or an empty string when no usable time is present."""
    text = "" if value is None else str(value).strip()
    match = re.match(r"^(\d{1,2}):(\d{2})", text)
    if not match:
        return ""
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return ""
    return f"{hour:02d}:{minute:02d}"


def parse_amount(value: object) -> float | None:
    """Parse ``-£1,234.56``, ``(12.00)``, ``12.00 CR`` etc. into a signed float."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "-"}:
        return None
    sign = 1.0
    upper = text.upper()
    if upper.endswith("CR"):
        text = text[:-2]
    elif upper.endswith("DR"):
        text, sign = text[:-2], -1.0
    text = text.strip()
    if text.startswith("(") and text.endswith(")"):
        text, sign = text[1:-1], -1.0
    for symbol in CURRENCY_SYMBOLS:
        text = text.replace(symbol, "")
    text = re.sub(r"(?i)\b(GBP|EUR|USD)\b", "", text)
    text = text.replace(",", "").replace(" ", "")
    if text.startswith("+"):
        text = text[1:]
    if text.startswith("-"):
        text, sign = text[1:], -sign
    if not re.fullmatch(r"\d+(\.\d+)?|\.\d+", text):
        return None
    return round(sign * float(text), 2)


def normalize_currency(value: object, amount_text: object = "") -> str:
    text = "" if value is None else str(value).strip().upper()
    if text in CURRENCY_SYMBOLS:
        return CURRENCY_SYMBOLS[text]
    if re.fullmatch(r"[A-Z]{3}", text):
        return text
    for symbol, code in CURRENCY_SYMBOLS.items():
        if symbol in str(amount_text):
            return code
    return "GBP"


def categorize(merchant: str, raw_category: str, amount: float) -> str:
    if amount > 0:
        return "Income"
    raw = raw_category.strip().lower()
    if raw in RAW_CATEGORY_MAP and RAW_CATEGORY_MAP[raw] != "Income":
        return RAW_CATEGORY_MAP[raw]
    lowered = merchant.lower()
    for keyword, category in MERCHANT_KEYWORDS:
        if keyword in lowered:
            return category
    return "General"


def read_csv_text(csv_text: str) -> pd.DataFrame:
    if not isinstance(csv_text, str) or not csv_text.strip():
        raise IngestionError("The uploaded statement is empty.")
    if len(csv_text) > MAX_CSV_CHARS:
        raise IngestionError(
            f"Statement file is too large (max {MAX_CSV_CHARS:,} characters)."
        )
    try:
        return pd.read_csv(
            io.StringIO(csv_text.lstrip("﻿")),
            dtype=str,
            keep_default_na=False,
            skipinitialspace=True,
            on_bad_lines="error",
        )
    except Exception as exc:  # pandas raises several parser error types
        raise IngestionError(f"Could not parse CSV: {exc.__class__.__name__}") from exc


def ingest_csv(csv_text: str, max_rows: int = MAX_ROWS) -> IngestResult:
    """Parse, normalise, validate and de-duplicate a bank statement CSV."""
    raw = read_csv_text(csv_text)
    rows_in = len(raw)
    if rows_in == 0:
        raise IngestionError("The statement contains no transactions.")
    if rows_in > max_rows:
        raise IngestionError(
            f"Statement has {rows_in} rows; the maximum is {max_rows}."
        )

    mapping = map_columns(list(raw.columns))
    if "date" not in mapping or "merchant" not in mapping:
        raise IngestionError(
            "Statement must include a date column and a merchant/description column."
        )
    has_split_amounts = "money_in" in mapping or "money_out" in mapping
    if "amount" not in mapping and not has_split_amounts:
        raise IngestionError(
            "Statement must include an amount column (or money in / money out columns)."
        )

    warnings: list[str] = []
    records: list[dict[str, object]] = []
    invalid = 0
    for _, row in raw.iterrows():
        if "amount" in mapping:
            amount_text = row[mapping["amount"]]
            amount = parse_amount(amount_text)
        else:
            money_in = parse_amount(row[mapping["money_in"]]) if "money_in" in mapping else None
            money_out = parse_amount(row[mapping["money_out"]]) if "money_out" in mapping else None
            amount_text = row[mapping.get("money_out") or mapping["money_in"]]
            if money_in is None and money_out is None:
                amount = None
            else:
                amount = round(abs(money_in or 0.0) - abs(money_out or 0.0), 2)

        date = parse_date(row[mapping["date"]])
        if date is None or amount is None:
            invalid += 1
            continue

        merchant = re.sub(r"\s+", " ", str(row[mapping["merchant"]]).strip())
        raw_category = (
            str(row[mapping["raw_category"]]).strip() if "raw_category" in mapping else ""
        )
        records.append(
            {
                "date": date,
                "time": parse_time(row[mapping["time"]]) if "time" in mapping else "",
                "merchant": merchant or "UNKNOWN MERCHANT",
                "amount": amount,
                "currency": normalize_currency(
                    row[mapping["currency"]] if "currency" in mapping else "", amount_text
                ),
                "raw_category": raw_category,
            }
        )

    if not records:
        raise IngestionError("No valid transactions found (check date and amount columns).")
    if invalid:
        warnings.append(f"{invalid} row(s) skipped because of an unreadable date or amount.")

    df = pd.DataFrame.from_records(records)
    before = len(df)
    df = df.drop_duplicates(subset=["date", "time", "merchant", "amount", "currency"])
    duplicates_dropped = before - len(df)
    if duplicates_dropped:
        warnings.append(f"{duplicates_dropped} exact duplicate row(s) removed.")

    currencies = sorted(df["currency"].unique())
    if len(currencies) > 1:
        warnings.append(
            "Multiple currencies detected (" + ", ".join(currencies) + "); "
            "totals are reported without FX conversion."
        )

    df["category"] = [
        categorize(m, c, a) for m, c, a in zip(df["merchant"], df["raw_category"], df["amount"])
    ]
    df = df.sort_values(["date", "time"], kind="stable").reset_index(drop=True)
    df.insert(0, "txn_id", [f"T{i + 1:03d}" for i in range(len(df))])
    df = df[INTERNAL_COLUMNS]

    return IngestResult(
        df=df,
        rows_in=rows_in,
        duplicates_dropped=duplicates_dropped,
        invalid_rows_dropped=invalid,
        warnings=warnings,
    )
