"""Unit tests for the pure Form 4 extractor (no edgartools / pandas needed).

These exercise the defensive parsing + aggregation contract against duck-typed
fakes and plain list-of-dict transaction tables — the shapes
``backend/scripts/verify_insider_extraction.py`` validates against live SEC.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.services.ownership_extractor import (
    TRANSACTION_CODE_LABELS,
    _ci,
    _iso_date,
    _num,
    _safe_getattr,
    _to_records,
    extract_form4_transactions,
    summarize_insider_activity,
)


# --- Fakes -----------------------------------------------------------------


class FakeOwner:
    def __init__(self, name=None, is_director=None, is_officer=None, is_ten_pct=None, title=None):
        self.name = name
        self.is_director = is_director
        self.is_officer = is_officer
        self.is_ten_pct_owner = is_ten_pct
        self.officer_title = title


class FakeIssuer:
    def __init__(self, ticker):
        self.ticker = ticker


class FakeSummary:
    def __init__(self, has_plan):
        self.has_10b5_1_plan = has_plan


class FakeForm4:
    """Mimics edgar.ownership.forms.Form4's duck-typed surface."""

    def __init__(self, *, market_trades=None, insider_name=None, position=None,
                 owners=None, ticker="AAPL", has_plan=None):
        self.market_trades = market_trades
        self.insider_name = insider_name
        self.position = position
        self.reporting_owners = owners or []
        self.issuer = FakeIssuer(ticker)
        self._has_plan = has_plan

    def get_ownership_summary(self):
        return FakeSummary(self._has_plan)


# --- _to_records -----------------------------------------------------------


def test_to_records_none_and_list():
    assert _to_records(None) == []
    assert _to_records([{"a": 1}, "junk", {"b": 2}]) == [{"a": 1}, {"b": 2}]


def test_to_records_dataframe_like():
    class FakeDF:
        empty = False

        def to_dict(self, orient):
            assert orient == "records"
            return [{"Shares": 10}, {"Shares": 20}]

    assert _to_records(FakeDF()) == [{"Shares": 10}, {"Shares": 20}]


def test_to_records_empty_dataframe():
    class EmptyDF:
        empty = True

        def to_dict(self, orient):  # pragma: no cover - should not be called
            raise AssertionError("empty frame should short-circuit")

    assert _to_records(EmptyDF()) == []


# --- small coercers --------------------------------------------------------


def test_ci_case_insensitive():
    row = {"AcquiredDisposed": "A", "Shares": 10}
    assert _ci(row, "acquireddisposed") == "A"
    assert _ci(row, "code", "Shares") == 10
    assert _ci(row, "missing") is None


@pytest.mark.parametrize(
    "raw,expected",
    [("1,234", 1234.0), ("$5.50", 5.5), (10, 10.0), (None, None), ("", None), (float("nan"), None)],
)
def test_num(raw, expected):
    assert _num(raw) == expected


def test_num_rejects_bool():
    assert _num(True) is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2024-05-01", "2024-05-01"),
        ("2024-05-01T00:00:00", "2024-05-01"),
        ("05/01/2024", "2024-05-01"),
        (date(2024, 5, 1), "2024-05-01"),
        ("nat", None),
        (None, None),
    ],
)
def test_iso_date(raw, expected):
    assert _iso_date(raw) == expected


# --- extract_form4_transactions -------------------------------------------


def test_extract_basic_sale():
    owner = FakeOwner(name="Jane Doe", is_officer=True, is_director=False, title="CFO")
    form4 = FakeForm4(
        market_trades=[
            {"Date": "2024-05-01", "Code": "S", "Shares": "1,000", "Price": "$10.00", "AcquiredDisposed": "D"}
        ],
        owners=[owner],
        ticker="AAPL",
        has_plan=True,
    )
    txns = extract_form4_transactions(form4, accession="0001-24-000001", filed_date="2024-05-02")
    assert len(txns) == 1
    t = txns[0]
    assert t["insider_name"] == "Jane Doe"
    assert t["insider_title"] == "CFO"
    assert t["is_officer"] is True
    assert t["is_director"] is False
    assert t["ticker"] == "AAPL"
    assert t["transaction_code"] == "S"
    assert t["transaction_label"] == TRANSACTION_CODE_LABELS["S"]
    assert t["shares"] == 1000.0
    assert t["price"] == 10.0
    assert t["value"] == 10000.0
    assert t["acquired_disposed"] == "D"
    assert t["is_10b5_1"] is True
    assert t["accession"] == "0001-24-000001"
    assert t["filed_date"] == "2024-05-02"


def test_extract_no_trades_returns_empty():
    form4 = FakeForm4(market_trades=None, owners=[FakeOwner(name="X")])
    assert extract_form4_transactions(form4) == []


def test_extract_value_none_when_price_missing():
    form4 = FakeForm4(
        market_trades=[{"Date": "2024-05-01", "Code": "P", "Shares": 100, "AcquiredDisposed": "A"}],
        owners=[FakeOwner(name="Buyer")],
    )
    t = extract_form4_transactions(form4)[0]
    assert t["shares"] == 100.0
    assert t["price"] is None
    assert t["value"] is None


def test_extract_never_raises_on_garbage():
    class Exploding:
        @property
        def market_trades(self):
            raise RuntimeError("boom")

    # Top-level guard must swallow and return [].
    assert extract_form4_transactions(Exploding()) == []


def test_extract_ten_pct_owner_flag():
    form4 = FakeForm4(
        market_trades=[{"Date": "2024-01-01", "Code": "P", "Shares": 1, "Price": 1, "AcquiredDisposed": "A"}],
        owners=[FakeOwner(name="Whale", is_ten_pct=True)],
    )
    assert extract_form4_transactions(form4)[0]["is_ten_pct_owner"] is True


# --- _safe_getattr (version-agnostic attribute access) ---------------------


def test_safe_getattr_plain_property():
    class Obj:
        value = 42

    assert _safe_getattr(Obj(), "value") == 42
    assert _safe_getattr(Obj(), "missing") is None


def test_safe_getattr_calls_zero_arg_method():
    class Obj:
        def value(self):
            return "called"

    # edgartools sometimes exposes the same field as a method, not a property.
    assert _safe_getattr(Obj(), "value") == "called"


def test_safe_getattr_swallows_raising_property():
    class Obj:
        @property
        def value(self):
            raise RuntimeError("boom")

    assert _safe_getattr(Obj(), "value") is None


def test_extract_handles_method_style_form4():
    """Same data as test_extract_basic_sale, but every field is a method —
    proving the extractor is agnostic to property-vs-method drift."""

    class MethodOwner:
        def name(self):
            return "Jane Doe"

        def is_officer(self):
            return True

        def is_director(self):
            return False

        def is_ten_pct_owner(self):
            return None

        def officer_title(self):
            return "CFO"

    class MethodIssuer:
        def ticker(self):
            return "AAPL"

    class MethodForm4:
        def insider_name(self):
            return None

        def position(self):
            return None

        def reporting_owners(self):
            return [MethodOwner()]

        def issuer(self):
            return MethodIssuer()

        def market_trades(self):
            return [
                {"Date": "2024-05-01", "Code": "S", "Shares": 1000, "Price": 10.0, "AcquiredDisposed": "D"}
            ]

        def get_ownership_summary(self):
            return FakeSummary(True)

    t = extract_form4_transactions(MethodForm4(), accession="acc")[0]
    assert t["insider_name"] == "Jane Doe"
    assert t["insider_title"] == "CFO"
    assert t["is_officer"] is True
    assert t["ticker"] == "AAPL"
    assert t["transaction_code"] == "S"
    assert t["shares"] == 1000.0
    assert t["value"] == 10000.0
    assert t["is_10b5_1"] is True


# --- summarize_insider_activity -------------------------------------------


def _txn(code, ad, shares, price, day, is_plan=False):
    return {
        "transaction_code": code,
        "acquired_disposed": ad,
        "shares": shares,
        "price": price,
        "value": shares * price,
        "transaction_date": day,
        "is_10b5_1": is_plan,
    }


def test_summarize_buys_sells_and_net():
    today = date(2024, 6, 1)
    txns = [
        _txn("P", "A", 100, 10, "2024-05-15"),  # buy
        _txn("S", "D", 40, 20, "2024-05-20"),   # sell
        _txn("S", "D", 10, 20, "2024-05-25", is_plan=True),  # planned sell
    ]
    s = summarize_insider_activity(txns, window_days=90, now=today)
    assert s["buy_count"] == 1
    assert s["sell_count"] == 2
    assert s["buy_shares"] == 100
    assert s["sell_shares"] == 50
    assert s["net_shares"] == 50
    assert s["buy_value"] == 1000
    assert s["sell_value"] == 1000  # 40*20 + 10*20
    assert s["plan_10b5_1_sell_shares"] == 10
    # discretionary nets out the 10b5-1 sale: +100 buy - 40 discretionary sell
    assert s["discretionary_net_shares"] == 60
    assert s["last_transaction_date"] == "2024-05-25"


def test_summarize_excludes_out_of_window():
    today = date(2024, 6, 1)
    txns = [
        _txn("P", "A", 100, 10, "2024-05-30"),  # in window
        _txn("P", "A", 999, 10, "2024-01-01"),  # outside 90d window
    ]
    s = summarize_insider_activity(txns, window_days=90, now=today)
    assert s["buy_shares"] == 100


def test_summarize_empty():
    s = summarize_insider_activity([], window_days=90, now=date(2024, 6, 1))
    assert s["buy_count"] == 0
    assert s["sell_count"] == 0
    assert s["net_shares"] == 0
    assert s["buy_value"] is None
    assert s["last_transaction_date"] is None


def test_summarize_net_zero_value_is_zero_not_none():
    # Equal priced buys and sells net to $0 — that's real data, not "no data" (None).
    today = date(2024, 6, 1)
    txns = [
        _txn("P", "A", 100, 10, "2024-05-10"),  # +$1,000
        _txn("S", "D", 100, 10, "2024-05-12"),  # -$1,000
    ]
    s = summarize_insider_activity(txns, window_days=90, now=today)
    assert s["buy_value"] == 1000
    assert s["sell_value"] == 1000
    assert s["net_value"] == 0.0  # not None


def test_summarize_value_none_when_no_priced_trades():
    # Shares but no price → we report the share count but no dollar figure.
    today = date(2024, 6, 1)
    txns = [{
        "transaction_code": "P", "acquired_disposed": "A",
        "shares": 100, "price": None, "value": None,
        "transaction_date": "2024-05-10", "is_10b5_1": False,
    }]
    s = summarize_insider_activity(txns, window_days=90, now=today)
    assert s["buy_count"] == 1
    assert s["buy_shares"] == 100
    assert s["buy_value"] is None
    assert s["net_value"] is None


def test_summarize_classification_is_code_authoritative():
    # A contradictory P+D row (code=purchase, flag=disposed) counts once, as a buy — never both.
    today = date(2024, 6, 1)
    txns = [{
        "transaction_code": "P", "acquired_disposed": "D",
        "shares": 50, "price": 2, "value": 100,
        "transaction_date": "2024-05-10", "is_10b5_1": False,
    }]
    s = summarize_insider_activity(txns, window_days=90, now=today)
    assert s["buy_count"] == 1
    assert s["sell_count"] == 0


def test_summarize_ignores_non_open_market_codes():
    # A grant (code 'A') is neither an open-market buy nor sell, even though acquired == 'A'.
    today = date(2024, 6, 1)
    txns = [{
        "transaction_code": "A", "acquired_disposed": "A",
        "shares": 999, "price": 1, "value": 999,
        "transaction_date": "2024-05-10", "is_10b5_1": False,
    }]
    s = summarize_insider_activity(txns, window_days=90, now=today)
    assert s["buy_count"] == 0
    assert s["sell_count"] == 0


def test_summarize_falls_back_to_acquired_disposed_without_code():
    today = date(2024, 6, 1)
    txns = [
        {"transaction_code": None, "acquired_disposed": "A", "shares": 10, "price": 1,
         "value": 10, "transaction_date": "2024-05-10", "is_10b5_1": False},
        {"transaction_code": None, "acquired_disposed": "D", "shares": 4, "price": 1,
         "value": 4, "transaction_date": "2024-05-11", "is_10b5_1": False},
    ]
    s = summarize_insider_activity(txns, window_days=90, now=today)
    assert s["buy_count"] == 1
    assert s["sell_count"] == 1


def test_num_rejects_infinity():
    assert _num(float("inf")) is None
    assert _num(float("-inf")) is None
    assert _num("inf") is None


def test_iso_date_non_zero_padded():
    assert _iso_date("2024-5-1") == "2024-05-01"


def test_iso_date_tz_aware_normalized_to_utc():
    # 2024-05-01 23:30 at -05:00 is 2024-05-02 UTC — must bucket to the UTC day, not local.
    dt = datetime(2024, 5, 1, 23, 30, tzinfo=timezone(timedelta(hours=-5)))
    assert _iso_date(dt) == "2024-05-02"
