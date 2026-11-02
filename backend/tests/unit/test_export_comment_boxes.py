"""Every workbook comment's box holds its text (E262).

Excel draws a cell comment in the box the file sizes, and openpyxl's default box, 144 by 79 pixels, cut a longer note
off where the reader hovered its cell. The builder sizes each box to its text (``excel_export_service._comment``).
openpyxl reads a comment's text back but not its box, so this file reads each box from the archive itself: the sheet's
drawing part (``xl/drawings/commentsDrawingN.vml``), joined to its comment by cell. It holds every box to the rule
stated here: as wide as the text's longest line at 7 pixels a character, up to 40 characters, plus 20 for the insets,
and as tall as the text wraps at that measure, between words and never at a hyphen, at 18 pixels a line, plus 14. It
reads every dataset the shared fixtures hold, among them the later-filing evidence's longest notes; it holds the helper
itself to the rule's examples, among them a note shorter than the measure, which no fixture writes; and it holds every
comment the app builds to that one helper, so none takes another box.

What the rule's numbers rest on (the pull request's offline proof, not this file): over every comment those fixtures
write, the box holds the text wrapped in Calibri 11's metrics (Carlito), the workbook's own font, in a wider stand-in
for the Tahoma Excel gives a note it writes itself (DejaVu Sans 10), and in LibreOffice's Liberation Sans 10, and
LibreOffice opens each box at the width the file gives it.
"""
import ast
import io
import json
import re
import textwrap
import xml.etree.ElementTree as ET
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest
from openpyxl.utils import get_column_letter

from app.services import excel_export_service
from app.services.excel_export_service import build_analysis_workbook
from tests.unit.test_excel_export import EXPORTED_AT, _dataset

BACKEND = Path(__file__).resolve().parents[2]
FIXTURES = BACKEND / "tests" / "fixtures"
APP = BACKEND / "app"
HELPER_FILE = APP / "services" / "excel_export_service.py"

# The rule, in pixels: a character's width, the measure in characters, a line's height, and the insets.
CHAR_PX, MEASURE, LINE_PX, INSET_X, INSET_Y = 7, 40, 18, 20, 14
# openpyxl's default box, which held about 90 characters.
OPENPYXL_DEFAULT = (144, 79)

MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RELS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
VML = "{urn:schemas-microsoft-com:vml}"
EXCEL = "{urn:schemas-microsoft-com:office:excel}"


def expected_box(text: str) -> tuple[int, int]:
    paragraphs = text.split("\n")
    measure = min(MEASURE, max(len(paragraph) for paragraph in paragraphs))
    lines = sum(max(1, len(textwrap.wrap(paragraph, measure, break_on_hyphens=False))) for paragraph in paragraphs)
    return measure * CHAR_PX + INSET_X, lines * LINE_PX + INSET_Y


def _datasets() -> list[tuple[str, dict]]:
    """The excel export's own dataset, the shared notes fixture's (its notes as the page reads them; the case that
    holds a lone surrogate, which no workbook can store, aside) and the later-filing evidence fixture's."""
    found = [("excel_export", _dataset())]
    for case in json.loads((FIXTURES / "analysis_data_notes.json").read_text())["cases"]:
        if case["name"] == "portable_reason_identity_utf16_ascii":
            continue
        dataset = deepcopy(case["dataset"])
        dataset["data_notes"] = deepcopy(case["expected"])
        found.append((f"notes:{case['name']}", dataset))
    for case in json.loads((FIXTURES / "analysis_later_filings.json").read_text())["cases"]:
        found.append((f"later:{case['name']}", deepcopy(case["dataset"])))
    return found


DATASETS = _datasets()


def comment_boxes(workbook: bytes) -> list[tuple[str, str, tuple[int, int]]]:
    """Each comment in the archive: its sheet's comments part, its cell, its text and its box (width, height) in
    pixels, read from the drawing part its sheet names beside the comments."""
    found = []
    with zipfile.ZipFile(io.BytesIO(workbook)) as archive:
        for rels_name in (name for name in archive.namelist() if name.startswith("xl/worksheets/_rels/")):
            targets = {rel.get("Type").rsplit("/", 1)[-1]: rel.get("Target").lstrip("/")
                       for rel in ET.fromstring(archive.read(rels_name)).iter(f"{RELS}Relationship")}
            if "comments" not in targets:
                continue
            texts = {comment.get("ref"): "".join(t.text or "" for t in comment.iter(f"{MAIN}t"))
                     for comment in ET.fromstring(archive.read(targets["comments"])).iter(f"{MAIN}comment")}
            shapes = {}
            for shape in ET.fromstring(archive.read(targets["vmlDrawing"])).iter(f"{VML}shape"):
                data = shape.find(f"{EXCEL}ClientData")
                cell = f"{get_column_letter(int(data.find(f'{EXCEL}Column').text) + 1)}{int(data.find(f'{EXCEL}Row').text) + 1}"
                size = dict(re.findall(r"(width|height):(\d+)px", shape.get("style")))
                assert set(size) == {"width", "height"}, f"{cell}: a box sized other than in pixels: {shape.get('style')}"
                shapes[cell] = (int(size["width"]), int(size["height"]))
            assert set(shapes) == set(texts), f"{targets['comments']}: a comment without its box, or a box without its comment"
            found += [(targets["comments"], cell, texts[cell], shapes[cell]) for cell in texts]
    return found


@pytest.fixture(scope="module")
def boxes() -> dict[str, list]:
    return {name: comment_boxes(build_analysis_workbook(deepcopy(dataset), exported_at=EXPORTED_AT))
            for name, dataset in DATASETS}


def test_every_comment_box_holds_its_text(boxes):
    wrong = [f"{name} {part} {cell}: {box}, the rule gives {expected_box(text)}: {text!r}"
             for name, found in boxes.items() for part, cell, text, box in found if box != expected_box(text)]
    assert wrong == []


def test_the_fixtures_reach_the_notes_the_default_box_cut(boxes):
    # Comments past the 90 characters the default box held, the later-filing evidence's longest (340) among them, and
    # comments of several paragraphs, so the rule is read where it matters; no box keeps the default.
    texts = {text for found in boxes.values() for _, _, text, _ in found}
    assert max(map(len, texts)) >= 300 and sum(len(text) > 90 for text in texts) >= 10
    assert sum(text.count("\n") >= 2 for text in texts) >= 3
    assert all(box != OPENPYXL_DEFAULT for found in boxes.values() for *_, box in found)


# The rule by example, each with the box it gives: (text, characters on its widest line, lines).
EXAMPLES = [
    # A box as wide as the text's longest line, so a short note keeps a narrow box; each line of text its own paragraph.
    ("Computed Q4.", 12, 1),
    ("Calculated figure.\nComputed Q4.", 18, 2),
    # Wrapped between words at the measure: 40 characters take one line, 41 two.
    ("a" * 19 + " " + "b" * 20, MEASURE, 1),
    ("a" * 19 + " " + "b" * 21, MEASURE, 2),
    # Never at a hyphen: a hyphenated word stays whole, so it takes the next line to itself (broken at its hyphens it
    # would end the first line, and the 30 z's would share the second). A figure's or a date's hyphen never breaks.
    ("x" * 30 + " earnings-per-share " + "z" * 30, MEASURE, 3),
    # A word longer than the measure breaks inside it.
    ("y" * 85, MEASURE, 3),
]


@pytest.mark.parametrize("text, characters, lines", EXAMPLES)
def test_the_rule_and_the_builder_s_helper_give_each_example_its_box(text, characters, lines):
    box = (characters * CHAR_PX + INSET_X, lines * LINE_PX + INSET_Y)
    assert expected_box(text) == box
    comment = excel_export_service._comment(text)
    assert (comment.width, comment.height, comment.text, comment.author) == (*box, text, "EarningsNerd")


def in_openpyxl_comments(module: str | None) -> bool:
    """openpyxl's comments package, or a module inside it."""
    return module == "openpyxl.comments" or (module or "").startswith("openpyxl.comments.")


def test_every_comment_the_app_builds_takes_the_sizing_helper():
    """Only the workbook builder reaches openpyxl's Comment, and only inside ``_comment``: imported by name from
    openpyxl.comments or a module inside it (``openpyxl.comments.comments`` defines it), under any alias and never by a
    star, never reached as an attribute (``openpyxl.comments.Comment``) and never through the module itself, so every
    comment the app builds takes a box sized to its text. A dynamic import (``importlib``) is out of its reach."""
    importers, stray = [], []
    for path in sorted(APP.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        where = path.relative_to(BACKEND)
        helper = next((node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_comment"), None)
        inside = {id(node) for node in ast.walk(helper)} if helper and path == HELPER_FILE else set()
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and in_openpyxl_comments(node.module):
                if any(alias.name == "*" for alias in node.names):
                    stray.append(f"{where}:{node.lineno} imports everything {node.module} holds")
                names |= {alias.asname or alias.name for alias in node.names if alias.name != "*"}
            elif isinstance(node, ast.ImportFrom) and node.module == "openpyxl" and any(
                    alias.name == "comments" for alias in node.names):
                stray.append(f"{where}:{node.lineno} imports openpyxl's comments module")
            elif isinstance(node, ast.Import) and any(alias.name.startswith("openpyxl.comments") for alias in node.names):
                stray.append(f"{where}:{node.lineno} imports openpyxl.comments whole")
            elif isinstance(node, ast.Attribute) and node.attr == "Comment" and id(node) not in inside:
                stray.append(f"{where}:{node.lineno} reaches Comment as an attribute outside _comment")
        if names:
            importers.append(path)
        stray += [f"{where}:{node.lineno} names {node.id} outside _comment"
                  for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id in names and id(node) not in inside]
    assert importers == [HELPER_FILE] and stray == []
