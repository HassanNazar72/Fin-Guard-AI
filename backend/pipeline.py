"""Statement pipeline: ingest -> security firewall -> deterministic toolbox.

Every API request goes through :func:`prepare_statement`, so there is exactly
one path by which statement data can reach the agent, and it is always
sanitised first.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd

from backend.config import SAMPLE_CSV_PATH
from backend.ingestor import IngestResult, ingest_csv
from backend.security import SanitizationReport, sanitize_dataframe
from backend.tools import FinancialToolbox


@dataclass
class PreparedStatement:
    df: pd.DataFrame
    ingest: IngestResult
    security: SanitizationReport
    toolbox: FinancialToolbox
    fingerprint: str
    is_sample: bool


@lru_cache(maxsize=1)
def load_sample_csv() -> str:
    return SAMPLE_CSV_PATH.read_text(encoding="utf-8")


def dataset_fingerprint(df: pd.DataFrame) -> str:
    """Content hash of the normalised statement.

    Hashing the *normalised* frame (rather than raw bytes) makes the fingerprint
    immune to line-ending and formatting differences, so the cached demo
    answers match the sample however it was checked out or re-uploaded.
    """
    canonical = df[["date", "time", "merchant", "amount", "currency"]].to_csv(
        index=False, float_format="%.2f", lineterminator="\n"
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def sample_fingerprint() -> str:
    return prepare_statement(load_sample_csv(), check_sample=False).fingerprint


def prepare_statement(csv_text: str, check_sample: bool = True) -> PreparedStatement:
    ingest = ingest_csv(csv_text)
    clean_df, security = sanitize_dataframe(ingest.df)
    fingerprint = dataset_fingerprint(clean_df)
    is_sample = check_sample and fingerprint == sample_fingerprint()
    return PreparedStatement(
        df=clean_df,
        ingest=ingest,
        security=security,
        toolbox=FinancialToolbox(clean_df),
        fingerprint=fingerprint,
        is_sample=is_sample,
    )
