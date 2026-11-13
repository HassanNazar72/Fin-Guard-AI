"""Pydantic v2 contracts for the API and for the LLM's structured output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.config import MAX_CSV_CHARS


class FinancialInsightReport(BaseModel):
    """The ONLY shape the agent is allowed to answer in.

    Passed to Gemini as ``response_schema`` and re-validated server-side, so a
    malformed model response can never reach the UI.
    """

    answer: str = Field(
        description="Concise answer for the customer. Every number must come from a tool output."
    )
    tools_invoked: list[str] = Field(
        description="Names of the tools whose outputs were used to answer."
    )
    flagged_risks: list[str] = Field(
        description="Short risk statements, e.g. a duplicate charge or price increase. Empty if none."
    )
    confidence_score: float = Field(description="Confidence in the answer between 0.0 and 1.0.")
    requires_human_review: bool = Field(
        description="True if a charge may need disputing or the data is ambiguous."
    )

    @field_validator("confidence_score")
    @classmethod
    def _clamp_confidence(cls, value: float) -> float:
        return round(min(max(float(value), 0.0), 1.0), 2)

    @field_validator("answer")
    @classmethod
    def _non_empty_answer(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("answer must not be empty")
        return value.strip()


Mode = Literal["live", "cached", "fallback", "blocked"]


class AnalyzeRequest(BaseModel):
    csv_text: str | None = Field(default=None, max_length=MAX_CSV_CHARS)
    use_sample: bool = False


class ChatRequest(BaseModel):
    # Hard ceiling at the schema layer; the 250-char product limit is enforced
    # in the handler so the user gets a friendly message instead of a 422.
    prompt: str = Field(max_length=2_000)
    csv_text: str | None = Field(default=None, max_length=MAX_CSV_CHARS)
    use_sample: bool = False


class ToolTiming(BaseModel):
    name: str
    duration_ms: float


class ExecutionTrace(BaseModel):
    model: str
    mode: Mode
    tools_called: list[str]
    tool_timings: list[ToolTiming] = Field(default_factory=list)
    confidence_score: float
    schema_validated: bool
    latency_ms: float
    llm_calls: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None


class Quota(BaseModel):
    remaining: int
    limit: int


class ChatStatus(BaseModel):
    mode: Mode
    message: str | None = None


class SecuritySummary(BaseModel):
    pii_fields_scrubbed: int
    injections_blocked: int
    prompt_blocked: bool = False
    events: list[dict[str, str | None]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    report: FinancialInsightReport
    trace: ExecutionTrace
    status: ChatStatus
    quota: Quota
    security: SecuritySummary
