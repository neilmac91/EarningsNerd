"""Wave 0 anchors (T0) for the trend_analysis_service hot-module refactor.

``tasks/refactor-plan-2026-10.md`` (M3) moves ``app/services/trend_analysis_service.py`` into a
``trend_analysis/`` package behind a façade, then splits ``build_dataset``,
``build_observation_catalogue`` and ``stream_trend_narrative`` into phases. Today's tests mostly
assert membership; these pin exact values at the seams those cuts cross, so a move or split that
changes behaviour fails here. Docstring line numbers are as of 76d45732.

Hermetic and order-independent: a test that needs a database gets a private SQLite file, bound
where the module's lazy imports read it (``app.database.SessionLocal``, as
``test_data_completeness.py:25-33`` does), and the provider is faked on the shared
``openai_service`` singleton with ``patch.object``, which deletes the instance attribute again on
exit. The only patch on the module's own namespace is ``_DETECTORS`` in T0.4; T1 re-points it to
``app.services.trend_analysis.detectors``.
"""
import copy
import hashlib
import json
from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import database
from app.config import settings
from app.models import Base, Company, FinancialFact, TrendAnalysis, User
from app.services import trend_analysis_service as svc
from app.services.openai_service import openai_service

_PROMPT_EVENT = (
    "The observation selector's prompt bytes (or PROMPT_VERSION) changed. A byte change is a "
    "PROMPT_VERSION event (backend/evals/RUNBOOK.md, 'Multi-Period Analysis observation-selector "
    "gate'): bump trend_analysis_service.PROMPT_VERSION, follow the RUNBOOK steps, then re-pin the "
    "version and the digests together. A pure move or split must leave all of them identical."
)

_M = 1_000_000.0
# One company, FY2020..FY2023: all five inflection detectors fire and every catalogue phase
# renders (gross margin's missing FY2023 is the selected-gap case).
# (concept, unit, balance-sheet instant?, FY2020..FY2023 values; None = not reported)
_HISTORY = (
    ("revenue", "USD", False, (1_000 * _M, 1_300 * _M, 1_560 * _M, 1_716 * _M)),
    ("gross_margin", "pure", False, (40.0, 39.0, 37.5, None)),
    ("operating_margin", "pure", False, (20.0, 18.5, 17.0, 15.0)),
    ("net_income", "USD", False, (100 * _M, 130 * _M, 150 * _M, 120 * _M)),
    ("earnings_per_share", "USD/shares", False, (1.0, 1.3, 1.5, 1.2)),
    ("operating_cash_flow", "USD", False, (150 * _M, 160 * _M, 170 * _M, 140 * _M)),
    ("free_cash_flow", "USD", False, (100 * _M, 120 * _M, 130 * _M, 40 * _M)),
    ("cash_and_equivalents", "USD", True, (50 * _M, 60 * _M, 55 * _M, 45 * _M)),
    ("current_ratio", "pure", True, (1.6, 1.4, 1.2, 0.95)),
    ("long_term_debt", "USD", True, (200 * _M, 220 * _M, 300 * _M, 400 * _M)),
)


@pytest.fixture
def session_factory(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'trend_anchors.sqlite'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    yield factory
    engine.dispose()


@pytest.fixture
def company_id(session_factory):
    with session_factory() as db:
        company = Company(cik="0000990001", ticker="ANCR", name="Anchor Co")
        db.add(company)
        db.flush()
        for concept, unit, instant, values in _HISTORY:
            for fiscal_year, value in zip(range(2020, 2024), values):
                if value is None:
                    continue
                db.add(FinancialFact(
                    company_id=company.id, concept=concept, raw_tag=f"us-gaap:{concept}", unit=unit,
                    period_start=None if instant else date(fiscal_year, 1, 1),
                    period_end=date(fiscal_year, 12, 31), fiscal_year=fiscal_year,
                    fiscal_period="FY", value=value, form="10-K",
                    accession=f"0000990001-{fiscal_year % 100:02d}-000001", source="companyfacts",
                    reconciled=True, is_latest=True,
                ))
        db.commit()
        return company.id


def _seeded_dataset(session_factory, company_id):
    with session_factory() as db:
        return svc.build_dataset(db, db.get(Company, company_id), "annual", "FY2020", "FY2023")


def _selection():
    return json.dumps({key: [] for key, _ in svc.ANALYSIS_SECTIONS}, separators=(",", ":"))


async def _drain(company_id, replies, *, start="FY2020", end="FY2023"):
    """Run the real stream (the ``test_analysis_stream.py:196-206`` drain) against a fake provider.
    Call N streams ``replies[N]``; a call beyond ``replies`` raises, so ``()`` means "no call"."""
    calls = []

    async def fake_stream_chat(messages, **kwargs):
        calls.append((copy.deepcopy(messages), kwargs))
        kwargs["usage_sink"].update({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
        for chunk in replies[len(calls) - 1]:
            yield chunk

    with patch.object(openai_service, "stream_chat", fake_stream_chat):
        events = [
            event
            async for event in svc.stream_trend_narrative(
                company_id=company_id, mode="annual", start_period=start, end_period=end,
            )
        ]
    return events, calls


# --- T0.1 ------------------------------------------------------------------------------------


def _observation_series(concept, label, points, *, unit="USD", percent=False):
    return {
        "concept": concept, "label": label, "unit": unit, "percent": percent,
        "points": points, "cagr": None,
    }


def _observation_dataset():
    """``TestCodeOwnedObservations._dataset()`` (test_trend_analysis_service.py:200-238) at its
    default ratio, reproduced rather than imported so neither file binds the other's helpers."""
    periods = ["2026Q1", "2026Q2"]
    marker = iter(f"F{i}" for i in range(1, 40))

    def points(values, yoys=(None, None)):
        return [
            {"period": period, "value": value, "marker": next(marker), "yoy": yoy,
             "unit": "USD", "period_end": f"2026-0{3 + index * 3}-30",
             "raw_tag": "test", "derived": False, "reconciled": True}
            for index, (period, value, yoy) in enumerate(zip(periods, values, yoys))
        ]

    return {
        "ticker": "TST", "company_name": "Test Co", "mode": "quarterly",
        "period_key": "2026Q1..2026Q2",
        "periods": [{"key": period} for period in periods],
        "series": [
            _observation_series("net_interest_income", "Net interest income",
                                points((10.0, 11.0), (0.176, 0.301))),
            _observation_series("noninterest_income", "Noninterest income",
                                points((7.0, 8.0), (0.10, 0.20))),
            _observation_series("net_income", "Net income",
                                points((20_000_000_000.0, 21_893_000_000.0), (0.271, 0.283))),
            _observation_series("operating_cash_flow", "Operating cash flow",
                                points((25_000_000_000.0, 26_000_000_000.0), (0.20, 0.315))),
            _observation_series("free_cash_flow", "Free cash flow",
                                points((16_000_000_000.0, 14_923_000_000.0), (0.10, -0.067))),
            _observation_series("shareholders_equity", "Shareholders' equity",
                                points((90.0, 100.0))),
            _observation_series("earnings_per_share", "EPS (basic)",
                                points((6.4, 7.7)), unit="USD/shares"),
            _observation_series("current_ratio", "Current ratio",
                                points((1.1, 1.003294804655586)), unit="pure"),
        ],
        "inflections": [{
            "kind": "test_signal", "detail": "A fixed signal uses both periods.",
            "markers": ["F1", "F2"],
        }],
    }


_CATALOGUE_CHANGED = (
    "build_observation_catalogue changed. Its order sets the order-dependent `required` flags and "
    "the empty-selection fallback, and its text is the selector's user message, so a change here "
    "is also a PROMPT_VERSION event (backend/evals/RUNBOOK.md)."
)


def test_t0_1_catalogue_order_snapshot():
    """T0.1: the exact (id, section, required) sequence and sentences that
    ``build_observation_catalogue`` (app/services/trend_analysis_service.py:935-1237) emits for the
    plan's fixture. Order drives the ``required`` flags at :994, :1015 and :1151-1153 and the
    fallback to ``section_items[0]`` at :1302-1305; the text becomes the user message at :1810."""
    catalogue = svc.build_observation_catalogue(_observation_dataset())
    assert [(item.id, item.section, item.required) for item in catalogue] == [
        ("trajectory.latest.net-interest-income.2026q2", "trajectory", True),
        ("trajectory.first.net-interest-income.2026q1", "trajectory", False),
        ("growth_quality.growth.net-interest-income.2026q1", "growth_quality", False),
        ("growth_quality.growth.net-interest-income.2026q2", "growth_quality", True),
        ("trajectory.latest.net-income.2026q2", "trajectory", True),
        ("growth_quality.growth.net-income.2026q1", "growth_quality", False),
        ("growth_quality.growth.net-income.2026q2", "growth_quality", True),
        ("growth_quality.comparison.net-income.net-interest-income.2026q1", "growth_quality", False),
        ("growth_quality.comparison.net-income.net-interest-income.2026q2", "growth_quality", False),
        ("growth_quality.comparison.net-income.noninterest-income.2026q1", "growth_quality", False),
        ("growth_quality.comparison.net-income.noninterest-income.2026q2", "growth_quality", False),
        ("growth_quality.comparison.operating-cash-flow.net-income.2026q1", "growth_quality", False),
        ("growth_quality.comparison.operating-cash-flow.net-income.2026q2", "growth_quality", False),
        ("cash_balance_sheet.level-comparison.free-cash-flow.net-income.2026q2", "cash_balance_sheet", True),
        ("cash_balance_sheet.level-comparison.operating-cash-flow.net-income.2026q2", "cash_balance_sheet", False),
        ("cash_balance_sheet.latest.shareholders-equity.2026q2", "cash_balance_sheet", False),
        ("cash_balance_sheet.ratio-threshold.current-ratio.2026q2", "cash_balance_sheet", True),
        ("growth_quality.latest-eps.earnings-per-share.2026q2", "growth_quality", False),
        ("red_flags.signal.test-signal.1", "red_flags", True),
        ("watch_next.growth.net-interest-income.2026q2", "watch_next", True),
        ("watch_next.metric.net-income.2026q2", "watch_next", False),
        ("watch_next.metric.free-cash-flow.2026q2", "watch_next", False),
    ], _CATALOGUE_CHANGED
    sentences = "\n".join(item.markdown for item in catalogue).encode("utf-8")
    assert hashlib.sha256(sentences).hexdigest() == (
        "2eb90932aca593c8632dc136c94e49caa4f9beb09573398fc51c9d439332404c"
    ), _CATALOGUE_CHANGED


def test_t0_1_required_flags_on_the_seeded_history(session_factory, company_id):
    """T0.1, the case the plan's fixture cannot reach: it has no margin series, so the
    first-margin-wins ``required`` at app/services/trend_analysis_service.py:1064-1066 is only
    exercised here (gross margin required, operating margin not), with :1151-1153 (EPS not
    required). The ids, sections and sentences of this catalogue are pinned by T0.2's user message."""
    catalogue = svc.build_observation_catalogue(_seeded_dataset(session_factory, company_id))
    assert len(catalogue) == 39
    assert [item.id for item in catalogue if item.required] == [
        "trajectory.latest.revenue.fy2023",
        "trajectory.cagr.revenue.fy2020-fy2023",
        "growth_quality.growth.revenue.fy2023",
        "trajectory.latest.net-income.fy2023",
        "growth_quality.growth.net-income.fy2023",
        "margins.latest.gross-margin.fy2022",
        "cash_balance_sheet.level-comparison.free-cash-flow.net-income.fy2023",
        "cash_balance_sheet.ratio-threshold.current-ratio.fy2023",
        "red_flags.signal.growth-deceleration.1",
        "red_flags.signal.margin-compression.2",
        "red_flags.signal.fcf-ni-divergence.3",
        "red_flags.signal.debt-build.4",
        "red_flags.signal.liquidity-squeeze.5",
        "watch_next.growth.revenue.fy2023",
    ], _CATALOGUE_CHANGED


# --- T0.2 ------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t0_2_selection_prompt_bytes(company_id):
    """T0.2: the bytes the selector receives (app/services/trend_analysis_service.py:1802-1815) and
    the one retry turn (:1826-1836), over a history that renders every catalogue phase. The system
    message is ``backend/prompts/trends-analyst-agent.md`` byte for byte (prompt_loader.py:118-131).
    Nothing on this path reads the clock, so the digests are wall-clock independent."""
    events, calls = await _drain(company_id, (["not json"], [_selection()]))
    assert events[-1]["type"] == "complete" and events[-1]["kind"] == "analysis"
    (first, kwargs), (retry, _) = calls

    def digest(message):
        return hashlib.sha256(message["content"].encode("utf-8")).hexdigest()

    assert retry[:2] == first and all(set(message) == {"role", "content"} for message in retry)
    assert {
        "prompt_version": svc.PROMPT_VERSION,
        "roles": [message["role"] for message in retry],
        "system": digest(first[0]),
        "user": digest(first[1]),
        "retry": digest(retry[2]),
    } == {
        "prompt_version": "trends-v7-observations",
        "roles": ["system", "user", "user"],
        "system": "8bf6c032d7f6930ca072abedb4d57ac43f42d25ba3bb297917e448a968e58680",
        "user": "aff5ba96228ec59b5071753e150b2d335c30845adf6c759f3185c287c346654d",
        "retry": "68ef47e97f8b19b340b2544b28bc0658811acd1c0c8b662df0ff4ee1e7db0218",
    }, _PROMPT_EVENT
    # The sampling arguments of the call (:1847-1852): no model override, the configured cap.
    assert sorted(kwargs) == ["max_tokens", "temperature", "usage_sink"]
    assert (kwargs["max_tokens"], kwargs["temperature"]) == (settings.ANALYSIS_MAX_TOKENS, 0.2)


# --- T0.3 ------------------------------------------------------------------------------------

_FINGERPRINT_CHANGED = (
    "dataset_fingerprint changed for an unchanged dataset: every cached TrendAnalysis row stops "
    "matching at trend_analysis_service.py:1753 and regenerates on its next request (a fleet-wide "
    "model-call wave). A pure move or split must keep it identical."
)


def test_t0_3_dataset_fingerprint_hex_of_a_literal_dataset():
    """T0.3: ``dataset_fingerprint`` (app/services/trend_analysis_service.py:739-743) is sha256 of
    ``json.dumps(sort_keys=True, separators=(",", ":"), default=str)`` (:742), compared against the
    cached row at :1753. The literal exercises each argument: unsorted keys, a ``date`` for
    ``default=str``, and non-ASCII text for the default ``ensure_ascii``."""
    dataset = {
        "ticker": "TST", "company_name": "Test Co", "mode": "annual", "period_key": "FY2022..FY2023",
        "periods": [
            {"key": "FY2022", "fiscal_year": 2022, "fiscal_period": "FY", "period_end": date(2022, 12, 31)},
            {"key": "FY2023", "fiscal_year": 2023, "fiscal_period": "FY", "period_end": "2023-12-31"},
        ],
        "series": [{
            "concept": "revenue", "label": "Revenue", "unit": "USD", "percent": False, "tone": "normal",
            "cagr": 0.1, "cagr_window": "FY2022..FY2023", "cagr_marker": "F3",
            "points": [
                {"period": "FY2022", "value": 1000.0, "marker": "F1", "yoy": None},
                {"period": "FY2023", "value": 1100.0, "marker": "F2", "yoy": 0.1, "qoq": svc.NOT_MEANINGFUL},
            ],
        }],
        "inflections": [{
            "kind": "growth_deceleration", "concepts": ["revenue"], "periods": ["FY2023"],
            "detail": "Revenue YoY growth decelerated: +20.0% → +10.0%.", "markers": ["F2", "F1"],
        }],
    }
    assert svc.dataset_fingerprint(dataset) == (
        "65636f5533b0cc56e92622a455f2a3ff23b6d9b553dd57c4f4078749f3b3279a"
    ), _FINGERPRINT_CHANGED


def _reference_cagr(series):
    """CAGR as ``_cagr`` (app/services/trend_analysis_service.py:248-252) computes it at W0.G, over
    the series' first and last valued annual points."""
    valued = [(int(point["period"].removeprefix("FY")), point["value"])
              for point in series["points"] if point.get("value") is not None]
    (first_fy, first), (last_fy, last) = valued[0], valued[-1]
    return (last / first) ** (1.0 / (last_fy - first_fy)) - 1.0


def test_t0_3_dataset_fingerprint_of_the_seeded_history(session_factory, company_id):
    """T0.3 over a real ``build_dataset`` (app/services/trend_analysis_service.py:271-530) result:
    the fingerprint is what the cache compares (:1745, :1753), so it pins the whole assembled
    dataset (periods, every point field, growth, window figures, markers, inflections) through
    the ``build_dataset`` split.

    CAGR (:248-252) is libm ``pow`` output, whose last bit may differ by platform, so the digest
    leaves it out and pins it another way: each CAGR must equal, bit for bit, the W0.G formula
    computed here over the series' valued endpoints. Both sides call the same ``pow`` on the same
    machine, so the check is exact on every platform, and a refactor that changes the arithmetic
    (which would change every cached fingerprint) fails here, not only a change past 12 digits."""
    dataset = _seeded_dataset(session_factory, company_id)
    for series in dataset["series"]:
        if series["cagr"] is not None:
            assert series["cagr"] == _reference_cagr(series), (series["concept"], _FINGERPRINT_CHANGED)
    cagr = {series["concept"]: series.pop("cagr") for series in dataset["series"]}
    assert cagr == pytest.approx({
        "revenue": 0.19721576725837586, "gross_margin": None, "operating_margin": None,
        "net_income": 0.06265856918261115, "earnings_per_share": 0.06265856918261115,
        "operating_cash_flow": -0.02273519408117486, "free_cash_flow": -0.2631937002719227,
        "cash_and_equivalents": -0.03451061539437028, "current_ratio": None,
        "long_term_debt": 0.2599210498948732,
    }, rel=1e-12)
    assert svc.dataset_fingerprint(dataset) == (
        "c92c1279b06cb3d3d2b763ee436dbef9f3b311595c48afc8606332ec99dd5fa5"
    ), _FINGERPRINT_CHANGED


# --- T0.4 ------------------------------------------------------------------------------------


def test_t0_4_raising_detector_does_not_break_build_dataset(session_factory, company_id, monkeypatch, caplog):
    """T0.4: ``detect_inflections`` (app/services/trend_analysis_service.py:726-733) runs each
    detector in its own try, logs a failure with its traceback and keeps going, so one detector
    bug never breaks ``build_dataset`` (:529) or drops the other detectors' flags."""
    baseline = _seeded_dataset(session_factory, company_id)
    assert [flag["kind"] for flag in baseline["inflections"]] == [
        "growth_deceleration", "margin_compression", "fcf_ni_divergence", "debt_build", "liquidity_squeeze",
    ]
    calls = []

    def _raising_detector(dataset):
        calls.append(dataset["period_key"])
        raise RuntimeError("detector bug")

    # The one patch on the module's own namespace (registry at :717-723). T1 re-points it to
    # app.services.trend_analysis.detectors; a stale target fails the `calls` check below.
    monkeypatch.setattr(svc, "_DETECTORS", (_raising_detector, *svc._DETECTORS))
    dataset = _seeded_dataset(session_factory, company_id)

    assert calls == ["FY2020..FY2023"]
    assert dataset == baseline
    failures = [r for r in caplog.records if r.getMessage() == "inflection detector _raising_detector failed"]
    assert len(failures) == 1 and failures[0].exc_info[0] is RuntimeError


# --- T0.5 ------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t0_5_complete_event_key_sets(company_id):
    """T0.5: the exact keys of the three ``complete`` events the router consumes: fresh
    (app/services/trend_analysis_service.py:1906-1923), cached (:1761-1774) and not-enough-data
    (:1787-1799). The fresh and cached sets are identical today, so the cached drain must prove it
    took the cache path (``cached`` is True, no provider call)."""
    fresh_events, fresh_calls = await _drain(company_id, ([_selection()],))
    cached_events, cached_calls = await _drain(company_id, ())
    sparse_events, sparse_calls = await _drain(company_id, (), start="FY2023", end="FY2023")
    fresh, cached, sparse = fresh_events[-1], cached_events[-1], sparse_events[-1]

    assert (len(fresh_calls), len(cached_calls), len(sparse_calls)) == (1, 0, 0)
    assert [(e["type"], e["kind"], e["cached"]) for e in (fresh, cached, sparse)] == [
        ("complete", "analysis", False), ("complete", "analysis", True),
        ("complete", "not_enough_data", False),
    ]
    analysis_keys = {
        "type", "kind", "analysis_id", "narrative", "citations", "grounded", "unverified",
        "mismatched", "cached", "invalidated", "n_periods", "usage",
    }
    assert set(fresh) == analysis_keys
    assert set(cached) == analysis_keys
    assert set(sparse) == analysis_keys - {"mismatched"}


# --- T0.6 ------------------------------------------------------------------------------------


def test_t0_6_persist_analysis_regenerates_in_place(session_factory, company_id):
    """T0.6: ``_persist_analysis`` (app/services/trend_analysis_service.py:1643-1701) updates the
    existing (company, mode, period_key) row (:1693-1695) rather than replacing it, so the id the
    PDF export reads (backend/app/routers/analysis.py:438-449) survives a regeneration under a
    new PROMPT_VERSION. A second key's row is written in between: SQLite assigns max(rowid) + 1,
    so if key A's row were the newest, a delete-and-reinsert would get its id back and pass."""
    with session_factory() as db:
        user = User(email="anchor@example.com")
        db.add(user)
        db.commit()
        user_id = user.id

    def persist(key, **fields):
        return svc._persist_analysis(**{
            "company_id": company_id, "mode": "annual", "key": key, "fingerprint": "fp-1",
            "dataset": {"period_key": key}, "narrative": "first", "citations": [{"n": 1}],
            "model": "model-1", "grounded": 1, "unverified": 0, "user_id": None, **fields,
        })

    first_id = persist("FY2020..FY2023")
    other_id = persist("FY2021..FY2023")
    with session_factory() as db:  # a PROMPT_VERSION bump leaves the stored row on the old version
        db.query(TrendAnalysis).filter_by(id=first_id).update({"prompt_version": "trends-v6-retired"})
        db.commit()
    second_id = persist(
        "FY2020..FY2023", fingerprint="fp-2", dataset={"period_key": "FY2020..FY2023", "v": 2},
        narrative="second", citations=[{"n": 1}, {"n": 2}], model="model-2", grounded=2,
        unverified=1, user_id=user_id,
    )

    assert first_id is not None and other_id > first_id
    assert second_id == first_id
    with session_factory() as db:
        rows = {row.period_key: row for row in db.query(TrendAnalysis)}
        assert sorted(rows) == ["FY2020..FY2023", "FY2021..FY2023"]
        row = rows["FY2020..FY2023"]
        assert (
            row.id, row.prompt_version, row.dataset_fingerprint, row.dataset_json, row.narrative_md,
            row.citations_json, row.model, row.grounded, row.unverified, row.created_by_user_id,
        ) == (
            first_id, svc.PROMPT_VERSION, "fp-2", {"period_key": "FY2020..FY2023", "v": 2}, "second",
            [{"n": 1}, {"n": 2}], "model-2", 2, 1, user_id,
        )
