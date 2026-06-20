"""Form 4 (insider transaction) extraction from EdgarTools ownership objects.

Source-verified against edgartools 5.36/5.37 (``edgar.ownership.forms.Form4``), but
kept deliberately defensive: EdgarTools' ownership API has both a summary layer and
a table layer, exact DataFrame column casing isn't guaranteed across versions, and
a couple of documented helpers (e.g. ``get_net_shares_traded``) aren't present in
all releases. So we read everything through ``getattr`` + case-insensitive column
lookup, treat every field as Optional, and **never raise** from extraction — one
malformed filing must not break the feed. The real shapes are validated against
live SEC via ``backend/scripts/verify_insider_extraction.py``.

This module imports nothing from EdgarTools (or the ``app.services.edgar`` package),
so it stays unit-testable without the heavy dependency: it operates on duck-typed
objects and plain row dicts.
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# SEC Form 4 transaction codes -> human label (Form 4/5 General Instruction 8).
TRANSACTION_CODE_LABELS: dict[str, str] = {
    "P": "Open-market purchase",
    "S": "Open-market sale",
    "A": "Grant or award",
    "D": "Disposition to the issuer",
    "F": "Payment of exercise/tax by shares",
    "M": "Option exercise / conversion",
    "C": "Conversion of derivative",
    "E": "Expiration of short derivative",
    "H": "Expiration of long derivative",
    "G": "Gift",
    "X": "Exercise of in-the-money derivative",
    "W": "Acquisition/disposition by will or inheritance",
    "J": "Other (explained in footnote)",
    "U": "Tender of shares",
    "I": "Discretionary transaction",
}


def _to_records(table: Any) -> list[dict]:
    """Normalize a transactions table to a list of row dicts.

    Accepts a pandas DataFrame (``market_trades``), a list of dicts (tests), or
    None. DataFrame conversion uses ``to_dict("records")`` so this module never
    needs to import pandas.
    """

    if table is None:
        return []
    to_dict = getattr(table, "to_dict", None)
    if callable(to_dict):  # pandas DataFrame (or similar)
        try:
            if getattr(table, "empty", False):
                return []
            records = to_dict("records")
            return [r for r in records if isinstance(r, dict)]
        except Exception:  # pragma: no cover - defensive
            return []
    if isinstance(table, list):
        return [r for r in table if isinstance(r, dict)]
    return []


def _ci(row: dict, *names: str) -> Any:
    """Case-insensitive lookup of the first matching key in a row dict."""
    lower = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def _clean_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        if value != value:  # NaN
            return None
    except Exception:  # pragma: no cover - defensive
        pass
    s = str(value).strip()
    if not s or s.lower() in {"nan", "nat", "none"}:
        return None
    return s


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        s = _clean_str(value)
        if s is None:
            return None
        try:
            f = float(s.replace(",", "").replace("$", ""))
        except (TypeError, ValueError):
            return None
    # Reject NaN and infinities — a stray inf would silently poison every downstream sum.
    return f if math.isfinite(f) else None


def _iso_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        if value != value:  # NaN / NaT
            return None
    except Exception:  # pragma: no cover - defensive
        pass
    if isinstance(value, datetime):
        try:
            # Normalize tz-aware timestamps to UTC before taking the date, so e.g.
            # 2024-05-01T23:30-05:00 (= 2024-05-02 UTC) doesn't bucket to the prior day.
            if value.tzinfo is not None:
                value = value.astimezone(timezone.utc)
            return value.date().isoformat()
        except Exception:  # pragma: no cover - e.g. NaT
            return None
    if isinstance(value, date):
        return value.isoformat()
    s = _clean_str(value)
    if s is None:
        return None
    if len(s) >= 10 and s[4:5] == "-" and s[7:8] == "-":
        try:
            date.fromisoformat(s[:10])
            return s[:10]
        except ValueError:
            pass
    # "%Y-%m-%d" also catches non-zero-padded ISO (e.g. "2024-5-1") the fast path skips.
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _safe_getattr(obj: Any, name: str) -> Any:
    """Attribute access tolerant of edgartools method-vs-property drift.

    Some edgartools fields are plain properties in one release and zero-arg
    methods in another (the same reason ``xbrl_service`` resolves ``Section.text``
    via ``callable``). Resolve either form and never raise.
    """
    try:
        val = getattr(obj, name, None)
        if callable(val):
            return val()
        return val
    except Exception:  # pragma: no cover - defensive
        return None


def _owner_fields(form4: Any) -> dict:
    """Insider identity from the Form 4 object (reporting owner #1)."""
    name = _clean_str(_safe_getattr(form4, "insider_name"))
    title = _clean_str(_safe_getattr(form4, "position"))
    is_director = is_officer = is_ten_pct = None

    owners = _safe_getattr(form4, "reporting_owners")
    first = None
    try:
        first = owners[0] if owners else None
    except (TypeError, KeyError, IndexError):  # pragma: no cover - defensive
        first = None
    if first is not None:
        is_director = _safe_getattr(first, "is_director")
        is_officer = _safe_getattr(first, "is_officer")
        # NOTE: edgartools uses `is_ten_pct_owner` (not `is_ten_percent_owner`).
        is_ten_pct = _safe_getattr(first, "is_ten_pct_owner")
        name = name or _clean_str(_safe_getattr(first, "name"))
        title = title or _clean_str(_safe_getattr(first, "position")) or _clean_str(
            _safe_getattr(first, "officer_title")
        )

    return {
        "insider_name": name,
        "insider_title": title,
        "is_director": bool(is_director) if is_director is not None else None,
        "is_officer": bool(is_officer) if is_officer is not None else None,
        "is_ten_pct_owner": bool(is_ten_pct) if is_ten_pct is not None else None,
    }


def _filing_10b5_1(form4: Any) -> Optional[bool]:
    """Filing-level Rule 10b5-1 flag (the reliable signal on 5.36.x)."""
    summary = _safe_getattr(form4, "get_ownership_summary")
    if summary is not None:
        val = _safe_getattr(summary, "has_10b5_1_plan")
        if val is not None:
            return bool(val)
    val = _safe_getattr(form4, "aff10b5_one")
    return bool(val) if val is not None else None


def extract_form4_transactions(
    form4: Any, *, accession: str = "", filed_date: Optional[str] = None
) -> list[dict]:
    """Extract open-market insider trades from a Form 4 object into row dicts.

    Primary path is ``form4.market_trades`` (the only layer carrying per-row date +
    acquired/disposed + price + code together). Returns ``[]`` for anything it can't
    parse — including grant/derivative-only filings with no open-market trades.
    """

    try:
        owner = _owner_fields(form4)
        issuer = _safe_getattr(form4, "issuer")
        ticker = _clean_str(_safe_getattr(issuer, "ticker")) if issuer is not None else None
        is_plan = _filing_10b5_1(form4)

        rows = _to_records(_safe_getattr(form4, "market_trades"))
        out: list[dict] = []
        for row in rows:
            code = _clean_str(_ci(row, "Code", "transaction_code", "code"))
            acquired_disposed = _clean_str(
                _ci(row, "AcquiredDisposed", "acquired_disposed", "AcquiredDisposedCode")
            )
            shares = _num(_ci(row, "Shares", "shares"))
            price = _num(_ci(row, "Price", "price", "PricePerShare"))
            value = shares * price if (shares is not None and price is not None) else None
            out.append(
                {
                    **owner,
                    "ticker": ticker,
                    "transaction_date": _iso_date(_ci(row, "Date", "transaction_date", "date")),
                    "transaction_code": code,
                    "transaction_label": TRANSACTION_CODE_LABELS.get(code) if code else None,
                    "shares": shares,
                    "price": price,
                    "value": value,
                    "acquired_disposed": acquired_disposed,
                    "is_10b5_1": is_plan,
                    "accession": accession or None,
                    "filed_date": filed_date,
                }
            )
        return out
    except Exception as exc:  # pragma: no cover - defensive top-level guard
        logger.warning("Form 4 extraction failed for %s: %s", accession, exc)
        return []


def _is_buy(txn: dict) -> bool:
    # The transaction code is authoritative for open-market trades (P = purchase, S = sale);
    # the acquired/disposed flag is only a fallback for rows with no code. This keeps buy/sell
    # mutually exclusive (a contradictory P+D row counts once, as a buy) and ignores
    # non-open-market codes (A grant, M exercise, F tax, G gift, ...) even if a caller passes
    # rows that bypassed `market_trades`.
    code = txn.get("transaction_code")
    if code:
        return code == "P"
    return txn.get("acquired_disposed") == "A"


def _is_sell(txn: dict) -> bool:
    code = txn.get("transaction_code")
    if code:
        return code == "S"
    return txn.get("acquired_disposed") == "D"


def _sum(txns: list[dict], key: str) -> float:
    return float(sum(t[key] for t in txns if isinstance(t.get(key), (int, float)) and not isinstance(t.get(key), bool)))


def transactions_in_window(
    transactions: list[dict], window_days: int, *, now: Optional[date] = None
) -> list[dict]:
    """Trailing-window slice: transactions on/after ``today - window_days``.

    Uses the transaction date (falling back to filed date); rows with no parseable date are
    excluded. Shared by ``summarize_insider_activity`` and the orchestration layer so the
    windowed summary and the returned transaction list/count always describe the same set.
    """
    cutoff = (now or datetime.now(timezone.utc).date()) - timedelta(days=window_days)

    def in_window(txn: dict) -> bool:
        iso = _iso_date(txn.get("transaction_date")) or _iso_date(txn.get("filed_date"))
        if not iso:
            return False
        try:
            return date.fromisoformat(iso) >= cutoff
        except ValueError:
            return False

    return [t for t in transactions if in_window(t)]


def summarize_insider_activity(
    transactions: list[dict], window_days: int = 90, *, now: Optional[date] = None
) -> dict:
    """Aggregate buy/sell activity over a trailing window, with a 10b5-1 split.

    Buys = code 'P' (purchase); sells = code 'S' (sale); see ``_is_buy``/``_is_sell``.
    ``market_trades`` is already open-market only, so this is the discretionary-vs-plan
    insider signal, not grants/option mechanics.
    """

    window = transactions_in_window(transactions, window_days, now=now)
    buys = [t for t in window if _is_buy(t)]
    sells = [t for t in window if _is_sell(t)]
    disc_buys = [t for t in buys if not t.get("is_10b5_1")]
    disc_sells = [t for t in sells if not t.get("is_10b5_1")]

    buy_shares, sell_shares = _sum(buys, "shares"), _sum(sells, "shares")
    # A *_value is None only when there are no priced trades ("no data"), kept distinct from a
    # genuine 0.0 — `buy_value or None` would wrongly collapse a real net-zero dollar flow to
    # None whenever buys and sells net out.
    buy_priced = any(t.get("value") is not None for t in buys)
    sell_priced = any(t.get("value") is not None for t in sells)
    buy_value = _sum(buys, "value") if buy_priced else None
    sell_value = _sum(sells, "value") if sell_priced else None
    net_value = (
        (buy_value or 0.0) - (sell_value or 0.0) if (buy_priced or sell_priced) else None
    )
    dates = [d for d in (_iso_date(t.get("transaction_date")) for t in window) if d]

    return {
        "window_days": window_days,
        "buy_count": len(buys),
        "sell_count": len(sells),
        "buy_shares": buy_shares,
        "sell_shares": sell_shares,
        "buy_value": buy_value,
        "sell_value": sell_value,
        "net_shares": buy_shares - sell_shares,
        "net_value": net_value,
        "discretionary_net_shares": _sum(disc_buys, "shares") - _sum(disc_sells, "shares"),
        "plan_10b5_1_sell_shares": _sum(
            [t for t in sells if t.get("is_10b5_1")], "shares"
        ),
        "last_transaction_date": max(dates) if dates else None,
    }
