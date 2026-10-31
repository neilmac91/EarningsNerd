"""Accounting scope of selected net-income concepts shared by financial consumers."""
from typing import Any

# Selected-concept meanings, not a claim that an undimensioned fact proves entity scope.
# FASB 2025 documentation distinguishes parent, common-holder, and NCI-inclusive income;
# IFRS ProfitLoss is the total, with owners-of-parent profit separately tagged.
_NET_INCOME_BASES = {
    "us-gaap:NetIncomeLoss": "attributable to the parent",
    "us-gaap:ProfitLoss": "including noncontrolling interests",
    "us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic": "available to common shareholders",
    "ifrs-full:ProfitLoss": "including noncontrolling interests",
    "ifrs-full:ProfitLossAttributableToOwnersOfParent": "attributable to owners of the parent",
}


def net_income_basis(concept: Any) -> str | None:
    """Name only the selected source concept; missing and custom concepts stay unknown."""
    return _NET_INCOME_BASES.get(concept) if isinstance(concept, str) else None
