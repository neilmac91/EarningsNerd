"""Offline tests for the eval harness scorers (roadmap S3).

These are deterministic and need no network/AI, so they prove the harness's scoring logic is
correct independent of any model run."""
import json

import pytest

from evals.schema import GroundTruthFact
from evals.scorers import (
    detect_hygiene_violations,
    parse_model_json,
    score_coverage,
    score_currency_consistency,
    score_financial_depth,
    score_numeric_accuracy,
    score_numeric_precision,
    score_specificity,
    score_summary,
    validate_schema,
)

# Apple FY2023-ish figures used as fixtures (values, not claims about a specific filing).
REVENUE = GroundTruthFact(metric="revenue", value=383_285_000_000.0, unit="USD")
NET_INCOME = GroundTruthFact(metric="net_income", value=96_995_000_000.0, unit="USD")
EPS = GroundTruthFact(metric="eps", value=6.13, unit="USD_per_share")


@pytest.mark.parametrize(
    "text",
    [
        "Revenue was $383.3 billion this year.",
        "Total revenue of 383,285 (in millions).",
        "revenue reached 383.285 billion dollars",
        "FY revenue: 383285000000",
    ],
)
def test_numeric_accuracy_matches_common_renderings(text):
    recall, matched, missing = score_numeric_accuracy(text, [REVENUE])
    assert recall == 1.0
    assert matched == ["revenue"]
    assert missing == []


def test_numeric_accuracy_partial_and_eps():
    text = "Revenue was $383.3B and diluted EPS of $6.13."
    recall, matched, missing = score_numeric_accuracy(text, [REVENUE, NET_INCOME, EPS])
    assert "revenue" in matched and "eps" in matched
    assert "net_income" in missing
    assert recall == pytest.approx(2 / 3, abs=1e-3)


def test_numeric_accuracy_no_ground_truth_is_not_penalized():
    recall, matched, missing = score_numeric_accuracy("anything", [])
    assert recall == 1.0


def test_validate_schema_accepts_canonical_shape():
    payload = {
        "executive_summary": "x",
        "financial_highlights": {"revenue": "1", "net_income": "2", "eps": "3", "key_metrics": []},
        "risk_factors": [],
        "management_discussion": "y",
        "outlook": "z",
    }
    valid, problems = validate_schema(payload)
    assert valid and problems == []


def test_validate_schema_flags_missing_keys_and_bad_types():
    valid, problems = validate_schema({"executive_summary": "x", "financial_highlights": []})
    assert not valid
    assert any("financial_highlights is not an object" in p for p in problems)
    assert any("missing key" in p for p in problems)


def test_validate_schema_accepts_production_financial_highlights_shape():
    # The production pipeline emits financial_highlights as a metric table + bullet lists, NOT the
    # flat revenue/net_income/eps fields. That shape is well-formed and must score schema_valid.
    payload = {
        "executive_summary": "Record services quarter.",
        "financial_highlights": {
            "table": [{"metric": "Revenue", "current_period": "$383B", "prior_period": "$394B",
                       "change": "-2.8%", "commentary": "Services offset iPhone."}],
            "profitability": ["Gross margin 44%"],
            "cash_flow": ["Operating cash flow $110B"],
            "balance_sheet": ["Total assets $352B"],
        },
        "risk_factors": ["Concentration risk."],
        "management_discussion": "Margin expansion on mix.",
        "outlook": "Continued momentum.",
    }
    valid, problems = validate_schema(payload)
    assert valid and problems == []


def test_validate_schema_rejects_empty_financial_highlights():
    # An empty object matches neither shape — still invalid (the guard isn't gutted).
    payload = {
        "executive_summary": "x", "financial_highlights": {},
        "risk_factors": [], "management_discussion": "y", "outlook": "z",
    }
    valid, problems = validate_schema(payload)
    assert not valid
    assert any("financial_highlights missing" in p for p in problems)


def test_validate_schema_accepts_structured_but_empty_production_shape():
    # Production keys PRESENT but empty is structurally valid — emptiness is coverage's concern, not
    # schema validity's. (Identify the shape by key presence, not truthiness.)
    payload = {
        "executive_summary": "x",
        "financial_highlights": {"table": [], "profitability": [], "cash_flow": [], "balance_sheet": []},
        "risk_factors": [], "management_discussion": "y", "outlook": "z",
    }
    valid, problems = validate_schema(payload)
    assert valid and problems == []


def test_parse_model_json_clean_vs_fenced_vs_garbage():
    payload, repaired = parse_model_json('{"a": 1}')
    assert payload == {"a": 1} and repaired is False

    payload, repaired = parse_model_json('```json\n{"a": 1}\n```')
    assert payload == {"a": 1} and repaired is True

    payload, repaired = parse_model_json("not json at all")
    assert payload is None and repaired is True


def test_coverage_ignores_placeholders():
    payload = {
        "executive_summary": "A detailed multi-sentence overview of the business and results.",
        "financial_highlights": {"revenue": "Not disclosed", "net_income": "N/A", "eps": "n/a", "key_metrics": []},
        "risk_factors": ["A substantive risk about supply chain concentration and tariffs."],
        "management_discussion": "short",  # too short → not substantive
        "outlook": "Management expects mid-single-digit revenue growth next fiscal year.",
    }
    ratio, missing = score_coverage(payload)
    assert "financial_highlights" in missing  # all placeholder values
    assert "management_discussion" in missing  # under length threshold
    assert "executive_summary" not in missing
    assert ratio == pytest.approx(3 / 5)


def test_score_summary_good_beats_bad_aggregate():
    good = json.dumps({
        "executive_summary": "Apple posted record results driven by Services growth and strong iPhone demand.",
        "financial_highlights": {"revenue": "$383.3 billion", "net_income": "$96.995 billion",
                                 "eps": "$6.13", "key_metrics": ["Services revenue up double digits"]},
        "risk_factors": ["Concentration in iPhone revenue exposes results to demand swings."],
        "management_discussion": "Management cited gross-margin expansion and disciplined opex control.",
        "outlook": "The company expects continued Services momentum and steady capital returns.",
    })
    bad = json.dumps({
        "executive_summary": "short",
        "financial_highlights": {"revenue": "Not disclosed", "net_income": "N/A", "eps": "n/a", "key_metrics": []},
        "risk_factors": [],
        "management_discussion": "n/a",
        "outlook": "pending",
    })
    gt = [REVENUE, NET_INCOME, EPS]
    good_score = score_summary(good, gt)
    bad_score = score_summary(bad, gt)

    assert good_score.schema_valid and not good_score.repaired
    assert good_score.numeric_accuracy == 1.0
    assert good_score.aggregate() > bad_score.aggregate()
    assert bad_score.numeric_accuracy == 0.0


def test_score_summary_unparseable_is_zero_floor():
    score = score_summary("totally not json", [REVENUE])
    assert score.schema_valid is False
    assert score.aggregate() == 0.0
    assert score.passed_gates is False  # unparseable output is a hard-gate veto


# ---------------------------------------------------------------------------
# Artifact-1 hard gates: numeric precision (G1) and output hygiene (G4)
# ---------------------------------------------------------------------------
def _payload(**overrides):
    base = {
        "executive_summary": "A detailed multi-sentence overview of the business and its results.",
        "financial_highlights": {"revenue": "$383.3 billion", "net_income": "$96.995 billion",
                                 "eps": "$6.13", "key_metrics": ["Services revenue up double digits"]},
        "risk_factors": ["Concentration in iPhone revenue exposes results to demand swings."],
        "management_discussion": "Management cited gross-margin expansion and disciplined opex control.",
        "outlook": "The company expects continued Services momentum and steady capital returns.",
    }
    base.update(overrides)
    return base


def test_numeric_precision_perfect_when_labeled_fields_match():
    precision, contradictions = score_numeric_precision(_payload(), [REVENUE, NET_INCOME, EPS])
    assert precision == 1.0 and contradictions == []


def test_numeric_precision_catches_wrong_revenue_recall_would_miss():
    # Wrong number in the labeled revenue field, but the correct one appears in prose — recall is
    # fooled, precision is not. This is the recall-only gap the hard gate closes.
    fh = {"revenue": "$999.9 billion", "net_income": "$96.995 billion", "eps": "$6.13",
          "key_metrics": []}
    payload = _payload(financial_highlights=fh,
                       executive_summary="Revenue was $383.3 billion, a record year for the company.")
    recall, _, _ = score_numeric_accuracy(__import__("json").dumps(fh) + " Revenue was $383.3 billion",
                                          [REVENUE])
    precision, contradictions = score_numeric_precision(payload, [REVENUE])
    assert recall == 1.0  # the correct figure is present somewhere
    assert precision == 0.0 and any("revenue" in c for c in contradictions)


def test_numeric_precision_absent_value_is_not_a_contradiction():
    fh = {"revenue": "Not disclosed", "net_income": "$96.995 billion", "eps": "$6.13",
          "key_metrics": []}
    precision, contradictions = score_numeric_precision(_payload(financial_highlights=fh),
                                                        [REVENUE, NET_INCOME, EPS])
    assert precision == 1.0 and contradictions == []  # absent → coverage's concern, not G1


def test_hygiene_detects_leaked_notices_and_placeholders():
    payload = _payload(
        executive_summary="As an AI language model, I cannot provide financial advice. TODO: fill in.",
        outlook="[insert outlook here]",
    )
    violations = detect_hygiene_violations(payload)
    assert any("as an ai" in v for v in violations)
    assert any("executive_summary" in v for v in violations)
    assert any("outlook" in v for v in violations)


def test_score_summary_sets_gate_failures_and_veto():
    import json as _json
    wrong = _payload(financial_highlights={"revenue": "$999.9 billion", "net_income": "$96.995 billion",
                                            "eps": "$6.13", "key_metrics": []})
    score = score_summary(_json.dumps(wrong), [REVENUE, NET_INCOME, EPS])
    assert score.passed_gates is False
    assert any(f.startswith("G1") for f in score.gate_failures)


def test_score_summary_clean_passes_gates():
    import json as _json
    score = score_summary(_json.dumps(_payload()), [REVENUE, NET_INCOME, EPS])
    assert score.passed_gates is True
    assert score.gate_failures == []
    assert score.numeric_precision == 1.0


# Sign fidelity: a loss reported as a profit must fail G1 even though abs-value renderings match.
NET_LOSS = GroundTruthFact(metric="net_income", value=-1_200_000_000.0, unit="USD")


def test_sign_flip_loss_reported_as_profit_is_a_contradiction():
    fh = {"revenue": "$383.3 billion", "net_income": "$1.2 billion",  # positive, but truth is a loss
          "eps": "$6.13", "key_metrics": []}
    precision, contradictions = score_numeric_precision(_payload(financial_highlights=fh), [NET_LOSS])
    assert precision == 0.0 and any("sign mismatch" in c for c in contradictions)


def test_loss_reported_as_loss_passes():
    for phrasing in ("net loss of $1.2 billion", "$(1.2) billion", "-$1.2 billion"):
        fh = {"revenue": "$383.3 billion", "net_income": phrasing, "eps": "$6.13", "key_metrics": []}
        precision, contradictions = score_numeric_precision(_payload(financial_highlights=fh), [NET_LOSS])
        assert precision == 1.0 and contradictions == [], phrasing


def test_profit_reported_as_loss_is_a_contradiction():
    fh = {"revenue": "$383.3 billion", "net_income": "net loss of $96.995 billion",
          "eps": "$6.13", "key_metrics": []}
    precision, contradictions = score_numeric_precision(_payload(financial_highlights=fh), [NET_INCOME])
    assert precision == 0.0 and any("sign mismatch" in c for c in contradictions)


# ---------------------------------------------------------------------------
# Alt-value matching: EPS basic vs diluted (a correct figure must not score as a miss)
# ---------------------------------------------------------------------------
EPS_BASIC_WITH_DILUTED_ALT = GroundTruthFact(
    metric="eps", value=2.40, unit="USD_per_share", alt_values=[2.39]
)


def test_recall_matches_diluted_eps_via_alt_value():
    # Output quotes diluted EPS ($2.39); ground truth's primary is basic ($2.40). With the diluted
    # value as an alt, this is a match, not a miss.
    recall, matched, missing = score_numeric_accuracy(
        "Diluted EPS: $2.39 vs $0.76.", [EPS_BASIC_WITH_DILUTED_ALT]
    )
    assert recall == 1.0 and matched == ["eps"] and missing == []


def test_recall_still_matches_basic_when_alt_present():
    recall, _, _ = score_numeric_accuracy("EPS of $2.40.", [EPS_BASIC_WITH_DILUTED_ALT])
    assert recall == 1.0


def test_recall_misses_when_neither_basic_nor_diluted_present():
    recall, matched, missing = score_numeric_accuracy(
        "EPS of $9.99.", [EPS_BASIC_WITH_DILUTED_ALT]
    )
    assert recall == 0.0 and missing == ["eps"]


def test_precision_accepts_diluted_eps_in_labeled_field_via_alt():
    fh = {"revenue": "$383.3 billion", "net_income": "$96.995 billion",
          "eps": "$2.39 (diluted)", "key_metrics": []}
    precision, contradictions = score_numeric_precision(
        _payload(financial_highlights=fh), [REVENUE, NET_INCOME, EPS_BASIC_WITH_DILUTED_ALT]
    )
    assert precision == 1.0 and contradictions == []


def test_alt_values_default_empty_is_backward_compatible():
    # A fact with no alts behaves exactly as before.
    plain = GroundTruthFact(metric="eps", value=6.13, unit="USD_per_share")
    recall, _, _ = score_numeric_accuracy("EPS $6.13.", [plain])
    assert recall == 1.0


def test_alt_values_none_does_not_crash():
    # A malformed fact (alt_values=None, e.g. JSON null) must not raise.
    none_alt = GroundTruthFact(metric="eps", value=6.13, unit="USD_per_share", alt_values=None)
    recall, _, _ = score_numeric_accuracy("EPS $6.13.", [none_alt])
    assert recall == 1.0


def test_financial_depth_rewards_cash_flow_balance_sheet_and_margins():
    """A deep financial section (P1.1 output) scores 1.0 across all three categories."""
    payload = {
        "executive_summary": "Solid year.",
        "financial_highlights": {
            "revenue": "$416.2B",
            "key_metrics": [
                "Operating cash flow $111.5B; free cash flow $98.8B",
                "Total assets $359.2B; long-term debt $98.7B; shareholders' equity $73.7B",
                "Gross margin 46.9%; operating margin 32.0%",
            ],
        },
        "management_discussion": "",
        "outlook": "",
    }
    depth, missing = score_financial_depth(payload)
    assert depth == 1.0
    assert missing == []


def test_financial_depth_ignores_placeholders_and_bare_terms():
    """'cash flow not disclosed' (placeholder) and a term with no number do NOT score depth."""
    payload = {
        "executive_summary": "Revenue was $416.2B.",
        "financial_highlights": {
            "revenue": "$416.2B",
            "key_metrics": [
                "Cash flow not disclosed in the provided excerpts",
                "Balance sheet figures were not captured",
            ],
        },
        "management_discussion": "Margins discussed qualitatively.",
        "outlook": "",
    }
    depth, missing = score_financial_depth(payload)
    assert depth == 0.0
    assert set(missing) == {"cash_flow", "balance_sheet", "margins"}


# --- narrative specificity (Wave 2 anti-boilerplate) -----------------------------------------

def _specificity_payload(exec_summary="", mgmt="", outlook=""):
    return {"executive_summary": exec_summary, "management_discussion": mgmt, "outlook": outlook}


def test_specificity_clean_concrete_prose_scores_high():
    """Concrete prose with explicit period-over-period framing and no filler scores ~1.0."""
    payload = _specificity_payload(
        exec_summary=(
            "Revenue rose 14% to $42.3B, up from $37.1B a year ago, driven by a 9% increase in "
            "datacenter units. Operating margin expanded 230bps to 31% as input costs fell from "
            "the prior year. Diluted EPS of $3.45 grew faster than net income on buyback-reduced "
            "share count."
        ),
    )
    score, flagged = score_specificity(payload)
    assert score >= 0.95
    assert flagged == []


def test_specificity_penalizes_boilerplate_filler():
    """Vague filler drags the score well below a clean summary's."""
    payload = _specificity_payload(
        exec_summary=(
            "The company remains well-positioned to navigate the challenging environment. "
            "Management is focused on execution and market conditions, with continued growth and "
            "solid performance expected going forward as it drives long-term value in a dynamic "
            "market and competitive landscape."
        ),
    )
    score, flagged = score_specificity(payload)
    assert score < 0.6
    assert "well-positioned" in flagged and "going forward" in flagged


def test_specificity_short_prose_is_not_penalized():
    score, flagged = score_specificity(_specificity_payload(exec_summary="Strong quarter."))
    assert score == 1.0
    assert flagged == []


def test_specificity_missing_change_language_costs_the_change_component():
    """Clean (no boilerplate) but static prose with no comparative framing loses the 0.2 change
    component → ~0.8, while the same prose with YoY framing scores ~1.0."""
    static = _specificity_payload(
        mgmt=(
            "The datacenter segment generated $20.1B of revenue and the gaming segment $9.4B. "
            "Gross margin was 31% and the company repurchased $4.0B of stock during the period "
            "across its three reportable segments and two geographies as disclosed."
        ),
    )
    score_static, _ = score_specificity(static)
    # No boilerplate (component 1.0) but no comparative framing (component 0.6): 0.8 + 0.2*0.6.
    assert 0.90 <= score_static <= 0.93

    changed = _specificity_payload(
        mgmt=static["management_discussion"] + " Datacenter revenue increased from $14.5B YoY.",
    )
    score_changed, _ = score_specificity(changed)
    assert score_changed > score_static


def test_score_summary_exposes_specificity_and_keeps_it_out_of_aggregate():
    """specificity is reported on the RubricScore but, like financial_depth, not folded into the
    aggregate (so the adoption math is unchanged)."""
    clean = {
        "executive_summary": "Revenue rose 14% to $42.3B, up from $37.1B in the prior year.",
        "financial_highlights": {"revenue": "$42.3B", "net_income": "$9.6B", "eps": "$3.45",
                                 "key_metrics": []},
        "risk_factors": [], "management_discussion": "Datacenter drove the increase from $14.5B YoY.",
        "outlook": "Guidance raised compared to the prior quarter.",
    }
    boiler = dict(clean)
    boiler["executive_summary"] = (
        "The company remains well-positioned to navigate the challenging environment, focused on "
        "execution and market conditions with continued growth and solid performance going forward."
    )
    boiler["management_discussion"] = "Long-term value in a dynamic market and competitive landscape."
    boiler["outlook"] = "Consistent with prior; no material change."

    s_clean = score_summary(clean, [REVENUE])
    s_boiler = score_summary(boiler, [REVENUE])
    assert s_clean.specificity > s_boiler.specificity
    # aggregate must not move with specificity (depends only on schema/recall/coverage).
    assert s_clean.aggregate() == s_boiler.aggregate()


# --- currency consistency (Wave 3 / FPI $-mislabel guard) ------------------------------------
_CNY_GT = [
    GroundTruthFact(metric="revenue", value=941_200_000_000.0, unit="CNY"),
    GroundTruthFact(metric="net_income", value=125_800_000_000.0, unit="CNY"),
    GroundTruthFact(metric="eps", value=44.0, unit="CNY_per_share"),
]
_DKK_GT = [
    GroundTruthFact(metric="revenue", value=309_100_000_000.0, unit="DKK"),
    GroundTruthFact(metric="net_income", value=102_400_000_000.0, unit="DKK"),
]
_TWD_GT = [GroundTruthFact(metric="revenue", value=2_894_000_000_000.0, unit="TWD")]


def _cur_payload(exec_summary: str) -> dict:
    return {"executive_summary": exec_summary, "financial_highlights": {}}


def test_currency_domestic_usd_filer_always_passes():
    """USD/domestic filer: '$' is correct, so the guard is a no-op (1.0)."""
    score, viol = score_currency_consistency(
        _cur_payload("Revenue rose to $383.3B; net income $97.0B; diluted EPS $6.13."),
        [REVENUE, NET_INCOME, EPS])
    assert score == 1.0 and viol == []


def test_currency_foreign_clean_native_scores_1():
    """Foreign filer rendered entirely in its reporting currency -> 1.0."""
    score, viol = score_currency_consistency(
        _cur_payload("Revenue rose 8% to RMB 941.2B; net income RMB 125.8B; EPS RMB 5.50."),
        _CNY_GT)
    assert score == 1.0 and viol == []


def test_currency_foreign_wholesale_mislabel_scores_near_zero():
    """A DKK filer whose figures are all rendered as bare '$' -> ~0 + a flagged violation."""
    score, viol = score_currency_consistency(
        _cur_payload("Novo reports revenue of $309.1B and net income of $102.4B, up 6% YoY."),
        _DKK_GT)
    assert score < 0.5
    assert viol and "DKK" in viol[0]


def test_currency_labeled_us_convenience_not_flagged():
    """A labeled US$ convenience figure paired with native currency is allowed (lookbehind)."""
    score, viol = score_currency_consistency(
        _cur_payload("Revenue was RMB 941.2B (US$129B convenience); net income RMB 125.8B."),
        _CNY_GT)
    assert score == 1.0 and viol == []


def test_currency_localized_dollar_symbol_not_flagged():
    """TWD rendered as 'NT$' is native, not a bare-$ mislabel."""
    score, viol = score_currency_consistency(
        _cur_payload("TSMC revenue reached NT$2,894.3B; net income NT$1,182.0B."),
        _TWD_GT)
    assert score == 1.0 and viol == []


def test_currency_incidental_bare_dollar_amid_native_scores_high():
    """Mostly-native prose with one stray bare-$ scores high (mild), not near-zero."""
    score, viol = score_currency_consistency(
        _cur_payload("Revenue RMB 941.2B, net income RMB 125.8B, cash RMB 400B; a $2.9B note matured."),
        _CNY_GT)
    assert score >= 0.6   # 3 RMB / (3 RMB + 1 bare-$) = 0.75
    assert viol


# --------------------------------------------------------------------------- G5 bank revenue integrity

_NII = GroundTruthFact(metric="net_interest_income", value=303_235_000.0, unit="USD")
_NONI = GroundTruthFact(metric="noninterest_income", value=11_871_000.0, unit="USD")


def test_bank_integrity_inert_without_component_facts():
    from evals.scorers import score_bank_revenue_integrity, compute_gate_failures
    # No component ground truth (the current golden set) → always passes, gate stays dormant.
    assert score_bank_revenue_integrity("anything at all", [REVENUE, NET_INCOME]) == (1.0, [])
    assert compute_gate_failures({}, [], [REVENUE]) == compute_gate_failures({}, [])


def test_bank_integrity_passes_when_both_components_surfaced():
    from evals.scorers import score_bank_revenue_integrity
    hay = json.dumps({"table": [
        {"metric": "Net Interest Income", "current_period": "$303.2M"},
        {"metric": "Non-Interest Income", "current_period": "$11.9M"},
    ]})
    assert score_bank_revenue_integrity(hay, [_NII, _NONI]) == (1.0, [])


def test_bank_integrity_gate_fires_when_component_missing():
    from evals.scorers import compute_gate_failures
    payload = {"financial_highlights": {"table": [
        {"metric": "Net Interest Income", "current_period": "$303.2M"},
        # Non-interest income dropped → G5 must fire.
    ]}}
    gates = compute_gate_failures(payload, [], [_NII, _NONI])
    assert any("G5 bank revenue" in g and "noninterest_income" in g for g in gates)
