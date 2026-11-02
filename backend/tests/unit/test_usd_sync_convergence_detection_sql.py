"""E198's census reads each stored row against each current row as E198's convergence reads them.

``ops/detection/usd_sync_convergence.sql`` copies rules from ``facts/currency.py`` and ``facts/fiscal_naming.py`` into its
statements: ``is_proxy_form``'s pattern (a key whose current row is a proxy's is left as found, and a proxy's row is
never made current), ``is_amount_unit`` (an amount or per-share unit is one whose part before '/' is three capital
letters), ``_another_currency``'s unit test over the concepts a company's companyfacts rows hold (``fed``),
``_promotable``'s marker (provenance validation 'unavailable'), ``_filed``'s reading of a row's date (text, compared as
strings) and ``_filing_dates``' (a Filing row by its exact accession). Its sets 2, 3, 5 and 6 read one candidate chain:
a row that is not current is eligible unless a current row at its key holds the key as E198's convergence decides
(``_promote_batch_rows``' ``later``: filed strictly after it, and a feed row only where the upsert's own Filing-date rule
keeps it too, R1u), so a same-day row and an older payload winner under such a feed row count, and a key a date it
cannot see decides counts as undated, never as caught up. This gate holds every copy to its source, the chain to one
text, the transaction to READ ONLY, and the file to statements that read. Nothing runs the SQL in CI; its rehearsal on
PostgreSQL is in its pull request's body. Retire it with the SQL file, whose header names it.
"""
import re
from pathlib import Path
from types import SimpleNamespace

from app.services.facts.currency import PayloadView, _filed, _kind, _promotable, is_amount_unit
from app.services.facts.fiscal_naming import _PROXY_FORM, is_proxy_form

SQL = Path(__file__).resolve().parents[3] / "ops" / "detection" / "usd_sync_convergence.sql"
PROXY_SETS, AMOUNT_SETS, CHAIN_SETS = 4, 6, 4  # the statements that declare each parameter; sets 2, 3, 5 and 6
UNITS = ["USD", "USD/shares", "CNY", "EUR/shares", "pure", "shares", "usd", "USDX", "US", "U5D", "USD/", "/USD", ""]
FORMS = ["DEF 14A", "def  14a ", "DEFA14A", "PRE 14C", "PX14A6G", "DEF 14A/A", "10-K", "10-K/A", "8-K", "S-4", "", None]
SHAPES = ["later", "same_day", "r1u", "gap", "undated"]  # each key's most likely shape first


def _code() -> str:
    """The file without its comments and \\echo lines: the SQL psql sends."""
    lines = SQL.read_text().splitlines()
    return "\n".join(line.split("--", 1)[0] for line in lines if not line.lstrip().startswith("\\echo"))


def _flat() -> str:
    return " ".join(_code().split())


def _params(name: str) -> list[str]:
    return re.findall(rf"'([^']*)'::text AS {name}", _code())


def _chains() -> list[str]:
    """Each set's candidate chain, from its keyed rows through its eligible ones."""
    return re.findall(r"keyed AS MATERIALIZED \(.*?\), eligible AS \(.*?\) \)", _flat())


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


def test_the_copied_proxy_pattern_uses_only_what_both_engines_read_alike():
    # Letters, digits, classes, the ? * + quantifiers, plain groups and anchors, as test_proxy_form_detection_sql.py
    # holds its own copy: a lookaround, a backreference, an inline flag or a class shorthand in _PROXY_FORM would need
    # its own translation into PostgreSQL's regex, not this transform. (The amount code reads ASCII capitals, where
    # is_amount_unit reads any upper-case letter: no currency code is outside ASCII.)
    assert re.fullmatch(r"[\^$A-Z0-9 \[\]?*+()/-]+", _params("proxy_form")[0])


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
            "'/', 1) <> 'USD') AS other") in _flat()


def test_every_usd_alone_reads_only_the_concepts_its_companyfacts_rows_hold():
    # _another_currency reads the stored units of the batch's concepts, so a USD filer whose per-filing writer stored a
    # row in another currency under a concept its payload does not carry still syncs in USD alone: it counts here too.
    code = _flat()
    assert code.count("fed AS MATERIALIZED ( SELECT DISTINCT company_id, concept FROM financial_fact WHERE source = "
                      "'companyfacts' )") == AMOUNT_SETS
    assert code.count("FROM financial_fact ff JOIN fed f ON f.company_id = ff.company_id AND f.concept = ff.concept "
                      "CROSS JOIN params p GROUP BY ff.company_id HAVING NOT bool_or(") == AMOUNT_SETS - 1
    assert code.count("LEFT JOIN fed f ON f.company_id = ff.company_id AND f.concept = ff.concept") == 1  # set 1


def test_every_set_reads_one_candidate_chain_over_the_companies_in_usd_alone():
    # Sets 2, 5 and 6 read amounts and per-share rows, set 3 ratios; each reads the same chain otherwise, so a fix to
    # one copy cannot leave another behind. Each keys only rows that are not current, of a company in USD alone.
    chains = _chains()
    assert len(chains) == CHAIN_SETS
    usd = "AND split_part(ff.unit, '/', 1) = 'USD'"
    assert sum(usd in chain for chain in chains) == CHAIN_SETS - 1
    assert len({chain.replace("AND ff.unit = 'pure'", usd) for chain in chains}) == 1
    assert all(chain.startswith("keyed AS MATERIALIZED ( SELECT DISTINCT ff.company_id, ff.concept, ff.period_end, "
                                "ff.fiscal_period, ff.unit FROM financial_fact ff JOIN usd_alone a ON a.company_id = "
                                "ff.company_id WHERE NOT ff.is_latest AND ff.fiscal_period IS NOT NULL AND ")
               for chain in chains)


def test_a_current_row_holds_a_candidate_only_as_the_convergence_lets_it():
    # _promote_batch_rows' later(): a current row holds its key against the batch's row only where it is filed
    # strictly after that row, and a feed row (no filing owner) of a filing the payload names only where it also has a
    # Filing row that outranks the batch row's by (date, accession), or the batch row has none (R1u). Every current
    # feed row is read as named, an upper bound. A same-day row and an older winner under such a feed row are eligible.
    chain = _chains()[0]
    assert ("SELECT o.filed > d.filed AND (o.filing_id IS NOT NULL OR (o.owned IS NOT NULL AND (d.owned IS NULL OR "
            "(o.owned, o.accession) > (d.owned, d.accession)))) AS holds") in chain
    assert ("FROM dated d LEFT JOIN dated o ON o.company_id = d.company_id AND o.concept = d.concept AND o.period_end "
            "= d.period_end AND o.fiscal_period = d.fiscal_period AND o.unit = d.unit AND o.is_latest") in chain
    assert "WHERE NOT d.is_latest AND NOT d.quarantined AND NOT d.proxy" in chain
    assert "WHERE NOT c.proxy_current AND NOT coalesce(c.held, false)" in chain
    for column in ("bool_or(o.id IS NOT NULL) AS has_current", "coalesce(bool_or(o.proxy), false) AS proxy_current",
                   "bool_or(h.holds) AS held", "bool_or(o.id IS NOT NULL AND h.holds IS NULL) AS open",
                   "max(o.filed) AS current_filed"):
        assert column in chain, column
    assert ".filed >" not in chain.replace("o.filed > d.filed AND", "").replace("c.filed > c.current_filed", "")


def test_a_key_a_date_it_cannot_see_decides_counts_as_undated_never_as_caught_up():
    # The sync also dates a row by the payload's filed, which SQL cannot see: where a current row's hold turns on such
    # a date, the candidate is undecided, so its key counts as undated, before the shapes a date decides.
    chain = _chains()[0]
    assert ("CASE WHEN NOT c.has_current THEN 'gap' WHEN c.open THEN 'undated' WHEN c.filed > c.current_filed THEN "
            "'later' WHEN c.filed = c.current_filed THEN 'same_day' ELSE 'r1u' END AS shape") in chain
    # Each key reports its most likely shape: the rank of a shape is its place in SHAPES, which names it back.
    rank = ("min(CASE e.shape " + " ".join(f"WHEN '{shape}' THEN {n}" for n, shape in enumerate(SHAPES[:-1], start=1))
            + f" ELSE {len(SHAPES)} END) AS rank")
    names = "(ARRAY[" + ", ".join(f"'{shape}'" for shape in SHAPES) + "])[k.rank]"
    assert _flat().count(rank) == 3 and _flat().count(names) == 2  # sets 2, 3 and 6 rank; sets 2 and 3 name


def test_a_row_is_dated_as_the_sync_dates_it_and_compared_as_python_compares_strings():
    # filed: the Filing row's date, else provenance filed_at's first ten characters where they spell YYYY-MM-DD, as
    # _filed slices it, compared as text (an impossible day sorts where the sync sorts it; nothing is cast, so nothing
    # raises under ON_ERROR_STOP). Another value reads as no date: undecided, never a date the sync would not read.
    # owned: the Filing row whose accession is the row's own exactly, as _filing_dates reads it. COLLATE "C" compares
    # by code point, as Python does, whatever the database's collation.
    chain = _chains()[0]
    shape = re.search(r"CASE WHEN pv\.pv ->> 'filed_at' ~ '([^']+)' THEN left\(pv\.pv ->> 'filed_at', 10\) END", chain)
    assert shape and "coalesce(to_char(fd.filed, 'YYYY-MM-DD'), " + shape.group(0) + ") COLLATE \"C\" AS filed" in chain
    view = PayloadView(currency="USD", foreign=frozenset(), known=frozenset(), newest_filed="", own={}, decider=None,
                       filed={})  # no Filing row and no payload date: _filed reads the provenance
    for filed_at in ("2024-02-15", "2024-02-15T08:00:00", "2024-02-30", "2024-13-45", "2024-2-5", "", None, "soon"):
        census = filed_at[:10] if filed_at and re.match(shape.group(1), filed_at) else None
        assert census is None or census == _filed("ACC", {"filed_at": filed_at}, {}, view), filed_at
    assert "LEFT JOIN filings fe ON fe.accession_number = ff.accession" in chain
    assert "to_char(fe.filing_date, 'YYYY-MM-DD') COLLATE \"C\" AS owned" in chain
    assert "ff.accession COLLATE \"C\" AS accession" in chain
    assert not re.search(r"::date|::int|make_date", chain) and "::date" not in _code()


def test_a_quarantined_row_is_the_one_the_sync_never_makes_current():
    assert not _promotable(SimpleNamespace(provenance={"validation": "unavailable"}))
    assert _promotable(SimpleNamespace(provenance={"validation": "passed"}))
    assert _code().count("coalesce(pv.pv ->> 'validation', '') = 'unavailable' AS quarantined") == CHAIN_SETS
    assert "->> 'validation' = 'unavailable'" in _code()  # set 4


def test_an_untagged_row_matches_an_untagged_one():
    # string_to_array('', ',') is empty, so both sides read an untagged row under a sentinel.
    code = _flat()
    assert code.count("string_agg(DISTINCT coalesce(o.raw_tag, '-'), ',') FILTER (WHERE o.id IS NOT NULL) AS "
                      "current_tags") == CHAIN_SETS
    assert code.count("coalesce(e.raw_tag, '-') = ANY (string_to_array(e.current_tags, ','))") == 2  # sets 2 and 6
    assert "raw_tag, '')" not in code


def test_set_6_ranks_decided_keys_first_and_counts_each_shape():
    # An undated key can stay listed after its company's sync, so a cohort ranked by every key could hold no decided
    # one. Each shape's column counts its own rank.
    code = _flat()
    assert "ORDER BY bc.keys - bc.undated DESC, bc.keys DESC, c.ticker LIMIT 50" in code
    for number, column in enumerate(("later", "same_day", "r1u", "gaps", "undated"), start=1):
        assert f"count(*) FILTER (WHERE k.rank = {number}) AS {column}" in code, column


def test_set_5_reads_every_eligible_rows_year():
    assert "years AS ( SELECT DISTINCT e.company_id, e.fiscal_year FROM eligible e WHERE e.fiscal_year IS NOT NULL )" \
        in _flat()


def test_the_file_reads_in_one_bounded_read_only_transaction():
    statements = [s.strip() for s in _code().split(";") if s.strip()]
    assert statements[:3] == ["BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
                              "SET LOCAL statement_timeout = '120s'", "SET LOCAL lock_timeout = '10s'"]
    assert statements[-1] == "COMMIT"
    assert all(s.startswith(("SELECT", "WITH")) for s in statements[3:-1])
    assert not re.search(r"\b(INSERT|UPDATE|DELETE|MERGE|ALTER|CREATE|DROP|TRUNCATE|GRANT|REVOKE|COPY|CALL|DO|"
                         r"LOCK|VACUUM|ANALYZE|REFRESH|SET\s+(?!LOCAL))\b", "\n".join(statements[3:-1]), re.IGNORECASE)


def test_the_header_names_its_gate_and_its_retirement():
    header = " ".join(line.removeprefix("--").strip() for line in SQL.read_text().split("BEGIN TRANSACTION", 1)[0]
                      .splitlines())  # the comment's words, whatever their line breaks
    assert "backend/tests/unit/test_usd_sync_convergence_detection_sql.py" in header
    assert "Retire: the records PR that reports the after run deletes this file" in header
