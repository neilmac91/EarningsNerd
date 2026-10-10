"""Fiscal dates anchored by annual reports, excluding rolling twelve-month periods."""
from __future__ import annotations

from datetime import date
from typing import Any

ANNUAL_FORMS = frozenset({"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"})


def reported_fiscal_year(record: dict, end: date) -> int | None:
    """Only a timely original annual report establishes its own fiscal-year label."""
    evidence = []
    for candidate in record.get("candidates") or [record]:
        fy = candidate.get("fy")
        if (candidate.get("form") not in ANNUAL_FORMS or candidate.get("fp") != "FY"
                or not isinstance(fy, int) or isinstance(fy, bool) or fy not in {end.year - 1, end.year}
                or candidate.get("period_end") != end
                or candidate.get("period_start") != record.get("period_start")):
            continue
        try:
            filed = date.fromisoformat(str(candidate.get("filed") or "")[:10])
        except ValueError:
            continue
        if 0 <= (filed - end).days <= 180:
            evidence.append((filed, fy))
    if not evidence:
        return None
    earliest = min(item[0] for item in evidence)
    years = {fy for filed, fy in evidence if filed == earliest}
    return next(iter(years)) if len(years) == 1 else None


def fiscal_year_labels(duration_values: dict, windows: list[tuple[date, date]]) -> dict[date, int]:
    """Keep January spillover dates and historical comparative labels consistent."""
    evidence: dict[date, set[int]] = {}
    for values in duration_values.values():
        for (end, kind), record in values.items():
            if kind == "FY" and (year := reported_fiscal_year(record, end)) is not None:
                evidence.setdefault(end, set()).add(year)
    labels = {end: next(iter(years)) for end, years in evidence.items() if len(years) == 1}
    ends = [end for _start, end in windows]
    # Old comparative-only history may lack its original filing. Contiguous year windows
    # can inherit an established adjacent issuer label, without trusting a later filer's fy.
    for ordered in (ends, list(reversed(ends))):
        for prior, current in zip(ordered, ordered[1:]):
            if current not in labels and prior in labels and 335 <= abs((current - prior).days) <= 395:
                labels[current] = labels[prior] + (1 if current > prior else -1)
    return {end: labels.get(end, end.year) for end in ends}


def _fiscal_year_windows(duration_values: dict) -> list[tuple[date, date]]:
    """Completed year windows require an actual annual report, not duration alone."""
    by_end: dict[date, date] = {}
    for values in duration_values.values():
        for (end, kind), record in values.items():
            start = record.get("period_start")
            candidates = record.get("candidates") or [record]
            annual_evidence = any(
                candidate.get("form") in ANNUAL_FORMS and candidate.get("period_start") == start
                and candidate.get("period_end") == end for candidate in candidates
            )
            if kind == "FY" and start is not None and annual_evidence:
                by_end[end] = min(start, by_end.get(end, start))
    return [(start, end) for end, start in sorted(by_end.items())]


def fiscal_duration_values(duration_values: dict, windows: list[tuple[date, date]], metadata: dict) -> dict:
    """Keep annual-duration rows only when their dates match a completed fiscal year."""
    filtered = {
        concept: {key: record for key, record in values.items()
                  if key[1] != "FY" or any(
                      key[0] == end and abs((record["period_start"] - start).days) <= 1
                      for start, end in windows
                  )}
        for concept, values in duration_values.items()
    }
    exclusions = []
    for concept, values in duration_values.items():
        for key, record in values.items():
            end = key[0]
            next_label = _next_year_label(end, record, windows)
            known_interim = any(start <= end < finish for start, finish in windows) or (
                next_label is not None and next_label[0] != "Q4"
            )
            if key in filtered[concept] or not known_interim:
                continue  # Absence of annual evidence alone cannot quarantine historical rows.
            for candidate in record.get("candidates") or [record]:
                exclusions.append({
                    "reason": "rolling_duration_not_fiscal_year", "concept": concept,
                    "unit": candidate["unit"], "value": candidate["value"],
                    "period_start": candidate["period_start"].isoformat(), "period_end": end.isoformat(),
                    "accession": candidate.get("accession"), "raw_tag": candidate.get("raw_tag"),
                    "filed_at": candidate.get("filed"), "fiscal_period": "FY", "fiscal_year": end.year,
                })
    if exclusions:
        metadata["calendar_exclusions"] = exclusions
    return filtered


def _next_year_label(end: date, record: dict, windows: list[tuple[date, date]],
                     fiscal_years: dict[date, int] | None = None) -> tuple[str, int] | None:
    """Bound the next cycle from the last completed year; SEC fy can lag the fiscal label."""
    prior_end = next((year_end for _start, year_end in reversed(windows) if year_end < end), None)
    fp = record.get("first_fp")
    if prior_end is None or fp not in {"Q1", "Q2", "Q3", "Q4"}:
        return None
    days = (end - prior_end).days
    # Fiscal calendars range from 12-week first quarters through 16/17-week Q4.
    bounds = {"Q1": (75, 105), "Q2": (150, 215), "Q3": (245, 300), "Q4": (335, 395)}
    low, high = bounds[fp]
    year = (fiscal_years or {}).get(prior_end, prior_end.year)
    return (fp, year + 1) if low <= days <= high else None


def _label_quarters(duration_values: dict, fy_windows: list[tuple[date, date]],
                    fiscal_years: dict[date, int] | None = None) -> dict[date, tuple[str, int]]:
    """Label dates relative to real fiscal years, then bounded in-progress periods."""
    years = fiscal_years if fiscal_years is not None else fiscal_year_labels(duration_values, fy_windows)
    records: dict[date, dict[str, Any]] = {}
    for values in duration_values.values():
        for (end, kind), record in values.items():
            if kind not in {"Q", "YTD6", "YTD9"}:
                continue
            existing = records.get(end)
            if existing is None or record["first_filed"] < existing["first_filed"]:
                records[end] = record
    labels = {}
    for end, record in records.items():
        window = next(((start, finish) for start, finish in fy_windows if start <= end <= finish), None)
        if window is not None:
            index = 4 - round((window[1] - end).days / 91.3)
            if 1 <= index <= 4:
                labels[end] = (f"Q{index}", years[window[1]])
                continue
        next_label = _next_year_label(end, record, fy_windows, years)
        if next_label:
            labels[end] = next_label
        elif not fy_windows or end < fy_windows[0][0]:
            # Earliest history/IPO fallback only: a conflicting later fiscal hint must not
            # overwrite a known calendar, or turn a missing year into an invented quarter.
            fp, fy = record.get("first_fp"), record.get("first_fy")
            if fp in {"Q1", "Q2", "Q3", "Q4"}:
                labels[end] = (fp, fy if isinstance(fy, int) else end.year)
    return labels
