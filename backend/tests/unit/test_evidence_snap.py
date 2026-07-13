"""Evidence auto-snap (task #40): measured provenance repair for supporting_evidence.

Measure-always, act-when-armed. The adversarial review of the first draft CONFIRMED (executed)
that fuzzy repair can attach a real-but-wrong-fact sentence under a Verified badge, so the flag
ships OFF and unarmed runs record would-snap forensics (original + candidate). Core invariants
pinned here: the round-trip property (an armed snap must pass the shared exact check), the
non-mutation of unarmed runs, the F2 length-ratio guard, the F3 recovery skip, and the F1
cross-metric limitation as an honest characterization.
"""
from pathlib import Path

from app.services.ai.evidence_snap import _sentences, snap_evidence, snap_value
from app.services.provenance_service import normalize_for_match, verify_excerpt_in_text

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
    "Compared with the prior year period:\n"
    "Gross margin percentage was 46.2% in 2025 and 45.0% in 2024.\n"
    "Revenue Total operating expenses 62,151 8 57,467\n"
)
NORM = normalize_for_match(SOURCE)
CANDS = _sentences(SOURCE)
CAND_NEEDLES = [normalize_for_match(c) for c in CANDS]
MIN_SCORE = 72.0


def _decide(evidence):
    return snap_value(evidence, CANDS, CAND_NEEDLES, NORM, MIN_SCORE)


def _sections(evidence_rtm="", evidence_fn=""):
    return {
        "results_that_matter": {
            "table": [
                {
                    "metric": "Revenue",
                    "commentary": "Services drove growth.",
                    "supporting_evidence": evidence_rtm,
                }
            ]
        },
        "notable_footnotes": [
            {"item": "Buybacks", "impact": "Share count fell.", "supporting_evidence": evidence_fn}
        ],
        "risks": [
            {"summary": "x", "supporting_evidence": "Item 1A. Risk Factors", "materiality": "low"}
        ],
        "forward_signals": {
            "quotes": [{"speaker": "CEO", "quote": "We expect supply constraints to persist"}]
        },
    }


COMPOSED_EPS = "Diluted earnings per share increased 16% to $13.64."


# ---------------------------------------------------------------------------
# snap_value — the decision function
# ---------------------------------------------------------------------------
def test_exact_evidence_is_exact():
    _, score, status = _decide("Total net sales increased 6% during 2025 compared to 2024")
    assert status == "exact" and score == 100.0


def test_composed_summary_matches_the_real_sentence():
    candidate, score, status = _decide(COMPOSED_EPS)
    assert status == "matched"
    assert candidate.startswith("Diluted earnings per share was $13.64")
    assert score >= MIN_SCORE


def test_matched_candidate_verifies_exactly_afterward():
    # THE round-trip invariant: an armed snap must pass the shared exact check — that is what
    # lights the read-time Verified badge, the #:~:text= deep link, and the eval dimension.
    candidate, _, status = _decide(COMPOSED_EPS)
    assert status == "matched"
    assert verify_excerpt_in_text(candidate, NORM)


def test_figure_guard_blocks_cross_metric_snap_via_year_exclusion():
    # Shares only YEARS with the high-scoring wrong sentence — years are excluded from the
    # guard (fiscal years co-occur across unrelated facts), so this must stay "left".
    _, _, status = snap_value(
        "Total net sales increased 99% during 2025 compared to 2024, driven primarily by higher "
        "Services revenue and the launch of new products.",
        CANDS,
        CAND_NEEDLES,
        NORM,
        MIN_SCORE,
    )
    assert status == "left"


def test_f1_characterization_wrong_fact_same_figure_can_match():
    # HONEST LIMITATION (skeptic F1, executed on the first draft): when the TRUE counterpart is
    # absent and a different fact shares a non-year figure, the decision function CAN pick the
    # wrong-fact sentence — the floor+guard pin *a* fact, not *the row's* fact. This is exactly
    # why mutation ships behind an unarmed flag with would-snap forensics: the arming decision
    # needs the fleet wrong-snap rate, which this test documents rather than hides.
    candidate, _, status = _decide(
        "Total cost of sales increased 6% during 2025 compared to 2024 on higher Services volume."
    )
    assert status == "matched"  # picks the net-sales sentence (same 6%) — wrong fact, real text
    assert "net sales" in candidate.lower()


def test_f2_short_boilerplate_fragment_cannot_replace_evidence():
    # Skeptic F2 (executed on the first draft at 97.2): partial_ratio aligns a contentless
    # lead-in ("Compared with the prior year period:") inside long evidence at ~100. The
    # length-ratio guard must reject fragment candidates.
    ev = (
        "Management expects continued strong demand for cloud offerings compared with the "
        "prior year period."
    )
    candidate, _, status = _decide(ev)
    assert status == "left" and candidate is None


def test_no_digit_evidence_matches_on_the_stricter_floor():
    candidate, _, status = _decide(
        "The backlog grew substantially as customers extended their commitments beyond the current cycle."
    )
    assert status == "matched"
    assert verify_excerpt_in_text(candidate, NORM)


def test_round_trip_guard_rejects_candidates_that_cannot_verify():
    # The demand sentence scores far above the floor but carries a SHORT inner quoted span
    # (“exceeded supply”) — extract_quoted_span shrinks its read-time needle below the
    # verifiable minimum, so verification would fail. A repair that cannot light the badge is
    # not a repair.
    _, _, status = _decide("Demand for our data-center products exceeded supply throughout the period")
    assert status == "left"


def test_table_blob_is_never_a_candidate():
    # Digit-density filter: the table transcription line must not be in the candidate pool —
    # the snap must never be able to INSTALL the artifact the evidence contract forbids.
    assert not any("62,151" in c for c in CANDS)
    ev = "Revenue Total operating expenses 62,151 8 57,467 up strongly versus the prior year"
    candidate, _, status = _decide(ev)
    assert status == "left" and candidate is None


def test_short_and_empty_evidence_are_skipped():
    for ev in ("", "   ", "Up 8% YoY.", None, 42):
        _, _, status = snap_value(ev, CANDS, CAND_NEEDLES, NORM, MIN_SCORE)
        assert status == "skipped"


# ---------------------------------------------------------------------------
# snap_evidence — the walker (armed semantics, scope, audit forensics)
# ---------------------------------------------------------------------------
def test_unarmed_records_would_snap_and_mutates_nothing():
    sections = _sections(evidence_rtm=COMPOSED_EPS)
    audit = snap_evidence(sections, SOURCE, MIN_SCORE, armed=False)
    assert sections["results_that_matter"]["table"][0]["supporting_evidence"] == COMPOSED_EPS
    assert audit["armed"] is False and not audit["snapped"]
    (entry,) = audit["would_snap"]
    # Forensics: original + candidate both recorded — the arming decision's evidence.
    assert entry["original"] == COMPOSED_EPS
    assert entry["candidate"].startswith("Diluted earnings per share was $13.64")
    assert entry["surface"] == "results_that_matter" and entry["score"] >= MIN_SCORE


def test_armed_mutates_and_records_original():
    sections = _sections(evidence_rtm=COMPOSED_EPS, evidence_fn="We repurchased 108 million shares for $20.2 billion.")
    audit = snap_evidence(sections, SOURCE, MIN_SCORE, armed=True)
    assert audit["armed"] is True and not audit["would_snap"]
    assert len(audit["snapped"]) == 2
    rtm_ev = sections["results_that_matter"]["table"][0]["supporting_evidence"]
    fn_ev = sections["notable_footnotes"][0]["supporting_evidence"]
    assert verify_excerpt_in_text(rtm_ev, NORM) and verify_excerpt_in_text(fn_ev, NORM)
    originals = {e["original"] for e in audit["snapped"]}
    assert COMPOSED_EPS in originals  # the destroyed text is preserved in the audit


def test_walker_never_touches_risks_or_quotes():
    sections = _sections(evidence_rtm=COMPOSED_EPS)
    before_risk = sections["risks"][0]["supporting_evidence"]
    before_quote = sections["forward_signals"]["quotes"][0]["quote"]
    snap_evidence(sections, SOURCE, MIN_SCORE, armed=True)
    assert sections["risks"][0]["supporting_evidence"] == before_risk
    assert sections["forward_signals"]["quotes"][0]["quote"] == before_quote


def test_recovery_authored_sections_are_skipped():
    # Skeptic F3: recovery re-asks generate from extract_sections context, not the excerpt —
    # their verbatim-TRUE evidence can fail the excerpt check and must not be rewritten or
    # counted as noncompliance.
    sections = _sections(evidence_rtm=COMPOSED_EPS, evidence_fn=COMPOSED_EPS)
    audit = snap_evidence(
        sections, SOURCE, MIN_SCORE, armed=True, skip_sections=frozenset({"notable_footnotes"})
    )
    assert sections["notable_footnotes"][0]["supporting_evidence"] == COMPOSED_EPS  # untouched
    assert all(e["surface"] == "results_that_matter" for e in audit["snapped"])
    assert audit["checked"] == 1


def test_no_source_measures_nothing():
    sections = _sections(evidence_rtm=COMPOSED_EPS)
    assert snap_evidence(sections, "", MIN_SCORE, armed=True) is None
    assert sections["results_that_matter"]["table"][0]["supporting_evidence"] == COMPOSED_EPS


def test_all_empty_evidence_yields_no_audit():
    assert snap_evidence(_sections(), SOURCE, MIN_SCORE, armed=True) is None


def test_malformed_shapes_are_tolerated():
    sections = {
        "results_that_matter": {"table": ["not-a-dict", {"metric": "x"}]},
        "notable_footnotes": "not-a-list",
    }
    assert snap_evidence(sections, SOURCE, MIN_SCORE, armed=True) is None


# ---------------------------------------------------------------------------
# Wiring pins (rule 12): always-measured, flag-armed, excerpt-only, off the event loop,
# recovery keys threaded.
# ---------------------------------------------------------------------------
def test_generation_wiring():
    src = (
        Path(__file__).resolve().parents[2] / "app" / "services" / "openai_service.py"
    ).read_text()
    assert "evidence_snap_audit = await run_in_threadpool(" in src  # F5: off the event loop
    assert "settings.AI_EVIDENCE_SNAP,\n            recovered_keys,\n        )" in src
    assert 'structured_summary.pop("_recovered_sections", [])' in src  # F3 threading
    assert 'summary_data["_recovered_sections"] = sorted(recovered.keys())' in src
    assert 'raw_summary_payload["evidence_snap_audit"] = evidence_snap_audit' in src
