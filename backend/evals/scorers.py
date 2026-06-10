"""Deterministic scorers for the eval harness.

These are pure functions with no network/AI dependency, so they are fast, reproducible, and
unit-tested offline. They are the defensible core of the bake-off: schema validity, numeric
grounding against XBRL ground truth, and substantive section coverage. (An optional LLM-judge
dimension can be layered on later for usefulness/precision — see README.)
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from evals.schema import REQUIRED_SECTIONS, GroundTruthFact, RubricScore

# Placeholder/failure phrases that must NOT count as substantive content. Kept in sync with
# summary_generation_service.calculate_section_coverage so the harness and product agree on
# what "covered" means.
PLACEHOLDER_PATTERNS = (
    "not disclosed", "not available", "unavailable", "n/a", "not found",
    "not provided", "no data", "could not", "unable to", "failed to",
    "missing", "pending", "being processed", "retry", "error",
)

_MIN_SUBSTANTIVE_CHARS = 20


# ---------------------------------------------------------------------------
# Schema validity
# ---------------------------------------------------------------------------
def validate_schema(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Lightweight structural validation against EVAL_SUMMARY_JSON_SCHEMA.

    We don't pull a full JSON-schema lib for this — the canonical shape is small and fixed.
    Returns (is_valid, list_of_problems)."""
    problems: List[str] = []
    if not isinstance(payload, dict):
        return False, ["top-level value is not an object"]

    for key in REQUIRED_SECTIONS:
        if key not in payload:
            problems.append(f"missing key: {key}")

    fh = payload.get("financial_highlights")
    if not isinstance(fh, dict):
        problems.append("financial_highlights is not an object")
    else:
        for k in ("revenue", "net_income", "eps", "key_metrics"):
            if k not in fh:
                problems.append(f"financial_highlights missing: {k}")
        if "key_metrics" in fh and not isinstance(fh["key_metrics"], list):
            problems.append("financial_highlights.key_metrics is not an array")

    if "risk_factors" in payload and not isinstance(payload["risk_factors"], list):
        problems.append("risk_factors is not an array")

    for str_key in ("executive_summary", "management_discussion", "outlook"):
        if str_key in payload and not isinstance(payload[str_key], str):
            problems.append(f"{str_key} is not a string")

    return (len(problems) == 0), problems


def parse_model_json(raw: str) -> Tuple[Optional[Dict[str, Any]], bool]:
    """Parse a model's text output as JSON. Returns (payload, repaired).

    `repaired` is True when strict json.loads failed and we fell back to extracting a JSON
    object — a soft failure that, in aggregate, signals the model isn't honoring enforced
    structured output (the whole motivation for S1)."""
    try:
        return json.loads(raw), False
    except (json.JSONDecodeError, TypeError):
        pass
    # Fallback: strip markdown fences and grab the outermost {...}.
    text = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1]), True
        except json.JSONDecodeError:
            return None, True
    return None, True


# ---------------------------------------------------------------------------
# Numeric grounding
# ---------------------------------------------------------------------------
def _number_renderings(value: float, unit: str) -> List[str]:
    """Plausible string renderings of a ground-truth value a model might emit.

    Covers billions/millions/raw with 0-3 decimals and comma grouping, so "383.3",
    "$383.285 billion", "383,285" (millions) and "383,285,000,000" all match revenue."""
    out: set[str] = set()
    av = abs(value)

    def with_decimals(x: float) -> List[str]:
        reps = []
        for d in range(0, 4):
            s = f"{x:.{d}f}"
            reps.append(s)
            # comma-grouped integer part
            try:
                intpart, _, frac = s.partition(".")
                grouped = f"{int(intpart):,}"
                reps.append(grouped if not frac else f"{grouped}.{frac}")
            except ValueError:
                pass
        return reps

    if unit == "USD_per_share":
        out.update(with_decimals(av))
    else:
        if av >= 1e9:
            out.update(with_decimals(av / 1e9))  # billions
        if av >= 1e6:
            out.update(with_decimals(av / 1e6))  # millions
        # raw dollars, grouped and ungrouped
        out.add(f"{int(round(av))}")
        out.add(f"{int(round(av)):,}")
    # drop trivially-short tokens that would false-match everywhere
    return [r for r in out if len(r.replace(",", "").replace(".", "")) >= 2]


def score_numeric_accuracy(
    haystack: str, ground_truth: List[GroundTruthFact]
) -> Tuple[float, List[str], List[str]]:
    """Fraction of ground-truth facts whose value appears (in any common rendering) in the
    candidate's financial text. Returns (recall, matched_metrics, missing_metrics)."""
    if not ground_truth:
        return 1.0, [], []  # nothing to verify → not penalized
    hay = haystack.lower()
    matched, missing = [], []
    for fact in ground_truth:
        renderings = _number_renderings(fact.value, fact.unit)
        if any(r.lower() in hay for r in renderings):
            matched.append(fact.metric)
        else:
            missing.append(fact.metric)
    recall = len(matched) / len(ground_truth)
    return round(recall, 4), matched, missing


# ---------------------------------------------------------------------------
# Section coverage (substantive content, not placeholders)
# ---------------------------------------------------------------------------
def _is_substantive(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        text = value.strip().lower()
        if len(text) < _MIN_SUBSTANTIVE_CHARS:
            return False
        if len(text) < 200 and any(p in text for p in PLACEHOLDER_PATTERNS):
            return False
        return True
    if isinstance(value, list):
        return any(_is_substantive(v) for v in value)
    if isinstance(value, dict):
        # financial_highlights: substantive if any sub-value is substantive
        return any(_is_substantive(v) for v in value.values())
    if isinstance(value, (int, float)):
        return True
    return False


def score_coverage(payload: Dict[str, Any]) -> Tuple[float, List[str]]:
    """Fraction of required sections containing substantive content. Returns (ratio, missing)."""
    missing = [s for s in REQUIRED_SECTIONS if not _is_substantive(payload.get(s))]
    covered = len(REQUIRED_SECTIONS) - len(missing)
    return round(covered / len(REQUIRED_SECTIONS), 4), missing


# ---------------------------------------------------------------------------
# Numeric precision / contradiction (Artifact-1 hard gate G1)
# ---------------------------------------------------------------------------
# `score_numeric_accuracy` above measures RECALL — are the right numbers present? It cannot
# catch a confidently-wrong figure: a summary whose revenue field reads "$4.2B" still scores
# perfect recall if the correct "$3.8B" appears elsewhere. Precision closes that: it checks the
# LABELED financial fields directly, so a number that contradicts ground truth is caught.
_LABELED_METRICS = ("revenue", "net_income", "eps")
_NUMBER_TOKEN_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?")
# Negative-value indicators: a leading minus or accounting parentheses on a figure, or an
# explicit loss word. `_number_renderings` matches on abs(value), so without this a profit
# reported where the truth is a loss (sign-flipped) would silently satisfy the G1 gate.
_NEGATIVE_INDICATOR_RE = re.compile(r"-\s*\$?\d|\(\s*\$?\d")
_LOSS_WORDS = ("loss", "deficit", "negative")


def _indicates_negative(field_val: str) -> bool:
    low = field_val.lower()
    return bool(_NEGATIVE_INDICATOR_RE.search(field_val)) or any(w in low for w in _LOSS_WORDS)


def score_numeric_precision(
    payload: Dict[str, Any], ground_truth: List[GroundTruthFact]
) -> Tuple[float, List[str]]:
    """Precision of the labeled financial fields. Returns (precision, contradictions).

    For each ground-truth metric with a matching `financial_highlights` field that contains a
    number, the field must (a) match the metric's sign and (b) render its value. A wrong number
    OR a flipped sign (a loss reported as a profit) is a contradiction. Absent values
    ("Not disclosed") are coverage's concern. precision = 1.0 when nothing numeric is checkable."""
    fh = payload.get("financial_highlights")
    if not isinstance(fh, dict) or not ground_truth:
        return 1.0, []
    gt_by_metric = {f.metric: f for f in ground_truth}
    checked = 0
    contradictions: List[str] = []
    for metric in _LABELED_METRICS:
        fact = gt_by_metric.get(metric)
        if fact is None:
            continue
        field_val = fh.get(metric)
        if not isinstance(field_val, str) or not _NUMBER_TOKEN_RE.search(field_val):
            continue  # absent or non-numeric → not a contradiction
        checked += 1
        if (fact.value < 0) != _indicates_negative(field_val):
            contradictions.append(
                f"{metric}: field '{field_val.strip()[:50]}' sign mismatch with ground truth "
                f"{fact.value:g} {fact.unit}"
            )
            continue
        renderings = _number_renderings(fact.value, fact.unit)
        if not any(r.lower() in field_val.lower() for r in renderings):
            contradictions.append(
                f"{metric}: field '{field_val.strip()[:50]}' contradicts ground truth "
                f"{fact.value:g} {fact.unit}"
            )
    precision = round((checked - len(contradictions)) / checked, 4) if checked else 1.0
    return precision, contradictions


# ---------------------------------------------------------------------------
# Output hygiene (Artifact-1 hard gate G4)
# ---------------------------------------------------------------------------
# Leaked AI/internal notices and placeholder filler must never reach a user. Deterministic and
# cheap to catch in the prose fields. (G2 fabricated comparatives / G3 hallucinated events need
# the source document and are assessed by the optional LLM judge, not here.)
HYGIENE_PATTERNS = (
    "as an ai", "as a language model", "i cannot", "i'm sorry", "i am sorry",
    "internal note", "internal only", "system prompt", "do not show", "do not display",
    "todo", "tbd", "lorem ipsum", "[insert", "[placeholder", "placeholder text", "xxxx",
)
_HYGIENE_PROSE_FIELDS = ("executive_summary", "management_discussion", "outlook")


def detect_hygiene_violations(payload: Dict[str, Any]) -> List[str]:
    """Return human-readable hygiene violations found in the prose fields and risk list."""
    violations: List[str] = []

    def scan(label: str, text: Any) -> None:
        if not isinstance(text, str):
            return
        low = text.lower()
        for p in HYGIENE_PATTERNS:
            if p in low:
                violations.append(f"{label}: contains '{p}'")

    for key in _HYGIENE_PROSE_FIELDS:
        scan(key, payload.get(key))
    rf = payload.get("risk_factors")
    if isinstance(rf, list):
        for i, item in enumerate(rf):
            scan(f"risk_factors[{i}]", item)
    return violations


def compute_gate_failures(
    payload: Dict[str, Any], contradictions: List[str]
) -> List[str]:
    """Combine Artifact-1 deterministic hard gates into a single veto list."""
    failures = [f"G1 numeric fidelity — {c}" for c in contradictions]
    failures += [f"G4 output hygiene — {h}" for h in detect_hygiene_violations(payload)]
    return failures


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------
def _financial_haystack(payload: Dict[str, Any]) -> str:
    """Text we search for ground-truth numbers: financial section + executive summary."""
    parts: List[str] = []
    fh = payload.get("financial_highlights")
    if isinstance(fh, dict):
        parts.append(json.dumps(fh))
    elif fh is not None:
        parts.append(str(fh))
    for k in ("executive_summary", "management_discussion", "outlook"):
        v = payload.get(k)
        if isinstance(v, str):
            parts.append(v)
    return " ".join(parts)


def score_summary(
    raw_or_payload: Any, ground_truth: List[GroundTruthFact]
) -> RubricScore:
    """Score one candidate summary. Accepts a raw string (from a model) or an already-parsed
    dict (from the baseline pipeline mapped into canonical shape)."""
    if isinstance(raw_or_payload, str):
        payload, repaired = parse_model_json(raw_or_payload)
    else:
        payload, repaired = raw_or_payload, False

    if payload is None:
        return RubricScore(
            schema_valid=False, repaired=True, numeric_accuracy=0.0, coverage=0.0,
            numeric_precision=0.0,
            gate_failures=["G1 numeric fidelity — unparseable output (no JSON object found)"],
            missing_sections=list(REQUIRED_SECTIONS),
            missing_facts=[f.metric for f in ground_truth],
        )

    schema_valid, _ = validate_schema(payload)
    numeric, matched, missing_facts = score_numeric_accuracy(
        _financial_haystack(payload), ground_truth
    )
    coverage, missing_sections = score_coverage(payload)
    precision, contradictions = score_numeric_precision(payload, ground_truth)
    return RubricScore(
        schema_valid=schema_valid,
        repaired=repaired,
        numeric_accuracy=numeric,
        coverage=coverage,
        numeric_precision=precision,
        gate_failures=compute_gate_failures(payload, contradictions),
        missing_sections=missing_sections,
        matched_facts=matched,
        missing_facts=missing_facts,
    )
