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

``EarningsPerShareBasicAndDiluted`` states both measures at once and belongs to both keys. The companyfacts fallback
keeps its diluted candidate until it writes an ``eps_diluted`` series of its own, a change to the locked T9 anchor
(``test_companyfacts_fixture.py``) that E260's second pull request carries. ``_FALLBACK_RESIDUE`` names that one
candidate, and fails once the fallback drops it, so the entry leaves in the same change.
"""

import ast
import inspect

import pytest

from app.services.edgar import xbrl_companyfacts
from app.services.edgar.instance.concepts import DURATION_CONCEPTS
from app.services.facts.concepts import COMPANYFACTS_DURATION_TAGS
from evals.build_golden_set import METRIC_CONCEPTS

pytestmark = pytest.mark.unit

# The companyfacts fallback's diluted candidate for the basic key, kept until it writes its own eps_diluted (E260).
_FALLBACK_RESIDUE = ("EarningsPerShareDiluted",)
# ifrs-full names the instance path tries after its us-gaap ones; the facts layer reads us-gaap companyfacts only.
_IFRS_EPS = frozenset({"BasicEarningsLossPerShare", "DilutedEarningsLossPerShare"})


def _fallback_lists() -> dict[str, list[str]]:
    """``parse_company_facts``'s inline candidates, in order, per key: each ``append_items(result, accession, "<key>",
    select_fact_data(us_gaap, accession, [<tags>], ...))``. A key filled any other way (cash, from a selected tag) is
    not one of these lists and is skipped."""
    out: dict[str, list[str]] = {}
    for node in ast.walk(ast.parse(inspect.getsource(xbrl_companyfacts.parse_company_facts))):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "append_items"):
            continue
        key, select = node.args[2], node.args[3] if len(node.args) > 3 else None
        if not (isinstance(select, ast.Call) and getattr(select.func, "id", None) == "select_fact_data"):
            continue
        assert isinstance(key, ast.Constant) and isinstance(select.args[2], ast.List), "read each list as a literal"
        out[key.value] = [element.value for element in select.args[2].elts]
    return out


def _basic_key_lists() -> dict[str, list[str]]:
    fallback = _fallback_lists()["earnings_per_share"]
    return {
        "instance path": list(DURATION_CONCEPTS["earnings_per_share"]),
        "eval harness": list(METRIC_CONCEPTS["eps"][1]),
        "facts layer": list(COMPANYFACTS_DURATION_TAGS["earnings_per_share"]),
        "companyfacts fallback": [name for name in fallback if name not in _FALLBACK_RESIDUE],
    }


def _diluted_key_lists() -> dict[str, list[str]]:
    return {
        "instance path": list(DURATION_CONCEPTS["eps_diluted"]),
        "facts layer": list(COMPANYFACTS_DURATION_TAGS["eps_diluted"]),
        "companyfacts fallback": _fallback_lists().get("eps_diluted", []),
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
    assert [name for name in _diluted_key_lists()[source] if "Diluted" not in name] == [], (
        f"{source}: a candidate for eps_diluted (\"EPS (diluted)\") names no diluted measure"
    )


def test_the_fallback_residue_is_still_in_the_fallback():
    # When the fallback writes its own eps_diluted and drops the diluted candidate, delete the residue entry with it.
    assert set(_FALLBACK_RESIDUE) <= set(_fallback_lists()["earnings_per_share"])


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
