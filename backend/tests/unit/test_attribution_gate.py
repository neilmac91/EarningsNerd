"""Attribution gate (the #805 path, step 4): every causal clause in a model-authored explanation slot
is measured against the excerpt the model generated from and dropped — the clause only — when armed.
Verification means the filing itself states that cause for that subject; two figures moving together
never verifies. Conservative like the quote gate: no source, no clause, malformed → untouched."""
import copy

from app.config import settings
from app.services.ai.attribution_gate import CONNECTIVE_RE, gate_attributions

FILING = (
    "Item 7. MD&A. Net operating revenues increased 12% to $12,472 million. The increase was driven by "
    "an increase in concentrate sales volume of 8%, favorable price/mix and a favorable foreign currency "
    "exchange rate impact of 3%, partially offset by increased marketing spending. Diluted weighted "
    "average shares outstanding declined to 24,391 million from 24,611 million. During the year we "
    "repurchased 220 million shares. Net income attributable to shareowners was $3,924 million. "
    "Interest income of $223.0 million mainly relates to interest income on cash and cash equivalents."
)
STATED = ("Net operating revenues rose 12% to $12.5B, driven by 8% concentrate sales volume growth, favorable "
          "price/mix and a 3% favorable foreign currency impact.")
INFERRED = "Diluted weighted average shares declined to 24,391 million from 24,611 million, reflecting share repurchases."
INFERRED_LEAD = "Interest income increased to $223.0M, primarily due to higher yields on cash balances."


def _sections(what_changed=STATED, takeaways=(INFERRED,), commentary=None, metric="Net operating revenues"):
    return {
        "the_print": {"headline": "Coca-Cola reported net operating revenues of $12.5B.",
                      "key_takeaways": list(takeaways), "what_changed": what_changed, "tone": "neutral"},
        "results_that_matter": {"table": [{"metric": metric, "current_period": "$12,472M", "prior_period": "$11,129M",
                                           "change": "+12.1%", "commentary": commentary or STATED, "supporting_evidence": ""}]},
        "earnings_quality": {"operating_vs_one_time": INFERRED_LEAD, "red_flags": []},
        "segments": [{"segment": "EMEA", "commentary": "Revenue rose, driven by volume growth in Africa."}],
        "balance_sheet_liquidity": {"leverage": "Total debt $43.9B.", "liquidity": "Cash $12.0B.",
                                    "working_capital": "Working capital rose, reflecting higher receivables.",
                                    "maturities_covenants": ["Long-term debt increased, driven by net issuances."]},
        "forward_signals": {"quotes": [{"speaker": "CEO", "quote": "Revenue rose, driven by a driver the filing never states."}]},
    }


def test_default_flag_is_off():
    assert settings.AI_ATTRIBUTION_GATE is False


def test_stated_driver_verifies_and_inferred_driver_is_measured_not_dropped_when_unarmed():
    sections = _sections()
    before = copy.deepcopy(sections)
    audit = gate_attributions(sections, FILING, armed=False)
    assert sections == before  # unarmed: nothing mutates
    assert audit["armed"] is False and audit["dropped"] == []
    slots = {u["slot"]: u for u in audit["unverified"]}
    assert "the_print.what_changed" not in slots  # the filing states this cause
    assert "results_that_matter.table[0].commentary" not in slots
    assert slots["the_print.key_takeaways[0]"]["connective"].lower() == "reflecting"  # co-movement is not cause
    assert slots["earnings_quality.operating_vs_one_time"]["clause"].startswith("higher yields")
    assert {"segments[0].commentary", "balance_sheet_liquidity.working_capital",
            "balance_sheet_liquidity.maturities_covenants[0]"} <= set(slots)
    assert audit["checked"] == audit["verified"] + len(audit["unverified"])
    assert audit["verified"] == 2


def test_armed_drops_only_the_clause_and_keeps_the_movement():
    sections = _sections()
    audit = gate_attributions(sections, FILING, armed=True)
    assert audit["armed"] is True and len(audit["dropped"]) == len(audit["unverified"]) >= 5
    assert sections["the_print"]["what_changed"] == STATED  # verified slot untouched, character for character
    assert sections["the_print"]["key_takeaways"][0] == "Diluted weighted average shares declined to 24,391 million from 24,611 million."
    assert sections["earnings_quality"]["operating_vs_one_time"] == "Interest income increased to $223.0M."
    assert sections["segments"][0]["commentary"] == "Revenue rose."
    assert sections["balance_sheet_liquidity"]["working_capital"] == "Working capital rose."
    assert sections["balance_sheet_liquidity"]["maturities_covenants"][0] == "Long-term debt increased."
    # Verbatim quotes are the quote gate's surface, never this gate's.
    assert sections["forward_signals"]["quotes"][0]["quote"].endswith("never states.")


def test_a_stated_cause_for_another_line_does_not_transfer():
    """The filing attributes the revenue increase to volume and price; applying that driver to a
    different subject (net income) is exactly the transfer the judge fails as G4."""
    sections = _sections(takeaways=("Net income rose 18%, driven by concentrate sales volume growth and favorable price/mix.",))
    audit = gate_attributions(sections, FILING, armed=False)
    assert any(u["slot"] == "the_print.key_takeaways[0]" for u in audit["unverified"])


def test_table_commentary_is_anchored_on_its_metric_not_its_framing():
    sections = _sections(commentary="Management attributes the increase to 8% concentrate sales volume growth, favorable "
                                    "price/mix and a 3% favorable foreign currency impact.")
    audit = gate_attributions(sections, FILING, armed=True)
    assert all(u["slot"] != "results_that_matter.table[0].commentary" for u in audit["unverified"])
    sections = _sections(commentary="Management attributes the increase to 8% concentrate sales volume growth.", metric="Interest income")
    audit = gate_attributions(sections, FILING, armed=False)
    assert any(u["slot"] == "results_that_matter.table[0].commentary" for u in audit["unverified"])


def test_measure_names_are_not_clauses():
    assert CONNECTIVE_RE.search("Net income attributable to shareowners was $3,924 million") is None
    assert CONNECTIVE_RE.search("Earnings attributable to controlling interests fell") is None
    assert CONNECTIVE_RE.search("The decline was attributable to lower volumes") is not None


def test_no_source_text_measures_and_drops_nothing():
    sections = _sections()
    before = copy.deepcopy(sections)
    assert gate_attributions(sections, "", armed=True) is None
    assert gate_attributions(sections, "   ", armed=True) is None
    assert sections == before


def test_slots_without_a_connective_or_malformed_values_return_none_or_pass_untouched():
    sections = {"the_print": {"headline": "Revenue rose 12%.", "key_takeaways": [None, 42], "what_changed": 7},
                "results_that_matter": {"table": ["not a row"]}, "segments": "not a list",
                "balance_sheet_liquidity": {"maturities_covenants": "not a list"}}
    before = copy.deepcopy(sections)
    assert gate_attributions(sections, FILING, armed=True) is None
    assert sections == before
    assert gate_attributions("not sections", FILING, armed=True) is None


def test_armed_drop_is_invisible_to_the_rendered_markdown():
    """Same ordering invariant as the quote gate: the gate runs on the object render reads, before
    the render, so a dropped clause never survives into the persisted markdown."""
    from app.services.summary_sections import render_sections, sections_to_markdown

    structured = {"schema_version": 2, "sections": _sections()}
    gate_attributions(structured["sections"], FILING, armed=True)
    md = sections_to_markdown(render_sections(structured))
    assert "reflecting share repurchases" not in md
    assert "higher yields on cash balances" not in md
    assert "concentrate sales volume growth" in md  # the stated driver survives
    assert "24,391 million from 24,611 million" in md  # the movement survives
