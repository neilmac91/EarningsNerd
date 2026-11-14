"""Form 4 ownership documents for tests, written to SEC's ownershipDocument schema (X0508). They are not
recorded filings: every name, CIK and number is invented. The insider scan's tests and the parser's share them."""
from __future__ import annotations

from typing import Optional


def owner(name: str, *, cik: str = "0001234567", director: bool = False, officer: bool = False,
          ten_percent: bool = False, title: Optional[str] = None) -> str:
    title_tag = f"<officerTitle>{title}</officerTitle>" if title else ""
    return f"""
    <reportingOwner>
        <reportingOwnerId><rptOwnerCik>{cik}</rptOwnerCik><rptOwnerName>{name}</rptOwnerName></reportingOwnerId>
        <reportingOwnerAddress><rptOwnerStreet1>1 Main St</rptOwnerStreet1><rptOwnerCity>Anytown</rptOwnerCity>
            <rptOwnerState>CA</rptOwnerState><rptOwnerZipCode>90000</rptOwnerZipCode></reportingOwnerAddress>
        <reportingOwnerRelationship>
            <isDirector>{int(director)}</isDirector><isOfficer>{int(officer)}</isOfficer>
            <isTenPercentOwner>{int(ten_percent)}</isTenPercentOwner><isOther>0</isOther>{title_tag}
        </reportingOwnerRelationship>
    </reportingOwner>"""


def trade(code: str, shares: str, price: Optional[str], date: str, *, acquired: Optional[str] = None,
          code_footnote: Optional[str] = None, price_footnote: Optional[str] = None) -> str:
    acquired = acquired or ("A" if code == "P" else "D")
    code_note = f'<footnoteId id="{code_footnote}"/>' if code_footnote else ""
    price_note = f'<footnoteId id="{price_footnote}"/>' if price_footnote else ""
    price_value = f"<value>{price}</value>" if price is not None else ""
    return f"""
        <nonDerivativeTransaction>
            <securityTitle><value>Common Stock</value></securityTitle>
            <transactionDate><value>{date}</value></transactionDate>
            <transactionCoding><transactionFormType>4</transactionFormType><transactionCode>{code}</transactionCode>
                <equitySwapInvolved>0</equitySwapInvolved>{code_note}</transactionCoding>
            <transactionAmounts>
                <transactionShares><value>{shares}</value></transactionShares>
                <transactionPricePerShare>{price_value}{price_note}</transactionPricePerShare>
                <transactionAcquiredDisposedCode><value>{acquired}</value></transactionAcquiredDisposedCode>
            </transactionAmounts>
            <postTransactionAmounts><sharesOwnedFollowingTransaction><value>10000</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
            <ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature>
        </nonDerivativeTransaction>"""


OPTION_EXERCISE = """
        <derivativeTransaction>
            <securityTitle><value>Stock Option (Right to Buy)</value></securityTitle>
            <conversionOrExercisePrice><value>50.00</value></conversionOrExercisePrice>
            <transactionDate><value>2026-10-05</value></transactionDate>
            <transactionCoding><transactionFormType>4</transactionFormType><transactionCode>M</transactionCode>
                <equitySwapInvolved>0</equitySwapInvolved></transactionCoding>
            <transactionAmounts>
                <transactionShares><value>2000</value></transactionShares>
                <transactionPricePerShare><value>0</value></transactionPricePerShare>
                <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
            </transactionAmounts>
            <exerciseDate><value>2024-01-01</value></exerciseDate>
            <expirationDate><value>2031-01-01</value></expirationDate>
            <underlyingSecurity><underlyingSecurityTitle><value>Common Stock</value></underlyingSecurityTitle>
                <underlyingSecurityShares><value>2000</value></underlyingSecurityShares></underlyingSecurity>
            <postTransactionAmounts><sharesOwnedFollowingTransaction><value>0</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
            <ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature>
        </derivativeTransaction>"""


def form4(*, owners: Optional[list[str]] = None, trades: Optional[list[str]] = None, derivatives: str = "",
          footnotes: Optional[dict[str, str]] = None, plan_box: Optional[int] = 0, document_type: str = "4",
          ticker: str = "EXMP", period: str = "2026-10-01", issuer_cik: str = "0000999999") -> str:
    owners = owners if owners is not None else [owner("Doe Jane", officer=True, title="Chief Financial Officer")]
    non_derivative = f"<nonDerivativeTable>{''.join(trades)}</nonDerivativeTable>" if trades else ""
    derivative = f"<derivativeTable>{derivatives}</derivativeTable>" if derivatives else ""
    notes = "".join(f'<footnote id="{key}">{text}</footnote>' for key, text in (footnotes or {}).items())
    plan = f"<aff10b5One>{plan_box}</aff10b5One>" if plan_box is not None else ""
    return f"""<?xml version="1.0"?>
<ownershipDocument>
    <schemaVersion>X0508</schemaVersion>
    <documentType>{document_type}</documentType>
    <periodOfReport>{period}</periodOfReport>
    <notSubjectToSection16>0</notSubjectToSection16>
    {plan}
    <issuer><issuerCik>{issuer_cik}</issuerCik><issuerName>Example Corp</issuerName>
        <issuerTradingSymbol>{ticker}</issuerTradingSymbol></issuer>
    {''.join(owners)}
    {non_derivative}
    {derivative}
    <footnotes>{notes}</footnotes>
    <ownerSignature><signatureName>/s/ Signer</signatureName><signatureDate>2026-10-03</signatureDate></ownerSignature>
</ownershipDocument>"""


def submission_text(document: str, *, accession: str = "0000999999-26-000001") -> str:
    """A filing's complete submission text file holding ``document`` as its primary document."""
    return f"""<SEC-DOCUMENT>{accession}.txt : 20261003
<SEC-HEADER>{accession}.hdr.sgml : 20261003
ACCESSION NUMBER:		{accession}
CONFORMED SUBMISSION TYPE:	4
</SEC-HEADER>
<DOCUMENT>
<TYPE>4
<SEQUENCE>1
<FILENAME>form4.xml
<TEXT>
<XML>
{document}
</XML>
</TEXT>
</DOCUMENT>
</SEC-DOCUMENT>
"""
