"""Original filed tables, including real competing layouts and split sign cells."""
import copy
import gzip
import hashlib
from pathlib import Path

from lxml import html
import pytest

from app.services.edgar.statement_relationship_source import extract_operating_to_pretax_source

SOURCES = {
    "meli": ("0001099590-26-000006", "57805abbd6d3b3a40e87e49529657b79f47986ac370e6f9a437eadc7ab72198d", 54),
    "se": ("0001140361-26-015366", "9474df67304ba388df96be05e3437b718755c2d18922440bbfb9de6f0e81f575", 461),
}


def original(ticker):
    path = Path(__file__).parents[1] / "fixtures/operating_pretax" / f"{ticker}-2025.html.gz"
    raw = gzip.decompress(path.read_bytes())
    assert hashlib.sha256(raw).hexdigest() == SOURCES[ticker][1]
    return raw


def set_text(cell, text):
    attributes = dict(cell.attrib)
    cell.clear()
    cell.attrib.update(attributes)
    cell.text = text


def extract(raw, ticker):
    return extract_operating_to_pretax_source(raw, accession=SOURCES[ticker][0],
                                             document_url="https://example.test/selected-primary.htm",
                                             period_of_report="2025-12-31")


@pytest.mark.parametrize("ticker", SOURCES)
def test_original_filed_bridge_preserves_source_units_rows_and_signs(ticker):
    result = extract(original(ticker), ticker)
    assert result is not None
    assert result["document_sha256"] == SOURCES[ticker][1]
    assert result["accession"] == SOURCES[ticker][0]
    assert result["currency"] == "USD"
    assert len(result["columns"]) == 3
    assert result["current"]["period_end"] == "2025-12-31"
    assert result["prior"]["period_end"] == "2024-12-31"
    assert result["relationship"] == "reported_between_operating_and_pretax"
    current = result["current"]
    if ticker == "meli":
        assert result["scale"] == 1000000
        assert current["operating"]["value"] == 3201000000
        assert [r["value"] for r in current["components"]] == [138000000, -160000000, -337000000]
        assert current["pretax"]["value"] == 2842000000
        assert [r["row"] for r in current["components"]] == [18, 19, 20]
        assert result["columns"][2]["label"] == "2023 (1)"
    else:
        assert result["scale"] == 1000
        assert current["operating"]["value"] == 1985306000
        assert [r["value"] for r in current["components"]] == [331072000, -33610000, -43443000, 21017000, 20517000]
        assert current["pretax"]["value"] == 2280859000
        negative = current["components"][1]
        assert negative["lexical"] == "( 33,610 )"
        assert [c["column"] for c in negative["cells"] if c["text"]] == [12, 13]
        assert current["column_end"] == 14


@pytest.mark.parametrize("ticker", SOURCES)
@pytest.mark.parametrize("change", ["unknown_row", "bad_arithmetic", "missing_component", "missing_endpoint", "duplicate"])
def test_original_statement_mutations_abstain(ticker, change):
    document = html.fromstring(original(ticker))
    table = document.xpath("//table")[SOURCES[ticker][2]]
    rows = table.xpath("./tr|./tbody/tr")
    component, endpoint = (18, 21) if ticker == "meli" else (23, 28)
    if change == "unknown_row":
        set_text(rows[component][0], "Unclassified reported item")
    elif change == "bad_arithmetic":
        cell = rows[component][1 if ticker == "meli" else 12]
        set_text(cell, "999")
    elif change == "missing_component":
        rows[component].getparent().remove(rows[component])
    elif change == "missing_endpoint":
        rows[endpoint].getparent().remove(rows[endpoint])
    else:
        # Duplicate the original statement together with its actual heading/unit ownership.
        if ticker == "meli":
            parent = table.getparent().getparent()
            context = list(table.getparent().itersiblings(preceding=True))[:4][::-1]
            for node in context + [table.getparent()]:
                parent.append(copy.deepcopy(node))
        else:
            table.getparent().getparent().append(copy.deepcopy(table.getparent()))
    assert extract(html.tostring(document), ticker) is None


def test_real_split_parenthesis_is_required():
    document = html.fromstring(original("se"))
    table = document.xpath("//table")[461]
    row = table.xpath("./tr|./tbody/tr")[24]
    row[13].clear()  # genuine separate closing-sign cell; numeric amount remains
    assert extract(html.tostring(document), "se") is None


@pytest.mark.parametrize("ticker,competing", [("meli", 67), ("meli", 121), ("se", 239)])
def test_real_recast_segment_and_percentage_tables_never_become_face_bridge(ticker, competing):
    document = html.fromstring(original(ticker))
    tables = document.xpath("//table")
    selected = tables[SOURCES[ticker][2]]
    # Even beneath the face statement's real title/units, these actual column grammars abstain.
    selected.getparent().replace(selected, copy.deepcopy(tables[competing]))
    assert extract(html.tostring(document), ticker) is None


@pytest.mark.parametrize("ticker", SOURCES)
def test_missing_explicit_unit_does_not_default_to_usd(ticker):
    document = html.fromstring(original(ticker))
    table = document.xpath("//table")[SOURCES[ticker][2]]
    siblings = table.itersiblings(preceding=True) if ticker == "se" else table.getparent().itersiblings(preceding=True)
    for node in siblings:
        if "dollars" in " ".join(node.itertext()):
            node.clear()
            node.text = "Amounts in reporting currency"
            break
    assert extract(html.tostring(document), ticker) is None


def test_original_header_variant_never_emits_invalid_comparative_date():
    document = html.fromstring(original("meli"))
    rows = document.xpath("//table")[54].xpath("./tr|./tbody/tr")
    set_text(rows[1][1], "Year Ended February 29,")
    for cell in rows[2]:
        text = " ".join(cell.itertext())
        for before, after in (("2025", "2024"), ("2024", "2023"), ("2023", "2022")):
            if before in text:
                set_text(cell, text.replace(before, after))
                break
    assert extract_operating_to_pretax_source(html.tostring(document), accession=SOURCES["meli"][0],
                                              document_url="https://example.test/selected-primary.htm",
                                              period_of_report="2024-02-29") is None


def test_original_statement_numeric_subcolumns_cannot_fuse_into_reconciled_values():
    document = html.fromstring(original("meli"))
    rows = document.xpath("//table")[54].xpath("./tr|./tbody/tr")
    # Retain original title, unit, year bands, row identities and cell positions.
    # Two numeric cells per band previously fused 1|10, 2|20, 3|30 into
    # 110 + 220 + 0 + 0 = 330, so bridge arithmetic alone did not refute it.
    for row_index, pair in ((15, ("1", "10")), (18, ("2", "20")),
                            (19, ("0", "0")), (20, ("0", "0")), (21, ("3", "30"))):
        column = 0
        for cell in rows[row_index]:
            span = int(cell.get("colspan", "1"))
            if column >= 3:
                offset = (column - 3) % 6
                set_text(cell, pair[0] if offset == 0 else pair[1] if offset == 2 else "")
            column += span
    assert extract(html.tostring(document), "meli") is None
