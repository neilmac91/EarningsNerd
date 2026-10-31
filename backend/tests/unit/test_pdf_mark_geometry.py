"""The PDFs' EN monogram is the canonical mark, outline for outline (lessons/brand-the-mark-is-protected.md).

frontend/tests/unit/markSingleSource.spec.ts holds every frontend and template rendition of the mark to
frontend/public/assets/earningsnerd-mark-mono.svg, but it never reads Python, so the inline copy in
app/services/pdf_branding.py (the masthead of both PDFs) had no gate. This test parses that copy as XML,
as mark_svg() builds it and as the two rendered PDFs carry it, and holds it to the canonical file the
way the spec does: the same tree of elements, the three outlines' d attributes equal, placed by the
canonical two groups' transforms and by nothing else (no transform on the svg or a path, no extra
element, no style or class that moves one), under the canonical viewBox with no preserveAspectRatio
that could stretch it. Nor does the PDF's stylesheet move it: WeasyPrint applies a transform set on
the svg or on any ancestor (`.masthead svg { transform: scaleX(1.6); }` stretched the mark while the
outline checks passed), so no declaration in any rule of either PDF's stylesheet, nested and
conditional rules included, or in any element's style attribute is a transform property
(transform, translate, rotate, scale or zoom, vendor-prefixed or not) or calls a transform function
(matrix(), skew() and the rest). Sizing is not geometry: under the viewBox a width or height scales
the mark evenly (a 200 dpi render of `.masthead svg { width: 80px; height: 20px; }` drew it whole,
smaller). Colour is not geometry either: test_export_palette_parity.py holds the fill.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import tinycss2

import tests.unit.test_export_palette_parity as palette  # the stylesheet and document readers both gates share
import tests.unit.test_export_service as export_fixtures
from app.services.export_service import ExportService
from app.services.pdf_branding import PALETTE, mark_svg

CANONICAL = Path(__file__).resolve().parents[3] / "frontend" / "public" / "assets" / "earningsnerd-mark-mono.svg"
SVG = "{http://www.w3.org/2000/svg}"
MOVES = re.compile(r"transform|translate|scale|rotate|matrix|skew", re.IGNORECASE)
SVG_ELEMENT = re.compile(r"<svg\b.*?</svg>", re.DOTALL)
MOVE_PROPERTY = re.compile(r"^(?:-[a-z]+-)?(?:transform|translate|rotate|scale|zoom)$")
TRANSFORM_FUNCTION = re.compile(
    r"^(?:-[a-z]+-)?(?:matrix(?:3d)?|translate(?:[xyz]|3d)?|scale(?:[xyz]|3d)?|rotate(?:[xyz]|3d)?|skew[xy]?|perspective)$"
)


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


def _moves(name: str, value: str) -> bool:
    """Whether a declaration is a transform property or calls a transform function anywhere in its value."""
    def calls(nodes) -> bool:
        return any(
            (node.type == "function" and (TRANSFORM_FUNCTION.match(node.lower_name) or calls(node.arguments)))
            or (node.type in ("() block", "[] block", "{} block") and calls(node.content))
            for node in nodes
        )
    return bool(MOVE_PROPERTY.match(name)) or calls(tinycss2.parse_component_value_list(value, skip_comments=True))


def stylesheet_moves(html: str) -> list[str]:
    """Every declaration that could move, turn or stretch the mark, in the PDF's stylesheet or in a style
    attribute: a transform on an ancestor moves the mark as surely as one on the svg."""
    found = [f"{rule} {{ {name}: {value} }}" for rule, block in palette.css_rules(palette.stylesheet(html))
             for name, value in block if _moves(name, value)]
    for element in palette.elements(html):
        style = element.get("style") or ""
        for item in tinycss2.parse_blocks_contents(style, skip_comments=True, skip_whitespace=True):
            if item.type == "declaration" and _moves(item.lower_name, tinycss2.serialize(item.value).strip()):
                found.append(f"<{element.tag.rsplit('}', 1)[-1]} style={style!r}>")
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


def test_no_pdf_stylesheet_moves_the_mark():
    for name, html in _rendered_pdfs().items():
        assert stylesheet_moves(html) == [], name
        assert len(palette.css_rules(palette.stylesheet(html))) > 30, name  # the reader found the stylesheet


def test_the_stylesheet_check_names_every_transform():
    """Planted forms: a transform on the svg or an ancestor, each individual transform property, a vendor
    prefix, a nested or conditional rule and a style attribute each fail; the look-alikes pass."""
    planted = (
        ".masthead svg { transform: scaleX(1.6); }",
        ".masthead { transform: scaleX(1.3); }",
        ".masthead svg { scale: 1.6 1; }",
        ".masthead { rotate: 3deg; }",
        ".masthead svg { translate: 4px 0; }",
        ".masthead svg { zoom: 2; }",
        ".masthead svg { -webkit-transform: rotate(3deg); }",
        ".masthead { svg { transform: skewX(8deg); } }",
        "@media print { .masthead svg { transform: matrix(1.6, 0, 0, 1, 0, 0); } }",
        ".masthead svg { --lean: rotate(4deg); }",
    )
    for css in planted:
        assert len(stylesheet_moves(f"<style>{css}</style>")) == 1, css
    assert stylesheet_moves('<div class="masthead" style="transform: scaleX(1.2)"></div>') == [
        "<div style='transform: scaleX(1.2)'>",
    ]
    look_alikes = ("th { text-transform: uppercase; }", ".masthead svg { width: 80px; height: 20px; }",
                   ".masthead { transform-origin: 0 0; }", "td { white-space: nowrap; }")
    assert [css for css in look_alikes if stylesheet_moves(f"<style>{css}</style>")] == []


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
