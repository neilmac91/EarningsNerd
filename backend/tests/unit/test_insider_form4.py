"""A Form 4 is parsed from its XML alone (ADR 0009): app/services/insider_form4.py.

The conftest's network gate fails any test that reaches a non-loopback host, so every parse here proves the
point of the module: no reporting owner is looked up. The documents are written to SEC's schema
(tests/support/form4_documents.py), not recorded.
"""
from importlib.metadata import version

import pytest

from app.services import insider_form4
from app.services.insider_form4 import (
    Form4ParseError,
    Form4ParserUnsupported,
    ownership_document_in,
    parse_form4,
    parse_form4_transactions,
)
from tests.support.form4_documents import OPTION_EXERCISE, form4, owner, submission_text, trade

PLAN_NOTE = "The sale was effected pursuant to a Rule 10b5-1 trading plan adopted by the reporting person on May 1, 2026."


def rows(document: str) -> list[dict]:
    return parse_form4_transactions(document, accession="0000999999-26-000001", filed_date="2026-10-03")


def test_an_officers_purchase_and_sale_become_two_rows_in_the_endpoints_shape():
    document = form4(trades=[trade("P", "1000", "150.25", "2026-10-01"), trade("S", "400", "155.10", "2026-10-02")])
    buy, sell = rows(document)
    assert buy == {
        "insider_name": "Jane Doe", "insider_title": "Chief Financial Officer",
        "is_director": False, "is_officer": True, "is_ten_pct_owner": False,
        "ticker": "EXMP", "transaction_date": "2026-10-01", "transaction_code": "P", "transaction_label": buy["transaction_label"],
        "shares": 1000.0, "price": 150.25, "value": 150250.0, "acquired_disposed": "A", "is_10b5_1": False,
        "accession": "0000999999-26-000001", "filed_date": "2026-10-03",
    }
    assert buy["transaction_label"] and sell["transaction_label"] and buy["transaction_label"] != sell["transaction_label"]
    assert (sell["transaction_code"], sell["shares"], sell["price"], sell["acquired_disposed"]) == ("S", 400.0, 155.10, "D")
    assert sell["value"] == pytest.approx(62040.0)


def test_a_plan_is_read_from_the_checkbox_and_from_a_footnote_and_marks_the_filing():
    by_box = rows(form4(trades=[trade("S", "400", "155.10", "2026-10-02")], plan_box=1))
    assert [row["is_10b5_1"] for row in by_box] == [True]
    # Older filings have no checkbox: the footnote on the trade says so.
    by_note = rows(form4(trades=[trade("S", "400", "155.10", "2026-10-02", code_footnote="F1")],
                         footnotes={"F1": PLAN_NOTE}, plan_box=None))
    assert [row["is_10b5_1"] for row in by_note] == [True]
    neither = rows(form4(trades=[trade("S", "400", "155.10", "2026-10-02")], plan_box=None))
    assert [row["is_10b5_1"] for row in neither] in ([False], [None])


def test_a_company_owner_keeps_its_name_and_a_person_is_shown_first_name_first():
    fund = owner("Example Capital Partners LP", cik="0001111111", ten_percent=True)
    director = owner("Smith John A", cik="0002222222", director=True)
    (row,) = rows(form4(owners=[fund, director], trades=[trade("S", "5000", "20.00", "2026-10-02")]))
    # One row per trade, not per owner. The flags are the first owner's, as the live path had them.
    assert "Example Capital Partners LP" in row["insider_name"] and "John A Smith" in row["insider_name"]
    assert "Lp" not in row["insider_name"] and "Partners Lp Example" not in row["insider_name"]
    assert (row["is_ten_pct_owner"], row["is_director"]) == (True, False)
    for filed, shown in [("Doe Jane", "Jane Doe"), ("Acme Holdings Inc.", "Acme Holdings Inc."), ("Vanguard Group Inc", "Vanguard Group Inc"),
                         ("Family Trust", "Family Trust"), ("Banks Tyra", "Tyra Banks")]:
        (named,) = rows(form4(owners=[owner(filed, director=True)], trades=[trade("P", "1", "1.00", "2026-10-01")]))
        assert named["insider_name"] == shown, filed


def test_a_filing_with_no_open_market_trade_has_no_rows():
    assert rows(form4(derivatives=OPTION_EXERCISE)) == []
    assert rows(form4()) == []
    # An award (A), a gift (G) and tax withholding (F) are not open-market trades.
    for code in ("A", "G", "F"):
        assert rows(form4(trades=[trade(code, "100", "0", "2026-10-01", acquired="A")])) == [], code


def test_a_trade_whose_price_is_only_in_a_footnote_has_no_price_and_no_value():
    (row,) = rows(form4(trades=[trade("S", "400", None, "2026-10-02", price_footnote="F2")],
                        footnotes={"F2": "Weighted average price; see remarks."}))
    assert (row["shares"], row["price"], row["value"]) == (400.0, None, None)


@pytest.mark.parametrize("text", [
    "", "<html><body><h1>Request Rate Threshold Exceeded</h1></body></html>", "not xml at all",
    "<?xml version='1.0'?><edgarSubmission><formType>13F-HR</formType></edgarSubmission>",
    form4(document_type="4/A", trades=[trade("S", "1", "1.00", "2026-10-02")]),
    form4(owners=[], trades=[trade("S", "1", "1.00", "2026-10-02")]),
])
def test_anything_that_is_not_a_form_4_document_is_refused_not_read_as_no_trades(text):
    # An error page answered with a 200 must not be stored as "this filing has no trades".
    with pytest.raises(Form4ParseError):
        rows(text)


def test_the_document_is_found_inside_a_submissions_text_file():
    document = form4(trades=[trade("P", "1000", "150.25", "2026-10-01")])
    found = ownership_document_in(submission_text(document))
    assert found is not None and rows(found) == rows(document)
    assert ownership_document_in("<SEC-DOCUMENT>no xml here</SEC-DOCUMENT>") is None
    assert ownership_document_in("") is None


def test_the_parse_refuses_an_edgartools_it_was_not_checked_against(monkeypatch):
    # The parts it assembles are edgartools internals. requirements.txt pins the version it was checked against.
    assert version("edgartools") == insider_form4.SUPPORTED_EDGARTOOLS
    monkeypatch.setattr(insider_form4, "SUPPORTED_EDGARTOOLS", "0.0.0")
    with pytest.raises(Form4ParserUnsupported):
        rows(form4(trades=[trade("P", "1", "1.00", "2026-10-01")]))


@pytest.mark.parametrize("filed, read", [("0000999999", "999999"), ("320193", "320193"), ("", None), ("n/a", None), ("0000000000", None)])
def test_the_document_says_whose_shares_it_reports(filed, read):
    parsed = parse_form4(form4(issuer_cik=filed, trades=[trade("P", "10", "1.00", "2026-10-01")]),
                         accession="0000999999-26-000001")
    assert parsed.issuer_cik == read
    assert len(parsed.transactions) == 1
