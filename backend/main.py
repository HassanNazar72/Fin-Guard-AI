"""FinGuard AI - FastAPI application.

Routes (all under ``/api`` so Vercel can route them to the Python function):

* ``GET  /api/health``  - liveness + whether live AI is configured
* ``GET  /api/quota``   - remaining live AI queries for the caller's IP
* ``POST /api/analyze`` - ingest + sanitise a statement, return KPIs/charts/flags
* ``POST /api/chat``    - answer a question via Gemini (live), the cache, or the
                          deterministic engine, always in the same JSON contract

The API is stateless: the browser keeps the CSV and re-sends it, the server
re-ingests it (<= 200 rows, a few ms) on every call. Nothing is persisted.
"""

from __future__ import annotations

import json
import logging
import re
import time
from functools import lru_cache
from typing import Any, Callable

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.agent import AgentError, FinGuardAgent, SchemaValidationError, get_client
from backend.config import ALLOWED_ORIGINS, CACHED_DEMOS_PATH, MAX_PROMPT_CHARS, MODEL_NAME
from backend.ingestor import IngestionError
from backend.insights import compose_report, route_intent
from backend.pipeline import PreparedStatement, load_sample_csv, prepare_statement
from backend.rate_limit import RateLimiter
from backend.schemas import (
    AnalyzeRequest,
    ChatRequest,
    ChatResponse,
    ChatStatus,
    ExecutionTrace,
    FinancialInsightReport,
    Mode,
    Quota,
    SecuritySummary,
    ToolTiming,
)
from backend.security import SecurityEvent, validate_user_prompt
from backend.tools import daily_cumulative_spend, monthly_category_spend

logger = logging.getLogger("finguard")
security_log = logging.getLogger("finguard.security")

app = FastAPI(
    title="FinGuard AI API",
    version="1.0.0",
    description="Autonomous financial statement analyst with a security-hardened Gemini agent.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next: Callable[..., Any]) -> Any:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(IngestionError)
async def ingestion_error_handler(_: Request, exc: IngestionError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# ------------------------------------------------------------- dependencies
_rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _rate_limiter


def get_llm_client() -> Any | None:
    return get_client()


def client_ip(request: Request) -> str:
    """Caller IP. On Vercel the edge sets ``x-forwarded-for``; its first hop is the client."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


# ------------------------------------------------------------------ helpers
def normalize_prompt_key(prompt: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", prompt.lower()).strip()


@lru_cache(maxsize=1)
def load_cached_demos() -> dict[str, Any]:
    try:
        return json.loads(CACHED_DEMOS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("cached_demos.json missing or unreadable; cache disabled")
        return {}


def cached_report(statement: PreparedStatement, prompt: str) -> FinancialInsightReport | None:
    if not statement.is_sample:
        return None
    demos = load_cached_demos()
    if demos.get("sample_fingerprint") != statement.fingerprint:
        return None
    entry = demos.get("responses", {}).get(normalize_prompt_key(prompt))
    return FinancialInsightReport.model_validate(entry["report"]) if entry else None


def resolve_statement(csv_text: str | None, use_sample: bool) -> PreparedStatement:
    if use_sample:
        return prepare_statement(load_sample_csv())
    if not csv_text or not csv_text.strip():
        raise HTTPException(status_code=400, detail="Provide csv_text or set use_sample=true.")
    return prepare_statement(csv_text)


def security_summary(
    statement: PreparedStatement, extra_events: list[SecurityEvent] | None = None, prompt_blocked: bool = False
) -> SecuritySummary:
    events = [e.to_dict() for e in statement.security.events]
    events += [e.to_dict() for e in extra_events or []]
    return SecuritySummary(
        pii_fields_scrubbed=statement.security.pii_fields_scrubbed,
        injections_blocked=statement.security.injections_blocked + (1 if prompt_blocked else 0),
        prompt_blocked=prompt_blocked,
        events=events,
    )


def transaction_flags(statement: PreparedStatement) -> dict[str, list[str]]:
    flags: dict[str, list[str]] = {}

    def add(txn_id: str, flag: str) -> None:
        flags.setdefault(txn_id, [])
        if flag not in flags[txn_id]:
            flags[txn_id].append(flag)

    for event in statement.security.events:
        if event.txn_id:
            add(event.txn_id, event.type)
    anomalies = statement.toolbox.detect_anomalies_and_duplicates()
    for dup in anomalies["duplicates"]:
        add(dup["first_txn_id"], "duplicate")
        add(dup["second_txn_id"], "duplicate")
    for out in anomalies["outliers"]:
        add(out["txn_id"], "outlier")
    subs = statement.toolbox.detect_subscription_creep()
    creeping = {item["merchant"] for item in subs["flagged_increases"]}
    df = statement.df
    for row in df[df["merchant"].isin(creeping)].itertuples():
        if row.date == df[df["merchant"] == row.merchant]["date"].max():
            add(row.txn_id, "price_increase")
    return flags


# ------------------------------------------------------------------- routes
@app.get("/api/health")
def health(client: Any = Depends(get_llm_client)) -> dict[str, Any]:
    return {"status": "ok", "model": MODEL_NAME, "live_ai_enabled": client is not None}


@app.get("/api/quota", response_model=Quota)
def quota(request: Request, limiter: RateLimiter = Depends(get_rate_limiter)) -> Quota:
    return Quota(remaining=limiter.remaining(client_ip(request)), limit=limiter.limit)


@app.post("/api/analyze")
def analyze(
    body: AnalyzeRequest,
    request: Request,
    limiter: RateLimiter = Depends(get_rate_limiter),
    client: Any = Depends(get_llm_client),
) -> dict[str, Any]:
    statement = resolve_statement(body.csv_text, body.use_sample)
    toolbox = statement.toolbox
    cashflow = toolbox.get_cashflow_summary()
    anomalies = toolbox.detect_anomalies_and_duplicates()
    subscriptions = toolbox.detect_subscription_creep()
    categories = toolbox.get_category_breakdown()
    flags = transaction_flags(statement)

    for event in statement.security.events:
        security_log.info("statement %s: %s (%s)", event.type, event.detail, event.txn_id)

    transactions = [
        {
            "txn_id": row.txn_id,
            "date": row.date,
            "time": row.time,
            "merchant": row.merchant,
            "amount": float(row.amount),
            "currency": row.currency,
            "category": row.category,
            "flags": flags.get(row.txn_id, []),
        }
        for row in statement.df.itertuples()
    ]
    return {
        "source": "sample" if statement.is_sample else "upload",
        "summary": {
            "rows_in": statement.ingest.rows_in,
            "rows_analyzed": len(statement.df),
            "duplicates_dropped": statement.ingest.duplicates_dropped,
            "invalid_rows_dropped": statement.ingest.invalid_rows_dropped,
            "warnings": statement.ingest.warnings,
            "period_start": cashflow["period_start"],
            "period_end": cashflow["period_end"],
            "currency": cashflow["currency"],
        },
        "kpis": {
            "total_income": cashflow["total_income"],
            "total_spend": cashflow["total_spend"],
            "net_cashflow": cashflow["net_cashflow"],
            "savings_rate_pct": cashflow["savings_rate_pct"],
            "anomalies_detected": anomalies["duplicate_count"]
            + anomalies["outlier_count"]
            + len(subscriptions["flagged_increases"]),
            "duplicates": anomalies["duplicate_count"],
            "outliers": anomalies["outlier_count"],
            "subscription_increases": len(subscriptions["flagged_increases"]),
        },
        "charts": {
            "monthly_category": monthly_category_spend(statement.df),
            "daily_cumulative": daily_cumulative_spend(statement.df),
        },
        "insights": {
            "subscriptions": subscriptions,
            "anomalies": anomalies,
            "categories": categories,
        },
        "transactions": transactions,
        "security": security_summary(statement).model_dump(),
        "quota": Quota(remaining=limiter.remaining(client_ip(request)), limit=limiter.limit).model_dump(),
        "live_ai_enabled": client is not None,
        "model": MODEL_NAME,
    }


def _fallback(
    statement: PreparedStatement, question: str
) -> tuple[FinancialInsightReport, list[ToolTiming]]:
    timings: list[ToolTiming] = []
    outputs: dict[str, dict[str, Any]] = {}
    for name in route_intent(question):
        started = time.perf_counter()
        outputs[name] = statement.toolbox.execute(name)
        timings.append(ToolTiming(name=name, duration_ms=round((time.perf_counter() - started) * 1000, 2)))
    return compose_report(question, outputs), timings


@app.post("/api/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    request: Request,
    client: Any = Depends(get_llm_client),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> ChatResponse:
    started = time.perf_counter()
    ip = client_ip(request)

    if len(body.prompt) > MAX_PROMPT_CHARS:
        raise HTTPException(
            status_code=400, detail=f"Prompt exceeds the {MAX_PROMPT_CHARS}-character limit."
        )
    statement = resolve_statement(body.csv_text, body.use_sample)

    def respond(
        report: FinancialInsightReport,
        mode: Mode,
        model: str,
        message: str | None = None,
        timings: list[ToolTiming] | None = None,
        llm_calls: int = 0,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        extra_events: list[SecurityEvent] | None = None,
        prompt_blocked: bool = False,
    ) -> ChatResponse:
        latency = round((time.perf_counter() - started) * 1000, 1)
        return ChatResponse(
            report=report,
            trace=ExecutionTrace(
                model=model,
                mode=mode,
                tools_called=report.tools_invoked,
                tool_timings=timings or [],
                confidence_score=report.confidence_score,
                schema_validated=True,
                latency_ms=latency,
                llm_calls=llm_calls,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
            status=ChatStatus(mode=mode, message=message),
            quota=Quota(remaining=limiter.remaining(ip), limit=limiter.limit),
            security=security_summary(statement, extra_events, prompt_blocked),
        )

    # 1) Prompt firewall.
    check = validate_user_prompt(body.prompt)
    if not check.ok:
        if not check.injection_patterns:
            raise HTTPException(status_code=400, detail=check.reason)
        event = SecurityEvent(
            type="prompt_rejected",
            detail="Blocked prompt injection in chat input (" + ", ".join(check.injection_patterns) + ")",
            field="prompt",
        )
        security_log.warning("prompt blocked from %s: %s", ip, ", ".join(check.injection_patterns))
        report = FinancialInsightReport(
            answer=(
                "This request was blocked by the FinGuard prompt-injection firewall. I can only "
                "analyse your statement - try asking about your spending, subscriptions or cash flow."
            ),
            tools_invoked=[],
            flagged_risks=["Prompt injection attempt detected in chat input"],
            confidence_score=1.0,
            requires_human_review=True,
        )
        return respond(
            report,
            "blocked",
            "security-firewall",
            message="Prompt blocked by the injection firewall - no AI call was made.",
            extra_events=[event],
            prompt_blocked=True,
        )
    question = check.cleaned

    # 2) Pre-cached answers for the sample statement's quick-action chips (no quota used).
    cached = cached_report(statement, question)
    if cached is not None:
        return respond(
            cached,
            "cached",
            f"{MODEL_NAME} (cached)",
            message="Served from the pre-computed demo cache - no live quota used.",
        )

    # 3) Live Gemini, guarded by the zero-bill rate limiter.
    if client is None:
        report, timings = _fallback(statement, question)
        return respond(
            report,
            "fallback",
            "deterministic-engine",
            message="Live AI is not configured on this server - showing deterministic Python insights.",
            timings=timings,
        )
    if not limiter.try_consume(ip):
        security_log.info("rate limit reached for %s", ip)
        report, timings = _fallback(statement, question)
        return respond(
            report,
            "fallback",
            "deterministic-engine",
            message=(
                f"Daily live AI limit reached ({limiter.limit}/{limiter.limit}). Showing deterministic "
                "Python insights; your quota refreshes on a rolling 24-hour window."
            ),
            timings=timings,
            extra_events=[SecurityEvent(type="rate_limited", detail="Live AI quota exhausted", field="ip")],
        )
    try:
        result = FinGuardAgent(client, statement.toolbox).run(question)
    except SchemaValidationError:
        logger.warning("Gemini output failed schema validation; using deterministic fallback")
        report, timings = _fallback(statement, question)
        return respond(
            report,
            "fallback",
            "deterministic-engine",
            message="The AI response failed schema validation, so a verified deterministic answer is shown.",
            timings=timings,
        )
    except AgentError as exc:
        logger.warning("Gemini unavailable: %s", exc)
        report, timings = _fallback(statement, question)
        return respond(
            report,
            "fallback",
            "deterministic-engine",
            message="Gemini is temporarily unavailable - showing deterministic Python insights.",
            timings=timings,
        )
    return respond(
        result.report,
        "live",
        MODEL_NAME,
        timings=result.tool_timings,
        llm_calls=result.llm_calls,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        message=f"{check.pii_scrubbed} PII field(s) in your prompt were redacted before the AI call."
        if check.pii_scrubbed
        else None,
    )
