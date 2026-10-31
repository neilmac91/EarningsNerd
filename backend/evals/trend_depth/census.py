"""Diagnosis census of the CURRENT Multi-Period Analysis "AI trend analysis" section (2026-10).

Reproduces analyses through the production code path (``trend_analysis.narrative.stream_trend_narrative``
with ``force=True``, the production model at DeepSeek, the app's own ``openai_service``) against the
harness's local facts store, then classifies every sentence of every narrative two independent ways.
Nothing under ``backend/app`` is modified: three module attributes of ``trend_analysis.narrative`` are
wrapped in-process to record what the run used (dataset, catalogue, raw selection replies).

Usage (from ``backend/``; a private store avoids SQLite contention with other harness processes)::

    export TREND_DEPTH_STORE=$HOME/.cache/earningsnerd-trend-depth/census-store.sqlite
    python -m evals.trend_depth.census run [--tickers REGN,SNAP]   # paid: ~USD 0.0002 per DeepSeek call;
                                                                   # rewrites runs.jsonl (a subset run too)
    python -m evals.trend_depth.census classify                    # free: template kind -> class
    python -m evals.trend_depth.census label [--limit 3]           # paid: Claude CLI (subscription), cached
    python -m evals.trend_depth.census report                      # free: results.json + results.md

Outputs go to ``tasks/analysis-depth-2026-10/census/``: ``runs.jsonl`` (one row per run, failures
included), ``narratives/<TICKER>-<mode>.md``, ``sentences.jsonl`` (deterministic labels),
``llm_labels.jsonl`` (blind labels, one row per narrative; re-runs skip labelled narratives) and
``results.json`` / ``results.md``. The class definitions and the template -> class table are
``CLASS_BY_TEMPLATE`` below and the census README.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import re
import statistics
import tempfile
import time
from collections import Counter, defaultdict
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from evals.trend_depth import bootstrap  # noqa: F401 - must precede every app import
from evals.trend_depth.companies import PEERS, EvalCompany, census_companies

from app.config import settings  # noqa: E402
from app.services import ai_metrics  # noqa: E402
from app.services.llm_pricing import prices_for_model  # noqa: E402
from app.services.trend_analysis import narrative as narrative_module  # noqa: E402
from app.services.trend_analysis.cache import PROMPT_VERSION  # noqa: E402
from app.services.trend_analysis.narrative_display import (  # noqa: E402
    compact_narrative_text, currency_precision_plan,
)
from app.services.trend_analysis.observations import (  # noqa: E402
    ANALYSIS_SECTIONS, TrendObservation, render_observation_selection,
)
from app.services.trend_analysis.periods import available_periods  # noqa: E402
from app.utils.datetimes import iso_z, utcnow  # noqa: E402
from evals.judge import _BILLING_ENV, _kill_and_reap  # noqa: E402
from evals.scorers import parse_model_json  # noqa: E402

OUT = bootstrap.RECORDS / "census"
RUNS = OUT / "runs.jsonl"
SENTENCES = OUT / "sentences.jsonl"
LLM_LABELS = OUT / "llm_labels.jsonl"
NARRATIVES = OUT / "narratives"

TARGET_ANNUAL = 40
QUARTERLY_TICKERS: tuple[str, ...] = ("REGN", "SNAP", "JPM", "COST", "PGR")  # one per profile + a non-calendar FY
QUARTERLY_WINDOW = 12  # the UI's "Last 12" quarterly preset (coverage limit)
INGEST_CONCURRENCY = 3
LLM_MODEL = "sonnet"
LLM_BUDGET_USD = 6.0
LLM_TIMEOUT_SECONDS = 300

CLASSES: tuple[str, ...] = ("restated_figure", "derived_comparison", "causal_claim", "judgement")
SECTION_TITLES: dict[str, str] = dict(ANALYSIS_SECTIONS)
SECTION_BY_TITLE: dict[str, str] = {title: key for key, title in ANALYSIS_SECTIONS}
OPERANDS_PREFIX = " Source operands: "  # presentation._OPERANDS_PREFIX (the wire grammar)
FALLBACK_SENTENCE = "Not enough data is available for this section in the selected periods."

# Template (section.kind, or red_flags.signal.<detector>) -> (primary class, directive, missingness).
# Decisions: a growth rate, a pp change and a CAGR each relate two values (current/prior or the window's
# endpoints), so they are derived_comparison; a margin or ratio stated at one period is restated_figure
# unless the sentence also orders it against a threshold. A "Watch ..." sentence keeps the class of the
# figure it restates and carries the directive flag. A missing value is a statement about one point
# (restated_figure + missingness). "No trend flags detected" reports that every threshold test came back
# negative (derived_comparison). A red-flag operand tail ("Source operands: ...") lists stored values with
# no relation asserted (restated_figure); the web UI renders it as a figure list, not prose.
CLASS_BY_TEMPLATE: dict[str, tuple[str, bool, bool]] = {
    "trajectory.latest": ("restated_figure", False, False),
    "trajectory.first": ("restated_figure", False, False),
    "trajectory.cagr": ("derived_comparison", False, False),
    "growth_quality.growth": ("derived_comparison", False, False),
    "growth_quality.comparison": ("derived_comparison", False, False),
    "growth_quality.latest-eps": ("restated_figure", False, False),
    "growth_quality.selected-gap": ("restated_figure", False, True),
    "margins.latest": ("restated_figure", False, False),
    "margins.change": ("derived_comparison", False, False),
    "margins.selected-gap": ("restated_figure", False, True),
    "cash_balance_sheet.level-comparison": ("derived_comparison", False, False),
    "cash_balance_sheet.latest": ("restated_figure", False, False),
    "cash_balance_sheet.ratio-threshold": ("derived_comparison", False, False),
    "cash_balance_sheet.selected-gap": ("restated_figure", False, True),
    "red_flags.signal.growth-deceleration": ("derived_comparison", False, False),
    "red_flags.signal.margin-compression": ("derived_comparison", False, False),
    "red_flags.signal.fcf-ni-divergence": ("derived_comparison", False, False),
    "red_flags.signal.debt-build": ("derived_comparison", False, False),
    "red_flags.signal.liquidity-squeeze": ("derived_comparison", False, False),
    "red_flags.signal.operands": ("restated_figure", False, False),
    "red_flags.no-signals": ("derived_comparison", False, False),
    "watch_next.growth": ("derived_comparison", True, False),
    "watch_next.level": ("restated_figure", True, False),
    "watch_next.metric": ("restated_figure", True, False),
    "section.fallback": ("restated_figure", False, True),
}

# Quantities each template states, for the page-visibility test: "value" (a point's level), "yoy" (the
# stated period's change vs the prior year / year-ago quarter), "cagr" (the series' window CAGR), or
# "computed" (a figure only the detector computes, shown nowhere else on the page).
_VALUE_TEMPLATES = frozenset({
    "trajectory.latest", "trajectory.first", "growth_quality.latest-eps", "margins.latest",
    "cash_balance_sheet.latest", "cash_balance_sheet.ratio-threshold",
    "cash_balance_sheet.level-comparison", "watch_next.level", "watch_next.metric",
    "red_flags.signal.operands", "red_flags.signal.liquidity-squeeze",
})
_YOY_TEMPLATES = frozenset({
    "growth_quality.growth", "growth_quality.comparison", "margins.change", "watch_next.growth",
    "red_flags.signal.growth-deceleration",
})
_COMPUTED_TEMPLATES = frozenset({
    "red_flags.signal.margin-compression", "red_flags.signal.fcf-ni-divergence", "red_flags.signal.debt-build",
})

CAUSE_WORDS = re.compile(
    r"\b(because|due to|driven by|drove|driving|owing to|as a result|result(?:ed|s|ing)? (?:of|in|from)|"
    r"led to|lead(?:s|ing)? to|caus\w*|attributab\w*|thanks to|reflect\w*|on the back of|fuel(?:l)?ed|"
    r"boost\w*|weigh(?:ed|ing)|pressur\w*|offset by|amid|since|stemm\w*|contribut\w*|impact\w*|"
    r"explain\w*|why|so that|therefore|hence)\b",
    re.IGNORECASE,
)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_MARKERS = re.compile(r"\s*\[F?\d+\]")
_CITATION_NUMBER = re.compile(r"\[(\d+)\]")

LLM_RUBRIC = """You label sentences from an automatically generated multi-year financial trend analysis of one \
public company, as shown to a retail investor. Label every sentence on its own wording.

Choose exactly ONE primary class per sentence:
- restated_figure: states a single stored or calculated value for one point or period (a level, a margin, \
a ratio, a per-share amount), or a plain list of such values that asserts no relation between them. A sentence \
saying that a value is not available is also restated_figure.
- derived_comparison: relates two or more values: a growth rate or change between periods (percent or \
percentage points), a compound annual growth rate over a window, an above/below/equal ordering of two values, \
a comparison with a threshold, or a direction or sequence across several periods.
- causal_claim: asserts WHY something happened, or what caused, drove or explains it (a reason, driver or \
mechanism), with or without words like "because" or "driven by".
- judgement: evaluates or interprets rather than reports: good/bad, strong/weak, healthy/concerning, quality, \
risk, sustainability, outlook or forecast, or advice-like language.

If a sentence mixes classes, pick the highest one present in this order: causal_claim > judgement > \
derived_comparison > restated_figure. A sentence telling the reader what to watch gets the class of the content \
it states (plus the directive flag); it is judgement only if it also evaluates or forecasts.

Flags (true or false, independent of the class):
- directive: the sentence tells the reader what to watch, check or do next.
- missingness: the sentence says a value or a section's data is unavailable or insufficient.

Return exactly one JSON object and no other text:
{"labels": [{"i": 1, "class": "restated_figure", "directive": false, "missingness": false}]}
with one entry per numbered sentence, in the given order, using the given sentence numbers."""


# --- in-process probes (no app file changes) ---------------------------------------------------

_CAPTURE: ContextVar[Optional[dict[str, Any]]] = ContextVar("census_capture", default=None)


def _install_probes() -> None:
    """Wrap the narrative module's own references so each run records what it actually used."""
    if getattr(narrative_module, "_census_probes", False):
        return
    parse, catalogue, dataset = (
        narrative_module.parse_observation_selection,
        narrative_module.build_observation_catalogue,
        narrative_module.build_dataset,
    )

    def parse_probe(raw: str, items: list[TrendObservation]) -> Optional[dict[str, list[str]]]:
        result = parse(raw, items)
        capture = _CAPTURE.get()
        if capture is not None:
            capture["attempts"].append({
                "raw": raw, "valid": result is not None, "selection": result,
                "at_s": time.perf_counter() - capture["t0"],
            })
        return result

    def catalogue_probe(data: dict[str, Any]) -> list[TrendObservation]:
        result = catalogue(data)
        capture = _CAPTURE.get()
        if capture is not None:
            capture["catalogue"] = result
        return result

    def dataset_probe(*args: Any, **kwargs: Any) -> dict[str, Any]:
        result = dataset(*args, **kwargs)
        capture = _CAPTURE.get()
        if capture is not None:
            capture["dataset"] = result
        return result

    narrative_module.parse_observation_selection = parse_probe
    narrative_module.build_observation_catalogue = catalogue_probe
    narrative_module.build_dataset = dataset_probe
    narrative_module._census_probes = True


# --- helpers ------------------------------------------------------------------------------------

def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _run_key(row: dict[str, Any]) -> str:
    return f"{row['ticker']}-{row['mode']}"


def _percentile(values: list[float], pct: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct
    low, high = math.floor(rank), math.ceil(rank)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def _template_of(observation_id: str) -> str:
    section, kind, *parts = observation_id.split(".")
    if section == "red_flags" and kind == "signal":
        return f"red_flags.signal.{parts[0] if parts else 'signal'}"
    return f"{section}.{kind}"


def _ui_annual_window(company_id: int, cap: int = 10) -> Optional[tuple[str, str]]:
    """PeriodPicker.latestRange for annual mode: disabled years count toward the cap."""
    db = bootstrap.SessionLocal()
    try:
        options = available_periods(db, company_id)["annual"]
    finally:
        db.close()
    enabled = [index for index, option in enumerate(options) if option["has_core"]]
    if not enabled:
        return None
    end = enabled[-1]
    start = next(index for index in enabled if index >= max(0, end - cap + 1))
    return options[start]["key"], options[end]["key"]


def _ui_quarterly_window(company_id: int, cap: int = QUARTERLY_WINDOW) -> tuple[str, str]:
    """PeriodPicker.latestRange for quarterly mode (no quarter is disabled)."""
    db = bootstrap.SessionLocal()
    try:
        options = available_periods(db, company_id)["quarterly"]
    finally:
        db.close()
    if len(options) < 2:
        raise ValueError("fewer than two quarters")
    return options[max(0, len(options) - cap)]["key"], options[-1]["key"]


POINT_FIELDS: tuple[str, ...] = ("period", "value", "yoy", "qoq", "marker", "derived")


def _table_points(series: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(zip(POINT_FIELDS, row)) for row in series["points"]]


def _compact_table(dataset: dict[str, Any]) -> dict[str, Any]:
    """The dataset fields the page's KPI strip and metrics table render (no lineage); points as rows."""
    return {
        "point_fields": list(POINT_FIELDS),
        "period_key": dataset["period_key"],
        "periods": [period["key"] for period in dataset["periods"]],
        "series": [
            {
                "concept": series["concept"], "label": series["label"], "unit": series["unit"],
                "percent": series["percent"], "cagr": series.get("cagr"),
                "cagr_window": series.get("cagr_window"), "cagr_marker": series.get("cagr_marker"),
                "window_pp": series.get("window_pp"),
                "points": [[point.get(field) for field in POINT_FIELDS] for point in series["points"]],
            }
            for series in dataset["series"]
        ],
        "inflections": [
            {key: signal.get(key) for key in ("kind", "concepts", "periods", "markers", "detail")}
            for signal in dataset.get("inflections") or []
        ],
    }


def _rendered_order(
    catalogue: list[TrendObservation], selection: dict[str, list[str]]
) -> list[dict[str, Any]]:
    """The production renderer's own order, with each observation's origin."""
    order: list[TrendObservation] = []

    def record(item: TrendObservation) -> str:
        order.append(item)
        return item.markdown

    render_observation_selection(catalogue, selection, render_item=record)
    picked = {item_id for ids in selection.values() for item_id in ids}
    rendered = []
    for item in order:
        origin = "required" if item.required else "selected" if item.id in picked else "fallback"
        rendered.append({"id": item.id, "section": item.section, "origin": origin,
                         "also_selected": item.required and item.id in picked})
    return rendered


def _selection_stats(
    catalogue: list[TrendObservation], selection: Optional[dict[str, list[str]]]
) -> dict[str, Any]:
    if selection is None:
        return {}
    by_id = {item.id: item for item in catalogue}
    stats: dict[str, Any] = {"sections": {}}
    for section, _ in ANALYSIS_SECTIONS:
        ids = selection[section]
        optional_ids = [item_id for item_id in ids if not by_id[item_id].required]
        candidates = [item for item in catalogue if item.section == section and not item.required]
        stats["sections"][section] = {
            "picked": len(ids), "picked_required": len(ids) - len(optional_ids),
            "picked_optional": len(optional_ids), "optional_candidates": len(candidates),
        }
    sections = stats["sections"].values()
    stats["picked_total"] = sum(entry["picked"] for entry in sections)
    stats["picked_optional_total"] = sum(entry["picked_optional"] for entry in sections)
    stats["picked_required_total"] = sum(entry["picked_required"] for entry in sections)
    stats["optional_candidates_total"] = sum(entry["optional_candidates"] for entry in sections)
    stats["all_empty"] = stats["picked_total"] == 0
    stats["no_optional_picked"] = stats["picked_optional_total"] == 0
    return stats


def _cost(records: list[dict[str, Any]]) -> dict[str, Any]:
    """The production price formula (llm_pricing.estimate_call_cost_usd) off-peak and in the peak window."""
    offpeak = 0.0
    for record in records:
        usage = record["usage"]
        hit_price, miss_price, out_price = prices_for_model(record.get("actual_model") or record.get("requested_model"))
        hit, miss = usage.get("cache_hit_tokens"), usage.get("cache_miss_tokens")
        if hit is None and miss is None:
            hit, miss = 0, usage.get("prompt_tokens") or 0
        offpeak += ((hit or 0) * hit_price + (miss or 0) * miss_price
                    + (usage.get("completion_tokens") or 0) * out_price) / 1_000_000
    return {
        "logged_usd": [record.get("estimated_cost_usd") for record in records],
        "logged_peak": [record.get("peak") for record in records],
        "offpeak_usd": round(offpeak, 6),
        "peak_usd": round(offpeak * settings.AI_PEAK_PRICE_MULTIPLIER, 6),
    }


# --- step 1: reproduce analyses -----------------------------------------------------------------

@dataclass(frozen=True)
class RunSpec:
    company: EvalCompany
    mode: str
    substitute_for: Optional[str] = None


_INGESTS: dict[str, "asyncio.Future[int]"] = {}


async def _ingest(ticker: str) -> int:
    """One ingest per ticker per process: bootstrap.ingest is not safe to run twice concurrently."""
    if ticker not in _INGESTS:
        _INGESTS[ticker] = asyncio.ensure_future(_ingest_uncached(ticker))
    return await _INGESTS[ticker]


async def _ingest_uncached(ticker: str) -> int:
    for attempt in range(2):
        try:
            return await bootstrap.ingest(ticker)
        except json.JSONDecodeError:
            # A shared raw-response cache file may be mid-write by another harness process.
            if attempt:
                raise
            await asyncio.sleep(3)
    raise AssertionError("unreachable")


async def _prepare(spec: RunSpec, gate: asyncio.Semaphore) -> dict[str, Any]:
    """Ingest and resolve the window; returns the row prefix (status ``failed`` on any refusal)."""
    company = spec.company
    row: dict[str, Any] = {
        "ticker": company.ticker, "mode": spec.mode, "sector": company.sector, "profile": company.profile,
        "split": company.split, "peer_group": company.peer_group, "substitute_for": spec.substitute_for,
        "prompt_version": PROMPT_VERSION, "model": bootstrap.PRODUCTION_MODEL,
    }
    async with gate:
        started = time.perf_counter()
        try:
            row["company_id"] = await _ingest(company.ticker)
        except Exception as exc:  # noqa: BLE001 - a census records every refusal and continues
            row.update(status="failed", failure_stage="ingest", failure_reason=f"{type(exc).__name__}: {exc}"[:300])
            return row
        row["ingest_s"] = round(time.perf_counter() - started, 2)
    identity = bootstrap.read_cached(f"identity/{company.ticker}.json") or {}
    row.update(cik=identity.get("cik"), company_name=identity.get("name"), sic=identity.get("sic"))
    try:
        if spec.mode == "annual":
            # The UI's "Last 10" (PeriodPicker.latestRange). bootstrap.latest_annual_window takes the
            # newest ten core years, which can span more than ten fiscal years when a year lacks core
            # data, and build_dataset refuses such a range (NEE, DUK in the first pass).
            try:
                row["bootstrap_window"] = list(bootstrap.latest_annual_window(row["company_id"]))
            except ValueError as exc:
                row["bootstrap_window"] = str(exc)
            ui = _ui_annual_window(row["company_id"])
            if ui is None:
                raise ValueError("no fiscal year with core data (top line and net income)")
            start, end = ui
            row["window_matches_bootstrap"] = row["bootstrap_window"] == [start, end]
        else:
            start, end = _ui_quarterly_window(row["company_id"])
    except ValueError as exc:
        row.update(status="failed", failure_stage="window", failure_reason=str(exc))
        return row
    row["window"] = [start, end]
    return row


async def _stream(row: dict[str, Any]) -> dict[str, Any]:
    """One production narrative generation, timed; fills the rest of the row."""
    capture: dict[str, Any] = {"attempts": [], "catalogue": None, "dataset": None, "t0": time.perf_counter()}
    token = _CAPTURE.set(capture)
    records, observer = ai_metrics.observe_ai_calls()
    marks: dict[str, float] = {}
    progress: Counter = Counter()
    complete: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    started_at = iso_z(utcnow())
    try:
        async for event in narrative_module.stream_trend_narrative(
            company_id=row["company_id"], mode=row["mode"], start_period=row["window"][0],
            end_period=row["window"][1], force=True,
        ):
            now = time.perf_counter() - capture["t0"]
            if event["type"] == "progress":
                progress[f"{event['stage']}:{event['percent']}"] += 1
                if event["stage"] == "writing" and "writing" not in marks:
                    marks["writing"] = now
            elif event["type"] == "token":
                marks["token"] = now
            elif event["type"] == "complete":
                marks["complete"] = now
                complete = event
            elif event["type"] == "error":
                marks["error"] = now
                error = event["message"]
    finally:
        ai_metrics.stop_observing(observer)
        _CAPTURE.reset(token)
    total_s = time.perf_counter() - capture["t0"]

    catalogue: list[TrendObservation] = capture["catalogue"] or []
    attempts = capture["attempts"]
    selection = attempts[-1]["selection"] if attempts else None
    provider_ms = [record.get("latency_ms") for record in records]
    row.update(
        started_at=started_at,
        status="ok" if complete is not None and complete.get("kind") == "analysis" else "failed",
        timings={
            "total_s": round(total_s, 3),
            "assemble_s": round(marks.get("writing", total_s), 3),
            "model_wall_s": round(attempts[-1]["at_s"] - marks["writing"], 3) if attempts and "writing" in marks else None,
            "publish_s": round(marks["complete"] - attempts[-1]["at_s"], 3) if attempts and "complete" in marks else None,
            "provider_ms": provider_ms,
            "provider_total_ms": sum(ms for ms in provider_ms if ms is not None) if provider_ms else None,
            "first_token_ms": records[0].get("first_token_ms") if records else None,
        },
        progress=dict(progress),
        ai_calls=records,
        cost=_cost(records),
        attempts=[{"raw": attempt["raw"], "valid": attempt["valid"]} for attempt in attempts],
        retries=max(0, len(attempts) - 1),
        selection=selection,
        selection_stats=_selection_stats(catalogue, selection),
        catalogue=[{"id": item.id, "section": item.section, "required": item.required, "markdown": item.markdown}
                   for item in catalogue],
        rendered=_rendered_order(catalogue, selection) if selection is not None else None,
        table=_compact_table(capture["dataset"]) if capture["dataset"] else None,
        complete=complete,
    )
    if row["status"] != "ok":
        row["failure_stage"] = "stream"
        row["failure_reason"] = error or (complete or {}).get("kind") or "no completion"
    return row


async def _stream_safely(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("status") == "failed":
        return row
    try:
        return await _stream(row)
    except Exception as exc:  # noqa: BLE001 - a census records every refusal and continues
        row.update(status="failed", failure_stage="stream", failure_reason=f"{type(exc).__name__}: {exc}"[:300])
        return row


def _write_narrative(row: dict[str, Any]) -> None:
    complete = row["complete"]
    lines = [
        f"# {row['ticker']} — {row['mode']} ({complete and row['table']['period_key']})",
        "",
        f"Reproduced {row['started_at']} through `stream_trend_narrative(force=True)` at prompt "
        f"`{row['prompt_version']}`, model `{row['model']}` (served: "
        f"{', '.join(str(record.get('actual_model')) for record in row['ai_calls'])}); local facts store "
        "built from live SEC companyfacts. Not a production `trend_analyses` row.",
        "",
        complete["narrative"],
        "",
        "## Sources",
        "",
    ]
    for citation in complete["citations"]:
        lines.append(
            f"[{citation['n']}] {citation['excerpt']} — {citation['section_ref']}"
            + (f" — {citation['source_url']}" if citation.get("source_url") else "")
        )
    NARRATIVES.mkdir(parents=True, exist_ok=True)
    (NARRATIVES / f"{_run_key(row)}.md").write_text("\n".join(lines) + "\n")


def _strip(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "company_id"}


async def run_census(tickers: Optional[set[str]]) -> None:
    _install_probes()
    logging.getLogger().setLevel(logging.WARNING)
    token = ai_metrics.set_trigger("eval")
    OUT.mkdir(parents=True, exist_ok=True)
    companies = [company for company in census_companies() if tickers is None or company.ticker in tickers]
    specs = [RunSpec(company, "annual") for company in companies]
    specs += [RunSpec(company, "quarterly") for company in companies if company.ticker in QUARTERLY_TICKERS]
    rows: list[dict[str, Any]] = []
    gate = asyncio.Semaphore(INGEST_CONCURRENCY)
    try:
        prepared = await asyncio.gather(*(_prepare(spec, gate) for spec in specs))
        # Streams run one at a time so each latency is the request's own (no other run's synchronous
        # dataset assembly or ingest blocking the event loop mid-stream).
        for row in prepared:
            rows.append(await _stream_safely(row))
            print(f"{_run_key(row)}: {rows[-1]['status']} {rows[-1].get('failure_reason') or ''}", flush=True)
        if tickers is None:
            rows += await _substitute(rows, gate)
            rows += await _substitute_quarterly(rows)
    finally:
        ai_metrics.reset_trigger(token)
    with RUNS.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(_strip(row), default=str) + "\n")
    for row in rows:
        if row["status"] == "ok":
            _write_narrative(row)
    ok = sum(1 for row in rows if row["status"] == "ok" and row["mode"] == "annual")
    print(f"annual successes: {ok}; rows: {len(rows)}")


async def _substitute(rows: list[dict[str, Any]], gate: asyncio.Semaphore) -> list[dict[str, Any]]:
    """Replace failed annual census companies with same-peer-group companies until 40 succeed."""
    used = {row["ticker"] for row in rows}
    added: list[dict[str, Any]] = []
    failed = [row for row in rows if row["mode"] == "annual" and row["status"] != "ok"]
    for failure in failed:
        if sum(1 for row in rows + added if row["mode"] == "annual" and row["status"] == "ok") >= TARGET_ANNUAL:
            break
        for ticker in PEERS.get(failure["peer_group"], ()):
            if ticker in used:
                continue
            used.add(ticker)
            company = EvalCompany(ticker, failure["sector"], "substitute", failure["profile"], failure["peer_group"])
            row = await _stream_safely(
                await _prepare(RunSpec(company, "annual", substitute_for=failure["ticker"]), gate)
            )
            added.append(row)
            print(f"substitute {ticker} for {failure['ticker']}: {row['status']}", flush=True)
            if row["status"] == "ok":
                break
    return added


async def _substitute_quarterly(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace a failed quarterly company with a same-peer-group company that has an annual run."""
    added: list[dict[str, Any]] = []
    annual_ok = {row["ticker"]: row for row in rows if row["mode"] == "annual" and row["status"] == "ok"}
    quarterly = {row["ticker"] for row in rows if row["mode"] == "quarterly"}
    for failure in [row for row in rows if row["mode"] == "quarterly" and row["status"] != "ok"]:
        for ticker in PEERS.get(failure["peer_group"], ()):
            if ticker in quarterly or ticker not in annual_ok:
                continue
            quarterly.add(ticker)
            source = annual_ok[ticker]
            company = EvalCompany(ticker, source["sector"], source["split"], source["profile"], source["peer_group"])
            row = await _stream_safely(
                await _prepare(RunSpec(company, "quarterly", substitute_for=failure["ticker"]), asyncio.Semaphore(1))
            )
            added.append(row)
            print(f"quarterly substitute {ticker} for {failure['ticker']}: {row['status']}", flush=True)
            if row["status"] == "ok":
                break
    return added


# --- step 3a: deterministic classification -------------------------------------------------------

def _display_texts(row: dict[str, Any]) -> dict[str, str]:
    """Each catalogue observation as the production presentation displays it (markers kept as [F#])."""
    catalogue = [TrendObservation(item["id"], item["section"], item["markdown"], item["required"])
                 for item in row["catalogue"]]
    precision = currency_precision_plan(render_observation_selection(catalogue, row["selection"]))
    displays: dict[str, str] = {}
    for item in catalogue:
        lead, separator, tail = item.markdown.partition(OPERANDS_PREFIX)
        if item.section == "red_flags" and separator:
            displays[item.id] = compact_narrative_text(lead, precision) + separator + tail
        else:
            displays[item.id] = compact_narrative_text(item.markdown, precision)
    return displays


def _strip_markers(text: str) -> str:
    return re.sub(r"\s+", " ", _MARKERS.sub("", text)).strip()


def _narrative_lines(narrative: str) -> list[tuple[str, str]]:
    section = ""
    lines: list[tuple[str, str]] = []
    for line in narrative.splitlines():
        if line.startswith("## "):
            section = SECTION_BY_TITLE[line[3:].strip()]
        elif line.strip():
            lines.append((section, line.strip()))
    return lines


def _split_sentences(line: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_SPLIT.split(line) if part.strip()]


def _visibility(
    template: str, mode: str, table: dict[str, Any], markers: list[str], signal: Optional[dict[str, Any]],
) -> dict[str, Optional[bool]]:
    """Whether every figure the sentence states is shown by the metrics table / the KPI strip.

    Metrics table: every series x period value, the change under it (YoY in annual mode; QoQ in
    quarterly mode wherever a QoQ exists, else YoY) and, annual only, the CAGR column for non-percent
    series. KPI strip: the latest valued point of the top line, net income, free cash flow and net
    margin, with CAGR (annual, non-percent), window pp (annual, percent) or YoY (quarterly).
    ``None`` = the sentence states no figure.
    """
    points: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    cagr: dict[str, dict[str, Any]] = {}
    for series in table["series"]:
        series = {**series, "points": _table_points(series)}
        for point in series["points"]:
            if point.get("marker"):
                points[point["marker"]] = (series, point)
        if series.get("cagr_marker"):
            cagr[series["cagr_marker"]] = series
    concepts = {series["concept"] for series in table["series"]}
    top = "revenue" if "revenue" in concepts else "net_interest_income"
    headline = {top, "net_income", "free_cash_flow", "net_margin"}

    def latest(series: dict[str, Any], point: dict[str, Any]) -> bool:
        valued = [candidate for candidate in series["points"] if candidate["value"] is not None]
        return bool(valued) and valued[-1]["period"] == point["period"]

    def value_visible(marker: str) -> tuple[bool, bool]:
        series, point = points[marker]
        return True, series["concept"] in headline and latest(series, point)

    def yoy_visible(marker: str) -> tuple[bool, bool]:
        series, point = points[marker]
        in_table = point.get("yoy") is not None and (mode == "annual" or point.get("qoq") is None)
        in_kpi = mode == "quarterly" and series["concept"] in headline and latest(series, point)
        return in_table, in_kpi

    if template in _COMPUTED_TEMPLATES:
        return {"table": False, "kpi": False}
    checks: list[tuple[bool, bool]] = []
    if template == "trajectory.cagr":
        for marker in markers:
            series = cagr[marker]
            checks.append((mode == "annual" and not series["percent"],
                           mode == "annual" and series["concept"] in headline and not series["percent"]))
    elif template in _VALUE_TEMPLATES:
        checks = [value_visible(marker) for marker in markers if marker in points]
    elif template in _YOY_TEMPLATES:
        current: list[str] = []
        if signal is not None:
            periods = set(signal["periods"])
            current = [marker for marker in markers if marker in points and points[marker][1]["period"] in periods]
        else:
            # Growth operands are cited as [current][prior]; the current point carries the stated change.
            by_concept: dict[str, list[str]] = defaultdict(list)
            for marker in markers:
                if marker in points:
                    by_concept[points[marker][0]["concept"]].append(marker)
            current = [group[0] for group in by_concept.values()]
        checks = [yoy_visible(marker) for marker in current]
    if not checks:
        return {"table": None, "kpi": None}
    return {"table": all(check[0] for check in checks), "kpi": all(check[1] for check in checks)}


def classify_runs() -> dict[str, Any]:
    rows = [row for row in _jsonl(RUNS) if row["status"] == "ok"]
    out: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for row in rows:
        displays = _display_texts(row)
        rendered = row["rendered"]
        lines = _narrative_lines(row["complete"]["narrative"])
        by_number = {citation["n"]: citation for citation in row["complete"]["citations"]}
        signals = {str(position): signal for position, signal in enumerate(row["table"]["inflections"], start=1)}
        cursor = 0
        for line_index, (section, line) in enumerate(lines):
            observation: Optional[dict[str, Any]] = None
            if line == FALLBACK_SENTENCE:
                template, matched = "section.fallback", True
            else:
                observation = rendered[cursor] if cursor < len(rendered) else None
                cursor += 1
                matched = observation is not None and (
                    _strip_markers(displays[observation["id"]]) == _strip_markers(line)
                )
                if not matched:
                    candidates = [item_id for item_id, text in displays.items()
                                  if _strip_markers(text) == _strip_markers(line)]
                    observation = next((item for item in rendered if item["id"] in candidates), None)
                    matched = observation is not None
                template = _template_of(observation["id"]) if observation else "unmatched"
            if not matched:
                mismatches.append({"run": _run_key(row), "line": line})
            line_markers = [by_number[int(n)]["marker"] for n in _CITATION_NUMBER.findall(line) if int(n) in by_number]
            signal = None
            if template.startswith("red_flags.signal.") and observation:
                signal = signals.get(observation["id"].split(".")[-1])
            for sentence_index, sentence in enumerate(_split_sentences(line)):
                sentence_template = template
                if template.startswith("red_flags.signal.") and sentence.startswith("Source operands:"):
                    sentence_template = "red_flags.signal.operands"
                klass, directive, missing = CLASS_BY_TEMPLATE.get(sentence_template, ("unmatched", False, False))
                sentence_markers = [by_number[int(n)]["marker"] for n in _CITATION_NUMBER.findall(sentence)
                                    if int(n) in by_number] or line_markers
                cause = sorted({match.group(0).lower() for match in CAUSE_WORDS.finditer(_strip_markers(sentence))})
                concepts = sorted({by_number[int(n)]["concept"] for n in _CITATION_NUMBER.findall(sentence)
                                   if int(n) in by_number})
                out.append({
                    "run": _run_key(row), "ticker": row["ticker"], "mode": row["mode"], "profile": row["profile"],
                    "sector": row["sector"], "section": section, "line": line_index, "sentence": sentence_index,
                    "text": sentence, "text_plain": _strip_markers(sentence),
                    "observation_id": observation["id"] if observation else None,
                    "origin": observation["origin"] if observation else "fallback",
                    "template": sentence_template, "matched": matched, "det_class": klass,
                    "directive": directive, "missingness": missing,
                    "text_directive": sentence.startswith("Watch "),
                    "text_missingness": "not available" in sentence or "Not enough data" in sentence,
                    "cause_words": cause, "concepts": concepts,
                    "visible": _visibility(sentence_template, row["mode"], row["table"], sentence_markers, signal),
                })
    with SENTENCES.open("w") as handle:
        for item in out:
            handle.write(json.dumps(item) + "\n")
    summary = {"runs": len(rows), "sentences": len(out), "unmatched_lines": mismatches}
    print(json.dumps({key: value if key != "unmatched_lines" else len(value) for key, value in summary.items()}))
    return summary


# --- step 3b: blind LLM labels via the Claude CLI ------------------------------------------------

def _llm_input(sentences: list[dict[str, Any]]) -> str:
    lines = ["Sentences of one analysis, in reading order (section heading in brackets):"]
    lines += [f"{index}. [{SECTION_TITLES[item['section']]}] {item['text_plain']}"
              for index, item in enumerate(sentences, start=1)]
    return "\n".join(lines)


def _parse_labels(raw: str, count: int) -> Optional[list[dict[str, Any]]]:
    payload, _repaired = parse_model_json(raw)
    labels = payload.get("labels") if isinstance(payload, dict) else None
    if not isinstance(labels, list) or len(labels) != count:
        return None
    parsed = []
    for index, label in enumerate(labels, start=1):
        if (not isinstance(label, dict) or label.get("i") != index or label.get("class") not in CLASSES
                or not isinstance(label.get("directive"), bool) or not isinstance(label.get("missingness"), bool)):
            return None
        parsed.append({"class": label["class"], "directive": label["directive"], "missingness": label["missingness"]})
    return parsed


async def _cli_call(system: str, user: str) -> dict[str, Any]:
    """The repo judge's subscription CLI invocation (evals/judge.py::_judge_via_cli)."""
    child_env = {key: value for key, value in os.environ.items() if key not in _BILLING_ENV}
    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", "--model", LLM_MODEL, "--output-format", "json",
        "--system-prompt", system, "--tools", "", "--strict-mcp-config", "--no-session-persistence",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        env=child_env, cwd=tempfile.gettempdir(),
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(user.encode("utf-8")), timeout=LLM_TIMEOUT_SECONDS)
    except BaseException:
        await _kill_and_reap(proc)
        raise
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI exit {proc.returncode}: {err.decode('utf-8', 'replace')[:300]}")
    outer = json.loads(out.decode("utf-8"))
    if outer.get("is_error") or outer.get("subtype") not in (None, "success"):
        raise RuntimeError(f"claude CLI error result: {str(outer)[:300]}")
    return outer


def _labels_current(row: dict[str, Any], items: list[dict[str, Any]]) -> bool:
    """A cached label row counts only for the exact sentences it labelled (a re-run may change them)."""
    return bool(row.get("labels")) and row.get("sentences") == [item["text_plain"] for item in items]


async def _label_run(run: str, sentences: list[dict[str, Any]]) -> dict[str, Any]:
    user = _llm_input(sentences)
    cost = 0.0
    calls: list[dict[str, Any]] = []
    labels = None
    for _attempt in range(2):
        outer = await _cli_call(LLM_RUBRIC, user)
        cost += float(outer.get("total_cost_usd") or 0.0)
        calls.append({"cost_usd": outer.get("total_cost_usd"), "duration_ms": outer.get("duration_ms"),
                      "models": sorted((outer.get("modelUsage") or {}).keys()), "usage": outer.get("usage")})
        labels = _parse_labels(str(outer.get("result", "")), len(sentences))
        if labels is not None:
            break
    return {"run": run, "n_sentences": len(sentences), "labels": labels, "cost_usd": round(cost, 6),
            "calls": calls, "model_alias": LLM_MODEL, "sentences": [item["text_plain"] for item in sentences]}


async def label_runs(limit: Optional[int]) -> None:
    sentences = _jsonl(SENTENCES)
    by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in sentences:
        by_run[item["run"]].append(item)
    done = {row["run"]: row for row in _jsonl(LLM_LABELS) if _labels_current(row, by_run.get(row["run"], []))}
    todo = [run for run in by_run if run not in done]
    if limit is not None:
        todo = todo[:limit]
    spent = sum(row["cost_usd"] for row in done.values())
    gate = asyncio.Semaphore(3)

    async def one(run: str) -> dict[str, Any]:
        async with gate:
            return await _label_run(run, by_run[run])

    measured = list(done.values())
    with LLM_LABELS.open("a") as handle:
        # The first three run alone so the extrapolated total is known before the rest are sent.
        head, tail = todo[:max(0, 3 - len(measured))], todo[max(0, 3 - len(measured)):]
        for run in head:
            result = await one(run)
            handle.write(json.dumps(result) + "\n")
            handle.flush()
            measured.append(result)
            spent += result["cost_usd"]
            print(f"{run}: labels={'ok' if result['labels'] else 'FAILED'} cost=${result['cost_usd']:.4f}", flush=True)
        if tail:
            mean = statistics.mean(row["cost_usd"] for row in measured)
            projected = spent + mean * len(tail)
            print(f"mean ${mean:.4f}/narrative; projected total ${projected:.2f} for {len(by_run)} narratives", flush=True)
            if projected > LLM_BUDGET_USD * 0.9:
                print("projected spend exceeds the budget; stopping before the remaining narratives")
                return
            for result in await asyncio.gather(*(one(run) for run in tail)):
                handle.write(json.dumps(result) + "\n")
                spent += result["cost_usd"]
                print(f"{result['run']}: labels={'ok' if result['labels'] else 'FAILED'} "
                      f"cost=${result['cost_usd']:.4f}", flush=True)
    print(f"total Claude CLI cost so far: ${spent:.4f}")


# --- step 3c/4: report --------------------------------------------------------------------------

def _kappa(first: list[str], second: list[str]) -> Optional[float]:
    if not first or len(first) != len(second):
        return None
    total = len(first)
    observed = sum(1 for a, b in zip(first, second) if a == b) / total
    left, right = Counter(first), Counter(second)
    expected = sum(left[key] * right[key] for key in set(left) | set(right)) / (total * total)
    return None if expected == 1 else round((observed - expected) / (1 - expected), 4)


def _shares(items: Iterable[dict[str, Any]], key: str) -> dict[str, Any]:
    items = list(items)
    counts = Counter(item[key] for item in items)
    total = len(items)
    return {"n": total, **{klass: {"count": counts.get(klass, 0),
                                   "share": round(counts.get(klass, 0) / total, 4) if total else None}
                           for klass in CLASSES}}


def _mean(values: list[float]) -> Optional[float]:
    return round(statistics.mean(values), 4) if values else None


def build_report() -> dict[str, Any]:
    runs = _jsonl(RUNS)
    sentences = _jsonl(SENTENCES)
    by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in sentences:
        by_run[item["run"]].append(item)
    llm_rows = {row["run"]: row for row in _jsonl(LLM_LABELS) if _labels_current(row, by_run.get(row["run"], []))}
    for run, row in llm_rows.items():
        for item, label in zip(by_run[run], row["labels"]):
            item["llm_class"], item["llm_directive"], item["llm_missingness"] = (
                label["class"], label["directive"], label["missingness"])
    ok = [row for row in runs if row["status"] == "ok"]
    annual_runs = [row for row in ok if row["mode"] == "annual"]
    annual = [item for item in sentences if item["mode"] == "annual"]
    labelled = [item for item in sentences if "llm_class" in item]
    labelled_annual = [item for item in labelled if item["mode"] == "annual"]

    def class_tables(items: list[dict[str, Any]]) -> dict[str, Any]:
        result = {"deterministic": _shares(items, "det_class")}
        with_llm = [item for item in items if "llm_class" in item]
        if with_llm:
            result["llm"] = _shares(with_llm, "llm_class")
        result["directive"] = sum(item["directive"] for item in items)
        result["missingness"] = sum(item["missingness"] for item in items)
        return result

    def grouped(items: list[dict[str, Any]], key: str) -> dict[str, Any]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            groups[item[key]].append(item)
        return {name: class_tables(group) for name, group in groups.items()}

    no_tail = [item for item in annual if item["template"] != "red_flags.signal.operands"]
    numeric = [item for item in annual if item["visible"]["table"] is not None]
    per_run_sentences = Counter(item["run"] for item in annual)
    per_run_concepts: dict[str, set[str]] = defaultdict(set)
    for item in annual:
        per_run_concepts[item["run"]].update(item["concepts"])
        if item["missingness"] and item["observation_id"]:
            per_run_concepts[item["run"]].add(item["observation_id"].split(".")[2].replace("-", "_"))

    def latency(rows: list[dict[str, Any]]) -> dict[str, Any]:
        def dist(values: list[float]) -> dict[str, Optional[float]]:
            values = [value for value in values if value is not None]
            return {"n": len(values), "p50": _percentile(values, 0.5), "p90": _percentile(values, 0.9),
                    "mean": _mean(values), "max": max(values) if values else None}
        return {
            "total_s": dist([row["timings"]["total_s"] for row in rows]),
            "assemble_s": dist([row["timings"]["assemble_s"] for row in rows]),
            "model_wall_s": dist([row["timings"]["model_wall_s"] for row in rows]),
            "provider_total_ms": dist([row["timings"]["provider_total_ms"] for row in rows]),
            "first_token_ms": dist([row["timings"]["first_token_ms"] for row in rows]),
        }

    def tokens(rows: list[dict[str, Any]]) -> dict[str, Any]:
        def field(name: str) -> list[float]:
            return [row["complete"]["usage"].get(name) for row in rows if row["complete"]["usage"].get(name) is not None]
        return {
            name: {"mean": _mean(field(name)), "min": min(field(name), default=None), "max": max(field(name), default=None)}
            for name in ("prompt_tokens", "completion_tokens", "cache_hit_tokens", "cache_miss_tokens", "estimated_cost_usd")
        } | {
            "offpeak_usd": {"mean": _mean([row["cost"]["offpeak_usd"] for row in rows]),
                            "total": round(sum(row["cost"]["offpeak_usd"] for row in rows), 6)},
            "peak_usd": {"mean": _mean([row["cost"]["peak_usd"] for row in rows]),
                         "total": round(sum(row["cost"]["peak_usd"] for row in rows), 6)},
            "any_peak_logged": any(any(row["cost"]["logged_peak"]) for row in rows),
            "served_models": sorted({str(call.get("actual_model")) for row in rows for call in row["ai_calls"]}),
            "reasoning_tokens_nonzero": sum(1 for row in rows for call in row["ai_calls"]
                                            if call["usage"].get("reasoning_tokens")),
        }

    def selection(rows: list[dict[str, Any]]) -> dict[str, Any]:
        stats = [row["selection_stats"] for row in rows if row.get("selection_stats")]
        section_empty = Counter()
        section_no_optional = Counter()
        for entry in stats:
            for section, values in entry["sections"].items():
                section_empty[section] += values["picked"] == 0
                section_no_optional[section] += values["picked_optional"] == 0 and values["optional_candidates"] > 0
        origins = Counter(item["origin"] for row in rows for item in row["rendered"] or [])
        return {
            "runs": len(stats),
            "retry_runs": sum(1 for row in rows if row["retries"]),
            "retry_rate": round(sum(1 for row in rows if row["retries"]) / len(rows), 4) if rows else None,
            "all_six_empty_runs": sum(entry["all_empty"] for entry in stats),
            "no_optional_pick_runs": sum(entry["no_optional_picked"] for entry in stats),
            "mean_picked": _mean([entry["picked_total"] for entry in stats]),
            "mean_picked_optional": _mean([entry["picked_optional_total"] for entry in stats]),
            "mean_picked_required_redundant": _mean([entry["picked_required_total"] for entry in stats]),
            "mean_optional_candidates": _mean([entry["optional_candidates_total"] for entry in stats]),
            "mean_catalogue_size": _mean([len(row["catalogue"]) for row in rows]),
            "mean_rendered": _mean([len(row["rendered"] or []) for row in rows]),
            "rendered_origin": dict(origins),
            "sections_with_empty_list": dict(section_empty),
            "sections_with_candidates_but_no_optional_pick": dict(section_no_optional),
        }

    agreement: dict[str, Any] = {}
    if labelled:
        for name, items in (("all", labelled), ("annual", labelled_annual)):
            det = [item["det_class"] for item in items]
            llm = [item["llm_class"] for item in items]
            confusion = Counter((a, b) for a, b in zip(det, llm))
            agreement[name] = {
                "n": len(items), "kappa_class": _kappa(det, llm),
                "raw_agreement": round(sum(a == b for a, b in zip(det, llm)) / len(items), 4),
                "kappa_directive": _kappa([str(i["directive"]) for i in items], [str(i["llm_directive"]) for i in items]),
                "kappa_missingness": _kappa([str(i["missingness"]) for i in items],
                                            [str(i["llm_missingness"]) for i in items]),
                "confusion_det_by_llm": {f"{a} -> {b}": count for (a, b), count in sorted(confusion.items())},
                # Sensitivity: without the one template whose wording the two methods read differently
                # ("Watch how X ... compares with <one stated figure>").
                "kappa_class_without_watch_next_metric": _kappa(
                    [item["det_class"] for item in items if item["template"] != "watch_next.metric"],
                    [item["llm_class"] for item in items if item["template"] != "watch_next.metric"]),
                "disagreements_by_template": dict(Counter(
                    f"{item['template']}: {item['det_class']} -> {item['llm_class']}"
                    for item in items if item["det_class"] != item["llm_class"]).most_common()),
            }
    disagreement_examples = [
        {"run": item["run"], "template": item["template"], "det": item["det_class"], "llm": item["llm_class"],
         "text": item["text_plain"]}
        for item in labelled_annual if item["det_class"] != item["llm_class"]
    ]
    seen_templates: set[str] = set()
    examples = []
    for example in disagreement_examples:
        if example["template"] not in seen_templates:
            seen_templates.add(example["template"])
            examples.append(example)

    paired = [row["ticker"] for row in ok if row["mode"] == "quarterly"]
    mode_comparison = {
        mode: {
            "runs": len(paired),
            "mean_sentences": _mean([sum(1 for item in sentences if item["run"] == f"{ticker}-{mode}") for ticker in paired]),
            "classes": class_tables([item for item in sentences if item["mode"] == mode and item["ticker"] in paired]),
            "table_visible_share": _mean([
                float(bool(item["visible"]["table"])) for item in sentences
                if item["mode"] == mode and item["ticker"] in paired and item["visible"]["table"] is not None]),
            "red_flag_signals": sum(1 for item in sentences if item["mode"] == mode and item["ticker"] in paired
                                    and item["template"].startswith("red_flags.signal.")
                                    and item["template"] != "red_flags.signal.operands"),
            "derived_q4_sentences": sum(1 for item in sentences if item["mode"] == mode and item["ticker"] in paired
                                        and "(derived Q4)" in item["text"]),
        }
        for mode in ("annual", "quarterly")
    }
    failures = [{"ticker": row["ticker"], "mode": row["mode"], "stage": row.get("failure_stage"),
                 "reason": row.get("failure_reason")} for row in runs if row["status"] != "ok"]
    substitutions = [{"ticker": row["ticker"], "mode": row["mode"], "for": row["substitute_for"],
                      "status": row["status"]} for row in runs if row.get("substitute_for")]
    report = {
        "generated_from": {"runs": len(runs), "ok": len(ok), "annual_ok": len(annual_runs),
                           "quarterly_ok": len(paired), "sentences": len(sentences),
                           "llm_labelled_runs": len(llm_rows), "llm_labelled_sentences": len(labelled),
                           "unmatched_sentences": sum(1 for item in sentences if not item["matched"])},
        "classes_annual": class_tables(annual),
        "classes_annual_without_operand_tails": class_tables(no_tail),
        "classes_by_section_annual": grouped(annual, "section"),
        "classes_by_profile_annual": grouped(annual, "profile"),
        "classes_by_mode_all": grouped(sentences, "mode"),
        "templates_annual": dict(Counter(item["template"] for item in annual).most_common()),
        "agreement": agreement,
        "disagreement_examples": examples,
        "cause_word_sentences": {
            "annual": sum(1 for item in annual if item["cause_words"]),
            "all": sum(1 for item in sentences if item["cause_words"]),
            "words": dict(Counter(word for item in sentences for word in item["cause_words"])),
            "examples": [item["text_plain"] for item in sentences if item["cause_words"]][:10],
        },
        "mean_sentences_per_analysis": _mean(list(per_run_sentences.values())),
        "sentences_per_analysis_range": [min(per_run_sentences.values(), default=None),
                                         max(per_run_sentences.values(), default=None)],
        "mean_distinct_metrics": _mean([len(concepts) for concepts in per_run_concepts.values()]),
        "mean_distinct_metrics_in_dataset": _mean([len(row["table"]["series"]) for row in annual_runs]),
        "visibility_annual": {
            "sentences": len(annual),
            "numeric_sentences": len(numeric),
            "restated_figure_visible_in_table": sum(1 for item in annual if item["det_class"] == "restated_figure"
                                                    and item["visible"]["table"]),
            "no_new_number_vs_table": sum(1 for item in numeric if item["visible"]["table"]),
            "no_new_number_vs_kpi_strip": sum(1 for item in numeric if item["visible"]["kpi"]),
            "restated_figure_visible_in_kpi_strip": sum(1 for item in annual if item["det_class"] == "restated_figure"
                                                        and item["visible"]["kpi"]),
        },
        "visibility_quarterly": {
            "numeric_sentences": sum(1 for item in sentences if item["mode"] == "quarterly"
                                     and item["visible"]["table"] is not None),
            "no_new_number_vs_table": sum(1 for item in sentences if item["mode"] == "quarterly"
                                          and item["visible"]["table"]),
        },
        "tokens_cost_annual": tokens(annual_runs),
        "tokens_cost_all": tokens(ok),
        "latency_annual": latency(annual_runs),
        "latency_all": latency(ok),
        "selection_annual": selection(annual_runs),
        "selection_all": selection(ok),
        "mode_comparison": mode_comparison,
        "failures": failures,
        "substitutions": substitutions,
        "windows_differing_from_bootstrap": [
            {"ticker": row["ticker"], "used_ui_window": row.get("window"), "bootstrap": row.get("bootstrap_window")}
            for row in runs if row["mode"] == "annual" and row.get("window_matches_bootstrap") is False
        ],
        "llm_cost_usd": round(sum(row["cost_usd"] for row in _jsonl(LLM_LABELS)), 4),
        "llm_calls": sum(len(row["calls"]) for row in _jsonl(LLM_LABELS)),
        "llm_served_models": sorted({model for row in _jsonl(LLM_LABELS) for call in row["calls"]
                                     for model in call["models"]}),
    }
    (OUT / "results.json").write_text(json.dumps(report, indent=1) + "\n")
    (OUT / "results.md").write_text(_markdown(report) + "\n")
    print(_markdown(report))
    return report


def _pct(value: Optional[float]) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def _class_row(label: str, table: dict[str, Any]) -> str:
    cells = [f"{_pct(table[klass]['share'])} ({table[klass]['count']})" for klass in CLASSES]
    return f"| {label} | {table['n']} | " + " | ".join(cells) + " |"


def _markdown(report: dict[str, Any]) -> str:
    header = "| Group | Sentences | " + " | ".join(CLASSES) + " |\n|---|---|" + "---|" * len(CLASSES)
    lines = ["# Census results (generated by `python -m evals.trend_depth.census report`)", "",
             "## Class proportions, annual analyses", "", header]
    overall = report["classes_annual"]
    lines.append(_class_row("All — deterministic (template)", overall["deterministic"]))
    if "llm" in overall:
        lines.append(_class_row("All — blind LLM", overall["llm"]))
    tails = report["classes_annual_without_operand_tails"]
    lines.append(_class_row("Without red-flag operand tails — deterministic", tails["deterministic"]))
    if "llm" in tails:
        lines.append(_class_row("Without red-flag operand tails — blind LLM", tails["llm"]))
    lines += ["", f"Flags (deterministic): directive {overall['directive']}, missingness {overall['missingness']}.",
              "", "## By section (annual)", "", header]
    for section, _ in ANALYSIS_SECTIONS:
        table = report["classes_by_section_annual"].get(section)
        if table:
            lines.append(_class_row(f"{SECTION_TITLES[section]} — det", table["deterministic"]))
            if "llm" in table:
                lines.append(_class_row(f"{SECTION_TITLES[section]} — LLM", table["llm"]))
    lines += ["", "## By profile (annual)", "", header]
    for profile, table in sorted(report["classes_by_profile_annual"].items()):
        lines.append(_class_row(f"{profile} — det", table["deterministic"]))
        if "llm" in table:
            lines.append(_class_row(f"{profile} — LLM", table["llm"]))
    lines += ["", "## Agreement (deterministic vs blind LLM)", ""]
    for name, values in report["agreement"].items():
        lines.append(f"- {name}: n={values['n']}, Cohen's kappa (class) = {values['kappa_class']}, raw agreement "
                     f"{_pct(values['raw_agreement'])}, kappa without watch_next.metric = "
                     f"{values['kappa_class_without_watch_next_metric']}, kappa directive = "
                     f"{values['kappa_directive']}, kappa missingness = {values['kappa_missingness']}")
        for pair, count in values["confusion_det_by_llm"].items():
            lines.append(f"  - {pair}: {count}")
    visibility = report["visibility_annual"]
    lines += ["", "## Other measures (annual)", "",
              f"- Mean sentences per analysis: {report['mean_sentences_per_analysis']} "
              f"(range {report['sentences_per_analysis_range']})",
              f"- Mean distinct metrics mentioned: {report['mean_distinct_metrics']} "
              f"(of {report['mean_distinct_metrics_in_dataset']} series in the dataset)",
              f"- Sentences with any cause word: {report['cause_word_sentences']['annual']} "
              f"(all modes: {report['cause_word_sentences']['all']}; words {report['cause_word_sentences']['words']})",
              f"- Restated figures already shown in the metrics table: {visibility['restated_figure_visible_in_table']} "
              f"of {visibility['sentences']} sentences",
              f"- Numeric sentences adding no figure the metrics table lacks: {visibility['no_new_number_vs_table']} "
              f"of {visibility['numeric_sentences']}",
              f"- Numeric sentences adding no figure the KPI strip lacks: {visibility['no_new_number_vs_kpi_strip']} "
              f"of {visibility['numeric_sentences']}"]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=("run", "classify", "label", "report"))
    parser.add_argument("--tickers", help="comma-separated subset (run step; skips substitution)")
    parser.add_argument("--limit", type=int, help="label at most N more narratives")
    args = parser.parse_args()
    if args.step == "run":
        asyncio.run(run_census(set(args.tickers.split(",")) if args.tickers else None))
    elif args.step == "classify":
        classify_runs()
    elif args.step == "label":
        asyncio.run(label_runs(args.limit))
    else:
        build_report()


if __name__ == "__main__":
    main()
