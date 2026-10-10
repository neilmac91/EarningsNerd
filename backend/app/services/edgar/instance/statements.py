"""Accession-aware XBRL extraction: statements."""

from typing import Any, Dict, List, Optional, Tuple

from .core import _iso_date, _numeric, logger, normalize_form
from .financial_profiles import FINANCIAL_PROFILES, is_financial_institution


def _concept_local(concept: Any) -> str:
    """Local name of an as-reported ``concept`` cell: ``us-gaap_InterestIncomeExpenseNet`` -> the
    part after the namespace ``_`` (``mcb_Foo`` -> ``Foo``). Namespace/local are joined by a single
    underscore; us-gaap/ifrs local names themselves carry none."""
    text = str(concept or "")
    return text.split("_", 1)[1] if "_" in text else text


def income_statement_dataframe(xb: Any) -> Any:
    """The filing's as-reported income statement as a face-value DataFrame, or None.

    Uses ``view="standard"`` (undimensioned face values — the filing document view; the successor
    to the deprecated ``include_dimensions=False``). Fully defensive: any failure in the statement
    machinery returns None so the caller falls back to the generic fact-query path and extraction
    never hard-fails.
    """
    try:
        statement = xb.statements.income_statement()
        if statement is None:
            return None
        try:
            df = statement.to_dataframe(view="standard")
        except TypeError:
            df = statement.to_dataframe()  # older signatures without `view`
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"income_statement() unavailable: {exc}")
        return None
    if df is None or getattr(df, "empty", True):
        return None
    return df


def _period_marker(text: str) -> str:
    """The parenthetical period marker of a statement column, upper-cased. ``"2025-09-30 (Q3)"`` ->
    ``"Q3"``; ``"2025-12-31 (FY)"`` -> ``"FY"``; no marker -> ``""``."""
    i, j = text.rfind("("), text.rfind(")")
    return text[i + 1:j].strip().upper() if 0 <= i < j else ""


def _statement_period_columns(df: Any, form: str) -> List[Tuple[str, Any]]:
    """[(period_end_iso, column)] for the statement's dated period columns, newest first.

    Columns look like ``"2025-12-31 (FY)"`` or ``"2025-09-30 (Q3)"``. We keep only the columns that
    represent the FILING's own reporting duration:
      • annual forms (10-K/20-F/40-F) → the ``(FY)`` column;
      • a 10-Q → the discrete ``(Qn)`` QUARTER column, NEVER a same-dated year-to-date column.
    A Q2/Q3 income statement carries both a ``(Qn)`` and a ``(YTD)`` column ending on the same date;
    without this filter the tie was broken by raw DataFrame column order, so a filer whose YTD column
    came first leaked the 6-/9-month cumulative in as if it were the quarter (observed live on ARCC:
    $2.259B 9-month reported as the $782M quarter). De-duped by ``(period_end, marker)``.
    """
    annual = normalize_form(form) in ("10-K", "20-F", "40-F")
    cols: List[Tuple[str, Any]] = []
    seen: set = set()
    for col in df.columns:
        text = str(col)
        end = _iso_date(text[:10])
        if end is None:
            continue
        marker = _period_marker(text)
        if annual:
            if marker != "FY":
                continue
        elif not (marker.startswith("Q") and marker[1:].isdigit()):
            # Non-annual (10-Q): only a discrete quarter; drop YTD/6-/9-month cumulatives and any
            # unlabelled column. If nothing matches, the caller gets [] and falls back to the generic
            # fact-query path (which has its own 75–105-day duration guard).
            continue
        key = (end, marker)
        if key in seen:
            continue
        seen.add(key)
        cols.append((end, col))
    cols.sort(key=lambda pc: pc[0], reverse=True)
    return cols


def _truthy_flag(value: Any) -> bool:
    """Normalize a statement flag cell to a bool. The as-reported DataFrame carries ``abstract`` /
    ``is_breakdown`` / ``dimension`` as booleans for face rows (``False``), but older/other views may
    use NaN or a dimension-axis string. NaN/None/"" → False; a real bool passes through; any other
    non-empty value (e.g. an axis name) → True."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, float) and value != value:  # NaN
        return False
    return bool(str(value).strip())


def _row_is_face_value(row: Any) -> bool:
    """A usable statement line: not an abstract header, not a dimensional breakdown member."""
    return not (
        _truthy_flag(row.get("abstract"))
        or _truthy_flag(row.get("is_breakdown"))
        or _truthy_flag(row.get("dimension"))
    )


def _select_statement_series(
    df: Any,
    anchors: Tuple[str, ...],
    expected_std: Optional[str],
    period_cols: List[Tuple[str, Any]],
    period_of_report: str,
    max_items: int = 5,
) -> Tuple[List[Tuple[str, float]], Optional[str]]:
    """Series + winning us-gaap tag for the total/component row of the first resolving anchor.

    For each anchor concept (priority order), take the face-value rows whose local concept matches.
    When several rows share the concept (a total plus disaggregation sub-lines), the total is the
    one whose ``standard_concept`` equals ``expected_std`` — the marker the as-reported statement
    puts only on the recognized line. Reads that row's value from every dated period column and
    requires an anchor at ``period_of_report`` (proving it is the figure this filing reports).
    """
    records = df.to_dict("records")
    for anchor in anchors:
        matches = [r for r in records if _concept_local(r.get("concept")) == anchor and _row_is_face_value(r)]
        if not matches:
            continue
        chosen = None
        if len(matches) == 1:
            chosen = matches[0]
        elif expected_std:
            marked = [r for r in matches if str(r.get("standard_concept") or "") == expected_std]
            if len(marked) == 1:
                chosen = marked[0]
        if chosen is None:
            continue  # genuinely ambiguous — don't guess
        series: List[Tuple[str, float]] = []
        for end, col in period_cols:
            if end > period_of_report:
                continue
            value = _numeric(chosen.get(col))
            if value is not None:
                series.append((end, value))
        if series and series[0][0] == period_of_report:
            return series[:max_items], f"us-gaap:{anchor}"
    return [], None


def _profile_required(profile: Dict[str, Any]) -> Tuple[str, ...]:
    """The metrics a profile MUST resolve to be accepted (default: a single ``revenue`` total)."""
    return tuple(profile.get("required", ("revenue",)))


def match_financial_profile(df: Any) -> Optional[Dict[str, Any]]:
    """First profile whose ``detect`` concept(s) are present, by concept presence (quick pre-filter).

    NOTE: this is a coarse presence check; ``extract_financial_statement_metrics`` additionally
    requires each candidate's ``required`` metrics to actually RESOLVE before accepting it (so an
    asset-manager that merely tags a net-interest line does not stick to the ``bank`` profile).
    """
    present = {
        _concept_local(r.get("concept"))
        for r in df.to_dict("records")
        if _row_is_face_value(r)
    }
    for profile in FINANCIAL_PROFILES:
        detect = profile["detect"]
        if not detect or present.intersection(detect):
            return profile
    return None


def extract_financial_statement_metrics(
    xb: Any,
    company: Any,
    sic: Optional[str],
    form: str,
    period_of_report: str,
    max_items: int = 5,
) -> Optional[Tuple[str, Dict[str, Tuple[List[Tuple[str, float]], str]], Tuple[str, ...]]]:
    """Industry-correct revenue for a financial institution, from its as-reported income statement.

    Returns ``(profile_key, {standardized_key: (series, raw_tag)}, suppress_keys)`` or None when the
    filer isn't a financial institution, the statement is unavailable, or nothing resolves — in
    every None case the caller keeps the unchanged generic fact-query extraction.

    Accepts the FIRST profile (bank → insurer → bdc → financial_generic) whose ``required`` metrics
    all resolve on this statement — not merely one whose detect-concept is present. That is what
    routes a broker-dealer/asset-manager (net-interest line but no non-interest-income total) past the
    ``bank`` profile to its genuine reported total.
    """
    if not is_financial_institution(company, sic):
        return None
    df = income_statement_dataframe(xb)
    if df is None:
        return None
    period_cols = _statement_period_columns(df, form)
    if not period_cols:
        return None
    records = df.to_dict("records")
    present = {_concept_local(r.get("concept")) for r in records if _row_is_face_value(r)}
    for profile in FINANCIAL_PROFILES:
        detect = profile["detect"]
        if detect and not present.intersection(detect):
            continue  # quick pre-filter; catch-all (empty detect) always considered
        metrics: Dict[str, Tuple[List[Tuple[str, float]], str]] = {}
        for key, anchors, expected_std in profile["selectors"]:
            series, raw_tag = _select_statement_series(
                df, anchors, expected_std, period_cols, period_of_report, max_items
            )
            if series and raw_tag:
                metrics[key] = (series, raw_tag)
        if all(req in metrics for req in _profile_required(profile)):
            return profile["key"], metrics, tuple(profile["suppress"])
    return None
