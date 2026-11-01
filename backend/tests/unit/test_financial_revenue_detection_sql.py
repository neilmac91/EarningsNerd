"""The E264 revenue census reads the tags, the financial SIC band and the margin scale the code uses.

``ops/detection/financial_revenue_state.sql`` copies ``facts/fi_revenue.py``'s ``FEE_TAG`` and ``TOTAL_TAGS`` into each
statement that reads a tag, with the ``us-gaap:`` namespace the collector writes into ``raw_tag``; compares
``companies.sic`` as ``facts/concepts.py::_is_financial_sic`` does, as text in byte order between its two literals,
an empty or NULL code being none; and counts a margin above 100% where ``facts/derive.py`` stores margins as
percentages. This gate holds every copy to its source, the transaction to READ ONLY, and the file to statements that
read. Nothing runs the SQL in CI; its rehearsal on PostgreSQL is in its PR. Retire it with the SQL file, whose header
names it.
"""
import inspect
import re
from datetime import date
from pathlib import Path

from app.services.facts.companyfacts import normalize_companyfacts
from app.services.facts.concepts import _is_financial_sic
from app.services.facts.derive import derive_same_period_metrics
from app.services.facts.fi_revenue import FEE_TAG, TOTAL_TAGS

SQL = Path(__file__).resolve().parents[3] / "ops" / "detection" / "financial_revenue_state.sql"
NAMESPACE = "us-gaap:"
FEE_SETS, TOTAL_SETS, SIC_SETS = 4, 2, 7  # the statements that declare each parameter
FINANCIAL = "c.sic <> '' AND c.sic COLLATE \"C\" BETWEEN p.sic_low AND p.sic_high"


def _code() -> str:
    """The file without its comments and \\echo lines: the SQL psql sends."""
    lines = SQL.read_text().splitlines()
    return "\n".join(line.split("--", 1)[0] for line in lines if not line.lstrip().startswith("\\echo"))


def _item(val, end, start, accn):
    return {"val": val, "end": end, "start": start, "accn": accn, "form": "10-K",
            "filed": f"{int(end[:4]) + 1}-02-15", "fy": int(end[:4]), "fp": "FY"}


def _band() -> tuple[str, str]:
    found = re.findall(r'"(\d+)" <= str\(sic\) <= "(\d+)"', inspect.getsource(_is_financial_sic))
    assert len(found) == 1, "_is_financial_sic no longer reads as one lexical range: re-derive the SQL's predicate"
    return found[0]


def test_every_tag_reading_statement_copies_the_rules_tags():
    code = _code()
    fees = re.findall(r"'([^']*)'::text AS fee_tag", code)
    totals = re.findall(r"ARRAY\[([^\]]*)\]::text\[\] AS total_tags", code)
    assert fees == [NAMESPACE + FEE_TAG] * FEE_SETS
    assert [re.findall(r"'([^']*)'", t) for t in totals] == [[NAMESPACE + tag for tag in TOTAL_TAGS]] * TOTAL_SETS


def test_the_namespace_is_the_one_the_collector_writes():
    years = [_item(v, f"{y}-12-31", f"{y}-01-01", f"K{y}") for y, v in ((2023, 100.0), (2024, 120.0))]
    generic = {"facts": {"us-gaap": {FEE_TAG: {"units": {"USD": years}}}}}
    financial = {"facts": {"us-gaap": {TOTAL_TAGS[0]: {"units": {"USD": years}}}}}
    read = [normalize_companyfacts(1, generic, financial_sic=False)[0],
            normalize_companyfacts(1, financial, financial_sic=True)[0]]
    tags = [{f["raw_tag"] for f in facts if f["concept"] == "revenue"} for facts in read]
    assert tags == [{NAMESPACE + FEE_TAG}, {NAMESPACE + TOTAL_TAGS[0]}]


def test_every_financial_test_compares_the_code_as_is_financial_sic_does():
    code = _code()
    low, high = _band()
    bounds = re.findall(r"'(\d+)'::text AS sic_low, '(\d+)'::text AS sic_high", code)
    assert bounds == [(low, high)] * SIC_SETS
    comparisons = re.findall(r"c\.sic\s+(<>|!=|<=|>=|=|<|>|BETWEEN|COLLATE|IN|LIKE|ILIKE|~|IS)", code)
    assert code.count(FINANCIAL) == SIC_SETS and len(comparisons) == 2 * SIC_SETS  # no other test of the code

    def sql_band(sic):  # the predicate above: NULL <> '' is not true; COLLATE "C" compares bytes
        return sic is not None and sic != "" and low.encode() <= sic.encode() <= high.encode()
    for sic in (None, "", "6", "60", "6000", "6021", "60 1", "6799", "67990", "6800", "5999", "7372", "６０２１"):
        assert sql_band(sic) == _is_financial_sic(sic), sic


def test_a_margin_above_100_percent_is_above_the_files_threshold():
    thresholds = re.findall(r"(\d+)::numeric AS full_margin", _code())
    assert thresholds == ["100"]
    scope = {"company_id": 1, "fiscal_year": 2024, "fiscal_period": "FY", "unit": "USD", "accession": "K",
             "period_start": date(2024, 1, 1), "period_end": date(2024, 12, 31), "reconciled": True}
    facts = [{**scope, "concept": "revenue", "value": 40.0}, {**scope, "concept": "net_income", "value": 40.0}]
    margin = next(f for f in derive_same_period_metrics(facts) if f["concept"] == "net_margin")
    assert margin["value"] == float(thresholds[0])  # a net income equal to revenue is stored as the threshold


def test_the_file_reads_in_one_bounded_read_only_transaction():
    code = _code()
    statements = [s.strip() for s in code.split(";") if s.strip()]
    assert statements[:3] == ["BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
                              "SET LOCAL statement_timeout = '120s'", "SET LOCAL lock_timeout = '10s'"]
    assert statements[-1] == "COMMIT"
    assert all(s.startswith(("SELECT", "WITH")) for s in statements[3:-1])
    assert not re.search(r"\b(INSERT|UPDATE|DELETE|MERGE|ALTER|CREATE|DROP|TRUNCATE|GRANT|REVOKE|COPY|CALL|DO|"
                         r"LOCK|VACUUM|ANALYZE|REFRESH|SET\s+(?!LOCAL))\b", "\n".join(statements[3:-1]),
                         re.IGNORECASE)


def test_the_header_names_its_gate_and_its_retirement():
    header = SQL.read_text().split("BEGIN TRANSACTION", 1)[0]
    assert "backend/tests/unit/test_financial_revenue_detection_sql.py" in header
    assert "Retire: the records PR that closes E264 deletes this file" in header
