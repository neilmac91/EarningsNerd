"""P0-2 guardrail (data-quality plan): list fields render as true bullets, never `"; "` runs.

Model bullets end with "." — joining them with "; " produced the ``.;`` artifact on every
web-rendered summary ("…$87.0B.; Total assets grew…") while the PDF serializer bulleted the
same data. These tests feed "."-terminated items through every list-valued field the renderer
accepts and pin: no ``.;`` anywhere in the output, and each field emits real markdown bullets.
"""
from app.services.openai_service import openai_service


def _summary_with_dot_terminated_lists():
    return {
        "metadata": {"company_name": "BankCo", "filing_type": "10-K", "reporting_period": "FY2025"},
        "sections": {
            "executive_snapshot": {
                "headline": "BankCo posted record results.",
                "key_points": [
                    "Net interest income rose to $95.4B.",
                    "Noninterest income reached $87.0B.",
                ],
                "tone": "confident",
            },
            "financial_highlights": {
                "table": [
                    {"metric": "Net income", "current_period": "$57.0B", "prior_period": "$55.7B"},
                ],
                "profitability": ["ROE was 17%.", "Efficiency ratio improved."],
                "cash_flow": ["Operating cash flow was -$147.8B.", "Driven by trading flows."],
                "balance_sheet": ["Total assets grew to $4.6T.", "CET1 ratio 15.4%."],
            },
            "management_discussion_insights": {
                "themes": ["Scale advantages.", "Credit normalization."],
                "capital_allocation": ["Dividend raised.", "Buybacks resumed."],
            },
            "guidance_outlook": {
                "guidance": "NII of ~$94B expected.",
                "tone": "cautious",
                "drivers": ["Rate path.", "Deposit repricing."],
                "watch_items": ["Card charge-offs.", "CRE exposure."],
            },
        },
    }


def test_no_join_artifact_anywhere():
    md = openai_service._build_structured_markdown(_summary_with_dot_terminated_lists())
    assert ".;" not in md
    assert "; " not in md  # no residual semicolon-joined runs from any of the 8 former sites


def test_every_list_field_renders_as_bullets():
    md = openai_service._build_structured_markdown(_summary_with_dot_terminated_lists())
    # Exec key_points: one top-level bullet per point (prose headline stays prose).
    assert "- Net interest income rose to $95.4B." in md
    assert "- Noninterest income reached $87.0B." in md
    # Financials groups: label bullet + nested item bullets.
    for label, item in [
        ("Profitability", "ROE was 17%."),
        ("Cash flow", "Operating cash flow was -$147.8B."),
        ("Balance sheet", "Total assets grew to $4.6T."),
        ("Themes", "Scale advantages."),
        ("Capital allocation", "Dividend raised."),
        ("Drivers", "Rate path."),
        ("Watch items", "Card charge-offs."),
    ]:
        assert f"- {label}:" in md, label
        assert f"  - {item}" in md, item


def test_numbers_stay_substring_matchable_for_eval_scorers():
    # The eval numeric scorers are substring checks over this text — bulleting must not break them.
    md = openai_service._build_structured_markdown(_summary_with_dot_terminated_lists()).lower()
    for token in ("95.4", "87.0", "147.8", "57.0"):
        assert token in md


def test_empty_and_blank_lists_emit_no_orphan_labels():
    summary = _summary_with_dot_terminated_lists()
    summary["sections"]["financial_highlights"]["profitability"] = ["", "   "]
    summary["sections"]["management_discussion_insights"]["themes"] = []
    md = openai_service._build_structured_markdown(summary)
    assert "- Profitability:" not in md
    assert "- Themes:" not in md


def test_outlook_and_risks_emit_no_field_name_scaffolding():
    """T1.1 gate: the Outlook `Guidance:`/`Tone:` field-name prefixes and the Risks `(Evidence: …)`
    wrapper are internal scaffolding and must never reach the web summary; the underlying text (and
    any figures in it) is still rendered."""
    summary = {
        "metadata": {"company_name": "NV", "filing_type": "10-Q", "reporting_period": "Q1"},
        "sections": {
            "risk_factors": [
                {"summary": "Export controls may limit shipments.",
                 "supporting_evidence": "$1.1B in inventory provisions this quarter."},
            ],
            "guidance_outlook": {
                "guidance": "No specific quantitative guidance provided.",
                "tone": "neutral",
                "drivers": ["Rubin platform ships 2H."],
            },
        },
    }
    md = openai_service._build_structured_markdown(summary)
    assert "Guidance:" not in md          # guidance rendered as prose, not a field label
    assert "Tone:" not in md              # neutral tone suppressed, no `Tone:` scaffold
    assert "(Evidence:" not in md         # no inline evidence wrapper
    assert "No specific quantitative guidance provided." in md   # guidance text kept
    assert "$1.1B in inventory provisions this quarter." in md   # evidence figures kept


def test_non_neutral_tone_renders_as_prose_not_field_label():
    summary = {
        "metadata": {"company_name": "NV", "filing_type": "10-Q", "reporting_period": "Q1"},
        "sections": {"guidance_outlook": {"tone": "cautious"}},
    }
    md = openai_service._build_structured_markdown(summary)
    assert "Tone:" not in md
    assert "tone was cautious" in md.lower()
