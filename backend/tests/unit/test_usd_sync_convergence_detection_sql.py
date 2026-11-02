"""E198's census reads a proxy, an amount unit, another currency and a quarantined row as the sync does.

``ops/detection/usd_sync_convergence.sql`` copies four rules from ``facts/currency.py`` and ``facts/fiscal_naming.py``
into its statements: ``is_proxy_form``'s pattern (a key whose current row is a proxy's is left as found, and a proxy's
row is never made current), ``is_amount_unit`` (an amount or per-share unit is one whose part before '/' is three
capital letters), ``_another_currency``'s unit test (a company in USD alone stores no such unit other than USD), and
``_promotable``'s marker (provenance validation 'unavailable'). It reads a company's units only over the concepts
its companyfacts rows hold (``fed``), as ``_another_currency`` reads the batch's, and counts a key that either side
leaves undated as undated, never as caught up: the sync also dates a row by the payload's ``filed``, which SQL cannot
see. This gate holds every copy to its source, the
transaction to READ ONLY, and the file to statements that read. Nothing runs the SQL in CI; its rehearsal on
PostgreSQL is in its pull request's body. Retire it with the SQL file, whose header names it.
"""
import re
from pathlib import Path
from types import SimpleNamespace

from app.services.facts.currency import _kind, _promotable, is_amount_unit
from app.services.facts.fiscal_naming import _PROXY_FORM, is_proxy_form

SQL = Path(__file__).resolve().parents[3] / "ops" / "detection" / "usd_sync_convergence.sql"
PROXY_SETS, AMOUNT_SETS = 4, 6  # the statements that declare each parameter
UNITS = ["USD", "USD/shares", "CNY", "EUR/shares", "pure", "shares", "usd", "USDX", "US", "U5D", "USD/", "/USD", ""]
FORMS = ["DEF 14A", "def  14a ", "DEFA14A", "PRE 14C", "PX14A6G", "DEF 14A/A", "10-K", "10-K/A", "8-K", "S-4", "", None]


def _code() -> str:
    """The file without its comments and \\echo lines: the SQL psql sends."""
    lines = SQL.read_text().splitlines()
    return "\n".join(line.split("--", 1)[0] for line in lines if not line.lstrip().startswith("\\echo"))


def _params(name: str) -> list[str]:
    return re.findall(rf"'([^']*)'::text AS {name}", _code())


def test_every_set_copies_is_proxy_forms_pattern_and_reads_the_form_as_it_does():
    assert _params("proxy_form") == ["^" + _PROXY_FORM.pattern.replace("(?:", "(") + "$"] * PROXY_SETS
    pattern = re.compile(_params("proxy_form")[0])
    for form in FORMS:  # the copy's normalization and match, read in Python, agree with the rule
        normalized = re.sub(r"\s+", " ", form or "").strip().upper()
        assert bool(pattern.search(normalized)) is is_proxy_form(form), form
    uses = re.findall(r"~ p\.proxy_form", _code())
    normalized_uses = re.findall(r"upper\(btrim\(regexp_replace\(coalesce\(ff\.form, ''\), '\\s\+', ' ', 'g'\)\)\) "
                                 r"~ p\.proxy_form", _code())
    assert uses and len(normalized_uses) == len(uses)


def test_every_amount_test_reads_a_unit_as_is_amount_unit_and_another_currency_as_the_sync_does():
    assert _params("amount_code") == ["^[A-Z]{3}$"] * AMOUNT_SETS
    code = re.compile(_params("amount_code")[0])
    for unit in UNITS:
        head = unit.split("/", 1)[0]  # split_part(unit, '/', 1)
        assert bool(code.search(head)) is is_amount_unit(head), unit
        another = bool(code.search(head)) and head != "USD"  # the file's usd_alone test, per row
        assert another is (bool(unit) and _kind(unit) == "amount" and unit.partition("/")[0] != "USD"), unit
    usd_alone = ("HAVING NOT bool_or(split_part(ff.unit, '/', 1) ~ p.amount_code AND split_part(ff.unit, '/', 1) "
                 "<> 'USD')")
    assert _code().count(usd_alone) == AMOUNT_SETS - 1  # set 1 reads it as a column instead
    assert ("bool_or(f.concept IS NOT NULL AND split_part(ff.unit, '/', 1) ~ p.amount_code AND split_part(ff.unit, "
            "'/', 1) <> 'USD') AS other") in " ".join(_code().split())


def test_every_usd_alone_reads_only_the_concepts_its_companyfacts_rows_hold():
    # _another_currency reads the stored units of the batch's concepts, so a USD filer whose per-filing writer stored a
    # row in another currency under a concept its payload does not carry still syncs in USD alone: it counts here too.
    code = " ".join(_code().split())
    assert code.count("fed AS MATERIALIZED ( SELECT DISTINCT company_id, concept FROM financial_fact WHERE source = "
                      "'companyfacts' )") == AMOUNT_SETS
    assert code.count("FROM financial_fact ff JOIN fed f ON f.company_id = ff.company_id AND f.concept = ff.concept "
                      "CROSS JOIN params p GROUP BY ff.company_id HAVING NOT bool_or(") == AMOUNT_SETS - 1
    assert code.count("LEFT JOIN fed f ON f.company_id = ff.company_id AND f.concept = ff.concept") == 1  # set 1


def test_a_key_either_side_leaves_undated_counts_as_undated_never_as_caught_up():
    code = " ".join(_code().split())
    assert "k.current_filed IS NOT NULL AND d.filed > k.current_filed)" not in code.replace(
        "bool_or(d.filed IS NOT NULL AND k.current_filed IS NOT NULL AND d.filed > k.current_filed)", "")
    assert code.count("AND (NOT k.has_current OR d.filed IS NULL OR k.current_filed IS NULL OR d.filed > "
                      "k.current_filed)") == 4  # sets 2, 3, 5 and 6
    assert code.count("NOT k.has_current OR bool_or(d.filed IS NOT NULL AND k.current_filed IS NOT NULL AND d.filed > "
                      "k.current_filed) AS decided") == 3  # sets 2, 3 and 6 split dated from undated


def test_a_quarantined_row_is_the_one_the_sync_never_makes_current():
    assert not _promotable(SimpleNamespace(provenance={"validation": "unavailable"}))
    assert _promotable(SimpleNamespace(provenance={"validation": "passed"}))
    assert _code().count("coalesce(pv.pv ->> 'validation', '') = 'unavailable' AS quarantined") == 4
    assert "->> 'validation' = 'unavailable'" in _code()  # set 4


def test_the_file_reads_in_one_bounded_read_only_transaction():
    statements = [s.strip() for s in _code().split(";") if s.strip()]
    assert statements[:3] == ["BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
                              "SET LOCAL statement_timeout = '120s'", "SET LOCAL lock_timeout = '10s'"]
    assert statements[-1] == "COMMIT"
    assert all(s.startswith(("SELECT", "WITH")) for s in statements[3:-1])
    assert not re.search(r"\b(INSERT|UPDATE|DELETE|MERGE|ALTER|CREATE|DROP|TRUNCATE|GRANT|REVOKE|COPY|CALL|DO|"
                         r"LOCK|VACUUM|ANALYZE|REFRESH|SET\s+(?!LOCAL))\b", "\n".join(statements[3:-1]), re.IGNORECASE)


def test_the_header_names_its_gate_and_its_retirement():
    header = SQL.read_text().split("BEGIN TRANSACTION", 1)[0]
    assert "backend/tests/unit/test_usd_sync_convergence_detection_sql.py" in header
    assert "Retire: the records PR that reports the after run deletes this file" in header
