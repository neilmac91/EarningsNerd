"""The PDFs' EN monogram is the canonical mark, outline for outline (lessons/brand-the-mark-is-protected.md).

frontend/tests/unit/markSingleSource.spec.ts holds every frontend and template rendition of the mark to
frontend/public/assets/earningsnerd-mark-mono.svg, but it never reads Python, so the inline copy in
app/services/pdf_branding.py (the masthead of both PDFs) had no gate. This test parses that copy as XML,
as mark_svg() builds it and as the two rendered PDFs carry it, and holds it to the canonical file the
way the spec does: the same tree of elements, the three outlines' d attributes equal, placed by the
canonical two groups' transforms and by nothing else (no transform on the svg or a path, no extra
element, no style or class that moves one), under the canonical viewBox with no preserveAspectRatio
that could stretch it. Colour is not geometry: test_export_palette_parity.py holds the fill.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import tests.unit.test_export_service as export_fixtures
from app.services.export_service import ExportService
from app.services.pdf_branding import PALETTE, mark_svg

CANONICAL = Path(__file__).resolve().parents[3] / "frontend" / "public" / "assets" / "earningsnerd-mark-mono.svg"
SVG = "{http://www.w3.org/2000/svg}"
MOVES = re.compile(r"transform|translate|scale|rotate|matrix|skew", re.IGNORECASE)
SVG_ELEMENT = re.compile(r"<svg\b.*?</svg>", re.DOTALL)


def geometry(element: ET.Element) -> tuple:
    """An element's place in the mark: its tag, its own transform, its outline and its children's."""
    return (
        element.tag.removeprefix(SVG),
        element.get("transform"),
        element.get("d"),
        tuple(geometry(child) for child in element),
    )


def moved_by_style(root: ET.Element) -> list[str]:
    """Elements a style or class could move, which the transform comparison cannot see."""
    return [
        f"<{element.tag.removeprefix(SVG)} {name}={element.get(name)!r}>"
        for element in root.iter()
        for name in ("style", "class")
        if MOVES.search(element.get(name) or "")
    ]


def problems(svg: str) -> list[str]:
    """Every way an inline mark departs from the canonical file's geometry."""
    root, canonical = ET.fromstring(svg), ET.parse(CANONICAL).getroot()
    found = []
    if root.get("viewBox") != canonical.get("viewBox"):
        found.append(f"viewBox {root.get('viewBox')!r} is not the canonical {canonical.get('viewBox')!r}")
    for name in ("transform", "preserveAspectRatio"):
        if root.get(name) is not None:
            found.append(f"the svg carries {name}={root.get(name)!r}")
    if [geometry(child) for child in root] != [geometry(child) for child in canonical]:
        found.append("the outlines or their groups differ from earningsnerd-mark-mono.svg")
    found += moved_by_style(root)
    return found


def _rendered_pdfs() -> dict[str, str]:
    analysis = export_fixtures.TestAnalysisPdfHtml()
    summary, filing = export_fixtures._make_summary_and_filing(export_fixtures._full_sections())
    return {
        "filing summary": ExportService().generate_pdf_html(summary, filing),
        "analysis": ExportService().generate_analysis_pdf_html(analysis._analysis(), analysis._company()),
    }


def test_the_canonical_file_holds_the_three_outlines_in_two_groups():
    """The comparison below is only as strong as the reference it reads."""
    canonical = ET.parse(CANONICAL).getroot()
    assert [element.get("transform") for element in canonical.iter(f"{SVG}g")] == [
        "translate(0,-14.8)", "translate(0.92,6.98) scale(0.9193)",
    ]
    outlines = [element.get("d") for element in canonical.iter(f"{SVG}path")]
    assert len(outlines) == 3 and all(d.startswith("M") for d in outlines)


@pytest.mark.parametrize("height, fill", [(34, PALETTE["brand_strong"]), (30, PALETTE["brand_strong"]), (12, "#FFFFFF")])
def test_mark_svg_is_the_canonical_geometry(height, fill):
    assert problems(mark_svg(height, fill)) == []


def test_both_pdfs_carry_the_canonical_mark_and_no_other_svg():
    for name, html in _rendered_pdfs().items():
        marks = SVG_ELEMENT.findall(html)
        assert len(marks) == 1, f"the {name} PDF carries {len(marks)} inline svg elements, not the masthead's one"
        assert problems(marks[0]) == [], name


def test_the_check_names_a_moved_or_redrawn_outline():
    """Planted forms: a nudged coordinate, a transform on a path, an extra group, a stretch and a
    style transform each fail, so a pass above means the geometry is the canonical file's."""
    mark = mark_svg()
    planted = {
        "a nudged coordinate": mark.replace("M2.8 28L26.2 28", "M2.8 28L26.3 28"),
        "a transform on a path": mark.replace('<path d="M101.76', '<path transform="translate(1,0)" d="M101.76'),
        "an extra group": mark.replace('<g transform="translate(0.92', '<g><g transform="translate(0.92').replace(
            "</g></g></svg>", "</g></g></g></svg>"),
        "a stretch": mark.replace("<svg ", '<svg preserveAspectRatio="none" '),
        "a moved group": mark.replace('<g transform="translate(0,-14.8)">', '<g transform="translate(0,-14.8)" style="transform: scale(1.1)">'),
        "a changed viewBox": mark.replace('viewBox="0 0 94.6 73.2"', 'viewBox="0 0 94.6 80"'),
    }
    for name, svg in planted.items():
        assert svg != mark, f"the planted form '{name}' did not apply"
        assert problems(svg), f"the check missed {name}"
