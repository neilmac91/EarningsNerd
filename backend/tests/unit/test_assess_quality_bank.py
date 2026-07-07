"""P0-2 guardrail (data-quality plan): bank-aware revenue grounding in assess_quality.

Pre-fix, the verdict demanded the XBRL ``revenue`` literal in the summary text — but a bank
reports its top line as components (NII + noninterest income) and the pipeline's own grounding
NOTE forbids emitting a single "Revenue" figure, so the badge false-fired on 100% of banks.
These tests pin the three-way rule: revenue-literal OR both components grounded OR (FI filer
with no extractable components → revenue check N/A). Non-FI behavior stays byte-identical.
"""
from app.services.summary_generation_service import assess_quality


def _metrics(**overrides):
    base = {
        "revenue": {"current": {"value": 182447000000.0, "period": "FY2025"}},
        "net_income": {"current": {"value": 57048000000.0, "period": "FY2025"}},
    }
    base.update(overrides)
    return base


def _summary(text: str):
    # Coverage snapshot at the 4/9 full bar so the tier is driven purely by grounding.
    return {
        "business_overview": text,
        "financial_highlights": {},
        "raw_summary": {
            "section_coverage": {
                "per_section": {
                    "executive_snapshot": True,
                    "financial_highlights": True,
                    "risk_factors": True,
                    "guidance_outlook": True,
                }
            }
        },
    }


BANK_TEXT = "Net interest income was $95.4B and noninterest income was $87.0B; net income $57.0B."


def test_bank_with_grounded_components_is_full():
    metrics = _metrics(
        net_interest_income={"current": {"value": 95443000000.0, "period": "FY2025"}},
        noninterest_income={"current": {"value": 87004000000.0, "period": "FY2025"}},
    )
    verdict = assess_quality(_summary(BANK_TEXT), metrics)
    assert verdict["numeric_grounded"] is True
    assert verdict["tier"] == "full"
    assert verdict["reasons"] == []


def test_bank_missing_one_component_in_text_is_partial():
    metrics = _metrics(
        net_interest_income={"current": {"value": 95443000000.0, "period": "FY2025"}},
        noninterest_income={"current": {"value": 87004000000.0, "period": "FY2025"}},
    )
    text = "Net interest income was $95.4B; net income $57.0B."  # noninterest income absent
    verdict = assess_quality(_summary(text), metrics)
    assert verdict["numeric_grounded"] is False
    assert "financial figures not grounded in SEC XBRL data" in verdict["reasons"]
    assert verdict["tier"] == "partial"


def test_fi_by_sic_without_components_skips_revenue_check():
    # Flag-off world: an FI filer (SIC band) whose components were never extracted — there is no
    # fair top-line figure to demand, so only net_income grounding applies.
    metrics = _metrics()  # revenue present, no components
    text = "Net income was $57.0B on a component-reported top line."
    verdict = assess_quality(_summary(text), metrics, sic="6021")
    assert verdict["numeric_grounded"] is True
    assert verdict["tier"] == "full"


def test_fi_by_sic_net_income_still_enforced():
    metrics = _metrics()
    text = "A summary with no grounded figures at all."
    verdict = assess_quality(_summary(text), metrics, sic="6021")
    assert verdict["numeric_grounded"] is False
    assert verdict["tier"] == "partial"


def test_non_bank_behavior_unchanged():
    # No components, no FI SIC: the revenue literal is still demanded, exactly as before.
    metrics = _metrics()
    ungrounded = assess_quality(_summary("Net income was $57.0B."), metrics)
    assert ungrounded["numeric_grounded"] is False
    assert ungrounded["tier"] == "partial"
    grounded = assess_quality(_summary("Revenue was $182.4B; net income $57.0B."), metrics)
    assert grounded["numeric_grounded"] is True
    assert grounded["tier"] == "full"


def test_no_total_bank_components_grounded_is_full():
    """The majority-bank case: NO revenue total, both components tagged. The top-line check must
    verify the components (not silently skip) — a hallucinated top line here must NOT pass."""
    metrics = {
        "net_interest_income": {"current": {"value": 95443000000.0, "period": "FY2025"}},
        "noninterest_income": {"current": {"value": 87004000000.0, "period": "FY2025"}},
        "net_income": {"current": {"value": 57048000000.0, "period": "FY2025"}},
    }  # NO "revenue" key
    grounded = assess_quality(_summary(BANK_TEXT), metrics)
    assert grounded["numeric_grounded"] is True
    assert grounded["tier"] == "full"


def test_no_total_bank_hallucinated_components_is_partial():
    """Regression guard for the reviewer-confirmed gap: revenue absent must NOT be a free pass."""
    metrics = {
        "net_interest_income": {"current": {"value": 95443000000.0, "period": "FY2025"}},
        "noninterest_income": {"current": {"value": 87004000000.0, "period": "FY2025"}},
        "net_income": {"current": {"value": 57048000000.0, "period": "FY2025"}},
    }
    text = "Net interest income was $99.9B and noninterest income was $12.3B; net income $57.0B."
    verdict = assess_quality(_summary(text), metrics)
    assert verdict["numeric_grounded"] is False
    assert verdict["tier"] == "partial"


def test_bank_with_grounded_revenue_total_is_full_without_components_in_text():
    # A bank that DOES state its reported total (e.g. JPM's $182.4B) passes on the literal alone.
    metrics = _metrics(
        net_interest_income={"current": {"value": 95443000000.0, "period": "FY2025"}},
        noninterest_income={"current": {"value": 87004000000.0, "period": "FY2025"}},
    )
    verdict = assess_quality(_summary("Total revenue was $182.4B; net income $57.0B."), metrics)
    assert verdict["numeric_grounded"] is True
    assert verdict["tier"] == "full"
