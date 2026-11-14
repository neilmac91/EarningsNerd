"""Parse one SEC Form 4 into the insider endpoint's trade rows, from its XML alone (ADR 0009).

edgartools builds its ``Form4`` object from this XML, but on the way it downloads every reporting owner's own
submissions (``ReportingOwners.from_reporting_owner_tags`` calls ``Entity(cik).data``) to learn one thing: whether
the owner is a company, so as not to reverse its name. That is one extra SEC request per filing. This module
assembles the same object from edgartools' own parts without that lookup, then hands it to
``ownership_extractor.extract_form4_transactions``, so the rows are the ones the live path produced.

The parts used are edgartools internals, not its public interface, so the parse refuses to run on a version it
was not checked against, and ``tests/unit/test_insider_form4.py`` parses Form 4 documents with the network closed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from importlib.metadata import version
from typing import Any, Optional

from app.services.ownership_extractor import extract_form4_transactions

# Recorded on each stored filing. Bump it when the rows this module produces for the same document change; no code
# parses a stored filing again, so the change that needs that resets the rows in its own migration.
PARSER_VERSION = 1
# The edgartools release whose internals this was checked against (backend/requirements.txt pins it).
SUPPORTED_EDGARTOOLS = "5.62.1"

_OWNERSHIP_DOCUMENT_RE = re.compile(r"<ownershipDocument\b.*?</ownershipDocument>", re.DOTALL)
# An owner that is a company is named as written; a person is filed "Last First" and shown "First Last".
# Without the owner lookup the name itself is the evidence: these words do not end a person's name.
_COMPANY_NAME_RE = re.compile(
    r"\b(llc|l\.l\.c\.|lp|l\.p\.|llp|ltd|limited|inc|incorporated|corp|corporation|co|company|plc|n\.v\.|nv|ag|sa|"
    r"s\.a\.|gmbh|trust|fund|funds|partners|partnership|capital|holdings|holding|management|advisors|advisers|"
    r"group|foundation|associates|investments|ventures|bank|enterprises)\.?$",
    re.IGNORECASE,
)


class Form4ParseError(ValueError):
    """The text is not a Form 4 ownership document this parser can read."""


class Form4ParserUnsupported(RuntimeError):
    """edgartools is not the version this parser was checked against."""


def parser_supported() -> bool:
    return version("edgartools") == SUPPORTED_EDGARTOOLS


def ownership_document_in(text: str) -> Optional[str]:
    """The ownership document inside a filing's complete submission text, or None when it has none."""
    found = _OWNERSHIP_DOCUMENT_RE.search(text or "")
    return found.group(0) if found else None


def _officer_title(filed: Optional[str], remarks: str) -> Optional[str]:
    """A title filed as "See Remarks" is the document's remarks, as edgartools reads it
    (``ReportingOwners.from_reporting_owner_tags``)."""
    return remarks if filed and "see remarks" in filed.lower() else filed


def _build_form4(xml: str) -> Any:
    # Lazy: edgartools is heavy, and this module must stay importable where it is not installed.
    from edgar._party import Address
    from edgar.core import get_bool
    from edgar.display.formatting import reverse_name
    from edgar.ownership import Form4
    from edgar.ownership.forms import _parse_aff10b5_one
    from edgar.ownership.models import Footnotes, Issuer, OwnerSignatures
    from edgar.ownership.owners import Owner, ReportingOwners
    from edgar.ownership.table_containers import DerivativeTable, NonDerivativeTable
    from edgar.ownership.tables import (
        DerivativeHoldings,
        DerivativeTransactions,
        NonDerivativeHoldings,
        NonDerivativeTransactions,
    )
    from edgar.xmltools import child_text, find_all_elements, find_element, local_name, parse_xml

    try:
        root = parse_xml(xml)
    except Exception as exc:
        raise Form4ParseError(f"not XML: {type(exc).__name__}") from exc
    if root is None or local_name(root) != "ownershipDocument":
        raise Form4ParseError("no ownershipDocument")
    form = (child_text(root, "documentType") or "").strip()
    if form != "4":
        raise Form4ParseError(f"documentType is {form!r}, not 4")

    remarks = child_text(root, "remarks") or ""
    owners = []
    for tag in find_all_elements(root, "reportingOwner"):
        identity = find_element(tag, "reportingOwnerId")
        relationship = find_element(tag, "reportingOwnerRelationship")
        filed_name = (child_text(identity, "rptOwnerName") or "").strip() if identity is not None else ""
        is_company = bool(_COMPANY_NAME_RE.search(filed_name))

        def flag(name: str) -> bool:
            return bool(get_bool(child_text(relationship, name))) if relationship is not None else False

        owners.append(
            Owner(
                cik=child_text(identity, "rptOwnerCik") if identity is not None else None,
                is_company=is_company,
                name=filed_name if is_company else reverse_name(filed_name),
                name_unreversed=filed_name,
                address=Address(),
                is_director=flag("isDirector"),
                is_officer=flag("isOfficer"),
                is_other=flag("isOther"),
                is_ten_pct_owner=flag("isTenPercentOwner"),
                officer_title=_officer_title(child_text(relationship, "officerTitle"), remarks)
                if relationship is not None else None,
            )
        )
    if not owners:
        raise Form4ParseError("no reporting owner")

    issuer = find_element(root, "issuer")
    non_derivative = find_element(root, "nonDerivativeTable")
    derivative = find_element(root, "derivativeTable")
    return Form4(
        form=form,
        footnotes=Footnotes.extract(root),
        issuer=Issuer(
            cik=(child_text(issuer, "issuerCik") or "") if issuer is not None else "",
            name=(child_text(issuer, "issuerName") or "") if issuer is not None else "",
            ticker=(child_text(issuer, "issuerTradingSymbol") or "") if issuer is not None else "",
        ),
        reporting_owners=ReportingOwners(owners),
        non_derivative_table=(
            NonDerivativeTable.extract(non_derivative, form=form)
            if non_derivative is not None
            else NonDerivativeTable(holdings=NonDerivativeHoldings(), transactions=NonDerivativeTransactions(), form=form)
        ),
        derivative_table=(
            DerivativeTable.extract(derivative, form=form)
            if derivative is not None
            else DerivativeTable(holdings=DerivativeHoldings(), transactions=DerivativeTransactions(), form=form)
        ),
        signatures=OwnerSignatures([]),
        reporting_period=child_text(root, "periodOfReport"),
        remarks=remarks,
        no_securities=child_text(root, "noSecuritiesOwned") == "1",
        aff10b5_one=_parse_aff10b5_one(child_text(root, "aff10b5One")),
    )


@dataclass(frozen=True)
class ParsedForm4:
    """A Form 4 document: the issuer whose shares it reports, and its open-market trades."""

    issuer_cik: Optional[str]   # as the document names it, without leading zeros; None when it names none
    transactions: list[dict]


def parse_form4(xml: str, *, accession: str, filed_date: Optional[str] = None) -> ParsedForm4:
    """One Form 4 document's issuer and open-market trades (``extract_form4_transactions`` rows). No network.

    ``transactions`` is empty for a filing with no open-market trade (a grant, an exercise, a derivative-only
    filing). Raises ``Form4ParseError`` for text that is not a Form 4 document, and ``Form4ParserUnsupported`` on
    an edgartools version this was not checked against.
    """
    if not parser_supported():
        raise Form4ParserUnsupported(f"edgartools {version('edgartools')} is not {SUPPORTED_EDGARTOOLS}")
    try:
        form4 = _build_form4(xml)
        trades = form4.market_trades
        expected = 0 if trades is None else len(trades)
    except Form4ParseError:
        raise
    except Exception as exc:
        raise Form4ParseError(f"unreadable ownership document: {type(exc).__name__}") from exc
    transactions = extract_form4_transactions(form4, accession=accession, filed_date=filed_date)
    if len(transactions) != expected:
        # The extractor answers [] for whatever it cannot read, which a live fetch may show for an hour and a
        # stored filing would keep for good: a filing whose trades were not all read is not "no trades".
        raise Form4ParseError(f"{expected} open-market trades, {len(transactions)} read")
    issuer_cik = str(getattr(form4.issuer, "cik", "") or "").strip().lstrip("0")
    return ParsedForm4(issuer_cik=issuer_cik if issuer_cik.isdigit() else None, transactions=transactions)


def parse_form4_transactions(xml: str, *, accession: str, filed_date: Optional[str] = None) -> list[dict]:
    """The open-market trades in one Form 4 document: ``parse_form4`` without the issuer."""
    return parse_form4(xml, accession=accession, filed_date=filed_date).transactions
