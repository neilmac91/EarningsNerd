"""The offline HTML aid retains one exact, structured text projection."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from evals import acceptance_source_view as source_view


def test_source_view_invariants_and_mutation_proofs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw = (
        '<!doctype html><html><head><title>Résultats</title>'
        '<style media="screen">.secret { display:none }</style>'
        '<script type="text/javascript">window.secret="never display";</script></head>'
        '<body><h1 data-owner="A&amp;B">Quarterly € report</h1><!-- retained note -->'
        '<p hidden style="color:red">Hidden <em>but retained</em></p>'
        '<ix:hidden contextRef="Q2" name="us-gaap:Revenue">Inline fact</ix:hidden>'
        '<table id="outer"><caption>Financial footnote</caption><tr class="heading">'
        '<th scope="col" rowspan="2">Metric<img src="cell.png" alt=""></th><th colspan="2">Period</th></tr>'
        '<tr><td headers="metric">Revenue</td><td><table aria-label="nested"><tr>'
        '<td style="visibility:hidden">Nested hidden value</td></tr></table></td></tr>'
        '<tr><td>A</td><td>B</td></tr></table>'
        '<img src="chart.png" alt="Revenue chart" style="width:10px" data-x="1">'
        '<footer><sup id="fn1">1</sup> Footnote text</footer></body></html>'
    ).encode("utf-8")

    projected = source_view.project_html(raw)
    source_view.verify_projection(raw, projected)
    assert projected["source_bytes"] == len(raw)
    assert projected["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert projected["semantic_coverage_attested"] is False
    assert projected["markup_is_reviewed_content"] is False
    assert projected["compact_text"] == (
        "RésultatsQuarterly € reportHidden but retainedInline factFinancial footnote"
        "MetricPeriodRevenueNested hidden valueAB1 Footnote text"
    )
    review = source_view.render_review(projected)
    assert source_view.review_text(review) == projected["compact_text"]
    reader = source_view.render_reader(projected)
    assert source_view.review_text(reader) == projected["compact_text"]
    assert len(reader.encode()) < len(review.encode())
    assert reader.count("@IMAGE ") == 2
    assert "@CELL T00001-R0001-C0001" in reader
    assert "@ROW T00002-R0001\t" in reader
    assert "@ROW T00001-R0003\t" in reader
    assert "@TABLE T00001" in review
    assert "@TABLE T00002 parent_table=T00001 parent_cell=T00001-R0002-C0002" in review
    assert "rowspan=2 colspan=1" in review
    assert "rowspan=1 colspan=2" in review
    assert "@IMAGE I00001" in review

    assert len(projected["tables"]) == 2
    outer, nested = projected["tables"]
    assert nested["parent_table_id"] == outer["id"]
    assert nested["parent_cell_id"] == outer["rows"][1]["cells"][1]["id"]
    assert [cell["rowspan"] for cell in outer["rows"][0]["cells"]] == [2, 1]
    assert [cell["colspan"] for cell in outer["rows"][0]["cells"]] == [1, 2]
    images = {image["src"]: image for image in projected["images"]}
    assert images["chart.png"]["alt"] == "Revenue chart"
    assert images["cell.png"]["alt"] == ""
    assert {item["kind"] for item in projected["exclusions"]} == {"style", "script", "comment"}
    for excluded in projected["exclusions"]:
        span = excluded["content"]
        assert span["sha256"] == hashlib.sha256(raw[span["start"] : span["end"]]).hexdigest()
        assert excluded["included_in_compact_text"] is False
    names = [item["name"] for item in projected["attributes"]]
    for expected in ("hidden", "style", "contextref", "name", "rowspan", "colspan", "src", "alt", "data-x"):
        assert expected in names
    hidden_units = [unit for unit in projected["units"] if unit["hidden_reasons"]]
    assert {reason for unit in hidden_units for reason in unit["hidden_reasons"]} >= {
        "hidden_attribute",
        "inline_xbrl_hidden",
        "inline_style_hidden",
    }
    assert "Hidden but retained" in projected["compact_text"]
    assert "Inline fact" in projected["compact_text"]
    assert "Nested hidden value" in projected["compact_text"]
    for unit in projected["units"]:
        span = unit["span"]
        assert span["sha256"] == hashlib.sha256(raw[span["start"] : span["end"]]).hexdigest()

    # Later duplicate attributes are ignored by HTML tree construction: semantics follow the first.
    duplicate_raw = (
        b'<div aria-hidden="false" aria-hidden="true">Visible first</div>'
        b'<p style="color:red" style="display:none">Visible style</p>'
        b'<img src="first.png" src="second.png" alt="a" alt="b">'
        b'<table><tr><td rowspan="1" rowspan="3" colspan="2" colspan="4">c</td></tr></table>'
    )
    duplicate_projected = source_view.project_html(duplicate_raw)
    assert all(unit["hidden_reasons"] == [] for unit in duplicate_projected["units"])
    assert [(image["src"], image["alt"]) for image in duplicate_projected["images"]] == [("first.png", "a")]
    duplicate_cell = duplicate_projected["tables"][0]["rows"][0]["cells"][0]
    assert (duplicate_cell["rowspan"], duplicate_cell["colspan"]) == (1, 2)
    assert [item["name"] for item in duplicate_projected["attributes"]].count("aria-hidden") == 2

    style_raw = (
        '<section style=" DISPLAY : none!important ; color:red"><span>Important display descendant</span></section>'
        '<div style="visibility:hidden ! IMPORTANT"><strong>Important visibility descendant</strong></div>'
        '<aside style="display : none"><span>Plain hidden descendant</span></aside>'
        '<p style="display:block!important;visibility:visible !important;xdisplay:none;visibility:hiddenly;display:none!importantx;color:red display:none">Near miss visible</p>'
    ).encode("utf-8")
    style_projected = source_view.project_html(style_raw)
    source_view.verify_projection(style_raw, style_projected)
    assert style_projected["compact_text"] == (
        "Important display descendantImportant visibility descendant"
        "Plain hidden descendantNear miss visible"
    )
    style_units = {unit["decoded"]: unit for unit in style_projected["units"]}
    for inherited_hidden in (
        "Important display descendant",
        "Important visibility descendant",
        "Plain hidden descendant",
    ):
        assert "inline_style_hidden" in style_units[inherited_hidden]["hidden_reasons"]
    assert style_units["Near miss visible"]["hidden_reasons"] == []
    style_values = {item["value"] for item in style_projected["attributes"] if item["name"] == "style"}
    assert style_values == {
        " DISPLAY : none!important ; color:red",
        "visibility:hidden ! IMPORTANT",
        "display : none",
        "display:block!important;visibility:visible !important;xdisplay:none;visibility:hiddenly;display:none!importantx;color:red display:none",
    }
    style_reader = source_view.render_reader(style_projected)
    important_line = next(line for line in style_reader.splitlines() if "Important display descendant" in line)
    near_miss_line = next(line for line in style_reader.splitlines() if "Near miss visible" in line)
    assert "hidden=inline_style_hidden" in important_line
    assert "hidden=-" in near_miss_line

    dropped = copy.deepcopy(projected)
    dropped["units"] = [unit for unit in dropped["units"] if "Quarterly" not in unit["decoded"]]
    with pytest.raises(ValueError, match="events and units differ"):
        source_view.verify_projection(raw, dropped)
    shifted = copy.deepcopy(projected)
    shifted["units"][0]["span"]["start"] += 1
    with pytest.raises(ValueError, match="text-unit locator mismatch"):
        source_view.verify_projection(raw, shifted)
    coherent = copy.deepcopy(projected)
    changed_unit = next(unit for unit in coherent["units"] if "Quarterly" in unit["decoded"])
    changed_unit["decoded"] = changed_unit["decoded"].replace("Quarterly", "Changed")
    coherent["compact_text"] = source_view._normalize_units(coherent["units"])
    coherent["compact_text_sha256"] = hashlib.sha256(coherent["compact_text"].encode()).hexdigest()
    with pytest.raises(ValueError, match="decoding mismatch"):
        source_view.verify_projection(raw, coherent)

    for malformed in (
        b"<table><tr><td>truncated",
        b"<p>text</table>",
        b'<p title="unterminated>text</p>',
        b"<p>text<!-- truncated</p>",
        b"<html><body><![CDATA[Material obligation: 10]]></body></html>",
    ):
        with pytest.raises(ValueError):
            source_view.project_html(malformed)
    with pytest.raises(ValueError, match="invalid rowspan"):
        source_view.project_html(b'<table><tr><td rowspan="all">x</td></tr></table>')
    monkeypatch.setattr(source_view, "MAX_UNIT_BYTES", 8)
    with pytest.raises(ValueError, match="oversized single parser unit"):
        source_view.project_html(b"<p>123456789</p>")
    monkeypatch.setattr(source_view, "MAX_UNIT_BYTES", 2 * 1024 * 1024)

    for implicit_boundary in (
        b"<div><p hidden>A<p>B</p></p></div>",
        b"<p hidden>A<div>B</div></p>",
        b"<p hidden>A<dialog>B</dialog></p>",
        b"<p hidden>A<center>B</center></p>",
        b"<p hidden>A<li>B</li></p>",
        b"<ul><li hidden>A<li>B</li></li></ul>",
        b"<dl><dt hidden>A<dd>B</dd></dt></dl>",
        b"<ruby><rt hidden>A<rp>B</rp></rt></ruby>",
        b"<ruby><rb hidden>A<rt>B</rt></rb></ruby>",
        b"<ruby><rtc hidden>A<rb>B</rb></rtc></ruby>",
        b"<select><option hidden>A<option>B</option></option></select>",
        b"<select><optgroup hidden><hr></optgroup></select>",
        b"<table><tr><td hidden>A<td>B</td></td></tr></table>",
        b"<table><tr hidden><tr></tr></tr></table>",
        b"<table><tbody><tr><td>A</td></tr><tfoot></tfoot></tbody></table>",
        b"<table><caption>A<tbody></tbody></caption></table>",
        b"<table><colgroup hidden><tbody></tbody></colgroup></table>",
        b"<a hidden>A<a>B</a></a>",
        b"<a hidden>A<em>B<a>C</a></em></a>",
        b"<button hidden>A<button>B</button></button>",
        b"<nobr hidden>A<nobr>B</nobr></nobr>",
        b"<form hidden>A<form>B</form>C</form>",
        b"<select><option>A</option></select>",
        b"<select hidden>A<select>B</select>C</select>",
        b"<h1 hidden>A<h2>B</h2></h1>",
        b"<table hidden>A<tr><td>B</td></tr></table>",
        b"<table>&nbsp;<tr><td>A</td></tr></table>",
        b"<table hidden><div>A</div></table>",
        b"<table hidden><table><tr><td>A</td></tr></table></table>",
        b"<table><tbody><tr><div>A</div></tr></tbody></table>",
        b"<table><tbody><tr><td>A<caption>B</caption></td></tr></tbody></table>",
        b"<table><tbody><tr>A<caption>B</caption></tr></tbody></table>",
        b"<table><tbody>A<caption>B</caption></tbody></table>",
        b"<tr><td>A</td></tr>",
        b"<div><span>A</div></span>",
        b"<div>A",
        b"<div hidden/>B",
        b"<ix:hidden/>",
    ):
        with pytest.raises(ValueError, match="unsupported implicit HTML boundary"):
            source_view.project_html(implicit_boundary)

    explicit_nested = (
        b"<html><body><ul><li hidden>outer<ul><li>inner</li></ul></li></ul>"
        b"<table><style>.excluded{}</style><script>excluded()</script><tbody><tr>"
        b"<td>outer<table><tbody><tr><td>inner</td></tr></tbody>"
        b"</table></td></tr></tbody></table>"
    )
    explicit_projected = source_view.project_html(explicit_nested)
    source_view.verify_projection(explicit_nested, explicit_projected)
    assert explicit_projected["compact_text"] == "outerinnerouterinner"
    inner_list_unit = next(unit for unit in explicit_projected["units"] if unit["decoded"] == "inner")
    assert inner_list_unit["hidden_reasons"] == ["hidden_attribute"]
    void_self_closing = source_view.project_html(b"<p>A<br/>B</p>")
    assert void_self_closing["compact_text"] == "AB"
    explicit_ruby = source_view.project_html(b"<ruby><rtc><rt>A</rt><rp>B</rp></rtc></ruby>")
    assert explicit_ruby["compact_text"] == "AB"

    source = tmp_path / "source.htm"
    source.write_bytes(raw)
    output = tmp_path / "view"
    manifest = source_view.build_source_view(source, hashlib.sha256(raw).hexdigest(), len(raw), output)
    assert json.loads((output / "manifest.json").read_text()) == manifest
    stored = json.loads((output / "source-view.json").read_text())
    assert source_view.review_text((output / "reader.txt").read_text()) == stored["compact_text"]
    with pytest.raises(ValueError, match="must not already exist"):
        source_view.build_source_view(source, hashlib.sha256(raw).hexdigest(), len(raw), output)
    with pytest.raises(ValueError, match="source size/hash mismatch"):
        source_view.build_source_view(source, "0" * 64, len(raw), tmp_path / "wrong")

    original_read = Path.read_bytes
    reads = 0

    def mutate_between_checks(path: Path) -> bytes:
        nonlocal reads
        data = original_read(path)
        if path == source:
            reads += 1
            if reads == 2:
                return data + b" "
        return data

    monkeypatch.setattr(Path, "read_bytes", mutate_between_checks)
    changed_output = tmp_path / "changed"
    with pytest.raises(ValueError, match="source changed during view construction"):
        source_view.build_source_view(source, hashlib.sha256(raw).hexdigest(), len(raw), changed_output)
    assert not changed_output.exists()
