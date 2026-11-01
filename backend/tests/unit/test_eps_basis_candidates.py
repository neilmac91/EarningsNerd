"""E260: every list that fills the basic EPS key names basic EPS, and every list that fills the diluted key names diluted.

Readers name ``earnings_per_share`` "EPS (basic)" and ``eps_diluted`` "EPS (diluted)" (E259). A diluted tag among the
basic key's candidates fills "EPS (basic)" with a diluted figure whenever a filer tags no undimensioned basic EPS, as
the instance path did before E260 for a filer that tags basic EPS by share class alone. This gate reads each list that
fills either key and fails a name that does not belong to it:

- the instance path's ``DURATION_CONCEPTS`` (``edgar/instance/concepts.py``);
- the eval harness's ``METRIC_CONCEPTS["eps"]`` (``evals/build_golden_set.py``), which the drift test in
  ``test_accession_xbrl_extraction.py`` holds equal to the instance list;
- the facts layer's ``COMPANYFACTS_DURATION_TAGS`` (``facts/concepts.py``);
- the companyfacts fallback's inline candidate lists, read from ``parse_company_facts``'s source
  (``edgar/xbrl_companyfacts.py``).

``test_every_file_naming_a_diluted_eps_tag_is_read_here`` holds that list of places to a search, so a list in a fifth
file fails until it is read here.

``EarningsPerShareBasicAndDiluted`` states both measures at once and belongs to both keys. Since E260's second pull
request the companyfacts fallback writes an ``eps_diluted`` series of its own, so no list keeps a diluted candidate for
the basic key (the founder approved that change to the locked T9 anchor, ``test_companyfacts_fixture.py``).
"""

import ast
import inspect
import re
from pathlib import Path

import pytest

from app.services.edgar import xbrl_companyfacts
from app.services.edgar.instance.concepts import DURATION_CONCEPTS
from app.services.facts.concepts import COMPANYFACTS_DURATION_TAGS
from evals.build_golden_set import METRIC_CONCEPTS

pytestmark = pytest.mark.unit

# ifrs-full names the instance path tries after its us-gaap ones; the facts layer reads us-gaap companyfacts only.
_IFRS_EPS = frozenset({"BasicEarningsLossPerShare", "DilutedEarningsLossPerShare"})
# A diluted EPS tag in any form (``EarningsPerShareBasicAndDiluted`` names both measures and is not matched).
_DILUTED_EPS_TAG = re.compile(r"EarningsPerShareDiluted|DilutedEarningsLossPerShare|PerDilutedShare")
# The files of the four lists above, the only ones that name such a tag.
_FILES_READ = {
    "app/services/edgar/instance/concepts.py",
    "app/services/edgar/xbrl_companyfacts.py",
    "app/services/facts/concepts.py",
}


def _fallback_lists() -> dict[str, list[str]]:
    """``parse_company_facts``'s inline candidates per key, every call's: each ``append_items(result, accession,
    "<key>", select_fact_data(us_gaap, accession, [<tags>], ...))``. Cash, filled from a selected tag, is the one key
    filled another way; a fill of any other key in another shape fails here, so no list goes unread."""
    out: dict[str, list[str]] = {}
    for node in ast.walk(ast.parse(inspect.getsource(xbrl_companyfacts.parse_company_facts))):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "append_items"):
            continue
        key, select = node.args[2], node.args[3] if len(node.args) > 3 else None
        assert isinstance(key, ast.Constant), "read each key as a literal"
        if key.value == "cash_and_equivalents":
            continue
        assert isinstance(select, ast.Call) and getattr(select.func, "id", None) == "select_fact_data", key.value
        assert isinstance(select.args[2], ast.List), f"{key.value}: read each list as a literal"
        out.setdefault(key.value, []).extend(element.value for element in select.args[2].elts)
    return out


def _basic_key_lists() -> dict[str, list[str]]:
    return {
        "instance path": list(DURATION_CONCEPTS["earnings_per_share"]),
        "eval harness": list(METRIC_CONCEPTS["eps"][1]),
        "facts layer": list(COMPANYFACTS_DURATION_TAGS["earnings_per_share"]),
        "companyfacts fallback": _fallback_lists()["earnings_per_share"],
    }


def _diluted_key_lists() -> dict[str, list[str]]:
    return {
        "instance path": list(DURATION_CONCEPTS["eps_diluted"]),
        "facts layer": list(COMPANYFACTS_DURATION_TAGS["eps_diluted"]),
        "companyfacts fallback": _fallback_lists()["eps_diluted"],
    }


@pytest.mark.parametrize("source", ["instance path", "eval harness", "facts layer", "companyfacts fallback"])
def test_every_basic_key_candidate_names_basic_eps(source):
    names = _basic_key_lists()[source]
    assert names, f"{source}: no candidates read"
    assert [name for name in names if "Basic" not in name] == [], (
        f"{source}: a candidate for earnings_per_share (\"EPS (basic)\") names no basic measure"
    )


@pytest.mark.parametrize("source", ["instance path", "facts layer", "companyfacts fallback"])
def test_every_diluted_key_candidate_names_diluted_eps(source):
    names = _diluted_key_lists()[source]
    assert names, f"{source}: no candidates read"
    assert [name for name in names if "Diluted" not in name] == [], (
        f"{source}: a candidate for eps_diluted (\"EPS (diluted)\") names no diluted measure"
    )


@pytest.mark.parametrize("key", ["earnings_per_share", "eps_diluted"])
def test_the_instance_lists_us_gaap_names_match_the_facts_layer(key):
    # One measure per key on every path: the instance list's us-gaap names, in order, are the facts layer's tuple.
    us_gaap = [name for name in DURATION_CONCEPTS[key] if name not in _IFRS_EPS]
    assert us_gaap == list(COMPANYFACTS_DURATION_TAGS[key])


def test_the_lists_are_read():
    lists = _fallback_lists()
    assert lists["total_assets"] == ["Assets"]
    assert lists["earnings_per_share"][0] == "EarningsPerShareBasic"
    assert "cash_and_equivalents" not in lists
    assert lists["eps_diluted"][0] == "EarningsPerShareDiluted"


def test_every_file_naming_a_diluted_eps_tag_is_read_here():
    # A list in another file fills a key this gate does not read: read it above and name its file, or keep the tag out.
    backend = Path(__file__).resolve().parents[2]
    found = {
        path.relative_to(backend).as_posix()
        for folder in ("app", "evals", "scripts") for path in sorted((backend / folder).rglob("*.py"))
        if _DILUTED_EPS_TAG.search(path.read_text(encoding="utf-8"))
    }
    assert found == _FILES_READ
