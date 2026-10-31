"""Withhold one complete reconciliation interpretation without reconstructing facts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import re
from typing import Any

LIMITATION = "This summary could not independently verify the stated directions of the adjusted EBITDA reconciliation."
MONEY = "\\$(?:[0-9]{1,3}(?:,[0-9]{3}){1,3}|[0-9]{1,12})(?:\\.[0-9]{1,3})? (?:thousand|million)"
MONTH = "(?:January|February|March|April|May|June|July|August|September|October|November|December)"
DATE = f"{MONTH} [0-9]{{1,2}}, [0-9]{{4}}"
FIRST = f"Reported net income of (?P<net>{MONEY}) includes a (?P<cogs>{MONEY}) reduction in cost of goods sold recognized for IEEPA tariff refunds, (?P<rounded_refund>{MONEY}) of which relates to IEEPA tariffs on goods sold in the prior fiscal year\\."
SECOND = f"The company's defined Adjusted EBITDA of (?P<total>{MONEY}) deducts that (?P<refund>{MONEY}) prior-year refund, along with other income net, provision for income taxes, depreciation and amortization, and stock-based compensation and related expense\\."
THIRD = f"The company also recognized a (?P<inventory>{MONEY}) reduction in the carrying value of inventories on hand as of (?P<date>{DATE}) for tariffs previously capitalized as cost of inventory\\."
WHOLE = re.compile(f"\\A(?P<first>{FIRST})(?P<gap1> )(?P<second>{SECOND})(?P<gap2> )(?P<third>{THIRD})\\Z")


def _value(money: str) -> Decimal:
    number, unit = money[1:].split(" ")
    return Decimal(number.replace(",", "")) * {"thousand": 1000, "million": 1000000}[unit]


def _bucket(money: str, operand: int) -> bool:
    number, unit = money[1:].split(" ")
    decimals = len(number.split(".")[1]) if "." in number else 0
    resolution = Decimal({"thousand": 1000, "million": 1000000}[unit]) / 10**decimals
    return abs(_value(money) - operand) <= resolution / 2


AUDIT_KEY = "reconciliation_direction_audit"


def strip_reconciliation_metadata(value: Any) -> None:
    """The model cannot supply this application's audit at any payload depth."""
    if isinstance(value, dict):
        value.pop(AUDIT_KEY, None)
        for child in value.values():
            strip_reconciliation_metadata(child)
    elif isinstance(value, list):
        for child in value:
            strip_reconciliation_metadata(child)


def withhold_reconciliation_directions(
    sections: dict[str, Any],
    index: Any,
    *,
    filing_type: str = "",
    recovered: bool = False,
) -> dict | None:
    """Own the entire finite envelope and retain independent authored sentences exactly.

    Native operands select a narrow interpretation family. They never authorize
    positive financial prose or assert that a source disclosure is absent.
    """
    strip_reconciliation_metadata(sections)
    section = sections.get("earnings_quality")
    if not isinstance(section, dict) or filing_type != "10-Q" or recovered:
        return None
    canonical, camel = section.get("operating_vs_one_time"), section.get("operatingVsOneTime")
    if canonical and camel and canonical != camel:
        return None
    authored = canonical or camel
    if not isinstance(authored, str):
        return None
    match = WHOLE.fullmatch(authored)
    if match is None:
        return None
    try:
        authored_date = datetime.strptime(match["date"], "%B %d, %Y").date().isoformat()
    except ValueError:
        return None
    operands = index.reconciliation_operands() if index is not None else None
    if operands is None:
        return None
    current = operands["current"]
    if (
        authored_date != operands["report_period"]
        or _value(match["net"]) != current[0]
        or _value(match["total"]) != current[-1]
        or _value(match["refund"]) != abs(current[-2])
        or not _bucket(match["rounded_refund"], abs(current[-2]))
        or sum(column[-1] == current[-1] for column in operands["columns"]) != 1
        or not any(amount > 0 for amount in current[1:-1])
    ):
        return None
    # This is a whole proposition replacement. Independent sentences stay authored;
    # no renderer marker turns them into source-verified financial statements.
    preserved = {"first": match["first"], "third": match["third"]}
    section.pop("operatingVsOneTime", None)
    section["operating_vs_one_time"] = (
        preserved["first"] + match["gap1"] + LIMITATION + match["gap2"] + preserved["third"]
    )
    return {
        "slot": "earnings_quality.operating_vs_one_time",
        "reason": "directions_not_verified",
        "preserved_authored": preserved,
        "source_operands": operands,
    }
