"""Display-only formatting after observation selection; never used in model inputs."""
from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP


_CURRENCY_AMOUNT = re.compile(r"\b([A-Z]{3}) (-?\d[\d,]*(?:\.\d+)?)( per share)?\b")
_SCALES = ((Decimal("1e12"), "T"), (Decimal("1e9"), "B"),
           (Decimal("1e6"), "M"), (Decimal("1e3"), "K"))


def period_label(text: str) -> str:
    return re.sub(r"\b(\d{4})Q([1-4])\b", r"Q\2 \1", text)


def _compact_currency(currency: str, amount: str, per_share: bool) -> str:
    value = Decimal(amount.replace(",", ""))
    scale, suffix = next(((scale, suffix) for scale, suffix in _SCALES
                          if abs(value) >= scale and not per_share), (Decimal(1), ""))
    digits = 2 if per_share or abs(value) < 1 else 1
    rendered = abs(value / scale).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    prefix = "$" if currency == "USD" else f"{currency}\u00a0"
    return f"{'-' if value < 0 else ''}{prefix}{rendered:,.{digits}f}{suffix}" + (
        " per share" if per_share else ""
    )


def currency_precision_plan(text: str) -> frozenset[tuple[str, str, bool]]:
    """Keep distinct source amounts distinct even across citations/Markdown text nodes."""
    displays: dict[str, set[tuple[str, str, bool]]] = {}
    for match in _CURRENCY_AMOUNT.finditer(text):
        currency, amount, per_share = match.groups()
        key = (currency, amount.replace(",", ""), bool(per_share))
        display = _compact_currency(currency, amount, bool(per_share))
        displays.setdefault(display, set()).add(key)
    return frozenset(key for amounts in displays.values() if len(amounts) > 1 for key in amounts)


def compact_narrative_text(
    text: str, precision: frozenset[tuple[str, str, bool]] | None = None,
) -> str:
    """Render only code-owned sentences, with the whole-narrative precision policy."""
    if precision is None:
        precision = currency_precision_plan(text)

    def currency(match: re.Match[str]) -> str:
        currency, amount, per_share = match.groups()
        key = (currency, amount.replace(",", ""), bool(per_share))
        return match[0] if key in precision else _compact_currency(currency, amount, bool(per_share))

    def ratio(match: re.Match[str]) -> str:
        value = Decimal(match[1])
        rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        # Do not turn a strict liquidity threshold into "1.00× above 1.00×".
        display = match[1] if value != 1 and rounded == 1 else str(rounded)
        return f"{display}×"

    text = _CURRENCY_AMOUNT.sub(currency, text)
    text = re.sub(r"\b(\d+\.\d+)x\b", ratio, text)
    return period_label(text)
