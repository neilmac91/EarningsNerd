"""One unit per series in the multi-period dataset (E102).

A series whose figures name different units (a leftover USD row beside native-currency rows, USD/shares beside
CNY/shares) would chart, compare and compound as one series, and the narrative and exports would read it so. The
whole dataset is refused instead, before any comparison, window figure, observation, narrative or export reads it:
no series is split, no value converted, no point dropped.
"""
from typing import Any, Optional, TypeVar, Union

Row = TypeVar("Row")

# One sentence, as the page's other dataset refusals print in the error Notice's title (chief design on #1719).
INCOMPATIBLE_UNITS_MESSAGE = "Figures in the selected period range mix currencies or units, so they can't be compared."


class IncompatibleUnitsError(ValueError):
    """The dataset refusal for figures that do not share one unit. The routes send its message as they send every
    dataset refusal (a ValueError: the dataset route's 400, the stream's error event). An export rebuilds a dataset the
    page built, so it answers 409 (the data changed since): the xlsx route when the request names the page's snapshot,
    the PDF route through its re-run check. ``code`` is the stable domain code for the analysis routes' error adapter
    once the shared error vocabulary (E31) lands."""

    code = "analysis_incompatible_units"

    def __init__(self) -> None:
        super().__init__(INCOMPATIBLE_UNITS_MESSAGE)


class UnitConflict:
    """An index entry for a period of a concept whose current facts name different units."""


UNIT_CONFLICT = UnitConflict()


def keep_one_unit(index: dict, key: Any, row: Any) -> None:
    """Index ``row`` under ``key``, the later row winning as before. Two current rows for one key that name
    different units mark the key a conflict, in whatever order they arrive, so the dataset that reads that
    period is refused (``one_unit``); one outside the selected periods refuses nothing."""
    held = index.get(key)
    index[key] = UNIT_CONFLICT if held is UNIT_CONFLICT or (held is not None and held.unit != row.unit) else row


def one_unit(row: Union[Row, UnitConflict, None]) -> Optional[Row]:
    """The indexed row for a period, or ``None``; a period whose current facts conflict refuses the dataset."""
    if row is UNIT_CONFLICT:
        raise IncompatibleUnitsError()
    return row


def series_unit(points: list[dict]) -> str:
    """The one unit every valued point of a series names, or ``IncompatibleUnitsError``. A point with no value is
    absent, never incompatible, and names no unit for the series; a numeric zero is a value; a ratio series names
    ``pure`` throughout. A series with no valued point takes a listed point's unit, else USD, as before."""
    units = {point.get("unit") for point in points if point.get("value") is not None}
    if len(units) > 1 or not all(isinstance(unit, str) and unit.strip() for unit in units):
        raise IncompatibleUnitsError()
    return next(iter(units), None) or next((point["unit"] for point in points if point.get("unit")), "USD")
