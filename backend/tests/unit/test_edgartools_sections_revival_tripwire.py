"""Tripwire: an edgartools bump must not silently switch summary excerpts back to native sections (E28).

The summary pipeline asks for native section text through
``app/services/edgar/xbrl_sections.py::_extract_sections_sync``, which calls edgartools'
``Filing.obj()``. Inside ``obj()`` edgartools loads the filing's index page from
``Filing.homepage_url``. edgartools 5.58.0 builds that URL without the accession folder
(``.../data/<cik>/<accession>-index.html``), and SEC has answered that form with 403 since about
2026-10-05 (edgartools issue #1421). So the call returns None for every filing, and every 10-K, 10-Q
and 20-F summary excerpt comes from the regex extractor
(``tasks/review-evidence/e28-native-sections-2026-10-15/``).

edgartools 5.61.0 builds the URL inside the accession folder. Taking that version while the section
source still goes through ``obj()`` would bring native sections back, and so change what the model
reads for every such summary, inside a dependency bump. ``backend/evals/RUNBOOK.md`` requires that
kind of model-input change to be measured, and E28 in ``tasks/todo.md`` leaves the choice (revive
from the HTML the pipeline already fetched, or retire the path) to the founder. This test fails the
bump until that choice has landed and the section source no longer calls ``obj()``.

No network: ``Filing`` builds its URLs from its constructor arguments.
"""
from __future__ import annotations

import ast
from pathlib import Path

from edgar import Filing

BACKEND = Path(__file__).resolve().parents[2]
SECTION_SOURCE = BACKEND / "app" / "services" / "edgar" / "xbrl_sections.py"

# Apple's FY2025 10-K, a golden-set filing; any real accession shows the URL shape.
CIK, ACCESSION = 320193, "0000320193-25-000079"
ACCESSION_FOLDER = ACCESSION.replace("-", "")


def _section_source_calls_obj() -> list[int]:
    """Line numbers of every ``<expr>.obj(...)`` call in the summary's section source."""
    tree = ast.parse(SECTION_SOURCE.read_text(encoding="utf-8"), filename=str(SECTION_SOURCE))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "obj"
    ]


def _index_url_reaches_sec() -> bool:
    """True when this edgartools builds the filing index URL inside the accession folder, the form
    SEC serves; False for the folderless form SEC refuses."""
    homepage = Filing(cik=CIK, company="Apple Inc.", form="10-K", filing_date="2025-10-31",
                      accession_no=ACCESSION).homepage_url
    if f"/data/{CIK}/{ACCESSION_FOLDER}/" in homepage:
        return True
    assert homepage.endswith(f"/data/{CIK}/{ACCESSION}-index.html"), (
        f"edgartools builds the filing index URL in a third form ({homepage}); re-measure E28 "
        "before trusting this tripwire"
    )
    return False


def test_an_edgartools_that_reaches_the_index_page_does_not_revive_the_section_path_silently():
    calls = _section_source_calls_obj()
    if not calls:
        return  # the section source no longer goes through obj(); E28's decision has landed
    assert not _index_url_reaches_sec(), (
        f"{SECTION_SOURCE.relative_to(BACKEND)} calls Filing.obj() (line(s) {calls}) and this "
        "edgartools builds the filing index URL inside the accession folder, so native summary "
        "sections would come back and change every 10-K/10-Q/20-F excerpt inside a dependency bump. "
        "Land E28's decision first (tasks/todo.md: revive the sections from the HTML the pipeline "
        "fetched, measured per backend/evals/RUNBOOK.md, or retire the path), then take the bump."
    )


def test_the_tripwire_reads_the_section_source_it_guards():
    """The guarded call exists today; if it moves, the tripwire must follow it, not pass vacuously."""
    assert SECTION_SOURCE.is_file(), "the summary section source moved; point SECTION_SOURCE at it"
    assert _section_source_calls_obj(), (
        "xbrl_sections.py no longer calls obj(): if E28's decision landed, delete this tripwire with it"
    )
