"""Engineering abstention gate from the separately reviewed WMT handback, not financial judgment."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

from app.services import metric_delta_service as deltas
from app.services.export_service import ExportService
from app.services.provenance_service import enrich_raw_summary
from app.services.summary_sections import render_sections, sections_to_markdown


def test_qualified_income_abstains_without_borrowing_operands_or_rounded_fallback():
    fixture = json.loads((
        Path(__file__).parents[1] / "fixtures/income_delta/wmt_engineering_handback_v2.json"
    ).read_text())
    originals = [copy.deepcopy(case["authored_row"]) for case in fixture["original_controls"]]
    assert len(originals) == 9
    metrics = {
        "net_income": fixture["selected_parent_income"]["value"],
        "operating_income": fixture["selected_operating_income"]["value"],
    }
    # Native entity/attribution ownership is absent for every qualified total-income row,
    # including the historical P row with exact displayed values. Preserve its authored +12.6%
    # as authored data; the display contract has no independently verified authored-change cell.
    expected = [None, None, None, None, "+1.6%", "+1.6%", "+1.6%", "+13.3%", "+13.2%"]
    original_section = {"table": originals}
    bound = deltas.bind_exact_xbrl_deltas(original_section, metrics)
    assert original_section == {"table": originals}
    assert [deltas.strict_xbrl_metric_key(row["metric"]) for row in originals[:4]] == [None] * 4
    assert [row.get("change_display") for row in bound["table"]] == [
        None, None, None, None, "+1.6%", "+1.6%", "+1.6%", None, None,
    ]
    for index in range(4):
        assert bound["table"][index]["change"] == originals[index]["change"]
        assert deltas.row_delta_fields(originals[index]) == {}
        # A stored envelope's version and stale code fields cannot supply missing entity scope.
        stale = {**originals[index], "change_display": "+99.0%",
                 "change_direction": "up", "change_tone": "gain"}
        assert deltas.delta_for_row(stale, exact_owned=True) is None
        for reload_metrics in (None, {}, metrics):
            assert "change_display" not in deltas.bind_exact_xbrl_deltas(
                {"table": [stale]}, reload_metrics, preserve_owned_when_unavailable=True,
            )["table"][0]

    for version, section_name in ((1, "financial_highlights"), (2, "results_that_matter")):
        raw = {"schema_version": version, "sections": {section_name: bound},
               deltas.EXACT_CONTEXT_KEY: deltas.EXACT_CONTEXT_VERSION}
        # Actual read-time enrichment and shared web/Markdown/CSV/PDF projection retain abstention.
        for candidate in (raw, enrich_raw_summary(raw, None, xbrl_standardized=metrics)):
            sections = render_sections(candidate)
            block = next(b for section in sections for b in section.blocks if b.kind == "metrics")
            assert [row[3] for row in block.rows] == [value or "—" for value in expected]
            assert [row.get("change_display") for row in block.metric_rows] == expected
            assert [row["change"] for row in block.metric_rows] == [r["change"] for r in originals]
            markdown = sections_to_markdown(sections)
            filing = SimpleNamespace(
                id=1, filing_date=None, period_end_date=None,
                sec_url="https://sec.example/filing", filing_type="10-K",
                company=SimpleNamespace(name="Engineering control"), content_cache=None,
            )
            summary = SimpleNamespace(filing_id=1, raw_summary=candidate)
            for surface in (markdown, ExportService().generate_csv(summary, filing),
                            ExportService().generate_pdf_html(summary, filing)):
                assert "+12.9%" not in surface and "+10.4%" not in surface
                assert "+1.7%" not in surface and "+99.0%" not in surface
                assert "+1.6%" in surface and "+13.3%" in surface and "+13.2%" in surface

    # Synthetic scope conflicts are distinct from the nine original retained controls.
    for label in (
        "Adjusted net income", "Net income attributable to OtherCo",
        "Net income attributable to noncontrolling interests",
        "Consolidated net income excluding noncontrolling interests",
        "  CONSOLIDATED  NET INCOME ATTRIBUTABLE TO WALMART  ", "Segment net loss",
        "Net income and diluted EPS", "Net income (including per share results)",
    ):
        row = {"metric": label, "current_period": "$21.9B", "prior_period": "$19.4B"}
        for owned in (False, True):
            assert deltas.delta_for_row(row, exact_owned=owned) is None
        assert deltas.row_delta_fields(row) == {}
    # Same displayed values and even standard-looking facts cannot authorize a qualified claim.
    invented = copy.deepcopy(metrics)
    invented["net_income"]["current"]["raw_tag"] = "us-gaap:ProfitLoss"
    invented["net_income"]["prior"]["raw_tag"] = "custom:ParentIncome"
    assert all("change_display" not in row for row in deltas.bind_exact_xbrl_deltas(
        {"table": originals[:4]}, invented,
    )["table"])

    # Review successor: invented values only. Collect all results before comparing so reverting
    # just the service to 3e5 exposes both amount bypasses and ratio suppression in one failure.
    synthetic_cases = {
        "earnings_presentation_amount": (
            "Net earnings/(loss) attributable to Example shareholders", "$120M", "$100M",
            None, None,
        ),
        "loss_income_presentation_amount": (
            "Net (loss) income attributable to Example", "$120M", "$100M", None, None,
        ),
        "presentation_ratio": (
            "Net income/(loss) margin", "50%", "40%", "+10.0 ppts", "+99.0%",
        ),
        "presentation_mixed_units": (
            "Net income/(loss) margin", "50%", "$40M", None, None,
        ),
        "presentation_missing_percentage": (
            "Net income/(loss) margin", "n/a%", "40%", None, None,
        ),
        "earnings_per_share": (
            "Diluted net earnings/(loss) per common share attributable to Example",
            "$1.20", "$1.00", "+20.0%", "+99.0%",
        ),
        "income_loss_per_share": (
            "Basic net (loss) income per common share attributable to Example",
            "$1.20", "$1.00", "+20.0%", "+99.0%",
        ),
        "punctuation_is_not_generic_alias": (
            "Net (income)", "$120M", "$100M", None, None,
        ),
        "generic_cached_invalid_displays": (
            "Net income", "not available", "not available", None, "+99.0%",
        ),
    }
    observed, expected_synthetic = {}, {}
    for case, (label, current, prior, plain_expected, owned_expected) in synthetic_cases.items():
        row = {"metric": label, "current_period": current, "prior_period": prior}
        plain = deltas.delta_for_row(row)
        stale = {**row, "change_display": "+99.0%", "change_direction": "up", "change_tone": "gain"}
        owned = deltas.delta_for_row(stale, exact_owned=True)
        observed[case] = (plain.display if plain else None, owned.display if owned else None)
        expected_synthetic[case] = (plain_expected, owned_expected)
        assert deltas.strict_xbrl_metric_key(label) == (
            "net_income" if label == "Net income" else None
        )
    assert observed == expected_synthetic
