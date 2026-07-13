"""Evidence auto-snap (task #40): deterministic provenance repair for supporting_evidence.

The -j/-k slices measured composed evidence at the model's prompt-tuning floor; this module
snaps non-verifying evidence to the best-matching REAL excerpt sentence at generation time.
Core invariant pinned here: a snapped value must verify by the shared EXACT check afterward
(that is the entire point — read-time badges/deep-links and the eval all use that check).
"""
from pathlib import Path

from app.services.ai.evidence_snap import snap_evidence, snap_value, _sentences
from app.services.provenance_service import normalize_for_match, verify_excerpt_in_text

# A filing-excerpt stand-in: prose sentences with figures, typography, and a table-ish blob.
SOURCE = (
    "Item 7. MD&A\n"
    "Total net sales increased 6% during 2025 compared to 2024, driven primarily by higher "
    "Services revenue and the launch of new products.\n"
    "Diluted earnings per share was $13.64, an increase of 16% from the prior year, reflecting "
    "higher net income and a lower share count.\n"
    "We repurchased 108 million shares of our common stock for $20.2 billion during the year.\n"
    "Demand for our data-center products “exceeded supply” throughout the period — we "
    "expect supply constraints to persist into next year.\n"
    "Our backlog grew substantially as customers extended their commitments beyond the "
    "current cycle.\n"
    "Gross margin percentage was 46.2% in 2025 and 45.0% in 2024.\n"
    "Revenue Total operating expenses 62,151 8 57,467\n"
)
NORM = normalize_for_match(SOURCE)
CANDS = _sentences(SOURCE)
CAND_NEEDLES = [normalize_for_match(c) for c in CANDS]
MIN_SCORE = 72.0


def _snap(evidence):
    return snap_value(evidence, CANDS, CAND_NEEDLES, NORM, MIN_SCORE)


def _sections(evidence_rtm=None, evidence_fn=None):
    sections = {
        "results_that_matter": {
            "table": [
                {
                    "metric": "Revenue",
                    "commentary": "Services drove growth.",
                    "supporting_evidence": evidence_rtm if evidence_rtm is not None else "",
                }
            ]
        },
        "notable_footnotes": [
            {
                "item": "Buybacks",
                "impact": "Share count fell.",
                "supporting_evidence": evidence_fn if evidence_fn is not None else "",
            }
        ],
        "risks": [
            {"summary": "x", "supporting_evidence": "Item 1A. Risk Factors", "materiality": "low"}
        ],
        "forward_signals": {
            "quotes": [{"speaker": "CEO", "quote": "We expect supply constraints to persist"}]
        },
    }
    return sections


# ---------------------------------------------------------------------------
# snap_value
# ---------------------------------------------------------------------------
def test_exact_evidence_is_untouched():
    ev = "Total net sales increased 6% during 2025 compared to 2024"
    value, score, status = _snap(ev)
    assert status == "exact" and value == ev and score == 100.0


def test_composed_summary_snaps_to_the_real_sentence():
    # The measured composed class: a fluent model-written summary of a real sentence's figures.
    value, score, status = _snap("Diluted earnings per share increased 16% to $13.64.")
    assert status == "snapped"
    assert value.startswith("Diluted earnings per share was $13.64")
    assert score >= MIN_SCORE


def test_snapped_value_verifies_exactly_afterward():
    # THE core invariant: repaired evidence must pass the shared exact check — this is what
    # lights the read-time Verified badge, the #:~:text= deep link, and the eval dimension.
    value, _, status = _snap("Diluted earnings per share increased 16% to $13.64.")
    assert status == "snapped"
    assert verify_excerpt_in_text(value, NORM)


def test_figure_guard_blocks_cross_metric_snap():
    # Evidence carrying figures may only snap to a sentence sharing one of them: a high
    # function-word overlap with a DIFFERENT fact's sentence must not win a Verified badge.
    value, _, status = snap_value(
        "Total net sales increased 99% during 2025 compared to 2024, driven primarily by higher "
        "Services revenue and the launch of new products.",
        CANDS,
        CAND_NEEDLES,
        NORM,
        MIN_SCORE,
    )
    assert status == "left"
    assert "99%" in value  # original text preserved


def test_no_digit_evidence_snaps_on_score_alone():
    value, _, status = _snap(
        "The backlog grew substantially as customers extended their commitments beyond the current cycle."
    )
    assert status == "snapped"
    assert verify_excerpt_in_text(value, NORM)


def test_round_trip_guard_rejects_candidates_that_cannot_verify():
    # The demand sentence is real prose and scores far above the floor, but it carries a SHORT
    # inner quoted span (“exceeded supply”) — extract_quoted_span shrinks its read-time needle
    # below _MIN_VERIFIABLE_LEN, so verification would fail. A repair that cannot light the
    # badge is not a repair: the original evidence must stay.
    ev = "Demand for our data-center products exceeded supply throughout the period"
    value, _, status = _snap(ev)
    assert status == "left" and value == ev


def test_below_floor_composed_evidence_is_left_in_place():
    ev = "Management expects robust performance across all segments going forward."
    value, _, status = _snap(ev)
    assert status == "left" and value == ev


def test_short_and_empty_evidence_are_skipped_untouched():
    for ev in ("", "   ", "Up 8% YoY.", None, 42):
        value, _, status = snap_value(ev, CANDS, CAND_NEEDLES, NORM, MIN_SCORE)
        assert status == "skipped" and value == ev


# ---------------------------------------------------------------------------
# snap_evidence (the section walker)
# ---------------------------------------------------------------------------
def test_walker_repairs_both_contracted_surfaces_and_audits():
    sections = _sections(
        evidence_rtm="Total net sales increased 6% in 2025 compared to 2024, driven by Services.",
        evidence_fn="We repurchased 108 million shares for $20.2 billion.",
    )
    audit = snap_evidence(sections, SOURCE, MIN_SCORE)
    assert audit["checked"] == 2
    assert len(audit["snapped"]) == 2
    surfaces = {s["surface"] for s in audit["snapped"]}
    assert surfaces == {"results_that_matter", "notable_footnotes"}
    rtm_ev = sections["results_that_matter"]["table"][0]["supporting_evidence"]
    fn_ev = sections["notable_footnotes"][0]["supporting_evidence"]
    assert verify_excerpt_in_text(rtm_ev, NORM) and verify_excerpt_in_text(fn_ev, NORM)
    assert audit["min_score"] == MIN_SCORE


def test_walker_never_touches_risks_or_quotes():
    sections = _sections(
        evidence_rtm="Diluted earnings per share increased 16% to $13.64.", evidence_fn=""
    )
    before_risk = sections["risks"][0]["supporting_evidence"]
    before_quote = sections["forward_signals"]["quotes"][0]["quote"]
    snap_evidence(sections, SOURCE, MIN_SCORE)
    assert sections["risks"][0]["supporting_evidence"] == before_risk
    assert sections["forward_signals"]["quotes"][0]["quote"] == before_quote


def test_no_source_measures_nothing():
    sections = _sections(evidence_rtm="Diluted earnings per share increased 16% to $13.64.")
    assert snap_evidence(sections, "", MIN_SCORE) is None
    assert (
        sections["results_that_matter"]["table"][0]["supporting_evidence"]
        == "Diluted earnings per share increased 16% to $13.64."
    )


def test_all_empty_evidence_yields_no_audit():
    # '' is the contracted no-prose answer — skipped, so an all-'' summary has nothing checked.
    assert snap_evidence(_sections(evidence_rtm="", evidence_fn=""), SOURCE, MIN_SCORE) is None


def test_malformed_shapes_are_tolerated():
    sections = {
        "results_that_matter": {"table": ["not-a-dict", {"metric": "x"}]},
        "notable_footnotes": "not-a-list",
    }
    assert snap_evidence(sections, SOURCE, MIN_SCORE) is None


def test_table_blob_is_not_a_candidate():
    # The table-ish source line must never be offered as a "repair" — _sentences length/shape
    # bounds keep candidates prose-like; a table transcription in evidence therefore stays left
    # (or matches nothing) rather than snapping to another table line.
    ev = "Revenue Total operating expenses 62,151 8 57,467 up strongly versus the prior year"
    value, _, status = _snap(ev)
    if status == "snapped":  # if it ever snaps, it must at least be to REAL locatable prose
        assert verify_excerpt_in_text(value, NORM)
    else:
        assert value == ev


# ---------------------------------------------------------------------------
# Wiring pin (rule 12): the snap runs in generation post-processing, flag-gated, excerpt-only.
# ---------------------------------------------------------------------------
def test_generation_wiring_is_flag_gated_and_excerpt_grounded():
    src = (
        Path(__file__).resolve().parents[2] / "app" / "services" / "openai_service.py"
    ).read_text()
    assert "if settings.AI_EVIDENCE_SNAP:" in src
    assert 'snap_evidence(\n                sections_info, filing_excerpt or "", settings.EVIDENCE_SNAP_MIN_SCORE\n            )' in src
    assert 'raw_summary_payload["evidence_snap_audit"] = evidence_snap_audit' in src
