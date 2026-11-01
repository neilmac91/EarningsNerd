"""Dashboard feed — deterministic "what changed" delta (pure) + feed composition (DB)."""
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.dashboard_feed_service import compose_feed, compute_what_changed


def _series(*pairs):
    """[(period, value), ...] -> xbrl series list."""
    return [{"period": p, "value": v, "form": "10-Q", "accn": "x"} for p, v in pairs]


# --------------------------------------------------------------------------- pure delta

def test_revenue_and_net_income_headline():
    current = {"revenue": _series(("2024-03-31", 100.0)), "net_income": _series(("2024-03-31", 20.0))}
    prior = {"revenue": _series(("2023-03-31", 80.0)), "net_income": _series(("2023-03-31", 25.0))}
    out = compute_what_changed(current, prior)
    assert out is not None
    assert out["data_quality"] == "ok"
    assert "Revenue up 25.0%" in out["headline"]
    assert "Net income down 20.0%" in out["headline"]
    metrics = {i["metric"]: i for i in out["items"]}
    assert metrics["revenue"]["direction"] == "up"
    assert metrics["net_income"]["direction"] == "down"
    # T1.5: chips carry the single-source display string + tone (no client-side formatting).
    assert metrics["revenue"]["display"] == "+25.0%" and metrics["revenue"]["tone"] == "gain"
    assert metrics["net_income"]["display"] == "−20.0%" and metrics["net_income"]["tone"] == "loss"


def test_negative_revenue_is_dropped_partial():
    current = {"revenue": _series(("2024-03-31", -5.0)), "net_income": _series(("2024-03-31", 20.0))}
    prior = {"revenue": _series(("2023-03-31", 80.0)), "net_income": _series(("2023-03-31", 10.0))}
    out = compute_what_changed(current, prior)
    assert out["data_quality"] == "partial"
    assert all(i["metric"] != "revenue" for i in out["items"])
    assert any(i["metric"] == "net_income" for i in out["items"])


def test_eps_netincome_sign_mismatch_drops_both():
    # Positive EPS but a net loss → distrust both.
    current = {
        "revenue": _series(("2024-03-31", 100.0)),
        "net_income": _series(("2024-03-31", -10.0)),
        "earnings_per_share": _series(("2024-03-31", 1.5)),
    }
    prior = {
        "revenue": _series(("2023-03-31", 90.0)),
        "net_income": _series(("2023-03-31", -5.0)),
        "earnings_per_share": _series(("2023-03-31", 1.0)),
    }
    out = compute_what_changed(current, prior)
    assert out["data_quality"] == "partial"
    present = {i["metric"] for i in out["items"]}
    assert "earnings_per_share" not in present
    assert "net_income" not in present
    assert "revenue" in present  # revenue survives


def test_negative_prior_revenue_is_dropped_partial():
    # A corrupt (negative) prior revenue must also invalidate the metric.
    current = {"revenue": _series(("2024-03-31", 100.0)), "net_income": _series(("2024-03-31", 20.0))}
    prior = {"revenue": _series(("2023-03-31", -80.0)), "net_income": _series(("2023-03-31", 10.0))}
    out = compute_what_changed(current, prior)
    assert out["data_quality"] == "partial"
    assert all(i["metric"] != "revenue" for i in out["items"])


def test_prior_eps_netincome_sign_mismatch_drops_both():
    # Prior period has positive EPS but a net loss → distrust both, even if current is consistent.
    current = {
        "net_income": _series(("2024-03-31", 10.0)),
        "earnings_per_share": _series(("2024-03-31", 0.5)),
    }
    prior = {
        "net_income": _series(("2023-03-31", -5.0)),
        "earnings_per_share": _series(("2023-03-31", 1.0)),
    }
    out = compute_what_changed(current, prior)
    assert out is None or out["data_quality"] == "partial"
    if out is not None:
        present = {i["metric"] for i in out["items"]}
        assert "earnings_per_share" not in present and "net_income" not in present


def test_matching_negative_signs_are_kept():
    # Net loss with negative EPS is internally consistent → kept.
    current = {"net_income": _series(("2024-03-31", -10.0)), "earnings_per_share": _series(("2024-03-31", -0.5))}
    prior = {"net_income": _series(("2023-03-31", -5.0)), "earnings_per_share": _series(("2023-03-31", -0.2))}
    out = compute_what_changed(current, prior)
    assert {i["metric"] for i in out["items"]} == {"net_income", "earnings_per_share"}


def test_in_instance_comparative_used_when_no_prior_filing():
    # No prior filing: an annual report's own prior year is the year its basis names ("Year over year"); an interim
    # report's own comparative is the year-ago quarter, never the quarter "Quarter over quarter" names (E261).
    current = {"revenue": _series(("2024-03-31", 120.0), ("2023-03-31", 100.0))}
    out = compute_what_changed(current, None, form="10-K")
    assert out is not None
    assert out["items"][0]["direction"] == "up"
    assert out["items"][0]["pct"] == 20.0
    assert compute_what_changed(current, None, form="10-Q") is None
    assert compute_what_changed(current, None) is None


def test_prior_filing_in_another_reporting_currency_is_never_differenced():
    # An issuer that switched to EUR restates its comparatives in EUR, so the delta comes from its
    # own filing's comparative (96), never from the prior filing's USD amount (100).
    current = {"reporting_currency": "EUR", "revenue": _series(("2024-12-31", 120.0), ("2023-12-31", 96.0))}
    prior = {"reporting_currency": "USD", "revenue": _series(("2023-12-31", 100.0))}
    item = compute_what_changed(current, prior, prior_period_end="2023-12-31", form="10-K")["items"][0]
    assert (item["current"], item["prior"], item["pct"]) == (120.0, 96.0, 25.0)
    # With no comparative of its own, the metric is withheld rather than compared across currencies.
    assert compute_what_changed(
        {**current, "revenue": _series(("2024-12-31", 120.0))}, prior, prior_period_end="2023-12-31", form="10-K"
    ) is None


def test_currency_guard_needs_two_known_and_different_currencies():
    # No comparative of its own (which every line would take first, E261), so the prior filing's amount shows.
    current = {"revenue": _series(("2024-12-31", 120.0))}
    prior = {"revenue": _series(("2023-12-31", 100.0))}
    for current_currency, prior_currency in (
        ("USD", "usd"), ("CNY", "RMB"), ("EUR", None), (None, "USD"), ("EUR", "pure"), ("EUR", "US Dollars"),
    ):
        out = compute_what_changed(
            {**current, "reporting_currency": current_currency}, {**prior, "reporting_currency": prior_currency}
        )
        assert out["items"][0]["prior"] == 100.0, (current_currency, prior_currency)


def test_missing_xbrl_returns_none():
    assert compute_what_changed(None, None) is None
    assert compute_what_changed({}, {}) is None


def test_no_prior_returns_none():
    # Single period, no prior anywhere → nothing to compare.
    assert compute_what_changed({"revenue": _series(("2024-03-31", 100.0))}, None) is None


# --------------------------------------------------------------------------- E259: the one EPS line
# A Q2 10-Q (quarter ended 2026-06-30) as the instance extractor stores it since P1.5: each series holds the quarter
# and its year-ago comparative. Its prior filing is the 10-Q for the quarter ended 2026-03-31.
_Q2 = {
    "net_income": _series(("2026-06-30", 12.0), ("2025-06-30", 8.0)),
    "earnings_per_share": _series(("2026-06-30", 1.02), ("2025-06-30", 0.81)),
    "eps_diluted": _series(("2026-06-30", 1.00), ("2025-06-30", 0.80)),
}
_Q1 = {
    "net_income": _series(("2026-03-31", 10.0)),
    "earnings_per_share": _series(("2026-03-31", 0.92)),
    "eps_diluted": _series(("2026-03-31", 0.90)),
}
_EPS_KEYS = ("eps_diluted", "earnings_per_share")


def _eps_items(out):
    return [(i["metric"], i["label"], i["current"], i["prior"]) for i in out["items"] if i["metric"] in _EPS_KEYS]


def test_eps_line_is_diluted_when_both_filings_carry_it():
    # Chief design's ruling on #1862: What changed carries the diluted line, named as /analysis names it, in its
    # rows and in the headline, after net income (the headline's first two items, in _DELTA_METRICS order).
    out = compute_what_changed(_Q2, _Q1)
    assert _eps_items(out) == [("eps_diluted", "EPS (diluted)", 1.00, 0.90)]
    assert [i["metric"] for i in out["items"]] == ["net_income", "eps_diluted"]
    assert out["headline"] == "Net income up 20.0%; EPS (diluted) up 11.1%"
    assert out["data_quality"] == "ok"


def test_eps_line_takes_one_key_for_both_sides_and_basic_when_a_side_has_no_diluted_series():
    # A blob stored before P1.5 (2026-06-14), or by the companyfacts fallback before E260's second pull request, has
    # no eps_diluted; any other blob has an empty one when no diluted figure was found. Two 10-Qs share no period, so
    # either side without it puts the pair on the basic line, its prior the prior filing's quarter: never the current
    # filing's year-ago diluted 0.80 (a plain key swap's pair).
    for current, prior in (
        (_Q2, {k: v for k, v in _Q1.items() if k != "eps_diluted"}),  # the prior predates P1.5
        (_Q2, {**_Q1, "eps_diluted": []}),  # the prior's diluted series is empty
        ({k: v for k, v in _Q2.items() if k != "eps_diluted"}, _Q1),  # the current predates P1.5
        ({**_Q2, "eps_diluted": []}, _Q1),  # the current's diluted series is empty
    ):
        out = compute_what_changed(current, prior)
        assert _eps_items(out) == [("earnings_per_share", "EPS (basic)", 1.02, 0.92)]
        assert all(i["prior"] not in (0.80, 0.81) for i in out["items"])
    # A pair shaped like the companyfacts fallback's before E260's second pull request: basic EPS only, with no
    # eps_diluted key and no raw_tag on either side.
    out = compute_what_changed(
        {"earnings_per_share": _series(("2026-06-30", 1.02))}, {"earnings_per_share": _series(("2026-03-31", 0.92))}
    )
    assert _eps_items(out) == [("earnings_per_share", "EPS (basic)", 1.02, 0.92)]
    assert out["headline"] == "EPS (basic) up 10.9%"


def test_eps_line_never_takes_another_period_than_the_prior_filings():
    # The prior 10-Q's XBRL has no EPS for the quarter it reported. The current 10-Q's own comparative is the
    # year-ago quarter, which would sit under "Quarter over quarter, against the 10-Q for the quarter ended Mar 31",
    # and the prior's own year-ago EPS is another quarter too, so the EPS line is withheld; net income still
    # differs against the prior filing's quarter.
    for prior in (
        {"net_income": _Q1["net_income"]},
        {**_Q1, "earnings_per_share": [], "eps_diluted": []},
        {**_Q1, "earnings_per_share": _series(("2026-06-30", 1.02)), "eps_diluted": _series(("2026-06-30", 1.00))},
        {**_Q1, "earnings_per_share": _series(("2025-03-31", 0.70)), "eps_diluted": _series(("2025-03-31", 0.69))},
    ):
        out = compute_what_changed(_Q2, prior)
        assert _eps_items(out) == []
        assert [(i["metric"], i["prior"]) for i in out["items"]] == [("net_income", 10.0)]
        assert out["data_quality"] == "ok"
    # The withheld line still checks net income's current sign (invariant 2), as the basic line did before.
    loss = {**_Q2, "net_income": _series(("2026-06-30", -12.0)), "revenue": _series(("2026-06-30", 100.0))}
    out = compute_what_changed(loss, {"net_income": _Q1["net_income"], "revenue": _series(("2026-03-31", 90.0))})
    assert [i["metric"] for i in out["items"]] == ["revenue"] and out["data_quality"] == "partial"


def test_eps_line_without_a_prior_filing_takes_the_filings_own_comparative():
    # An annual report with no prior XBRL (the company's first filing here, a prior filing never extracted, or one
    # in another reporting currency) takes its own prior year on every line, the EPS line's too, diluted where that
    # series has one, else basic. An interim report's own comparative is the year-ago quarter, so it compares
    # nothing: not under "Quarter over quarter" (E261).
    annual = {k: [{**e, "form": "10-K"} for e in v] for k, v in _Q2.items()}
    assert _eps_items(compute_what_changed(annual, None, form="10-K")) == [("eps_diluted", "EPS (diluted)", 1.00, 0.80)]
    only_basic_comparative = {**annual, "eps_diluted": _series(("2026-06-30", 1.00))}
    assert _eps_items(compute_what_changed(only_basic_comparative, None, form="10-K")) == [
        ("earnings_per_share", "EPS (basic)", 1.02, 0.81)
    ]
    for prior, period_end in ((None, None), (None, "2026-03-31"), ({}, "2026-03-31"), ({}, None)):
        assert compute_what_changed(_Q2, prior, prior_period_end=period_end, form="10-Q") is None
    # A reporting-currency change discards the prior filing's figures: the restated comparative stands in for the
    # year the prior 10-K reported, and the prior filing's USD diluted EPS (0.90) is never differenced against EUR.
    eur = {**annual, "reporting_currency": "EUR"}
    usd_prior = {**_Q1, "reporting_currency": "USD", "net_income": _series(("2025-06-30", 9.0))}
    out = compute_what_changed(eur, usd_prior, prior_period_end="2025-06-30", form="10-K")
    assert _eps_items(out) == [("eps_diluted", "EPS (diluted)", 1.00, 0.80)]
    assert compute_what_changed({**_Q2, "reporting_currency": "EUR"}, {**_Q1, "reporting_currency": "USD"},
                                prior_period_end="2026-03-31", form="10-Q") is None


def test_eps_line_takes_this_filings_restated_figure_for_the_prior_filings_period():
    # A 10:1 split between two 10-Ks. The prior 10-K reported FY2024 diluted EPS of 11.93; this 10-K restates that
    # year as 1.19. Both are the year the basis names ("Year over year, against the 10-K for the year ended Jan 31,
    # 2025"), so the restated figure is the like-for-like one: not "down 75.4%" beside net income up 144.6%.
    current = {
        "net_income": _series(("2026-01-31", 72.9), ("2025-01-31", 29.8)),
        "earnings_per_share": _series(("2026-01-31", 2.97), ("2025-01-31", 1.20)),
        "eps_diluted": _series(("2026-01-31", 2.94), ("2025-01-31", 1.19)),
    }
    prior = {
        "net_income": _series(("2025-01-31", 29.8)),
        "earnings_per_share": _series(("2025-01-31", 12.0)),
        "eps_diluted": _series(("2025-01-31", 11.93)),
    }
    out = compute_what_changed(current, prior)
    assert _eps_items(out) == [("eps_diluted", "EPS (diluted)", 2.94, 1.19)]
    assert out["headline"] == "Net income up 144.6%; EPS (diluted) up 147.1%"
    # A prior 10-K stored before P1.5 has no diluted series: this 10-K's own figure for that year completes the
    # diluted pair, so an annual pair keeps the diluted line.
    pre_p15 = {k: v for k, v in prior.items() if k != "eps_diluted"}
    assert _eps_items(compute_what_changed(current, pre_p15)) == [("eps_diluted", "EPS (diluted)", 2.94, 1.19)]
    # A 1:10 reverse split: the restated year (11.9) sits far above the prior 10-K's as-filed basic EPS (1.20), so
    # it is checked against this filing's own basic EPS for that year (12.0), never against the prior filing's.
    reverse = {
        "net_income": _series(("2026-01-31", 72.9), ("2025-01-31", 29.8)),
        "earnings_per_share": _series(("2026-01-31", 29.7), ("2025-01-31", 12.0)),
        "eps_diluted": _series(("2026-01-31", 29.4), ("2025-01-31", 11.9)),
    }
    as_filed = {
        "net_income": _series(("2025-01-31", 29.8)),
        "earnings_per_share": _series(("2025-01-31", 1.20)),
        "eps_diluted": _series(("2025-01-31", 1.19)),
    }
    assert _eps_items(compute_what_changed(reverse, as_filed)) == [("eps_diluted", "EPS (diluted)", 29.4, 11.9)]


def test_a_diluted_pair_above_basic_falls_to_the_basic_line():
    # Diluted EPS cannot exceed basic EPS for the same period (the check facts/reconcile.py makes); a series that
    # does is not what its key says, so the line falls to basic, on either side.
    for current, prior in (
        ({**_Q2, "eps_diluted": _series(("2026-06-30", 1.10), ("2025-06-30", 0.80))}, _Q1),
        (_Q2, {**_Q1, "eps_diluted": _series(("2026-03-31", 0.95))}),
    ):
        out = compute_what_changed(current, prior)
        assert _eps_items(out) == [("earnings_per_share", "EPS (basic)", 1.02, 0.92)]
        assert out["data_quality"] == "ok"
    # Equal figures, as in a loss year or with nothing dilutive, keep the diluted line; half a cent above basic is above.
    equal = {**_Q2, "eps_diluted": _series(("2026-06-30", 1.02), ("2025-06-30", 0.81))}
    equal_prior = {**_Q1, "eps_diluted": _series(("2026-03-31", 0.92))}
    assert _eps_items(compute_what_changed(equal, equal_prior)) == [("eps_diluted", "EPS (diluted)", 1.02, 0.92)]
    above = {**_Q2, "eps_diluted": _series(("2026-06-30", 1.025), ("2025-06-30", 0.80))}
    assert _eps_items(compute_what_changed(above, _Q1)) == [("earnings_per_share", "EPS (basic)", 1.02, 0.92)]


def test_invariant_two_holds_a_restated_prior_year_to_its_own_net_income():
    # This 10-K restates FY2024 to a loss the prior 10-K reported as a profit. The EPS line's prior side is the
    # restated figure, so invariant 2 holds it to the restated net income for that year, never to the prior 10-K's
    # as-reported one, and nothing is withheld.
    current = {
        "revenue": _series(("2025-12-31", 100.0), ("2024-12-31", 90.0)),
        "net_income": _series(("2025-12-31", 30.0), ("2024-12-31", -2.0)),
        "earnings_per_share": _series(("2025-12-31", 0.30), ("2024-12-31", -0.02)),
    }
    prior = {
        "revenue": _series(("2024-12-31", 90.0)),
        "net_income": _series(("2024-12-31", 5.0)),
        "earnings_per_share": _series(("2024-12-31", 0.05)),
    }
    out = compute_what_changed(current, prior)
    assert _eps_items(out) == [("earnings_per_share", "EPS (basic)", 0.30, -0.02)]
    assert [i["metric"] for i in out["items"]] == ["revenue", "net_income", "earnings_per_share"]
    assert out["data_quality"] == "ok"


def test_a_stale_eps_series_never_stands_for_the_filings_period():
    # An unusable diluted figure for the quarter leaves its year-ago entry newest: it never stands for this quarter.
    unusable = [{"period": "2026-06-30", "value": True, "form": "10-Q", "accn": "x"}] + _series(("2025-06-30", 0.80))
    out = compute_what_changed({**_Q2, "eps_diluted": unusable}, _Q1)
    assert _eps_items(out) == [("earnings_per_share", "EPS (basic)", 1.02, 0.92)]
    # A filing whose EPS stops a period before its net income shows no EPS line.
    out = compute_what_changed(
        {"net_income": _Q2["net_income"], "earnings_per_share": _series(("2025-06-30", 0.81))}, _Q1
    )
    assert _eps_items(out) == [] and [i["metric"] for i in out["items"]] == ["net_income"]


def test_invariant_two_holds_net_income_to_basic_eps_where_the_filing_reports_it():
    revenue = {"revenue": _series(("2026-06-30", 100.0))}, {"revenue": _series(("2026-03-31", 90.0))}
    # A diluted line with no basic series to check against: its sign disagrees with net income, so both go.
    current = {**revenue[0], "net_income": _series(("2026-06-30", -12.0)), "eps_diluted": _series(("2026-06-30", 1.00))}
    prior = {**revenue[1], "net_income": _series(("2026-03-31", -10.0)), "eps_diluted": _series(("2026-03-31", 0.90))}
    out = compute_what_changed(current, prior)
    assert [i["metric"] for i in out["items"]] == ["revenue"] and out["data_quality"] == "partial"
    # A warrant liability's fair-value gain: net income and basic EPS above zero, diluted EPS below it (the diluted
    # numerator leaves the gain out). Basic EPS agrees with net income, so nothing is withheld, and the diluted line
    # shows the diluted figures.
    current = {
        **revenue[0],
        "net_income": _series(("2026-06-30", 5.0)),
        "earnings_per_share": _series(("2026-06-30", 0.05)),
        "eps_diluted": _series(("2026-06-30", -0.09)),
    }
    prior = {
        **revenue[1],
        "net_income": _series(("2026-03-31", 4.0)),
        "earnings_per_share": _series(("2026-03-31", 0.04)),
        "eps_diluted": _series(("2026-03-31", 0.04)),
    }
    out = compute_what_changed(current, prior)
    assert _eps_items(out) == [("eps_diluted", "EPS (diluted)", -0.09, 0.04)]
    assert [i["metric"] for i in out["items"]] == ["revenue", "net_income", "eps_diluted"]
    assert out["data_quality"] == "ok"
    # The same gain in the prior quarter: that filing's basic EPS agrees with its net income, so nothing is withheld.
    current = {
        **revenue[0],
        "net_income": _series(("2026-06-30", 5.0)),
        "earnings_per_share": _series(("2026-06-30", 0.05)),
        "eps_diluted": _series(("2026-06-30", 0.04)),
    }
    prior = {
        **revenue[1],
        "net_income": _series(("2026-03-31", 4.0)),
        "earnings_per_share": _series(("2026-03-31", 0.04)),
        "eps_diluted": _series(("2026-03-31", -0.03)),
    }
    out = compute_what_changed(current, prior)
    assert _eps_items(out) == [("eps_diluted", "EPS (diluted)", 0.04, -0.03)] and out["data_quality"] == "ok"
    # The basic line shown (the prior has no diluted series) disagrees in the prior period: basic and net income go,
    # and the current filing's diluted series does not take its place.
    prior = {**revenue[1], "net_income": _series(("2026-03-31", -10.0)), "earnings_per_share": _series(("2026-03-31", 0.92))}
    out = compute_what_changed({**_Q2, **revenue[0]}, prior)
    assert [i["metric"] for i in out["items"]] == ["revenue"] and out["data_quality"] == "partial"


# --------------------------------------------------------------------------- E261: one comparison period
# Every line compares this filing's own period with ONE comparison period: the prior filing's period of report (the
# date the change report's basis line prints), else the newest period the prior filing's XBRL reports, else for an
# annual report its own year before. A line's prior side is this filing's own figure for that period where it reports
# one, else the prior filing's; a line with neither is withheld.

# The rule 12 gate: each figure encodes its period (YYYYMMDD plus the metric's offset), so a line's prior decodes to
# the period it came from, and every line of a report decodes to the one period its basis names, or none shows.
_OFFSET = {"revenue": 0.0, "net_income": 0.1, "earnings_per_share": 0.2, "eps_diluted": 0.15}


def _encoded(*periods, metrics=tuple(_OFFSET)):
    return {metric: _series(*((p, float(p.replace("-", "")) + _OFFSET[metric]) for p in periods)) for metric in metrics}


_NOTE_YEAR = ("2025-12-31", "2025-09-30", "2025-06-30", "2025-03-31", "2024-12-31")  # a 10-K with a quarterly note
_ONE_PERIOD_SCENARIOS = {
    # name: (current blob, prior blob, prior period of report, form, the period every prior decodes to, or None)
    "quarter, prior quarter extracted": (
        _encoded("2026-06-30", "2025-06-30"), _encoded("2026-03-31", "2025-03-31"), "2026-03-31", "10-Q", "20260331"),
    "quarter, prior quarter partly extracted": (
        _encoded("2026-06-30", "2025-06-30"), _encoded("2026-03-31", metrics=("revenue",)), "2026-03-31", "10-Q",
        "20260331"),
    "quarter, prior quarter never extracted": (_encoded("2026-06-30", "2025-06-30"), None, "2026-03-31", "10-Q", None),
    "quarter, no prior filing": (_encoded("2026-06-30", "2025-06-30"), None, None, "10-Q", None),
    "quarter, prior in another currency": (
        {**_encoded("2026-06-30", "2025-06-30"), "reporting_currency": "EUR"},
        {**_encoded("2026-03-31"), "reporting_currency": "USD"}, "2026-03-31", "10-Q", None),
    "year, prior year extracted": (
        _encoded("2025-12-31", "2024-12-31", "2023-12-31"), _encoded("2024-12-31", "2023-12-31"), "2024-12-31", "10-K",
        "20241231"),
    "year, prior never extracted, quarterly note": (_encoded(*_NOTE_YEAR), None, "2024-12-31", "10-K", "20241231"),
    "year, no prior filing, quarterly note": (_encoded(*_NOTE_YEAR), None, None, "10-K", "20241231"),
    "year, period of report a few days off": (_encoded("2025-09-27", "2024-09-28"), None, "2024-09-30", "10-K", "20240928"),
    "year, prior a year behind its own comparatives": (
        _encoded("2025-12-31", "2024-12-31", "2023-12-31"), None, "2023-12-31", "10-K", "20231231"),
}


@pytest.mark.parametrize("name", list(_ONE_PERIOD_SCENARIOS))
def test_every_line_compares_the_one_period_its_basis_names(name):
    current, prior, prior_end, form, expected = _ONE_PERIOD_SCENARIOS[name]
    out = compute_what_changed(current, prior, prior_period_end=prior_end, form=form)
    assert {str(int(i["prior"])) for i in (out or {}).get("items", [])} == ({expected} if expected else set())


def test_a_restated_year_puts_every_line_on_this_filings_own_figures():
    # This 10-K restates FY2024 (revenue recast to 85, net income to a loss). Every line takes the restated figure for
    # the year the basis names, never the prior 10-K's as-filed 90 beside a restated EPS.
    current = {
        "revenue": _series(("2025-12-31", 100.0), ("2024-12-31", 85.0)),
        "net_income": _series(("2025-12-31", 30.0), ("2024-12-31", -2.0)),
        "earnings_per_share": _series(("2025-12-31", 0.30), ("2024-12-31", -0.02)),
    }
    prior = {
        "revenue": _series(("2024-12-31", 90.0)),
        "net_income": _series(("2024-12-31", 5.0)),
        "earnings_per_share": _series(("2024-12-31", 0.05)),
    }
    out = compute_what_changed(current, prior, prior_period_end="2024-12-31", form="10-K")
    assert [(i["metric"], i["prior"], i["current"]) for i in out["items"]] == [
        ("revenue", 85.0, 100.0), ("net_income", -2.0, 30.0), ("earnings_per_share", -0.02, 0.30),
    ]


def _earnings(period, net_income, eps):
    return {"net_income": _series((period, net_income)), "earnings_per_share": _series((period, eps))}


def test_eps_is_never_differenced_across_a_share_split():
    # A 10:1 split between two 10-Qs: EPS falls tenfold while net income rises 12%. The EPS line is withheld and the
    # report marked partial; net income stands (invariant 3).
    q2 = {**_earnings("2026-06-30", 16599.0, 0.68), "eps_diluted": _series(("2026-06-30", 0.67))}
    q1 = {**_earnings("2026-03-31", 14881.0, 6.04), "eps_diluted": _series(("2026-03-31", 5.98))}
    out = compute_what_changed(q2, q1)
    assert [(i["metric"], i["prior"]) for i in out["items"]] == [("net_income", 14881.0)]
    assert out["data_quality"] == "partial"
    # A 1:10 reverse split, a 3-for-2 split (exactly 1.5x), and a micro-cap's reverse split at a few cents of EPS.
    for current, prior in (((110.0, 11.0), (100.0, 1.00)), ((157.5, 1.05), (150.0, 1.50)), ((-1.1, -0.45), (-1.0, -0.02))):
        out = compute_what_changed(_earnings("2026-06-30", *current), _earnings("2026-03-31", *prior))
        assert [i["metric"] for i in out["items"]] == ["net_income"], (current, prior)
    # A quarter's buybacks, a cent of EPS whose rounding cannot tell, and a 3-for-2 split at a dime of EPS, where half a
    # cent either way cannot prove the move (the guard withholds only a proved split), keep the line.
    for current, prior in (((103.0, 1.06), (100.0, 1.00)), ((1.6, 0.02), (1.0, 0.01)), ((15.0, 0.10), (15.0, 0.15))):
        out = compute_what_changed(_earnings("2026-06-30", *current), _earnings("2026-03-31", *prior))
        assert [i["metric"] for i in out["items"]] == ["net_income", "earnings_per_share"], (current, prior)
        assert out["data_quality"] == "ok"
    # This filing's own figures are on its own share basis, so its own prior year is never held to the check: a real
    # doubling of the share count between its two years (a stock-funded acquisition) keeps the EPS line.
    k = {"net_income": _series(("2025-12-31", 300.0), ("2024-12-31", 100.0)),
         "earnings_per_share": _series(("2025-12-31", 1.50), ("2024-12-31", 1.00))}
    out = compute_what_changed(k, None, prior_period_end="2024-12-31", form="10-K")
    assert [(i["metric"], i["prior"], i["current"]) for i in out["items"]] == [
        ("net_income", 100.0, 300.0), ("earnings_per_share", 1.00, 1.50),
    ]
    assert out["data_quality"] == "ok"


def test_a_diluted_pair_across_a_split_gives_way_to_the_filings_own_basic_pair():
    # A 10-K after a 2:1 split: its blob holds diluted EPS for its own year only, and basic EPS for both years, the
    # prior one restated. The diluted pair takes its prior from the prior 10-K, before the split, so the guard refuses
    # it; the basic pair is this filing's own figures for both years, on one share basis, and shows instead.
    k = {"net_income": _series(("2025-12-31", 100.0), ("2024-12-31", 90.0)),
         "earnings_per_share": _series(("2025-12-31", 1.00), ("2024-12-31", 0.90)),
         "eps_diluted": _series(("2025-12-31", 0.99))}
    prior = {"net_income": _series(("2024-12-31", 90.0)),
             "earnings_per_share": _series(("2024-12-31", 1.80)),
             "eps_diluted": _series(("2024-12-31", 1.79))}
    out = compute_what_changed(k, prior, prior_period_end="2024-12-31", form="10-K")
    assert [(i["metric"], i["prior"], i["current"]) for i in out["items"]] == [
        ("net_income", 90.0, 100.0), ("earnings_per_share", 0.90, 1.00),
    ]
    assert out["data_quality"] == "ok"
    # With no clean pair to fall to, the split pair is withheld and the report marked, as before.
    out = compute_what_changed({**k, "earnings_per_share": _series(("2025-12-31", 1.00))}, prior,
                               prior_period_end="2024-12-31", form="10-K")
    assert [i["metric"] for i in out["items"]] == ["net_income"] and out["data_quality"] == "partial"


def test_net_income_never_takes_the_year_ago_quarter():
    # The prior 10-Q reports revenue only. Net income's year-ago quarter, a loss beside positive EPS, used to stand in
    # for the prior quarter and fail invariant 2, withholding both lines. Now no line takes it.
    q2 = {"revenue": _series(("2026-06-30", 110.0)),
          "net_income": _series(("2026-06-30", 12.0), ("2025-06-30", -8.0)),
          "earnings_per_share": _series(("2026-06-30", 1.02), ("2025-06-30", 0.81))}
    out = compute_what_changed(q2, {"revenue": _series(("2026-03-31", 100.0))}, prior_period_end="2026-03-31", form="10-Q")
    assert [(i["metric"], i["prior"]) for i in out["items"]] == [("revenue", 100.0)] and out["data_quality"] == "ok"


def _spanning(period, value, days):
    """One figure ending ``period`` that runs ``days`` days (no start when ``days`` is None)."""
    [entry] = _series((period, value))
    if days is not None:
        entry["period_start"] = (date.fromisoformat(period) - timedelta(days=days)).isoformat()
    return [entry]


def test_a_line_never_compares_periods_of_different_lengths():
    # A 12-week quarter (84 days) against a 16-week one (112) or a half-year (182) is withheld. A 14-week quarter (98)
    # is within drift, and a figure without a start is taken as it is.
    current = {"revenue": _spanning("2026-08-15", 84.0, 84)}
    for prior_days, kept in ((112, False), (182, False), (84, True), (98, True), (None, True)):
        prior = {"revenue": _spanning("2026-05-23", 112.0, prior_days)}
        assert (compute_what_changed(current, prior) is not None) is kept, prior_days


def test_a_prior_period_within_drift_of_this_ones_compares_nothing():
    # A prior row dated a few days before this filing's own period (a re-filed quarter, a 52/53-week calendar), on it,
    # or after it names this filing's own period. The drift that matches a period of report to its context end would
    # match the filing's own figure, so nothing is compared, rather than a flat 0.0% against itself.
    q2 = {"revenue": _series(("2026-06-30", 110.0), ("2025-06-30", 90.0)),
          "net_income": _series(("2026-06-30", 12.0), ("2025-06-30", 8.0))}
    for prior_end in ("2026-06-27", "2026-06-30", "2026-07-15", "2026-09-30T00:00:00+00:00"):
        for form in ("10-Q", "10-K"):
            assert compute_what_changed(q2, None, prior_period_end=prior_end, form=form) is None, (prior_end, form)
    # A prior filing whose XBRL reports only this filing's own period names no prior period either.
    assert compute_what_changed(q2, {metric: series[:1] for metric, series in q2.items()}) is None


def test_a_series_that_stops_before_this_period_never_stands_for_it():
    # Net income's newest figure is the year-ago quarter: it stands for this quarter on neither side.
    current = {"revenue": _series(("2026-06-30", 110.0), ("2025-06-30", 90.0)), "net_income": _series(("2025-06-30", 8.0))}
    prior = {"revenue": _series(("2026-03-31", 100.0)), "net_income": _series(("2026-03-31", 10.0))}
    out = compute_what_changed(current, prior, prior_period_end="2026-03-31", form="10-Q")
    assert [(i["metric"], i["prior"], i["current"]) for i in out["items"]] == [("revenue", 100.0, 110.0)]


@pytest.mark.parametrize("year_before", ["2024-09-28", "2024-09-21"])  # FY2025 of 52 weeks (364 days) and 53 (371)
def test_a_52_or_53_week_year_is_one_year_back(year_before):
    current = {"revenue": _series(("2025-09-27", 120.0), ("2025-06-28", 31.0), (year_before, 100.0))}
    out = compute_what_changed(current, None, form="10-K")
    assert [(i["prior"], i["current"]) for i in out["items"]] == [(100.0, 120.0)]


def test_a_transition_period_or_two_years_back_is_not_the_year_before():
    # A fiscal-year change: the six-month transition period is no year, and the year before it ends 18 months back.
    # Two years back is not the year before either.
    for current in ({"revenue": _series(("2025-12-31", 120.0), ("2025-06-30", 55.0), ("2024-06-30", 100.0))},
                    {"revenue": _series(("2025-12-31", 120.0), ("2023-12-31", 100.0))}):
        assert compute_what_changed(current, None, form="10-K") is None


# E260: a blob extracted since E260 holds a diluted-only filer's EPS under eps_diluted alone, with an empty
# earnings_per_share; one extracted before (or by the companyfacts fallback before E260's second pull request) can
# hold that diluted figure under earnings_per_share and carry no eps_diluted.
_DILUTED_ONLY_Q2 = {"revenue": _series(("2026-06-30", 110.0)), "net_income": _series(("2026-06-30", 12.0)),
                    "earnings_per_share": [], "eps_diluted": _series(("2026-06-30", 1.00))}


def test_a_diluted_only_10q_against_a_prior_with_its_figure_under_the_basic_key_shows_no_eps_line():
    # No key carries both sides, so no EPS line shows, where the two were differenced as "EPS (basic)" before E260.
    prior = {"revenue": _series(("2026-03-31", 100.0)), "net_income": _series(("2026-03-31", 10.0)),
             "earnings_per_share": _series(("2026-03-31", 0.90))}
    out = compute_what_changed(_DILUTED_ONLY_Q2, prior, prior_period_end="2026-03-31", form="10-Q")
    assert _eps_items(out) == []
    assert [i["metric"] for i in out["items"]] == ["revenue", "net_income"] and out["data_quality"] == "ok"
    # A prior extracted since E260 carries the diluted figure too, and the pair is the diluted line.
    prior_since = {**prior, "earnings_per_share": [], "eps_diluted": _series(("2026-03-31", 0.90))}
    out = compute_what_changed(_DILUTED_ONLY_Q2, prior_since, prior_period_end="2026-03-31", form="10-Q")
    assert _eps_items(out) == [("eps_diluted", "EPS (diluted)", 1.00, 0.90)]


def test_a_diluted_only_10k_compares_its_diluted_figure_with_its_own_prior_year():
    k = {"net_income": _series(("2025-12-31", 300.0), ("2024-12-31", 250.0)), "earnings_per_share": [],
         "eps_diluted": _series(("2025-12-31", 1.50), ("2024-12-31", 1.25))}
    legacy_prior = {"net_income": _series(("2024-12-31", 250.0)), "earnings_per_share": _series(("2024-12-31", 1.25))}
    for prior in (None, legacy_prior):
        out = compute_what_changed(k, prior, prior_period_end="2024-12-31", form="10-K")
        assert _eps_items(out) == [("eps_diluted", "EPS (diluted)", 1.50, 1.25)], prior
        assert out["data_quality"] == "ok"


# --------------------------------------------------------------------------- composition (DB)

@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


@contextmanager
def _feed_scenario():
    from app.database import SessionLocal
    from app.models import Company, Filing, Summary, User, Watchlist

    db = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    user = User(email=f"feed-{suffix}@example.com", hashed_password="x", email_verified=True, is_active=True)
    company = Company(cik=f"cik{suffix}", ticker=f"T{suffix[:4].upper()}", name=f"Co {suffix}")
    db.add_all([user, company])
    db.commit()
    db.refresh(user)
    db.refresh(company)

    def _filing(accession, ftype, date_str, xbrl):
        return Filing(
            company_id=company.id,
            accession_number=accession,
            filing_type=ftype,
            filing_date=datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc),
            document_url=f"https://sec.example/{accession}/doc.htm",
            sec_url=f"https://sec.example/{accession}/",
            xbrl_data=xbrl,
        )

    older = _filing(f"{suffix}-old", "10-Q", "2023-03-31", {"revenue": _series(("2023-03-31", 80.0))})
    newer = _filing(f"{suffix}-new", "10-Q", "2024-03-31", {"revenue": _series(("2024-03-31", 100.0))})
    eightk = _filing(f"{suffix}-8k", "8-K", "2024-04-01", None)
    db.add_all([older, newer, eightk])
    db.commit()
    db.refresh(newer)
    # A ready summary for the newest filing.
    db.add(Summary(filing_id=newer.id, business_overview="A real overview of the business."))
    db.add(Watchlist(user_id=user.id, company_id=company.id))
    db.commit()

    ids = (user.id, company.id, newer.id, company.ticker)
    db.close()
    try:
        yield ids
    finally:
        db = SessionLocal()
        from app.models import Company, Filing, Summary, User, Watchlist
        fids = [f.id for f in db.query(Filing).filter(Filing.company_id == ids[1]).all()]
        db.query(Summary).filter(Summary.filing_id.in_(fids)).delete(synchronize_session=False)
        db.query(Watchlist).filter(Watchlist.user_id == ids[0]).delete(synchronize_session=False)
        db.query(Filing).filter(Filing.company_id == ids[1]).delete(synchronize_session=False)
        db.query(Company).filter(Company.id == ids[1]).delete(synchronize_session=False)
        db.query(User).filter(User.id == ids[0]).delete(synchronize_session=False)
        db.commit()
        db.close()


@contextmanager
def _multi_feed_scenario(company_specs, *, watchlist_all=True):
    """Build users/companies/filings/summaries for multi-company feed tests.

    ``company_specs``: one dict per company, in the order the companies are created:
        {
          "filings": [(label, filing_type, date_str, xbrl[, period_end]), ...],  # created in this order (id asc)
          "summary_labels": [label, ...],  # optional; filings that get a ready summary
        }
    Each filing ``label`` must be unique across the whole scenario. Yields a SimpleNamespace with
    ``user_id``, ``company_ids`` (creation order), ``tickers`` (creation order), and
    ``filing_ids`` (label -> id)."""
    from app.database import SessionLocal
    from app.models import Company, Filing, Summary, User, Watchlist

    db = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    user = User(email=f"multifeed-{suffix}@example.com", hashed_password="x", email_verified=True, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)

    company_ids: list[int] = []
    tickers: list[str] = []
    filing_ids: dict[str, int] = {}
    for ci, spec in enumerate(company_specs):
        company = Company(cik=f"cik{suffix}{ci}", ticker=f"T{suffix[:3].upper()}{ci}", name=f"Co {suffix} {ci}")
        db.add(company)
        db.commit()
        db.refresh(company)
        company_ids.append(company.id)
        tickers.append(company.ticker)
        for label, ftype, date_str, xbrl, *period_end in spec["filings"]:
            filing = Filing(
                company_id=company.id,
                accession_number=f"{suffix}-{label}",
                filing_type=ftype,
                filing_date=datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc),
                period_end_date=(
                    datetime.fromisoformat(period_end[0]).replace(tzinfo=timezone.utc) if period_end else None
                ),
                document_url=f"https://sec.example/{suffix}-{label}/doc.htm",
                sec_url=f"https://sec.example/{suffix}-{label}/",
                xbrl_data=xbrl,
            )
            db.add(filing)
            db.commit()  # commit per filing so ids are assigned in creation order (same-day tie-break)
            db.refresh(filing)
            filing_ids[label] = filing.id
        for label in spec.get("summary_labels", []):
            db.add(Summary(filing_id=filing_ids[label], business_overview="A real overview of the business."))
        if watchlist_all:
            db.add(Watchlist(user_id=user.id, company_id=company.id))
    db.commit()

    ns = SimpleNamespace(user_id=user.id, company_ids=company_ids, tickers=tickers, filing_ids=filing_ids)
    db.close()
    try:
        yield ns
    finally:
        db = SessionLocal()
        from app.models import Company, Filing, Summary, User, Watchlist
        fids = [f.id for f in db.query(Filing).filter(Filing.company_id.in_(company_ids)).all()]
        db.query(Summary).filter(Summary.filing_id.in_(fids)).delete(synchronize_session=False)
        db.query(Watchlist).filter(Watchlist.user_id == ns.user_id).delete(synchronize_session=False)
        db.query(Filing).filter(Filing.company_id.in_(company_ids)).delete(synchronize_session=False)
        db.query(Company).filter(Company.id.in_(company_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id == ns.user_id).delete(synchronize_session=False)
        db.commit()
        db.close()


@pytest.mark.requires_db
def test_compose_feed_orders_filters_and_annotates():
    from app.database import SessionLocal

    with _feed_scenario() as (uid, cid, newer_id, ticker):
        db = SessionLocal()
        items = compose_feed(db, uid, limit=20)
        db.close()

        # One card per company: the newest eligible filing (the newer 10-Q). The 8-K is ineligible
        # and the older 10-Q is not the company's newest, so neither surfaces.
        assert [it["filing_type"] for it in items] == ["10-Q"]
        assert items[0]["filing_id"] == newer_id
        assert items[0]["company"]["ticker"] == ticker
        # Newest has a ready summary and an "up" revenue headline computed against the prior 10-Q the
        # feed no longer returns — proving the what-changed comparison still reaches full history.
        assert items[0]["summary_status"] == "ready"
        assert items[0]["what_changed"] is not None
        assert items[0]["what_changed"]["items"][0]["direction"] == "up"


def _dropped(written, served, path="item"):
    """Every path of ``written`` that ``served`` lacks or changes: what the response model lost."""
    if isinstance(written, dict):
        if not isinstance(served, dict):
            return [path]
        return [
            p for key, value in written.items()
            for p in ([f"{path}.{key}"] if key not in served else _dropped(value, served[key], f"{path}.{key}"))
        ]
    if isinstance(written, list):
        if not isinstance(served, list) or len(served) != len(written):
            return [path]
        return [p for i, (w, s) in enumerate(zip(written, served)) for p in _dropped(w, s, f"{path}[{i}]")]
    return [] if written == served else [path]


@pytest.mark.requires_db
def test_feed_endpoint_serves_every_field_the_composer_writes():
    """The route's response model is the feed's contract: FastAPI drops any key it does not declare.
    The chips read the delta policy's display string and tone (T1.5), which the model left out, so
    production chips showed no figure and took their colour from the direction (Codex on #1290).
    Through the real route, each feed item keeps every key compose_feed wrote, at every level."""
    import json

    from fastapi.testclient import TestClient

    from app.config import settings
    from app.database import SessionLocal
    from app.models import User
    from app.routers.auth import create_access_token
    from main import app

    with _feed_scenario() as (uid, _cid, newer_id, _ticker):
        db = SessionLocal()
        written = json.loads(json.dumps(next(i for i in compose_feed(db, uid, limit=20) if i["filing_id"] == newer_id)))
        email = db.get(User, uid).email
        db.close()
        assert written["what_changed"]["items"][0]["display"] == "+25.0%"
        assert written["what_changed"]["items"][0]["tone"] == "gain"
        with TestClient(app) as client:
            client.cookies.set(settings.COOKIE_NAME, create_access_token(data={"sub": email}))
            response = client.get("/api/dashboard/feed")
        assert response.status_code == 200
        served = next(i for i in response.json()["items"] if i["filing_id"] == newer_id)
        assert _dropped(written, served) == []


@pytest.mark.requires_db
def test_compose_feed_one_item_per_company():
    # The regression test for the old "newest N filings across the whole watchlist" bug: two
    # companies with two eligible filings each must yield exactly two items (one per company), each
    # that company's newest filing.
    from app.database import SessionLocal

    specs = [
        {"filings": [
            ("a-old", "10-Q", "2023-06-30", {"revenue": _series(("2023-06-30", 80.0))}),
            ("a-new", "10-Q", "2024-06-30", {"revenue": _series(("2024-06-30", 100.0))}),
        ]},
        {"filings": [
            ("b-old", "10-K", "2023-12-31", {"revenue": _series(("2023-12-31", 200.0))}),
            ("b-new", "10-K", "2024-12-31", {"revenue": _series(("2024-12-31", 250.0))}),
        ]},
    ]
    with _multi_feed_scenario(specs) as ns:
        db = SessionLocal()
        items = compose_feed(db, ns.user_id, limit=20)
        db.close()

        assert len(items) == 2
        assert sorted(it["company"]["id"] for it in items) == sorted(ns.company_ids)  # each once
        by_company = {it["company"]["id"]: it for it in items}
        assert by_company[ns.company_ids[0]]["filing_id"] == ns.filing_ids["a-new"]
        assert by_company[ns.company_ids[1]]["filing_id"] == ns.filing_ids["b-new"]


@pytest.mark.requires_db
def test_compose_feed_orders_companies_by_latest_filing_desc():
    from app.database import SessionLocal

    # Company A carries an extra older filing so the old "newest N filings across the watchlist" bug
    # would return three items (b-new, a-new, a-old); the fix returns two heads ordered by date desc.
    specs = [
        {"filings": [
            ("a-old", "10-Q", "2023-06-30", None),
            ("a-new", "10-Q", "2024-06-30", None),  # A's head (older than B's head)
        ]},
        {"filings": [("b-new", "10-K", "2024-12-31", None)]},  # newest head -> first
    ]
    with _multi_feed_scenario(specs) as ns:
        db = SessionLocal()
        items = compose_feed(db, ns.user_id, limit=20)
        db.close()

        assert [it["filing_id"] for it in items] == [ns.filing_ids["b-new"], ns.filing_ids["a-new"]]


@pytest.mark.requires_db
def test_compose_feed_same_day_tie_breaks_by_id_desc():
    from app.database import SessionLocal

    # 10-Q created first, then a same-day 10-K -> the 10-K has the higher id and wins the tie.
    specs = [
        {"filings": [
            ("tie-q", "10-Q", "2024-03-31", None),
            ("tie-k", "10-K", "2024-03-31", None),
        ]},
    ]
    with _multi_feed_scenario(specs) as ns:
        db = SessionLocal()
        items = compose_feed(db, ns.user_id, limit=20)
        db.close()

        assert len(items) == 1
        assert items[0]["filing_id"] == max(ns.filing_ids["tie-q"], ns.filing_ids["tie-k"])
        assert items[0]["filing_id"] == ns.filing_ids["tie-k"]


@pytest.mark.requires_db
def test_compose_feed_limit_caps_company_count():
    from app.database import SessionLocal

    # Company C carries two filings, both newer than A and B. The old "newest N filings across the
    # watchlist" bug with limit=2 would return C's two filings (c, c-old) and drop B entirely; the
    # fix caps COMPANIES, so it returns one head each for the two newest companies (C, B).
    specs = [
        {"filings": [("a", "10-Q", "2024-01-31", None)]},  # stalest company -> dropped by limit=2
        {"filings": [("b", "10-Q", "2024-06-30", None)]},
        {"filings": [
            ("c-old", "10-K", "2024-11-30", None),
            ("c", "10-K", "2024-12-31", None),  # newest company's head
        ]},
    ]
    with _multi_feed_scenario(specs) as ns:
        db = SessionLocal()
        items = compose_feed(db, ns.user_id, limit=2)
        db.close()

        assert [it["filing_id"] for it in items] == [ns.filing_ids["c"], ns.filing_ids["b"]]
        assert ns.filing_ids["a"] not in {it["filing_id"] for it in items}
        assert ns.filing_ids["c-old"] not in {it["filing_id"] for it in items}


@pytest.mark.requires_db
def test_compose_feed_skips_companies_without_eligible_filings():
    from app.database import SessionLocal

    # Company A has an eligible 10-Q; company B has only an ineligible 8-K -> B is absent.
    specs = [
        {"filings": [("a-10q", "10-Q", "2024-06-30", None)]},
        {"filings": [("b-8k", "8-K", "2024-07-01", None)]},
    ]
    with _multi_feed_scenario(specs) as ns:
        db = SessionLocal()
        items = compose_feed(db, ns.user_id, limit=20)
        db.close()

        assert [it["filing_id"] for it in items] == [ns.filing_ids["a-10q"]]
        assert ns.company_ids[1] not in {it["company"]["id"] for it in items}

    # A watchlist carrying only ineligible forms yields an empty feed.
    with _multi_feed_scenario([{"filings": [("only-8k", "8-K", "2024-07-01", None)]}]) as ns:
        db = SessionLocal()
        assert compose_feed(db, ns.user_id, limit=20) == []
        db.close()


@pytest.mark.requires_db
def test_compose_feed_what_changed_uses_prior_same_form_not_feed():
    from app.database import SessionLocal

    # Newest is a 10-Q (rev 120). Its prior SAME-FORM is the older 10-Q (rev 100) -> "up 20%". A
    # 10-K sits between them (rev 200); if the comparison used the nearest prior filing regardless of
    # form, the delta would read "down". Single-period xbrl on the head forces the prior value to
    # come from the prior filing, not an in-instance comparative.
    specs = [
        {"filings": [
            ("q-older", "10-Q", "2023-06-30", {"revenue": _series(("2023-06-30", 100.0))}),
            ("k-mid", "10-K", "2024-03-31", {"revenue": _series(("2024-03-31", 200.0))}),
            ("q-newest", "10-Q", "2024-06-30", {"revenue": _series(("2024-06-30", 120.0))}),
        ]},
    ]
    with _multi_feed_scenario(specs) as ns:
        db = SessionLocal()
        items = compose_feed(db, ns.user_id, limit=20)
        db.close()

        assert items[0]["filing_id"] == ns.filing_ids["q-newest"]
        rev = next(i for i in items[0]["what_changed"]["items"] if i["metric"] == "revenue")
        assert rev["direction"] == "up"
        assert rev["pct"] == 20.0


@pytest.mark.requires_db
def test_compose_feed_compares_only_the_period_its_prior_same_form_filing_reported():
    from app.database import SessionLocal

    def chips(filings):
        with _multi_feed_scenario([{"filings": filings}]) as ns:
            db = SessionLocal()
            try:
                [item] = compose_feed(db, ns.user_id, limit=20)
            finally:
                db.close()
        changed = item["what_changed"]
        return changed and [(i["metric"], i["prior"]) for i in changed["items"]]

    q2 = ("q2", "10-Q", "2026-08-01", {"revenue": _series(("2026-06-30", 110.0), ("2025-06-30", 90.0))}, "2026-06-30")
    # The prior 10-Q was never summarized, or there is none: no chips, rather than revenue "up 22.2%" against the
    # year-ago quarter under "Quarter over quarter".
    assert chips([("q1", "10-Q", "2026-05-01", None, "2026-03-31"), q2]) is None
    assert chips([q2]) is None
    assert chips([("q1", "10-Q", "2026-05-01", {"revenue": _series(("2026-03-31", 100.0))}, "2026-03-31"), q2]) == [
        ("revenue", 100.0)
    ]
    # The prior row's period end is the period compared, not an older one its stored XBRL happens to hold.
    assert chips([("q1", "10-Q", "2026-05-01", {"revenue": _series(("2025-12-31", 95.0))}, "2026-03-31"), q2]) is None
    # An annual report keeps its own year before, with its prior 10-K never extracted or with none on file.
    k25 = ("k25", "10-K", "2026-02-20", {"revenue": _series(("2025-12-31", 500.0), ("2024-12-31", 440.0))}, "2025-12-31")
    assert chips([("k24", "10-K", "2025-02-20", None, "2024-12-31"), k25]) == [("revenue", 440.0)]
    assert chips([k25]) == [("revenue", 440.0)]


@pytest.mark.requires_db
def test_compose_feed_fpi_form_behind_flag(monkeypatch):
    from app.config import settings
    from app.database import SessionLocal

    specs = [{"filings": [("f-20f", "20-F", "2024-04-30", None)]}]
    with _multi_feed_scenario(specs) as ns:
        # Flag off (the default): the 20-F is ineligible, so the feed is empty.
        monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", False)
        db = SessionLocal()
        assert compose_feed(db, ns.user_id, limit=20) == []
        db.close()

        # Flag on: the FPI annual report surfaces.
        monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", True)
        db = SessionLocal()
        items = compose_feed(db, ns.user_id, limit=20)
        db.close()
        assert [it["filing_id"] for it in items] == [ns.filing_ids["f-20f"]]
        assert items[0]["filing_type"] == "20-F"


@pytest.mark.requires_db
def test_compose_feed_empty_for_no_watchlist():
    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    user = User(email=f"nofeed-{uuid.uuid4().hex}@example.com", hashed_password="x", email_verified=True)
    db.add(user)
    db.commit()
    uid = user.id
    try:
        assert compose_feed(db, uid, limit=20) == []
    finally:
        db.query(User).filter(User.id == uid).delete()
        db.commit()
        db.close()


def test_feed_form_types_gated_by_fpi_flag(monkeypatch):
    """The feed adds FPI ANNUAL forms (20-F/40-F) behind the flag, but never 6-K (XBRL-less/noisy)."""
    from app.config import settings
    from app.services import dashboard_feed_service as svc

    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", False)
    assert svc._feed_form_types() == ("10-K", "10-Q")

    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", True)
    on = svc._feed_form_types()
    assert "20-F" in on and "40-F" in on
    assert "6-K" not in on  # deliberately excluded from the what-changed feed
