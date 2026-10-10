"""Deterministic adjacent-figure checks for narrative citations."""
from __future__ import annotations

import re
from typing import Any


# --- numeric-fidelity scan (audit D2: the deterministic backstop behind "every cited figure") --

# A printed figure near a citation: optional $, digits with thousands commas, optional decimals,
# optional %/pp/compact-scale suffix (incl. the "bn"/"mn"/"tn" style). Linear (single
# character-class core, no nesting) — this scans model output on the event loop.
_FIDELITY_NUM_RE = re.compile(
    r"(\$)?(\d[\d,]*(?:\.\d+)?)\s*(%|pp|[bmt]n\b|[BTMK]\b|billion|million|trillion|thousand)?",
    re.IGNORECASE,
)


_FIDELITY_SCALES = {
    "k": 1e3, "thousand": 1e3,
    "m": 1e6, "mn": 1e6, "million": 1e6,
    "b": 1e9, "bn": 1e9, "billion": 1e9,
    "t": 1e12, "tn": 1e12, "trillion": 1e12,
}


# How far back from "[n]" the claimed figure may sit — the copilot adjacency window's sibling.
_FIDELITY_WINDOW_CHARS = 48


# A resolved citation marker inside the window ("[1]"): both a scrub target (its digits are NOT
# figures) and the window's hard left bound — the claim before an earlier marker belongs to THAT
# marker, not this one (the copilot _claim_span_start rule). Bounded digit run keeps it linear.
_FIDELITY_MARKER_RE = re.compile(r"\[\d{1,4}\]")


def _window_number_tokens(window: str) -> list[tuple[float, int, float]]:
    """Every printed figure in a window as (number, decimals, scale). Skips tokens that are not
    financial figures: period identifiers (FY2024, 2026Q3), bare years, and small bare counts
    ("over the past 5 years", "3rd consecutive quarter" — no $, no suffix, no decimals)."""
    tokens: list[tuple[float, int, float]] = []
    for match in _FIDELITY_NUM_RE.finditer(window):
        dollar, raw, suffix = match.group(1), match.group(2), match.group(3)
        start, end = match.start(2), match.end(2)
        if start > 0 and window[start - 1].isalpha():
            continue  # FY2024 / Q3-style token — part of an identifier
        if end < len(window) and window[end] == "Q":
            continue  # 2026Q3
        number = float(raw.replace(",", ""))
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        if not dollar and suffix is None and decimals == 0:
            if 1900 <= number <= 2100:
                continue  # a bare year in prose
            if number < 1000:
                continue  # a small bare count, not a financial figure (the copilot rule)
        scale = _FIDELITY_SCALES.get(suffix.lower(), 1.0) if suffix else 1.0
        tokens.append((number, decimals, scale))
    return tokens


def _fidelity_candidates(citation: dict[str, Any], point: dict[str, Any]) -> list[float]:
    """Every dataset figure the prompt licenses against this marker: the point's value (plus its
    ×100 form for CAGR markers ONLY — growth fractions print as percentages, but licensing ×100
    for monetary values would wave through exactly the scale-slip errors the scan exists to
    catch) and the point's YoY/QoQ deltas (pp form for percent series, ×100 relative form
    otherwise)."""
    candidates: list[float] = []
    value = citation.get("value")
    if isinstance(value, (int, float)):
        candidates.append(float(value))
        if point.get("kind") == "cagr":
            candidates.append(float(value) * 100.0)
    for key in ("yoy", "qoq"):
        growth = point.get(key)
        if isinstance(growth, (int, float)):
            candidates.extend([float(growth), float(growth) * 100.0])
    return candidates


def _token_matches_any(token: tuple[float, int, float], candidates: list[float]) -> bool:
    """Half-ULP-of-the-printed-precision comparison: '391.0B' (1 decimal at 1e9 scale) accepts
    anything the display formatter would round to 391.0B. Signs compare absolutely — prose sign
    conventions vary ('outflow of $71.9B' cites a negative value)."""
    number, decimals, scale = token
    target = abs(number) * scale
    tolerance = max(0.55 * scale * 10.0 ** (-decimals), 1e-9)
    return any(abs(target - abs(c)) <= tolerance for c in candidates)


def scan_numeric_fidelity(
    text: str, citations: list[dict[str, Any]], index: dict[str, dict[str, Any]]
) -> list[int]:
    """Citation numbers whose adjacent claim contains figures and NONE of them matches the cited
    point's dataset figures. Deterministic, no model involved. The window is bounded at the
    previous citation marker (an earlier claim's figure belongs to ITS marker) — so in a chain
    "[1][2]" the second marker's window is empty and it passes as qualitative, the same rule the
    copilot adjacency guard applies. Qualitative references (no figure in the window) always
    pass; a claim citing several figures passes if ANY of them matches ("from $X to $Y [a][b]").
    """
    by_concept_period = {
        (entry.get("concept"), entry.get("period")): entry for entry in index.values()
    }
    mismatched: list[int] = []
    for citation in citations:
        n = citation.get("n")
        point = by_concept_period.get((citation.get("concept"), citation.get("period")), {})
        candidates = _fidelity_candidates(citation, point)
        if not candidates:
            continue
        marker = f"[{n}]"
        cursor = 0
        clean = True
        while clean:
            position = text.find(marker, cursor)
            if position == -1:
                break
            cursor = position + len(marker)
            window = text[max(0, position - _FIDELITY_WINDOW_CHARS):position]
            # Bound at the previous resolved marker — everything before it was that marker's claim.
            previous_marker = None
            for marker_match in _FIDELITY_MARKER_RE.finditer(window):
                previous_marker = marker_match
            if previous_marker is not None:
                window = window[previous_marker.end():]
            tokens = _window_number_tokens(window)
            if tokens and not any(_token_matches_any(t, candidates) for t in tokens):
                clean = False
        if not clean:
            mismatched.append(int(n))
    return mismatched
