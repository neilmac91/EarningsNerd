"""Every export colour is a design token in its role, and every export text clears 4.5:1 on its ground.

The frontend's colour gates (designSnapshotParity, designTokenParity, the ESLint hex rule) never read
Python, and the exports had drifted: pdf_branding.PALETTE held #6B7280 as the tertiary ink, the
flat-delta grey, which reads 4.26:1 on the masthead's tint, where the tertiary ink token is #636A77.
This test reads DESIGN.md's frontmatter (designSnapshotParity holds it equal to tailwind.config.js)
and checks the exports as they render:

1. Roles: each PALETTE key names one token in ROLES and holds that token's value, so a value that is
   some other token (the flat grey for the tertiary ink) fails; CHART_SERIES is chart-1 to chart-6 in
   order. A new PALETTE key fails until ROLES names its token.
2. Output: every colour in the two PDFs' stylesheets and SVG fills, every colour the workbook sets on
   a cell, a tab or a chart, and every hex literal in the four export modules is a token value.
3. Contrast: every text colour the PDF stylesheet sets clears 4.5:1 on its ground (the rule's own
   background, else the masthead's tint for a masthead rule, else the white page): the masthead's
   document kind, the table header and the tertiary ink among them. Every workbook cell's font
   clears 4.5:1 on its fill, or on white without one.
4. Sage (D-041, applying D-030 to the exports): in the PDFs, text takes a brand colour only in a link
   and in the wordmark's "Nerd"; in the workbook, no text does (the sheet tabs keep it).
5. The wordmark (the PDF rendition of BG-27): "Earnings" in the ink, "Nerd" italic in brand-strong.

Out of reach (review): a colour set in an inline style attribute (the export modules write none) and
the embedded brand PNG's pixels.
"""
from __future__ import annotations

import ast
import io
import re
import zipfile
from pathlib import Path

import tinycss2
import yaml
from openpyxl import load_workbook

import tests.unit.test_excel_export as workbook_fixtures
import tests.unit.test_export_service as export_fixtures
from app.services.excel_export_service import CHART_SERIES, build_analysis_workbook
from app.services.export_service import ExportService
from app.services.pdf_branding import PALETTE

ROOT = Path(__file__).resolve().parents[3]
EXPORT_MODULES = ("export_service.py", "excel_export_service.py", "analysis_export_metadata.py", "pdf_branding.py")
_FRONTMATTER = re.match(r"^---\n(.*?)\n---\n", (ROOT / "DESIGN.md").read_text(encoding="utf-8"), re.DOTALL)
TOKENS = {name: str(value).upper() for name, value in yaml.safe_load(_FRONTMATTER.group(1))["colors"].items()
          if str(value).startswith("#")}
TOKEN_VALUES = set(TOKENS.values())
SAGE = {value for name, value in TOKENS.items() if name.startswith("brand")}
WHITE = TOKENS["white"]

# Each PALETTE key's token, by role.
ROLES = {
    "brand": "brand",
    "brand_strong": "brand-strong",
    "brand_weak": "brand-weak",
    "brand_border": "brand-border",
    "background": "background-light",
    "panel": "panel-light",
    "ink": "text-primary-light",
    "ink_secondary": "text-secondary-light",
    "ink_tertiary": "text-tertiary-light",
    "border": "border-light",
}
HEX = re.compile(r"#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})(?![0-9A-Za-z])")
BARE_HEX = re.compile(r"^[0-9A-Fa-f]{6}$")  # openpyxl's form: no "#"


def normal(hex_value: str) -> str:
    digits = hex_value.lstrip("#").upper()
    return "#" + ("".join(c * 2 for c in digits) if len(digits) == 3 else digits[-6:])


def luminance(hex_value: str) -> float:
    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (int(normal(hex_value)[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(ink: str, ground: str) -> float:
    lighter, darker = sorted((luminance(ink), luminance(ground)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def css_rules(css: str) -> list[tuple[str, dict[str, str]]]:
    """(selector, declarations) for each block of a stylesheet; a margin box nested in @page reads as
    "@page @top-left", so its declarations are checked like any rule's."""
    rules: list[tuple[str, dict[str, str]]] = []

    def declarations(content) -> tuple[dict[str, str], list]:
        items = tinycss2.parse_declaration_list(content, skip_comments=True, skip_whitespace=True)
        found = {item.name: tinycss2.serialize(item.value).strip() for item in items if item.type == "declaration"}
        return found, [item for item in items if item.type == "at-rule"]

    def walk(nodes, prefix: str) -> None:
        for node in nodes:
            if node.type == "qualified-rule":
                rules.append((prefix + tinycss2.serialize(node.prelude).strip(), declarations(node.content)[0]))
            elif node.type == "at-rule" and node.content is not None and node.lower_at_keyword != "font-face":
                name = f"{prefix}@{node.lower_at_keyword} {tinycss2.serialize(node.prelude).strip()}".strip()
                found, nested = declarations(node.content)
                if found:
                    rules.append((name, found))
                walk(nested, name + " ")

    walk(tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True), "")
    return rules


def stylesheet(html: str) -> str:
    return "".join(re.findall(r"<style>(.*?)</style>", html, re.DOTALL))


def colour(value: str | None) -> str | None:
    match = HEX.search(value or "")
    return normal(match.group()) if match else None


def text_colours(html: str) -> list[tuple[str, str, str]]:
    """(selector, text colour, ground) for every rule that sets a text colour."""
    rules = css_rules(stylesheet(html))
    masthead = next((colour(decl.get("background")) for selector, decl in rules if selector == ".masthead"), None)
    found = []
    for selector, decl in rules:
        ink = colour(decl.get("color"))
        if ink is None:
            continue
        own = colour(decl.get("background") or decl.get("background-color"))
        ground = own or (masthead if selector.startswith(".masthead ") else None) or WHITE
        found.append((selector, ink, ground))
    return found


def _pdfs() -> dict[str, str]:
    analysis = export_fixtures.TestAnalysisPdfHtml()
    summary, filing = export_fixtures._make_summary_and_filing(export_fixtures._full_sections())
    return {
        "filing summary": ExportService().generate_pdf_html(summary, filing),
        "analysis": ExportService().generate_analysis_pdf_html(analysis._analysis(), analysis._company()),
    }


def _workbook_bytes() -> bytes:
    return build_analysis_workbook(workbook_fixtures._dataset(), exported_at=workbook_fixtures.EXPORTED_AT)


def workbook_colours(data: bytes) -> list[tuple[str, str, str | None]]:
    """(where, colour, role) for every colour the workbook sets; role is "text" with its ground."""
    found: list[tuple[str, str, str | None]] = []
    book = load_workbook(io.BytesIO(data))
    for sheet in book.worksheets:
        tab = sheet.sheet_properties.tabColor
        if tab is not None and tab.type == "rgb":
            found.append((f"{sheet.title} tab", normal(tab.rgb), None))
        for row in sheet.iter_rows():
            for cell in row:
                where = f"{sheet.title}!{cell.coordinate}"
                fill = normal(cell.fill.start_color.rgb) if cell.fill.patternType == "solid" else None
                if fill:
                    found.append((where + " fill", fill, None))
                for side in ("left", "right", "top", "bottom"):
                    edge = getattr(cell.border, side)
                    if edge is not None and edge.color is not None and edge.color.type == "rgb":
                        found.append((f"{where} {side} border", normal(edge.color.rgb), None))
                font = cell.font.color
                if font is not None and font.type == "rgb" and cell.value not in (None, ""):
                    found.append((where + " text", normal(font.rgb), fill or WHITE))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            if name.startswith("xl/charts/"):
                for value in re.findall(r'srgbClr val="([0-9A-Fa-f]{6})"', archive.read(name).decode("utf-8")):
                    found.append((name, normal(value), None))
    return found


def module_hex_literals() -> list[tuple[str, int, str]]:
    found = []
    for module in EXPORT_MODULES:
        path = ROOT / "backend" / "app" / "services" / module
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                hexes = HEX.findall(node.value) + ([node.value] if BARE_HEX.match(node.value) else [])
                found += [(module, node.lineno, normal(value)) for value in hexes]
    return found


def test_each_palette_key_holds_its_roles_token():
    assert set(PALETTE) == set(ROLES), "name the new key's token in ROLES (or drop the key)"
    drift = {key: (PALETTE[key], ROLES[key], TOKENS[ROLES[key]]) for key in PALETTE
             if normal(PALETTE[key]) != TOKENS[ROLES[key]]}
    assert drift == {}, "PALETTE key: (value, its role's token, that token's value)"
    assert [normal(value) for value in CHART_SERIES] == [TOKENS[f"chart-{n}"] for n in range(1, 7)]


def test_every_rendered_and_written_colour_is_a_token():
    off_token = []
    for name, html in _pdfs().items():
        css = stylesheet(html)
        fills = re.findall(r'(?:fill|stroke)="([^"]+)"', html)
        off_token += [(name, value) for value in HEX.findall(css) + fills
                      if value != "currentColor" and normal(value) not in TOKEN_VALUES]
    off_token += [(where, value) for where, value, _ in workbook_colours(_workbook_bytes()) if value not in TOKEN_VALUES]
    off_token += [(f"{module}:{line}", value) for module, line, value in module_hex_literals() if value not in TOKEN_VALUES]
    assert off_token == []


def test_every_text_colour_clears_its_ground():
    checked, low = set(), []
    for name, html in _pdfs().items():
        for selector, ink, ground in text_colours(html):
            checked.add(selector)
            if contrast(ink, ground) < 4.5:
                low.append(f"{name}: {selector} {ink} on {ground} is {contrast(ink, ground):.2f}:1")
    for where, ink, ground in workbook_colours(_workbook_bytes()):
        if ground is not None and contrast(ink, ground) < 4.5:
            low.append(f"workbook: {where} {ink} on {ground} is {contrast(ink, ground):.2f}:1")
    assert low == []
    # The roles the rule names are among the rules read, so a pass covers them.
    assert {".masthead .doc-kind", "th", ".meta", ".footnote", "@page @top-left"} <= checked


def test_sage_colours_only_links_and_the_wordmark():
    """D-041: a header, a label or a figure rests in the ink; sage marks a link (its target is the
    source) and the wordmark's "Nerd"."""
    sage_text = []
    for name, html in _pdfs().items():
        for selector, ink, _ in text_colours(html):
            if ink in SAGE:
                sage_text += [(name, part.strip()) for part in selector.split(",")
                              if not re.search(r"(?:^|\s)a$", part.strip()) and part.strip() != ".masthead .wordmark em"]
    sage_text += [(where, ink) for where, ink, ground in workbook_colours(_workbook_bytes())
                  if ground is not None and ink in SAGE]
    assert sage_text == []


def test_the_wordmark_reads_earnings_in_the_ink_and_nerd_italic_in_brand_strong():
    for name, html in _pdfs().items():
        assert '<span class="wordmark">Earnings<em>Nerd</em></span>' in html, name
        rules = dict(css_rules(stylesheet(html)))
        assert colour(rules[".masthead .wordmark"]["color"]) == TOKENS["text-primary-light"], name
        nerd = rules[".masthead .wordmark em"]
        assert colour(nerd["color"]) == TOKENS["brand-strong"] and nerd["font-style"] == "italic", name


def test_the_checks_read_what_they_claim():
    """Planted forms: the contrast and sage readers flag the defects this PR fixed."""
    assert round(contrast("#6B7280", TOKENS["brand-weak"]), 2) == 4.26  # the old tertiary on the tint
    assert round(contrast(TOKENS["text-tertiary-light"], TOKENS["brand-weak"]), 2) == 4.80
    planted = ".masthead { background: #ECF2EE; } .masthead .doc-kind { color: #6B7280; } th { color: #3C6650; }"
    found = {selector: (ink, ground) for selector, ink, ground in text_colours(f"<style>{planted}</style>")}
    assert found == {".masthead .doc-kind": ("#6B7280", "#ECF2EE"), "th": ("#3C6650", WHITE)}
    nested = css_rules("@page { size: A4; @top-left { color: #636A77; } }")
    assert ("@page @top-left", {"color": "#636A77"}) in nested
