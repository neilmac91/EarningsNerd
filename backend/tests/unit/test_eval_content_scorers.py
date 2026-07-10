"""Offline tests for the Tier-3.0 content-quality scorers (redundancy + prose/table delta consistency).

Deterministic — no network/AI. They prove the scorers behave on realistic canonical payloads and,
critically, do NOT false-fire on a clean summary (a level like "74.9%" is not read as a delta; a
single headline echo is free; unit-less integers like years never register as figures)."""
from evals.scorers import (
    _figure_keys,
    score_delta_consistency,
    score_forward_quote_fidelity,
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
    # A figure smeared across ALL THREE sections restates twice; one echo is free, so it is penalised
    # (1 − (2−1)/3 = 0.6667).
    assert score == 0.6667


def test_redundancy_penalises_a_single_figure_across_all_three_sections():
    # Regression guard: one figure in exec + MD&A + outlook must NOT score a perfect 1.0.
    payload = {
        "executive_summary": "Revenue was $81.6B.",
        "management_discussion": "Revenue of $81.6B recurred.",
        "outlook": "Guidance implies $81.6B again.",
    }
    score, _ = score_redundancy(payload)
    assert score < 1.0


def test_redundancy_parses_rendered_markdown_and_excludes_the_table_home():
    # The production pipeline maps the full rendered markdown into executive_summary. The scorer must
    # split on the ## headings and measure restatement across the PROSE sections, excluding the
    # table-bearing "home" section — NOT compare the flattened blob against sub-fields (a tautology).
    md = "\n".join([
        "## Executive Assessment", "Revenue was $81.6B on data-center demand.", "",
        "## Financial Highlights", "| Metric | Value |", "| --- | --- |", "| Revenue | $81.6B |", "",
        "## Management Strategy & Execution", "Revenue of $81.6B reflects AI leadership.", "",
        "## Forward Outlook", "An $81.6B run-rate looks durable.",
    ])
    payload = {"executive_summary": md, "management_discussion": "", "outlook": ""}
    score, reasons = score_redundancy(payload)
    # $81.6B appears in THREE prose sections (the Financial Highlights table copy is excluded as the
    # home) → beyond the one free echo → penalised.
    assert reasons == ["figure restated across sections: 81.6b"]
    assert score < 1.0


def test_redundancy_excludes_table_homes_with_alignment_colons():
    # GFM alignment delimiters (| :--- |, | ---: |) must still be recognised as a table home, else
    # the table's figures get miscounted as narrative restatement.
    md = "\n".join([
        "## Executive Assessment", "Revenue reached a record.", "",
        "## Financial Highlights", "| Metric | Value |", "| :--- | ---: |", "| Revenue | $81.6B |",
    ])
    payload = {"executive_summary": md, "management_discussion": "", "outlook": ""}
    # $81.6B lives only in the (aligned) table home → no narrative restatement.
    assert score_redundancy(payload) == (1.0, [])


def test_redundancy_markdown_mode_is_clean_when_each_figure_has_one_home():
    md = "\n".join([
        "## Executive Assessment", "Revenue rose to a record on AI demand.", "",
        "## Financial Highlights", "| Metric | Value |", "| --- | --- |", "| Revenue | $81.6B |", "",
        "## Management Strategy & Execution", "Management cited operating leverage and buybacks.", "",
        "## Forward Outlook", "Guidance implies continued sequential growth.",
    ])
    payload = {"executive_summary": md, "management_discussion": "", "outlook": ""}
    assert score_redundancy(payload) == (1.0, [])


def test_figure_keys_ignore_period_boilerplate():
    # Regression guard: the single-letter "m" suffix must not swallow the "m" of "months", so
    # "3 months" / "12 months" register NO figure — otherwise 10-Q period boilerplate would read as
    # $3M / $12M and pollute the redundancy dimension across every section that repeats it.
    assert _figure_keys("For the 3 months ended March 31, revenue was $44.1 billion.") == {"44.1b"}
    assert _figure_keys("For the trailing 12 months and the 3 months ended.") == set()
    # …but a genuine scaled figure at a sentence end still registers.
    assert "44.1b" in _figure_keys("Revenue was $44.1B.")
    assert "3m" in _figure_keys("A one-time charge of $3 million.")


def test_redundancy_is_unpolluted_by_period_boilerplate():
    payload = {
        "executive_summary": "For the 3 months ended March 31, revenue rose sharply.",
        "management_discussion": "For the 3 months ended, margins held firm.",
        "outlook": "",
    }
    assert score_redundancy(payload) == (1.0, [])


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


def test_delta_consistency_does_not_read_a_hyphenated_range_as_a_delta():
    # Regression guard: a range hyphen ("8-10%") is not a minus cue, so a scanned section quoting a
    # range near a metric is not a contradiction.
    payload = {
        "executive_summary": "",
        "management_discussion": "Revenue rose 8-10% across the segment mix.",
        "outlook": "",
        **_fh([{"metric": "Revenue", "change_display": "+69.2%"}]),
    }
    assert score_delta_consistency(payload) == (1.0, [])


def test_delta_consistency_ignores_forward_guidance_in_outlook():
    # Founder repro: outlook is forward guidance, not the reported period's delta, so it is not
    # scanned — "guided revenue to grow 8-10%" is never compared to the table's historical +69.2%.
    payload = {
        "executive_summary": "Revenue grew to $44.1 billion.",
        "management_discussion": "",
        "outlook": "Management guided revenue to grow 8-10% next quarter.",
        **_fh([{"metric": "Revenue", "change_display": "+69.2%"}]),
    }
    assert score_delta_consistency(payload) == (1.0, [])


def test_delta_consistency_still_flags_a_reported_period_contradiction_in_prose():
    # The outlook exclusion must not blind the scorer to a real contradiction in exec/MD&A.
    payload = {
        "executive_summary": "Revenue jumped 40% this quarter.",
        "management_discussion": "",
        "outlook": "Revenue up 40% expected next year.",  # forward guidance — ignored
        **_fh([{"metric": "Revenue", "change_display": "+69.2%"}]),
    }
    score, details = score_delta_consistency(payload)
    assert score == 0.0 and "Revenue" in details[0]


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


# --- canaries: each scorer must be able to FIRE on a PRODUCTION-shaped payload -----------------
# The production pipeline maps the fully rendered markdown (metrics table INSIDE executive_summary)
# into the payload. A scorer that structurally cannot fire on that shape is a dead instrument — both
# content scorers had a mirror-image tautology there (redundancy toward 0.0, delta toward 1.0). These
# assert the OPPOSITE of the usual "clean input scores 1.0": that a genuine defect is caught on the
# real shape, so a future refactor can't silently re-break the instrument before it binds at re-pin.

_TABLE_MD = "\n".join([
    "## Financial Highlights",
    "| Metric | Current | Prior | Change | Note |",
    "| --- | --- | --- | --- | --- |",
    "| Revenue | $44.1B | $26.0B | +69.2% | data-center |",
])


def test_canary_redundancy_fires_on_production_markdown():
    md = "\n".join([
        "## Executive Assessment", "Revenue was $44.1B on AI demand.", "",
        _TABLE_MD, "",
        "## Management Strategy & Execution", "Revenue of $44.1B recurred across lines.", "",
        "## 3-Year Investment Perspective", "The $44.1B print caps three years of growth.",
    ])
    payload = {"executive_summary": md, "management_discussion": "", "outlook": "",
               **_fh([{"metric": "Revenue", "change_display": "+69.2%"}])}
    score, reasons = score_redundancy(payload)
    # $44.1B restated across THREE prose sections (the table copy is excluded) → must fire.
    assert score < 1.0 and reasons == ["figure restated across sections: 44.1b"]


def test_canary_delta_consistency_fires_on_production_markdown():
    # Founder A/B: an identical prose-vs-table contradiction must be flagged in the production
    # markdown shape (table inside the blob) exactly as in the fields shape — the rendered table's
    # own change cell must NOT self-satisfy the proximity check.
    md = "\n".join(["## Executive Assessment", "Revenue surged 92% on AI demand.", "", _TABLE_MD])
    markdown_payload = {"executive_summary": md, "management_discussion": "", "outlook": "",
                        **_fh([{"metric": "Revenue", "change_display": "+69.2%"}])}
    fields_payload = {"executive_summary": "Revenue surged 92% on AI demand.",
                      "management_discussion": "", "outlook": "",
                      **_fh([{"metric": "Revenue", "change_display": "+69.2%"}])}
    md_result = score_delta_consistency(markdown_payload)
    fields_result = score_delta_consistency(fields_payload)
    assert md_result[0] == 0.0 and "Revenue" in md_result[1][0]   # production shape now FIRES
    assert md_result == fields_result                             # both shapes agree (A/B)


# --- forward-quote verbatim fidelity (T5.4) -----------------------------------------------------

FILING_TEXT = (
    "Item 7. MD&A - Outlook. Management stated: “We believe demand for our accelerated computing "
    "platforms will continue to outpace supply through the first half of next year.” Our board "
    "declared the company’s largest-ever repurchase authorization — $110 billion."
)
_REAL_QUOTE = ("We believe demand for our accelerated computing platforms will continue to "
               "outpace supply through the first half of next year.")
_FAKE_QUOTE = "We are confident revenue will double next year and margins will expand dramatically."


def _forward_md(*quotes):
    lines = ["## The Print", "A quarter of records.", "", "## Forward Signals",
             "Guidance maintained for fiscal 2027.", ""]
    lines += [f'> "{q}" — CFO' for q in quotes]
    return "\n".join(lines)


def test_forward_quote_fidelity_perfect_when_all_quotes_verify():
    # Typography drift included: the model types straight punctuation, the filing typesets curly.
    payload = {"executive_summary": _forward_md(_REAL_QUOTE,
               "the company's largest-ever repurchase authorization - $110 billion")}
    assert score_forward_quote_fidelity(payload, FILING_TEXT) == (1.0, [])


def test_forward_quote_fidelity_flags_fabrication_with_score():
    payload = {"executive_summary": _forward_md(_REAL_QUOTE, _FAKE_QUOTE)}
    score, violations = score_forward_quote_fidelity(payload, FILING_TEXT)
    assert score == 0.5
    assert len(violations) == 1 and "no counterpart" in violations[0]


def test_forward_quote_fidelity_labels_near_miss():
    # One word changed ("first" -> "second"): a close counterpart exists in the filing.
    near = _REAL_QUOTE.replace("first half", "second half")
    payload = {"executive_summary": _forward_md(near)}
    score, violations = score_forward_quote_fidelity(payload, FILING_TEXT)
    assert score == 0.0 and "near-miss" in violations[0]


def test_forward_quote_fidelity_ignores_quotes_outside_forward_sections():
    # Only the forward/outlook section's blockquotes are schema-contracted verbatim quotes.
    md = "\n".join(["## The Print", f'> "{_FAKE_QUOTE}" — CEO', "", "## Forward Signals",
                    "Guidance maintained."])
    assert score_forward_quote_fidelity({"executive_summary": md}, FILING_TEXT) == (1.0, [])


def test_forward_quote_fidelity_neutral_without_referent_markdown_or_quotes():
    quoted = {"executive_summary": _forward_md(_FAKE_QUOTE)}
    assert score_forward_quote_fidelity(quoted, None) == (1.0, [])       # no filing text
    assert score_forward_quote_fidelity(quoted, "") == (1.0, [])
    flat = {"executive_summary": "No markdown headings here.", "outlook": "Guidance maintained."}
    assert score_forward_quote_fidelity(flat, FILING_TEXT) == (1.0, [])  # no rendered markdown
    no_quotes = {"executive_summary": _forward_md()}
    assert score_forward_quote_fidelity(no_quotes, FILING_TEXT) == (1.0, [])
    short = {"executive_summary": _forward_md("We expect growth.")}     # under the shared floor
    assert score_forward_quote_fidelity(short, FILING_TEXT) == (1.0, [])


def test_forward_quote_fidelity_rides_score_summary_only_when_text_provided():
    payload = {"executive_summary": _forward_md(_FAKE_QUOTE), "management_discussion": "m",
               "outlook": "Guidance maintained.", "financial_highlights": {"revenue": "$1B"},
               "risk_factors": [{"text": "Concentration risk remains material."}]}
    without = score_summary(payload, [])
    assert without.forward_quote_fidelity == 1.0                         # neutral default
    with_text = score_summary(payload, [], filing_text=FILING_TEXT)
    assert with_text.forward_quote_fidelity == 0.0                       # measured when threaded


def test_forward_quote_fidelity_accepts_curly_blockquote_delimiters():
    # Production renders straight delimiters, but a candidate's own markdown may typeset curly
    # ones (Gemini on #623) — the line must MEASURE, not read falsely neutral.
    md = "\n".join(["## The Print", "Records.", "", "## Forward Signals",
                    f"> “{_FAKE_QUOTE}” — CEO"])
    score, violations = score_forward_quote_fidelity({"executive_summary": md}, FILING_TEXT)
    assert score == 0.0 and len(violations) == 1
