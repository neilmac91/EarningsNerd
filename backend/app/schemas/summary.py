from __future__ import annotations

import copy
import json
import math
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.utils.numbers import parse_display_number

_MISSING_STRINGS = {
    "",
    "n/a",
    "na",
    "not available",
    "not disclosed",
    "none",
    "-",
    "—",
    "--",
    "n.a.",
}

def _is_missing(value: Optional[str]) -> bool:
    if value is None:
        return True
    stripped = value.strip()
    if not stripped:
        return True
    return stripped.lower() in _MISSING_STRINGS


def _parse_numeric(value: Optional[str]) -> Optional[Decimal]:
    return parse_display_number(value)[0]


_XBRL_CONFIDENCE_NOTE = "Prior period from XBRL"


# Only whole, recognized labels may borrow a comparative. Qualifiers such as adjusted,
# pretax, growth or per-share expenses describe different measures and remain unmatched.
_PRIOR_METRIC_KEYS = {
    "net interest income": "net_interest_income",
    "non-interest income": "noninterest_income",
    "noninterest income": "noninterest_income",
    "net investment income": "net_investment_income",
    "premiums earned": "premiums_earned",
    "premium earned": "premiums_earned",
    "premiums earned (net)": "premiums_earned",
    "revenue": "revenue",
    "revenues": "revenue",
    "total revenue": "revenue",
    "total revenues": "revenue",
    "net sales": "revenue",
    "net income": "net_income",
    "gross profit": "gross_profit",
    "operating income": "operating_income",
    "net margin": "net_margin",
    "gross margin": "gross_margin",
    "operating margin": "operating_margin",
    "diluted eps": "eps_diluted",
    "eps (diluted)": "eps_diluted",
    "diluted earnings per share": "eps_diluted",
    "earnings per share (diluted)": "eps_diluted",
}


def _infer_xbrl_metric(metric_name: str) -> Optional[str]:
    if not metric_name:
        return None
    return _PRIOR_METRIC_KEYS.get(" ".join(metric_name.lower().split()))


def _format_xbrl_value(metric_key: str, value: float) -> str:
    if metric_key in ("earnings_per_share", "eps_diluted"):
        return f"${value:,.2f}"
    if metric_key in ("net_margin", "gross_margin", "operating_margin"):
        return f"{value:.1f}%"
    return f"${value:,.0f}"


def _is_missing_number(value: Optional[Decimal]) -> bool:
    if value is None:
        return True
    if isinstance(value, Decimal):
        return value.is_nan()
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return True


class NormalizedFact(BaseModel):
    metric: str
    current_period: Optional[str] = Field(default=None, alias="currentPeriod")
    prior_period: Optional[str] = Field(default=None, alias="priorPeriod")
    commentary: Optional[str] = None
    current_value: Optional[Decimal] = Field(default=None, alias="currentValue")
    prior_value: Optional[Decimal] = Field(default=None, alias="priorValue")
    delta_value: Optional[Decimal] = Field(default=None, alias="deltaValue")
    delta_percent: Optional[Decimal] = Field(default=None, alias="deltaPercent")

    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={Decimal: lambda v: float(v) if v is not None and not math.isnan(float(v)) else None},
    )

    @model_validator(mode="after")
    def _derive_values(cls, model: "NormalizedFact") -> "NormalizedFact":
        current_period = model.current_period
        prior_period = model.prior_period

        if model.current_value is None:
            model.current_value = _parse_numeric(current_period)

        if model.prior_value is None:
            model.prior_value = _parse_numeric(prior_period)

        current_value = model.current_value
        prior_value = model.prior_value

        if isinstance(current_value, (int, float, str)) and not isinstance(current_value, Decimal):
            try:
                current_value = Decimal(str(current_value))
            except (InvalidOperation, TypeError, ValueError):
                current_value = None
            model.current_value = current_value

        if isinstance(prior_value, (int, float, str)) and not isinstance(prior_value, Decimal):
            try:
                prior_value = Decimal(str(prior_value))
            except (InvalidOperation, TypeError, ValueError):
                prior_value = None
            model.prior_value = prior_value

        if _is_missing_number(current_value):
            current_value = None
            model.current_value = None
        if _is_missing_number(prior_value):
            prior_value = None
            model.prior_value = None

        if current_value is None or prior_value is None:
            model.delta_value = None
            model.delta_percent = None
            return model

        delta_value = current_value - prior_value
        model.delta_value = delta_value

        if prior_value == 0:
            model.delta_percent = None
        else:
            model.delta_percent = (delta_value / abs(prior_value)) * Decimal("100")

        return model


class SummarySchema(BaseModel):
    metrics: list[NormalizedFact] = Field(default_factory=list)
    notes: Optional[str] = None
    has_prior_period: bool = Field(default=True, alias="hasPriorPeriod")

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def _flag_missing_prior(cls, model: "SummarySchema") -> "SummarySchema":
        metrics: Iterable[NormalizedFact] = model.metrics or []
        has_prior_period = True
        for metric in metrics:
            prior_period_value = getattr(metric, "prior_period", None)
            if isinstance(prior_period_value, str):
                missing_prior_period = _is_missing(prior_period_value)
            else:
                missing_prior_period = prior_period_value is None

            if missing_prior_period or _is_missing_number(getattr(metric, "prior_value", None)):
                has_prior_period = False
                break

        model.has_prior_period = has_prior_period
        return model


def attach_normalized_facts(
    financial_section: Optional[dict[str, Any]],
    xbrl_metrics: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """
    Attach normalized financial facts to the provided financial highlights section.

    Returns a defensive copy of the input dictionary with a `normalized` key added
    when normalization is successful.
    """
    if not isinstance(financial_section, dict):
        return financial_section

    table = financial_section.get("table")
    if not isinstance(table, list):
        summary = SummarySchema(notes=financial_section.get("notes"), metrics=[])
    else:
        metrics: list[NormalizedFact] = []
        normalized_rows: list[dict[str, Any]] = []

        for row in table:
            row_dict: Optional[dict[str, Any]] = None

            if isinstance(row, NormalizedFact):
                row_dict = row.model_dump(by_alias=True)
            elif hasattr(row, "model_dump") and callable(getattr(row, "model_dump")):
                model_dump = row.model_dump()
                if isinstance(model_dump, dict):
                    row_dict = model_dump
            elif isinstance(row, dict):
                row_dict = dict(row)

            if not isinstance(row_dict, dict):
                continue

            metric_name = (
                row_dict.get("metric")
                or row_dict.get("Metric")
            )
            if not metric_name:
                continue

            current_period = (
                row_dict.get("current_period")
                or row_dict.get("currentPeriod")
            )
            prior_period = (
                row_dict.get("prior_period")
                or row_dict.get("priorPeriod")
            )
            commentary = row_dict.get("commentary")

            fact = NormalizedFact(
                metric=metric_name,
                current_period=current_period,
                prior_period=prior_period,
                commentary=commentary,
            )

            xbrl_key = _infer_xbrl_metric(metric_name)
            # Issuers also use "Gross margin" for currency amounts. Percentage
            # XBRL comparisons require an explicitly percentage-valued current row.
            if xbrl_key in ("net_margin", "gross_margin", "operating_margin") and not parse_display_number(current_period)[1]:
                xbrl_key = None
            prior_filled_from_xbrl = False

            if xbrl_metrics and xbrl_key:
                metric_info = xbrl_metrics.get(xbrl_key) or {}
                # Surface the per-ADS EPS block (ADS-ratio correctness layer) onto the row so it
                # reaches the frontend. Purely additive — a new `per_ads` key; it never alters the
                # as-filed per-ordinary-share `current_period`, so it can't regress the eval baseline.
                # Present only on the EPS row of ratio != 1 ADRs (else metric_info has no per_ads).
                per_ads = metric_info.get("per_ads")
                if isinstance(per_ads, dict):
                    row_dict["per_ads"] = per_ads
                prior_entry = metric_info.get("prior")
                if prior_entry and prior_entry.get("value") is not None:
                    prior_value_raw = prior_entry.get("value")
                    try:
                        prior_value_decimal = Decimal(str(prior_value_raw))
                    except (InvalidOperation, TypeError, ValueError):
                        prior_value_decimal = None

                    prior_value_applied = False
                    if prior_value_decimal is not None and fact.prior_value is None:
                        fact.prior_value = prior_value_decimal
                        prior_value_applied = True

                    if _is_missing(prior_period):
                        formatted_prior = _format_xbrl_value(xbrl_key, prior_value_raw)
                        fact.prior_period = formatted_prior
                        row_dict["prior_period"] = formatted_prior
                        row_dict["priorPeriod"] = formatted_prior
                        prior_filled_from_xbrl = True

                    if (prior_filled_from_xbrl or prior_value_applied) and _XBRL_CONFIDENCE_NOTE not in (fact.commentary or ""):
                        fact.commentary = (
                            f"{fact.commentary}\n{_XBRL_CONFIDENCE_NOTE}"
                            if fact.commentary
                            else _XBRL_CONFIDENCE_NOTE
                        )
                        row_dict["commentary"] = fact.commentary

            metrics.append(fact)

            for key, value in list(row_dict.items()):
                if isinstance(value, Decimal):
                    row_dict[key] = float(value)

            normalized_rows.append(row_dict)

        if normalized_rows:
            table = normalized_rows

        summary = SummarySchema(notes=financial_section.get("notes"), metrics=metrics)

    section_copy = copy.deepcopy(financial_section)
    if isinstance(table, list):
        section_copy["table"] = table
    section_copy["normalized"] = json.loads(summary.model_dump_json(by_alias=True))
    return section_copy

