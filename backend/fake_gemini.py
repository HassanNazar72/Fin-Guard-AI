"""Deterministic, offline stand-in for ``google.genai.Client``.

Used by the pytest suite and the offline eval harness. It speaks the same
interface as the real SDK (``client.models.generate_content(model=, contents=,
config=)``) and returns genuine ``google.genai.types.GenerateContentResponse``
objects, so the production agent code path runs unmodified with zero network
access and zero API keys.

Behaviour
---------
* Tool-selection turn (``config.tools`` set, no function responses yet):
  returns function calls chosen by ``route`` (defaults to the keyword router).
* Follow-up tool turn: returns a plain text turn with no calls (loop ends).
* Structured turn (``config.response_schema`` set): parses ``<question>`` and
  ``<tool_outputs>`` from the prompt and returns a ``FinancialInsightReport``
  JSON built by the deterministic composer, or ``final_text`` if overridden.

Every payload the "model" receives is recorded in ``received_text`` so tests
can assert that no raw PII or injected instructions ever reached it.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from google.genai import types

from backend.insights import compose_report, route_intent


def _text_response(text: str) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(content=types.Content(role="model", parts=[types.Part(text=text)]))
        ],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=120, candidates_token_count=max(1, len(text) // 4)
        ),
    )


def _function_call_response(names: list[str]) -> types.GenerateContentResponse:
    parts = [types.Part(function_call=types.FunctionCall(name=n, args={})) for n in names]
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=parts))],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=180, candidates_token_count=12 * len(names)
        ),
    )


def _serialize(contents: Any) -> str:
    if isinstance(contents, str):
        return contents
    if isinstance(contents, list):
        return "\n".join(_serialize(item) for item in contents)
    if hasattr(contents, "model_dump_json"):
        return contents.model_dump_json(exclude_none=True)
    return str(contents)


def _has_function_responses(contents: Any) -> bool:
    if not isinstance(contents, list):
        return False
    for content in contents:
        for part in getattr(content, "parts", None) or []:
            if getattr(part, "function_response", None) is not None:
                return True
    return False


def _first_user_text(contents: Any) -> str:
    if isinstance(contents, str):
        return contents
    for content in contents if isinstance(contents, list) else [contents]:
        for part in getattr(content, "parts", None) or []:
            if getattr(part, "text", None):
                return part.text
    return ""


def _parse_final_prompt(text: str) -> tuple[str, dict[str, dict[str, Any]]]:
    question = re.search(r"<question>\n(.*?)\n</question>", text, re.S)
    outputs = re.search(r"<tool_outputs>\n(.*?)\n</tool_outputs>", text, re.S)
    return (
        question.group(1) if question else "",
        json.loads(outputs.group(1)) if outputs else {},
    )


class _FakeModels:
    def __init__(self, owner: "FakeGeminiClient"):
        self._owner = owner

    def generate_content(self, *, model: str, contents: Any, config: Any = None) -> Any:
        owner = self._owner
        owner.calls.append({"model": model, "config": config, "contents": contents})
        owner.received_text += _serialize(contents) + "\n"
        if config is not None and getattr(config, "system_instruction", None):
            owner.received_text += str(config.system_instruction) + "\n"
        if owner.raise_error is not None:
            raise owner.raise_error

        if config is not None and getattr(config, "tools", None):
            if _has_function_responses(contents):
                return _text_response("Tool results received.")
            return _function_call_response(owner.route(_first_user_text(contents)))

        if config is not None and getattr(config, "response_schema", None) is not None:
            if owner.final_text is not None:
                return _text_response(owner.final_text)
            question, outputs = _parse_final_prompt(_serialize(contents))
            return _text_response(compose_report(question, outputs).model_dump_json())

        return _text_response("OK")


class FakeGeminiClient:
    """Drop-in replacement for ``genai.Client`` in tests and offline evals."""

    def __init__(
        self,
        route: Callable[[str], list[str]] = route_intent,
        final_text: str | None = None,
        raise_error: Exception | None = None,
    ):
        self.route = route
        self.final_text = final_text
        self.raise_error = raise_error
        self.calls: list[dict[str, Any]] = []
        self.received_text = ""
        self.models = _FakeModels(self)
