"""The detection SQL reads a proxy form exactly as ``is_proxy_form`` does, in every one of its sets.

``ops/detection/proxy_form_winners.sql`` copies ``facts/currency.py``'s ``_PROXY_FORM`` into each
statement's params, anchored as ``fullmatch`` anchors it and with ``(/A)?`` for ``(?:/A)?``
(PostgreSQL's regular expressions have no non-capturing group), and normalizes the form first as
``is_proxy_form`` does: whitespace collapsed to one space, trimmed, upper-cased. This gate holds every
copy and every match to the Python rule, so the rule and its copies change together. Retire it with the
SQL file, whose header names it.
"""
import re
from pathlib import Path

from app.services.facts.currency import _PROXY_FORM

SQL = Path(__file__).resolve().parents[3] / "ops" / "detection" / "proxy_form_winners.sql"
SETS = 4  # each statement declares its own params
NORMALIZED_MATCH = re.compile(
    r"upper\(btrim\(regexp_replace\(\w+\.form, '\\s\+', ' ', 'g'\)\)\) !?~ p\.proxy_form"
)


def _sql_pattern() -> str:
    return "^" + _PROXY_FORM.pattern.replace("(?:", "(") + "$"


def test_the_python_pattern_uses_only_what_both_engines_read_alike():
    # Letters, digits, classes, the ? * + quantifiers, plain groups and anchors; a lookaround, a
    # backreference or a class shorthand would need its own translation, not this transform.
    assert re.fullmatch(r"[\^$A-Z0-9 \[\]?*+()/-]+", _sql_pattern())


def test_every_set_copies_is_proxy_forms_pattern():
    literals = re.findall(r"'([^']*)'::text AS proxy_form", SQL.read_text())
    assert literals == [_sql_pattern()] * SETS


def test_every_match_reads_the_form_as_is_proxy_form_does():
    text = SQL.read_text()
    uses = re.findall(r"!?~ p\.proxy_form", text)
    assert uses and len(NORMALIZED_MATCH.findall(text)) == len(uses)
