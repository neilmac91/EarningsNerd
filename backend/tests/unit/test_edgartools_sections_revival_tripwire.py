"""Tripwire: an edgartools bump must not silently switch summary excerpts back to native sections (E28).

The summary pipeline asks for native section text through
``app/services/edgar/xbrl_sections.py::_extract_sections_sync``, which calls edgartools'
``Filing.obj()``. On edgartools 5.58.0, ``obj()`` reads the primary document through
``Filing.html()``, and ``html()`` sends any primary document that opens with an XML declaration
(every inline-XBRL 10-K, 10-Q and 20-F in the golden set) to the filing's index page instead. 5.58.0
builds that page's URL without the accession folder, and SEC has refused that form with 403 since
early October (between 2026-10-04 and 2026-10-07 in CI's reports; dgunning/edgartools#1421). So the
primary document resolves to None, the call returns None for every filing, and each excerpt built
since then comes from the regex extractor (``tasks/review-evidence/e28-native-sections-2026-10-15/``).

Upstream has fixed this twice: 5.61.0 builds the index URL inside the accession folder, and 5.62.0
reads inline XBRL from the submission without loading the index page at all. Either release brings
native sections back for every excerpt built after the bump, which changes what the model reads
inside a dependency change. ``backend/evals/RUNBOOK.md`` requires that change to be measured, and E28
in ``tasks/todo.md`` leaves the choice (revive from the HTML the pipeline already fetched, or retire
the path) to the founder.

Two fixes by two routes mean no single URL shape or code path is the right thing to watch, so the
tripwire keys on the version: while the section source holds an ``obj()`` allow-list entry, the
installed edgartools must be the version measured dead. The allow-list gate
(``test_edgartools_obj_allowlist.py``) holds every literal form of access to the accessor (the call,
a bare alias, ``"obj"`` passed by name to ``getattr`` or a wrapper) to exact equality, so its entry is
present while the path is. An accessor name built at runtime (held in a variable) is outside what an
AST walk can see; the gate then reports the entry as missing, and the second test below asks for a
check that the call is really gone before this file is deleted. When E28 lands, the entry goes, the
second test fails, and this file is deleted with it.

No network.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import edgar

ALLOWLIST_GATE = Path(__file__).with_name("test_edgartools_obj_allowlist.py")
SECTION_SOURCE = ("app/services/edgar/xbrl_sections.py", "_extract_sections_sync")

# The version under which the section source was measured to return None for every filing.
MEASURED_DEAD_ON = "5.58.0"


def _allowed_obj_calls() -> dict[tuple[str, str], str]:
    # tests/unit is not a package, so load the gate's module from its file.
    spec = importlib.util.spec_from_file_location("_edgartools_obj_allowlist_gate", ALLOWLIST_GATE)
    assert spec is not None and spec.loader is not None, f"cannot load {ALLOWLIST_GATE.name}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ALLOWED_OBJ_CALLS


def test_an_edgartools_bump_does_not_revive_the_section_path_silently():
    if SECTION_SOURCE not in _allowed_obj_calls():
        return  # E28 has landed; the second test asks for this file's deletion
    assert edgar.__version__ == MEASURED_DEAD_ON, (
        f"edgartools {edgar.__version__} is installed, and {SECTION_SOURCE[0]}::{SECTION_SOURCE[1]} "
        f"still reaches Filing.obj(). The section source was measured dead on {MEASURED_DEAD_ON} "
        "only: 5.61.0 builds the filing index URL inside the accession folder SEC serves, and "
        "5.62.0 reads inline XBRL without the index page, so either brings native summary sections "
        "back and changes every 10-K/10-Q/20-F excerpt built after the bump. Land E28's decision "
        "first (tasks/todo.md: revive the sections from the HTML the pipeline fetched, measured per "
        "backend/evals/RUNBOOK.md, or retire the path), then take the bump."
    )


def test_the_tripwire_retires_with_the_section_path():
    """Fails once the path has gone, so the tripwire is deleted with it rather than passing vacuously."""
    assert SECTION_SOURCE in _allowed_obj_calls(), (
        f"{SECTION_SOURCE[0]}::{SECTION_SOURCE[1]} left the obj() allow-list. First confirm the "
        "section source no longer reaches Filing.obj() by any route (an accessor name held in a "
        "variable is invisible to the allow-list's AST walk). Then: if E28's decision landed, delete "
        "this tripwire in the same PR; if the call only moved, point SECTION_SOURCE at its new entry"
    )
