"""Regenerate ``backend/cached_demos.json`` for the sample statement.

The three quick-action chips in the UI are answered from this cache when the
sample statement is loaded, so the public demo spends zero Gemini quota on its
most common traffic.

    python -m scripts.build_cached_demos          # deterministic composer (offline)
    python -m scripts.build_cached_demos --live   # capture real Gemini answers

The cache is keyed to the sample's content fingerprint; if the sample CSV
changes, stale answers are ignored automatically until this script is re-run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agent import FinGuardAgent, get_client  # noqa: E402
from backend.config import CACHED_DEMOS_PATH, MODEL_NAME  # noqa: E402
from backend.insights import deterministic_answer  # noqa: E402
from backend.main import normalize_prompt_key  # noqa: E402
from backend.pipeline import load_sample_csv, prepare_statement  # noqa: E402

QUICK_PROMPTS = (
    "Audit my recurring subscriptions",
    "Check for duplicate or anomalous charges",
    "Summarize my cash flow & savings rate",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true", help="use the real Gemini API")
    args = parser.parse_args()

    statement = prepare_statement(load_sample_csv(), check_sample=False)
    client = get_client() if args.live else None
    if args.live and client is None:
        print("GEMINI_API_KEY is not set; cannot run --live.", file=sys.stderr)
        return 1

    responses = {}
    for prompt in QUICK_PROMPTS:
        if client is not None:
            report = FinGuardAgent(client, statement.toolbox).run(prompt).report
        else:
            report = deterministic_answer(prompt, statement.toolbox)
        responses[normalize_prompt_key(prompt)] = {"prompt": prompt, "report": report.model_dump()}
        print(f"cached: {prompt}")

    payload = {
        "description": "Pre-computed answers for the sample statement's quick-action prompts.",
        "model": MODEL_NAME,
        "generated_with": "gemini-live" if client is not None else "deterministic-composer",
        "sample_fingerprint": statement.fingerprint,
        "responses": responses,
    }
    CACHED_DEMOS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {CACHED_DEMOS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
