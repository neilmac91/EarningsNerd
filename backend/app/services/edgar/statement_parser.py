"""
Pure helpers for extracting metric values from EdgarTools statement DataFrames.

Schema notes for ``Statement.to_dataframe()`` in edgartools 5.x:

- Rows are positionally indexed; the XBRL concept lives in a ``concept`` column
  (e.g. ``us-gaap_NetIncomeLoss``). Very old versions used concepts as the
  DataFrame index, which is kept as a fallback.
- Segment/geography breakdowns appear as extra rows flagged ``dimension=True``
  and header rows as ``abstract=True``; only rows where both are False are
  consolidated statement-line values.
- Period columns are labelled with the period end date, optionally annotated
  with a duration marker: ``"2025-06-30 (FY)"``, ``"2026-03-31 (Q3)"`` or a
  bare ``"2025-06-30"``.
"""

import re
from typing import Any, List, Optional, Tuple

_PERIOD_COLUMN_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:\s*\((\w+)\))?$")

# Duration preference when the same period-end appears under several markers:
# the full-period (FY) figure is the statement's primary value.
_DURATION_RANK = {"FY": 0, "Q4": 1, "Q3": 2, "Q2": 3, "Q1": 4}


def statement_dataframe(financials, statement_name: str):
    """Get a statement DataFrame from an EdgarTools Financials object.

    EdgarTools 5.x exposes statements as methods (``financials.income_statement()``);
    older versions exposed properties. Handle both so an API drift degrades to the
    company-facts fallback instead of silently returning nothing.
    """
    statement = getattr(financials, statement_name, None)
    if callable(statement):
        statement = statement()
    if statement is None:
        return None
    return statement.to_dataframe()


def normalize_concept(concept: Any) -> str:
    """Strip the namespace prefix from an XBRL concept name.

    ``us-gaap_NetIncomeLoss`` / ``us-gaap:NetIncomeLoss`` -> ``NetIncomeLoss``.
    """
    text = str(concept)
    return re.sub(r"^[a-z][\w-]*[_:](?=[A-Z])", "", text)


def _coerce_scalar(value: Any) -> Optional[float]:
    """Convert a cell to float, rejecting None/NaN/non-numeric values."""
    if value is None:
        return None
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    if result != result:  # NaN
        return None
    return result


def period_columns(df) -> List[Tuple[str, str, Optional[str]]]:
    """Return ``(column_label, period_iso, duration_marker)`` for period columns."""
    found = []
    for col in df.columns:
        match = _PERIOD_COLUMN_RE.match(str(col).strip())
        if match:
            found.append((col, match.group(1), match.group(2)))
    return found


def extract_metric_values(
    df, candidates: List[str]
) -> Tuple[Optional[str], List[Tuple[str, float]]]:
    """Extract ``(matched_concept, [(period_iso, value), ...])``.

    Matches ``candidates`` (bare concept names, e.g. ``"NetIncomeLoss"``)
    against the ``concept`` column when present, else against the index
    (legacy shape). Dimension/abstract rows are excluded. When the same
    period end appears under multiple duration markers, the full-period
    value (FY, then the longest quarter marker) wins. Values are sorted
    by period descending.
    """
    if df is None or df.empty:
        return None, []

    if "concept" in df.columns:
        rows = df
        if "abstract" in df.columns:
            rows = rows[rows["abstract"] != True]  # noqa: E712 (pandas mask)
        if "dimension" in df.columns:
            rows = rows[rows["dimension"] != True]  # noqa: E712
        concepts = rows["concept"].map(normalize_concept)
        for candidate in candidates:
            matched = rows[concepts == candidate]
            if matched.empty:
                continue
            return candidate, _values_from_rows(matched)
        return None, []

    # Legacy shape: concepts as index, period columns directly.
    for candidate in candidates:
        if candidate in df.index:
            return candidate, _values_from_rows(df.loc[[candidate]])
    return None, []


def _values_from_rows(matched) -> List[Tuple[str, float]]:
    best: dict = {}  # period_iso -> (duration_rank, value)
    # Iterate positionally so duplicate column labels yield each scalar exactly
    # once instead of a sub-Series that fails float() conversion.
    for pos, col in enumerate(matched.columns):
        match = _PERIOD_COLUMN_RE.match(str(col).strip())
        if not match:
            continue
        period_iso, marker = match.group(1), match.group(2)
        for value in matched.iloc[:, pos].tolist():
            scalar = _coerce_scalar(value)
            if scalar is None:
                continue
            rank = _DURATION_RANK.get(marker, 5) if marker else 5
            current = best.get(period_iso)
            if current is None or rank < current[0]:
                best[period_iso] = (rank, scalar)
            break  # first consolidated row for this column wins
    return sorted(
        ((period, value) for period, (_, value) in best.items()),
        key=lambda item: item[0],
        reverse=True,
    )
