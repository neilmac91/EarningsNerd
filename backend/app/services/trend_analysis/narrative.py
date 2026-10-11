"""Cached narrative streaming over code-owned financial observations.

Transport-agnostic narrative pipeline: yields plain event dicts for the SSE route.

Event contract (the Copilot shapes, so frontend consumers share plumbing):
  {"type": "progress", "stage", "message", "percent"}
  {"type": "token", "text"}                              (fresh generations only)
  {"type": "complete", "kind": "analysis" | "not_enough_data", "analysis_id", "narrative",
   "citations", "grounded", "cached", "n_periods", "usage", "narrative_presentation" (analysis only)}
  {"type": "error", "message"}

Cache-first (D4): if a row matches (company, mode, period_key) with the same prompt_version
AND dataset_fingerprint and current presentation, it is re-served with no model call or meter (the
router meters only non-cached "analysis" completions). ``force`` always regenerates.
Opens its own sessions: the request's session is gone by the time this generator runs.
"""
from __future__ import annotations

import json
from contextlib import closing
from typing import Any, Optional

from app.config import settings
from app.models import Company
from app.services.ai.copilot_chat import merge_chat_usage
from app.services.trend_analysis.cache import (
    logger, PROMPT_VERSION, _load_cached_analysis, _persist_analysis,
)
from app.services.trend_analysis.dataset import (
    build_dataset, dataset_fingerprint, _has_minimum_analysis_data, marker_index,
)
from app.services.trend_analysis.fidelity import scan_numeric_fidelity
from app.services.trend_analysis.observations import (
    ANALYSIS_SECTIONS, build_observation_catalogue, compact_observation_catalogue,
    parse_observation_selection,
)
from app.services.trend_analysis.presentation import (
    cached_analysis_completion, presentation_is_current, render_narrative_presentation,
)
from app.services.trend_analysis.stream_events import analysis_completion


class _NarrativeRun:
    company_id: int
    mode: str
    start_period: str
    end_period: str
    force: bool
    user_id: Optional[int]
    ticker: Any
    dataset: Any
    fingerprint: Any
    key: Any
    invalidated: Any
    catalogue: Any
    base_messages: Any
    index: Any
    model_name: Any
    total_usage: Any
    selection: Any
    assembled: bool

    def __init__(
        self, company_id: int, mode: str, start_period: str, end_period: str,
        force: bool, user_id: Optional[int],
    ) -> None:
        self.company_id = company_id
        self.mode = mode
        self.start_period = start_period
        self.end_period = end_period
        self.force = force
        self.user_id = user_id
        self.assembled = False


def _assemble(run: _NarrativeRun, SessionLocal: Any):
    db = SessionLocal()
    try:
        company = db.get(Company, run.company_id)
        if company is None:
            yield {"type": "error", "message": "Company not found."}
            return
        run.ticker = company.ticker
        try:
            run.dataset = build_dataset(db, company, run.mode, run.start_period, run.end_period)
        except ValueError as exc:
            yield {"type": "error", "message": str(exc)}
            return
        run.fingerprint = dataset_fingerprint(run.dataset)
        run.key = run.dataset["period_key"]
        cached = _load_cached_analysis(db, run.company_id, run.mode, run.key)
        if (
            not run.force
            and cached is not None
            and cached.narrative_md
            and cached.prompt_version == PROMPT_VERSION
            and cached.dataset_fingerprint == run.fingerprint
            and presentation_is_current(cached.dataset_json or {})
        ):
            yield cached_analysis_completion(run.dataset, cached)
            return
        # A saved row no longer matches (prompt, presentation or facts): this regeneration
        # is system-triggered, not user-triggered — the router exempts it from the fair-use meter.
        # A `force` refresh is user-initiated and stays metered.
        run.invalidated = cached is not None and not run.force
    finally:
        # Never hold a DB connection through the model call.
        db.close()

    run.assembled = True


def _selection_messages(run: _NarrativeRun, get_named_prompt: Any, openai_service: Any) -> None:
    prompt = get_named_prompt("trends-analyst-agent")
    run.catalogue = build_observation_catalogue(run.dataset)
    selection_shape = json.dumps({key: [] for key, _ in ANALYSIS_SECTIONS}, separators=(",", ":"))
    run.base_messages = [
        {"role": "system", "content": prompt.raw},
        {
            "role": "user",
            "content": (
                compact_observation_catalogue(run.catalogue)
                + "\n\nReturn exactly one JSON object with this shape and no other text:\n"
                + selection_shape
            ),
        },
    ]

    run.index = marker_index(run.dataset)
    run.model_name = openai_service.model
    run.total_usage: dict[str, Any] = {}
    run.selection: Optional[dict[str, list[str]]] = None


def _not_enough_data(run: _NarrativeRun) -> dict[str, Any]:
    return {
        "type": "complete",
        "kind": "not_enough_data",
        "analysis_id": None,
        "narrative": "",
        "citations": [],
        "grounded": 0,
        "unverified": 0,
        "cached": False,
        "invalidated": run.invalidated,
        "n_periods": len(run.dataset["periods"]),
        "usage": {},
    }


def _append_retry(messages: list[dict[str, Any]]) -> None:
    messages.append(
        {
            "role": "user",
            "content": (
                "The prior reply was rejected. Return only the complete JSON object with "
                "all six required keys. Every value must be a list of at most three IDs "
                "from that key's section; do not add prose, fields, or replacement text."
            ),
        }
    )


def _publish(run: _NarrativeRun):
    narrative, citations, grounded, unverified, presentation = render_narrative_presentation(
        run.dataset, run.catalogue, run.selection, run.index,
    )
    mismatched = scan_numeric_fidelity(narrative, citations, run.index)
    if unverified or mismatched:
        logger.error(
            "code-owned trend observations failed citation fidelity for %s (%s %s): "
            "unverified=%d mismatched=%s",
            run.ticker, run.mode, run.key, unverified, mismatched,
        )
        yield {"type": "error", "message": "The analysis could not be generated. Please try again."}
        return

    run.dataset = {**run.dataset, "narrative_presentation": presentation}
    # The sole token payload is emitted only after strict selection validation and code rendering.
    yield {"type": "token", "text": narrative}
    analysis_id = _persist_analysis(
        company_id=run.company_id,
        mode=run.mode,
        key=run.key,
        fingerprint=run.fingerprint,
        dataset=run.dataset,
        narrative=narrative,
        citations=citations,
        model=run.model_name,
        grounded=grounded,
        unverified=unverified,
        user_id=run.user_id,
    )
    yield analysis_completion(
        run.dataset, analysis_id=analysis_id, narrative=narrative, citations=citations,
        grounded=grounded, unverified=unverified, mismatched=len(mismatched),
        cached=False, invalidated=run.invalidated, usage=run.total_usage,
    )


async def stream_trend_narrative(
    *,
    company_id: int,
    mode: str,
    start_period: str,
    end_period: str,
    force: bool = False,
    user_id: Optional[int] = None,
):
    """Yield code-owned narrative events; see the module contract for cache semantics."""
    from app.database import SessionLocal
    from app.services.openai_service import STREAM_ERROR_SENTINEL, openai_service
    from app.services.prompt_loader import get_named_prompt

    run = _NarrativeRun(company_id, mode, start_period, end_period, force, user_id)
    yield {"type": "progress", "stage": "assembling", "message": "Assembling the numbers…", "percent": 10}
    with closing(_assemble(run, SessionLocal)) as events:
        for event in events:
            yield event
    if not run.assembled:
        return
    yield {"type": "progress", "stage": "writing", "message": "Writing the analysis…", "percent": 30}
    if not _has_minimum_analysis_data(run.dataset):
        yield _not_enough_data(run)
        return
    _selection_messages(run, get_named_prompt, openai_service)
    # The model may rank only catalogue IDs.  Its raw chunks are never user-visible.  One retry is
    # retained for malformed selection JSON; usage still sums every physical model call.
    for attempt in range(2):
        messages = list(run.base_messages)
        if attempt:
            _append_retry(messages)
            yield {
                "type": "progress",
                "stage": "verifying",
                "message": "Re-checking the selection…",
                "percent": 80,
            }

        usage_sink: dict[str, Any] = {}
        parts: list[str] = []
        stream_failed = False
        async for chunk in openai_service.stream_chat(
            messages, max_tokens=settings.ANALYSIS_MAX_TOKENS, temperature=0.2, usage_sink=usage_sink,
        ):
            if chunk.startswith(STREAM_ERROR_SENTINEL):
                detail = chunk[len(STREAM_ERROR_SENTINEL):]
                logger.warning("trend observation selection stream failed for %s: %s", run.ticker, detail)
                stream_failed = True
                break
            parts.append(chunk)
            if len(parts) % 40 == 0:
                yield {
                    "type": "progress",
                    "stage": "writing" if attempt == 0 else "verifying",
                    "message": "Selecting grounded observations…",
                    "percent": 60 if attempt == 0 else 85,
                }
        merge_chat_usage(run.total_usage, usage_sink)
        if stream_failed:
            yield {"type": "error", "message": "The analysis could not be generated. Please try again."}
            return

        candidate_text = "".join(parts).strip()
        run.selection = parse_observation_selection(candidate_text, run.catalogue)
        if run.selection is not None:
            break
    if run.selection is None:
        yield {"type": "error", "message": "The analysis could not be generated. Please try again."}
        return

    with closing(_publish(run)) as events:
        for event in events:
            yield event
