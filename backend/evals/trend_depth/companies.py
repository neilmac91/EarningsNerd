"""Company sets for the Multi-Period Analysis depth evaluation.

EVAL_SET: 20 companies, one development and one held-out company per sector, so a prompt tuned on the
development half is scored on unseen companies whose metrics behave the same way (a bank against a
bank, a loss-maker against a loss-maker). Never tune a prompt while reading held-out outputs. The census
showed that the current pipeline cannot build an annual analysis for insurers and managed-care companies
(their top line ingests as premiums, so no year has core data) and that XOM now resolves to a new holding
company CIK with one quarter of facts; the set therefore uses COP for energy and a software pair in place
of UNH and PGR.

CENSUS_EXTRA: 20 more companies; with EVAL_SET they form the 40-company census of the CURRENT pipeline.

PEERS: sector peer groups ingested into the harness's own facts store for percentile context. A peer
group always includes the eval companies of that sector.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalCompany:
    ticker: str
    sector: str
    split: str  # "dev" | "holdout" | "census"
    profile: str  # "operating" | "loss_making" | "bank" | "insurer"
    peer_group: str


EVAL_SET: tuple[EvalCompany, ...] = (
    EvalCompany("REGN", "Biopharma", "dev", "operating", "biopharma"),
    EvalCompany("VRTX", "Biopharma", "holdout", "operating", "biopharma"),
    EvalCompany("SNAP", "Internet (loss-making)", "dev", "loss_making", "internet"),
    EvalCompany("RIVN", "Autos (loss-making)", "holdout", "loss_making", "autos"),
    EvalCompany("JPM", "Banks", "dev", "bank", "banks"),
    EvalCompany("USB", "Banks", "holdout", "bank", "banks"),
    EvalCompany("COST", "Retail", "dev", "operating", "retail"),
    EvalCompany("TGT", "Retail", "holdout", "operating", "retail"),
    EvalCompany("NVDA", "Semiconductors", "dev", "operating", "semis"),
    EvalCompany("AMD", "Semiconductors", "holdout", "operating", "semis"),
    EvalCompany("COP", "Energy", "dev", "operating", "energy"),
    EvalCompany("CVX", "Energy", "holdout", "operating", "energy"),
    EvalCompany("PG", "Consumer staples", "dev", "operating", "staples"),
    EvalCompany("KO", "Consumer staples", "holdout", "operating", "staples"),
    EvalCompany("CAT", "Industrials", "dev", "operating", "industrials"),
    EvalCompany("DE", "Industrials", "holdout", "operating", "industrials"),
    EvalCompany("NEE", "Utilities", "dev", "operating", "utilities"),
    EvalCompany("DUK", "Utilities", "holdout", "operating", "utilities"),
    EvalCompany("MSFT", "Software", "dev", "operating", "software"),
    EvalCompany("ORCL", "Software", "holdout", "operating", "software"),
)

# The census of the CURRENT pipeline ran on the first eval set below plus CENSUS_EXTRA, with the
# substitutions census.py records (XOM -> COP, UNH -> CVS, PGR -> CB, PLD -> SO; see census/README.md).
_CENSUS_FIRST_TWENTY: tuple[EvalCompany, ...] = (
    EvalCompany("REGN", "Biopharma", "dev", "operating", "biopharma"),
    EvalCompany("VRTX", "Biopharma", "holdout", "operating", "biopharma"),
    EvalCompany("SNAP", "Internet (loss-making)", "dev", "loss_making", "internet"),
    EvalCompany("RIVN", "Autos (loss-making)", "holdout", "loss_making", "autos"),
    EvalCompany("JPM", "Banks", "dev", "bank", "banks"),
    EvalCompany("USB", "Banks", "holdout", "bank", "banks"),
    EvalCompany("COST", "Retail", "dev", "operating", "retail"),
    EvalCompany("TGT", "Retail", "holdout", "operating", "retail"),
    EvalCompany("NVDA", "Semiconductors", "dev", "operating", "semis"),
    EvalCompany("AMD", "Semiconductors", "holdout", "operating", "semis"),
    EvalCompany("XOM", "Energy", "dev", "operating", "energy"),
    EvalCompany("CVX", "Energy", "holdout", "operating", "energy"),
    EvalCompany("PG", "Consumer staples", "dev", "operating", "staples"),
    EvalCompany("KO", "Consumer staples", "holdout", "operating", "staples"),
    EvalCompany("CAT", "Industrials", "dev", "operating", "industrials"),
    EvalCompany("DE", "Industrials", "holdout", "operating", "industrials"),
    EvalCompany("NEE", "Utilities", "dev", "operating", "utilities"),
    EvalCompany("DUK", "Utilities", "holdout", "operating", "utilities"),
    EvalCompany("UNH", "Health care services", "dev", "operating", "healthcare_services"),
    EvalCompany("PGR", "Insurance", "holdout", "insurer", "insurance"),
)

CENSUS_EXTRA: tuple[EvalCompany, ...] = (
    EvalCompany("AAPL", "Technology hardware", "census", "operating", "megacap_tech"),
    EvalCompany("MSFT", "Software", "census", "operating", "megacap_tech"),
    EvalCompany("AMZN", "Internet retail", "census", "operating", "megacap_tech"),
    EvalCompany("GOOGL", "Internet", "census", "operating", "internet"),
    EvalCompany("META", "Internet", "census", "operating", "internet"),
    EvalCompany("WMT", "Retail", "census", "operating", "retail"),
    EvalCompany("HD", "Retail", "census", "operating", "retail"),
    EvalCompany("NKE", "Consumer discretionary", "census", "operating", "staples"),
    EvalCompany("DIS", "Media", "census", "operating", "media"),
    EvalCompany("BA", "Aerospace (loss-making)", "census", "loss_making", "industrials"),
    EvalCompany("PFE", "Biopharma", "census", "operating", "biopharma"),
    EvalCompany("LLY", "Biopharma", "census", "operating", "biopharma"),
    EvalCompany("BAC", "Banks", "census", "bank", "banks"),
    EvalCompany("GS", "Capital markets", "census", "bank", "banks"),
    EvalCompany("T", "Telecom", "census", "operating", "media"),
    EvalCompany("UPS", "Transportation", "census", "operating", "industrials"),
    EvalCompany("PLD", "REIT", "census", "operating", "utilities"),
    EvalCompany("NFLX", "Media", "census", "operating", "media"),
    EvalCompany("ORCL", "Software", "census", "operating", "megacap_tech"),
    EvalCompany("INTC", "Semiconductors", "census", "operating", "semis"),
)

# Peer groups for percentile context (latest fiscal year). Each lists tickers ingested into the
# harness's facts store through the production companyfacts ingest.
PEERS: dict[str, tuple[str, ...]] = {
    "biopharma": ("REGN", "VRTX", "AMGN", "GILD", "BIIB", "PFE", "LLY", "MRK", "BMY"),
    "internet": ("SNAP", "PINS", "META", "GOOGL", "TTD", "RDDT"),
    "autos": ("RIVN", "TSLA", "LCID", "F", "GM"),
    "banks": ("JPM", "USB", "BAC", "WFC", "C", "PNC", "TFC", "GS"),
    "retail": ("COST", "TGT", "WMT", "HD", "LOW", "DG", "BJ"),
    "semis": ("NVDA", "AMD", "INTC", "AVGO", "QCOM", "TXN", "MU"),
    "energy": ("COP", "CVX", "OXY", "EOG", "MPC", "PSX", "SLB"),
    "staples": ("PG", "KO", "PEP", "CL", "KMB", "MDLZ", "NKE"),
    "industrials": ("CAT", "DE", "HON", "ETN", "EMR", "PH", "BA", "UPS"),
    "utilities": ("NEE", "DUK", "SO", "D", "AEP", "XEL", "PLD"),
    "healthcare_services": ("UNH", "ELV", "CI", "HUM", "CVS", "CNC"),
    "insurance": ("PGR", "TRV", "ALL", "CB", "HIG"),
    "megacap_tech": ("AAPL", "MSFT", "AMZN", "ORCL"),
    "software": ("MSFT", "ORCL", "ADBE", "CRM", "NOW", "INTU", "ADP"),
    "media": ("DIS", "NFLX", "T", "CMCSA"),
}

# Companies whose outputs the blind human pack shows (current vs proposed). Chosen to span the
# metric behaviours the spec is meant to handle: a large-cap operating company with a product mix,
# a loss-maker, a bank, a retailer with a non-calendar year and a held-out company.
HUMAN_PACK: tuple[str, ...] = ("REGN", "SNAP", "JPM", "COST", "VRTX")


def eval_companies(split: str | None = None) -> list[EvalCompany]:
    return [c for c in EVAL_SET if split is None or c.split == split]


def census_companies() -> list[EvalCompany]:
    return [*_CENSUS_FIRST_TWENTY, *CENSUS_EXTRA]


def by_ticker(ticker: str) -> EvalCompany:
    for company in (*EVAL_SET, *_CENSUS_FIRST_TWENTY, *CENSUS_EXTRA):
        if company.ticker == ticker:
            return company
    raise KeyError(ticker)
