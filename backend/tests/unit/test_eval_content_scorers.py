"""Offline tests for the Tier-3.0 content-quality scorers (redundancy + prose/table delta consistency).

Deterministic — no network/AI. They prove the scorers behave on realistic canonical payloads and,
critically, do NOT false-fire on a clean summary (a level like "74.9%" is not read as a delta; a
single headline echo is free; unit-less integers like years never register as figures)."""
from evals.scorers import (
    score_delta_consistency,
    score_redundancy,
    score_summary,
)


# --- redundancy -------------------------------------------------------------------------------


def test_redundancy_is_perfect_when_no_figure_is_restated():
    payload = {
        "executive_summary": "Revenue rose 85% to $81.6B on data-center demand.",
        "management_discussion": "Management cited operating leverage and disciplined spend.",
        "outlook": "Guidance points to continued sequential growth.",
    }
    assert score_redundancy(payload) == (1.0, [])


def test_redundancy_allows_one_sanctioned_headline_echo():
    # $81.6B in exec + mgmt = one restatement (the headline echo the exec summary is entitled to).
    payload = {
        "executive_summary": "Revenue was $81.6B.",
        "management_discussion": "Revenue of $81.6B was driven by AI.",
        "outlook": "Momentum continues.",
    }
    score, _ = score_redundancy(payload)
    assert score == 1.0


def test_redundancy_penalises_figures_restated_across_sections():
    payload = {
        "executive_summary": "Revenue $81.6B, net income $32B, margin 74.9%.",
        "management_discussion": "Revenue $81.6B and net income $32B; margin 74.9%.",
        "outlook": "We expect an $81.6B run-rate.",
    }
    score, details = score_redundancy(payload)
    assert score < 1.0
    assert any("81.6b" in d for d in details)


def test_redundancy_ignores_unitless_numbers_like_years_and_counts():
    payload = {
        "executive_summary": "In 2024 the company had 3 segments and 12 products.",
        "management_discussion": "By 2024 it operated 3 segments across 12 products.",
        "outlook": "",
    }
    assert score_redundancy(payload) == (1.0, [])


def test_redundancy_normalizes_scale_words_and_symbols():
    # "$81.6 billion" and "$81.6B" are the SAME figure — restated across three sections.
    payload = {
        "executive_summary": "Revenue of $81.6 billion.",
        "management_discussion": "Revenue reached $81.6B.",
        "outlook": "A record $81.6 billion top line.",
    }
    score, details = score_redundancy(payload)
    assert details == ["figure restated across sections: 81.6b"]
    # A figure smeared across ALL THREE sections restates twice; one echo is free, so it is penalised.
    assert score == 0.75


def test_redundancy_penalises_a_single_figure_across_all_three_sections():
    # Regression guard: one figure in exec + MD&A + outlook must NOT score a perfect 1.0.
    payload = {
        "executive_summary": "Revenue was $81.6B.",
        "management_discussion": "Revenue of $81.6B recurred.",
        "outlook": "Guidance implies $81.6B again.",
    }
    score, _ = score_redundancy(payload)
    assert score < 1.0


# --- delta consistency ------------------------------------------------------------------------


def _fh(rows):
    return {"financial_highlights": {"table": rows}}


def test_delta_consistency_perfect_when_prose_matches_table():
    payload = {
        "executive_summary": "Revenue surged 85% and net income grew 210% year over year.",
        "management_discussion": "Gross margin expanded to 74.9%.",
        "outlook": "",
        **_fh([
            {"metric": "Revenue", "change_display": "+85.0%"},
            {"metric": "Net Income", "change_display": "+210.6%"},
            {"metric": "Gross Margin", "change_display": "+14.4 ppts"},
        ]),
    }
    assert score_delta_consistency(payload) == (1.0, [])


def test_delta_consistency_does_not_read_a_level_as_a_delta():
    # "gross margin of 74.9%" is a LEVEL (no direction cue) and revenue's change is not quantified
    # in the prose → there is nothing to contradict, so the score stays 1.0.
    payload = {
        "executive_summary": "Revenue set a record; gross margin of 74.9% reflected scale.",
        "management_discussion": "",
        "outlook": "",
        **_fh([{"metric": "Revenue", "change_display": "+85.0%"}]),
    }
    assert score_delta_consistency(payload) == (1.0, [])


def test_delta_consistency_flags_a_contradicting_prose_delta():
    payload = {
        "executive_summary": "Revenue jumped 92% this quarter.",
        "management_discussion": "",
        "outlook": "",
        **_fh([{"metric": "Revenue", "change_display": "+85.0%"}]),
    }
    score, details = score_delta_consistency(payload)
    assert score == 0.0
    assert details and "Revenue" in details[0]


def test_delta_consistency_skips_ppt_rows():
    # A margin's ppt delta is not comparable to a relative % in prose — never compared, never flagged.
    payload = {
        "executive_summary": "Gross margin improved 14 percentage points; it also rose 24% relative.",
        "management_discussion": "",
        "outlook": "",
        **_fh([{"metric": "Gross Margin", "change_display": "+14.4 ppts"}]),
    }
    assert score_delta_consistency(payload) == (1.0, [])


def test_delta_consistency_no_table_is_not_penalised():
    assert score_delta_consistency({"executive_summary": "Revenue up 85%."}) == (1.0, [])


def test_delta_consistency_matches_metric_names_on_word_boundaries():
    # Regression guard: metric "EPS" must not match inside "steps" and pull the unrelated "5%" into
    # scope — that would be a false contradiction against the table's EPS change.
    payload = {
        "executive_summary": "Management took steps to lift margins by 5%.",
        "management_discussion": "",
        "outlook": "",
        **_fh([{"metric": "EPS", "change_display": "+40.0%"}]),
    }
    assert score_delta_consistency(payload) == (1.0, [])


# --- integration ------------------------------------------------------------------------------


def test_score_summary_carries_the_new_dimensions():
    payload = {
        "executive_summary": "Revenue surged 85% to $81.6B.",
        "financial_highlights": {"table": [{"metric": "Revenue", "change_display": "+85.0%"}]},
        "risk_factors": [],
        "management_discussion": "Operating leverage improved.",
        "outlook": "Sequential growth expected.",
    }
    score = score_summary(payload, [])
    assert score.redundancy == 1.0
    assert score.delta_consistency == 1.0


def test_score_summary_reflects_contradiction_and_redundancy():
    payload = {
        "executive_summary": "Revenue jumped 92% to $81.6B; net income $32B.",
        "financial_highlights": {"table": [{"metric": "Revenue", "change_display": "+85.0%"}]},
        "risk_factors": [],
        "management_discussion": "Revenue of $81.6B and net income $32B repeated here.",
        "outlook": "An $81.6B and $32B outlook.",
    }
    score = score_summary(payload, [])
    assert score.delta_consistency == 0.0   # prose "92%" contradicts table "85.0%"
    assert score.redundancy < 1.0           # $81.6B and $32B restated across sections
