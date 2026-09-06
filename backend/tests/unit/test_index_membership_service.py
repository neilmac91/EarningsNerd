"""Index-membership loader: normalization, membership, the fail-open gate, and committed-list integrity."""
import json
from datetime import date

from app.config import settings
from app.services import index_membership_service as idx
from app.utils.datetimes import utcnow

# Rule-12 gate for the refresh cadence: the indexes rebalance ~quarterly and the refresh workflow runs
# monthly, so a committed list older than this means the workflow has been failing (or the founder
# has stopped merging its PRs) for at least two cycles. 100 days = one quarter plus slack.
MAX_UNIVERSE_AGE_DAYS = 100


def test_normalize_ticker_canonicalizes_dual_class():
    # Alpha Vantage uses a dot for dual classes; FMP uses a dash. Both must land on the same form.
    assert idx.normalize_ticker("brk-b") == "BRK.B"
    assert idx.normalize_ticker("BRK.B") == "BRK.B"
    assert idx.normalize_ticker("  aapl ") == "AAPL"
    assert idx.normalize_ticker("") == ""
    assert idx.normalize_ticker(None) == ""


def test_is_member_matches_regardless_of_separator():
    assert idx.is_member("AAPL")
    assert idx.is_member("MSFT")
    assert idx.is_member("BRK.B")
    assert idx.is_member("BRK-B")  # dash form normalizes to the committed dot form
    assert not idx.is_member("ZZZZ")
    assert not idx.is_member("")


def test_active_member_filter_off_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "CALENDAR_INDEX_FILTER_ENABLED", False)
    assert idx.active_member_filter() is None


def test_active_member_filter_on_returns_full_set(monkeypatch):
    monkeypatch.setattr(settings, "CALENDAR_INDEX_FILTER_ENABLED", True)
    members = idx.active_member_filter()
    assert members is not None and len(members) >= 500
    assert "AAPL" in members


def test_active_member_filter_fails_open_on_empty_list(monkeypatch):
    """If the list failed to load (empty set), the filter must disable itself even when the flag is on
    — a missing/corrupt list can never be allowed to empty the calendar."""
    monkeypatch.setattr(settings, "CALENDAR_INDEX_FILTER_ENABLED", True)
    monkeypatch.setattr(idx, "_MEMBER_TICKERS", frozenset())
    assert idx.active_member_filter() is None


def test_active_universe_label_tracks_the_filter(monkeypatch):
    """The label surfaced on /api/calendar mirrors active_member_filter exactly, so the UI caption
    can never claim the index universe while actually serving unfiltered."""
    monkeypatch.setattr(settings, "CALENDAR_INDEX_FILTER_ENABLED", False)
    assert idx.active_universe_label() == "all"

    monkeypatch.setattr(settings, "CALENDAR_INDEX_FILTER_ENABLED", True)
    assert idx.active_universe_label() == "sp500_nasdaq100"

    # Fail-open: an unhealthy list disables the filter, so the label must fall back to "all".
    monkeypatch.setattr(idx, "_MEMBER_TICKERS", frozenset())
    assert idx.active_universe_label() == "all"


def test_committed_membership_list_is_healthy():
    """Guard the data file itself: enough tickers, all normalized, unique, with the tricky dual-class
    names present in AV/dot format."""
    payload = json.loads(idx._DATA_PATH.read_text(encoding="utf-8"))
    members = payload["members"]
    tickers = [m["ticker"] for m in members]

    assert len(tickers) >= 500  # S&P 500 alone is ~503
    assert len(tickers) == len(set(tickers)), "duplicate tickers in committed list"
    assert all(t == idx.normalize_ticker(t) and t for t in tickers), "tickers must be pre-normalized"

    tset = set(tickers)
    for required in ("AAPL", "MSFT", "NVDA", "BRK.B", "BF.B", "GOOGL", "GOOG", "FOXA", "NWSA"):
        assert required in tset, f"{required} missing from committed universe"
    # Nasdaq-only names (not in the S&P 500) must be captured by the union.
    assert {"ASML", "MELI", "PDD"} & tset, "expected some Nasdaq-100-only names in the union"
    # Both spin-offs began trading and joined the S&P 500 in June 2026.
    assert {"FDXF", "HONA"} <= tset

    # Every entry declares at least one index label.
    assert all(m.get("indices") for m in members)


def test_committed_membership_list_is_fresh():
    """Fail when the committed universe is stale, relative to the date the test runs.

    ``generated_on`` is written by ``scripts/refresh_index_membership.py`` on every regeneration.
    Two silent monthly failures (the old Nasdaq article lacked the table) let the list age
    unnoticed — this turns that into a red CI, with the fix in the message.
    """
    payload = json.loads(idx._DATA_PATH.read_text(encoding="utf-8"))
    generated_on = date.fromisoformat(payload["generated_on"])
    age_days = (utcnow().date() - generated_on).days

    assert age_days <= MAX_UNIVERSE_AGE_DAYS, (
        f"index_membership.json was generated {age_days} days ago ({generated_on}); the calendar's "
        f"S&P 500 / Nasdaq 100 universe is stale. Run the 'Refresh index membership' GitHub workflow "
        f"(Actions → Run workflow; public lists need no credentials) or "
        f"`cd backend && python scripts/refresh_index_membership.py`, then merge the "
        f"resulting PR. If the workflow failed, see the 'Universe refresh failed' issue it opened."
    )
