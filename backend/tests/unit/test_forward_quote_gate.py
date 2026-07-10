"""T5.4 forward-quote gate: every §5 quote is verified against the filing text the model generated
from (exact substring under the shared `normalize_for_match` — typography-folded, case/whitespace
insensitive); failures are always audited and dropped only when armed. Conservative by design
(the figure_trace posture): no source basis / short quotes / malformed entries never flag, so a
degraded generation can never lose content to an upstream pipeline failure.

Scores pinned below were verified empirically: a one-word change scores ~96 partial_ratio
(near-miss ≥ 92 = lightly paraphrased), a paraphrase ~62, a fabrication ~44."""
from app.config import settings
from app.services.ai.forward_quote_gate import NEAR_MISS_SCORE, gate_forward_quotes

# Filing text uses the typography real filings use: curly quotes, curly apostrophe, em-dash.
FILING = (
    "Item 7. MD&A - Outlook. We expect capital expenditures to increase substantially in fiscal "
    "2027 as we scale our data center footprint, and we remain committed to our dividend program. "
    "Management stated: “We believe demand for our accelerated computing platforms will continue "
    "to outpace supply through the first half of next year.” Our board declared the company’s "
    "largest-ever repurchase authorization — $110 billion. Certain statements are forward-looking."
)
VERBATIM = "We expect capital expenditures to increase substantially in fiscal 2027"
FABRICATED = "We are confident revenue will double next year and margins will expand dramatically."


def _sections(*quotes):
    return {
        "forward_signals": {
            "guidance": "Guidance maintained for fiscal 2027.",
            "known_trends": ["Data center demand"],
            "quotes": [dict(q) for q in quotes],
        }
    }


def _q(text, speaker="CFO"):
    return {"speaker": speaker, "quote": text, "context": "MD&A"}


def test_default_flag_is_off():
    # Advisory-first (the figure-trace precedent): measurement ships, the drop does not.
    assert settings.AI_FORWARD_QUOTE_GATE is False


def test_verbatim_quote_verifies():
    sections = _sections(_q(VERBATIM))
    audit = gate_forward_quotes(sections, FILING, armed=False)
    assert audit == {
        "checked": 1, "verified": 1, "unverified": [], "near_miss": 0,
        "dropped": [], "armed": False,
    }


def test_case_whitespace_and_typography_drift_all_verify():
    """The shared normalization absorbs the classes that are 'the same text' to a human: case,
    whitespace runs/newlines, and straight-vs-curly quotes/apostrophes/dashes (the model types
    ASCII; filings typeset typography)."""
    sections = _sections(
        _q("we EXPECT capital  expenditures\nto increase substantially in fiscal 2027"),
        # filing: “…” curly-quoted sentence; model emits it bare with straight punctuation
        _q("We believe demand for our accelerated computing platforms will continue to outpace "
           "supply through the first half of next year."),
        # filing: company’s …— $110 billion; model: company's … - $110 billion
        _q("the company's largest-ever repurchase authorization - $110 billion"),
    )
    audit = gate_forward_quotes(sections, FILING, armed=False)
    assert (audit["checked"], audit["verified"]) == (3, 3) and not audit["unverified"]


def test_fabricated_quote_is_flagged_not_dropped_when_unarmed():
    sections = _sections(_q(VERBATIM), _q(FABRICATED, speaker="CEO"))
    audit = gate_forward_quotes(sections, FILING, armed=False)
    assert (audit["checked"], audit["verified"]) == (2, 1)
    assert audit["near_miss"] == 0 and audit["dropped"] == []
    (entry,) = audit["unverified"]
    assert entry["speaker"] == "CEO" and entry["score"] < NEAR_MISS_SCORE
    # unarmed = measurement only: the quote SURVIVES
    assert len(sections["forward_signals"]["quotes"]) == 2


def test_near_miss_is_bucketed_separately():
    # One word changed ("first" -> "second"): still not verbatim, but the filing carries a close
    # counterpart — the lightly-paraphrased population that wants prompt tuning, not the gate.
    sections = _sections(
        _q("We believe demand for our accelerated computing platforms will continue to outpace "
           "supply through the second half of next year.")
    )
    audit = gate_forward_quotes(sections, FILING, armed=False)
    assert audit["verified"] == 0 and audit["near_miss"] == 1
    assert audit["unverified"][0]["score"] >= NEAR_MISS_SCORE


def test_armed_drops_only_the_failing_quote():
    sections = _sections(_q(VERBATIM), _q(FABRICATED, speaker="CEO"))
    audit = gate_forward_quotes(sections, FILING, armed=True)
    remaining = sections["forward_signals"]["quotes"]
    assert [q["quote"] for q in remaining] == [VERBATIM]
    assert audit["dropped"] == [{"speaker": "CEO", "quote": FABRICATED}]
    assert audit["armed"] is True
    # the section's other fields are NEVER touched (coverage cannot be drained section-wide)
    assert sections["forward_signals"]["guidance"] == "Guidance maintained for fiscal 2027."
    assert sections["forward_signals"]["known_trends"] == ["Data center demand"]


def test_armed_drop_of_every_quote_leaves_empty_list_and_intact_section():
    sections = _sections(_q(FABRICATED))
    audit = gate_forward_quotes(sections, FILING, armed=True)
    assert sections["forward_signals"]["quotes"] == []
    assert audit["verified"] == 0 and len(audit["dropped"]) == 1
    assert sections["forward_signals"]["guidance"]  # survives


def test_wrapping_quote_marks_are_stripped_before_matching():
    # Models often wrap the quote field's value in literal quote marks; a FULL wrapping pair is
    # stripped (inner spans never shrink the needle — see the fabricated-wrapper tests below).
    sections = _sections(_q(f'"{VERBATIM}"'))
    audit = gate_forward_quotes(sections, FILING, armed=False)
    assert audit["verified"] == 1


def test_short_quotes_pass_uncounted():
    # < _MIN_VERIFIABLE_LEN normalized chars is unverifiable-by-construction (shared floor) —
    # kept, and excluded from the audit; a lone short quote means nothing to measure -> None.
    sections = _sections(_q("We expect growth."))
    assert gate_forward_quotes(sections, FILING, armed=True) is None
    assert len(sections["forward_signals"]["quotes"]) == 1


def test_no_source_text_measures_and_drops_nothing():
    # The figure-trace no-grounding-basis rule: a degraded generation (no excerpt, no filing
    # text) must never lose content to the pipeline failure that degraded it.
    sections = _sections(_q(FABRICATED))
    assert gate_forward_quotes(sections, "", armed=True) is None
    assert len(sections["forward_signals"]["quotes"]) == 1


def test_missing_section_or_quotes_returns_none():
    assert gate_forward_quotes({}, FILING, armed=True) is None
    assert gate_forward_quotes({"forward_signals": "not a dict"}, FILING, armed=True) is None
    assert gate_forward_quotes(_sections(), FILING, armed=True) is None  # empty quotes list
    no_quotes = {"forward_signals": {"guidance": "Maintained."}}
    assert gate_forward_quotes(no_quotes, FILING, armed=True) is None


def test_armed_drop_is_invisible_to_the_rendered_markdown():
    """The ordering invariant the wiring depends on: the gate runs on the SAME sections object
    render_sections reads, BEFORE the render — so a dropped quote can never survive into the
    persisted business_overview markdown (the desync class the drop-site placement exists to
    prevent). Mirrors summarize_filing exactly: gate → stamp schema_version → render → markdown."""
    from app.services.summary_sections import render_sections, sections_to_markdown

    structured = {"schema_version": 2, "sections": _sections(_q(VERBATIM), _q(FABRICATED))}
    gate_forward_quotes(structured["sections"], FILING, armed=True)
    md = sections_to_markdown(render_sections(structured))
    assert VERBATIM in md
    assert FABRICATED not in md
    assert "Guidance maintained for fiscal 2027." in md  # section text untouched


def test_malformed_entries_pass_untouched():
    sections = _sections(_q(VERBATIM))
    sections["forward_signals"]["quotes"].extend([
        "just a string",                      # non-dict item
        {"speaker": "CFO", "quote": None},    # non-string quote
        {"speaker": "CFO", "quote": "   "},   # blank quote
    ])
    audit = gate_forward_quotes(sections, FILING, armed=True)
    assert audit["checked"] == 1 and audit["verified"] == 1
    assert len(sections["forward_signals"]["quotes"]) == 4  # nothing malformed was dropped


# --- adversarial-review fixes (post-#623) --------------------------------------------------------

def test_fabricated_wrapper_around_real_quoted_fragment_is_flagged():
    """Review finding (executed bypass): the needle is the WHOLE quote value — an inner quoted
    span must never shrink it, or a fabricated wrapper verifies via any real 8+-char fragment."""
    wrapper = ('Revenue will triple by 2030 and "We expect capital expenditures to increase '
               'substantially in fiscal 2027" so margins are guaranteed to expand forever.')
    sections = _sections(_q(wrapper, speaker="CEO"))
    audit = gate_forward_quotes(sections, FILING, armed=True)
    assert audit["verified"] == 0 and len(audit["dropped"]) == 1
    assert sections["forward_signals"]["quotes"] == []


def test_long_fabrication_with_short_inner_quote_is_measured():
    """Review finding (executed bypass): a 100+-char fabrication carrying a sub-floor inner quote
    used to reduce to that span and pass UNCOUNTED (audit None). The whole value is now checked."""
    fabrication = ('We are fully confident our "Vision 2030 plan" will double revenue and expand '
                   'margins dramatically across every segment next year.')
    sections = _sections(_q(fabrication))
    audit = gate_forward_quotes(sections, FILING, armed=True)
    assert audit is not None and audit["checked"] == 1 and audit["verified"] == 0
    assert sections["forward_signals"]["quotes"] == []


def test_single_quote_full_wrap_is_stripped():
    sections = _sections(_q(f"'{VERBATIM}'"))
    audit = gate_forward_quotes(sections, FILING, armed=False)
    assert audit["verified"] == 1


def test_inline_markdown_emphasis_does_not_fail_a_verbatim_quote():
    """Review finding: the renderer strips **emphasis** for display, so the gate must match on the
    same stripped text — a verbatim phrase the model decorated is not drift."""
    decorated = "We expect **capital expenditures** to increase substantially in fiscal 2027"
    sections = _sections(_q(decorated))
    audit = gate_forward_quotes(sections, FILING, armed=False)
    assert audit["verified"] == 1


def test_fully_verbatim_quote_still_verifies_after_wrapper_strip_change():
    # Regression guard for the fix itself: the plain path is untouched.
    sections = _sections(_q(VERBATIM))
    assert gate_forward_quotes(sections, FILING, armed=True)["verified"] == 1


def test_newline_in_quote_text_renders_as_single_line_blockquote():
    """Review finding + Gemini on #625: a newline inside the model's quote string broke the GFM
    blockquote (continuation lines lost the '> ' prefix) and hid the quote from the eval's
    line-anchored regex. The renderer now collapses internal whitespace — one sentence, one line."""
    from app.services.summary_sections import render_sections, sections_to_markdown

    two_line = VERBATIM.replace("capital expenditures", "capital\nexpenditures")
    structured = {"schema_version": 2, "sections": _sections(_q(two_line))}
    md = sections_to_markdown(render_sections(structured))
    line = next(ln for ln in md.splitlines() if ln.startswith("> "))
    assert VERBATIM in line  # whole quote on the one blockquote line, whitespace collapsed
