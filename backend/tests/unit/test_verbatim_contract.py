"""T4 follow-up rule-12 pins: the verbatim-copying contract exists on every surface the model
reads, and the recovery re-ask keeps parity with the main schema.

The T5.4 fleet readout measured 8/8 forward-quote failures as LIGHT PARAPHRASE (re-tensing /
in-span elision at rapidfuzz 97-99.6) and zero fabrications — so the fix is mechanical copying
instructions + a worked example (lessons/arch-edit-causal-directive-add-example.md), and these
pins keep them from silently regressing out of the prompt."""
import inspect
from pathlib import Path

from app.services.openai_service import openai_service
from app.services.prompt_loader import get_structured_prompt

# Anchored to __file__ (Gemini on #626): tests/unit/ -> backend/ -> app/... — runs
# identically regardless of the runner's working directory.
_OPENAI_SERVICE_SRC = (
    Path(__file__).resolve().parents[2] / "app" / "services" / "openai_service.py"
).read_text()


class TestSchemaTemplateContract:
    def test_quote_instruction_carries_the_mechanics(self):
        # The §5 quote field had the WEAKEST verbatim directive in the prompt (bare "verbatim")
        # on exactly the field the production gate measures.
        assert "copied CHARACTER-FOR-CHARACTER from the filing" in _OPENAI_SERVICE_SRC
        assert "never substitute, add, drop, or re-tense a word" in _OPENAI_SERVICE_SRC
        assert "choose a shorter CONTIGUOUS span" in _OPENAI_SERVICE_SRC

    def test_blanket_verbatim_rule_with_worked_example(self):
        # Rule + worked example (both measured failure modes shown as WRONG cases). The Rules
        # block is mode-independent, so the contract survives USE_STRUCTURED_OUTPUT both ways.
        assert "VERBATIM COPYING" in _OPENAI_SERVICE_SRC
        assert "(words substituted)" in _OPENAI_SERVICE_SRC
        assert "(a word removed inside the span)" in _OPENAI_SERVICE_SRC

    def test_worked_example_is_fictional_and_marked_illustrative(self):
        # Adversarial-review finding (reproduced against the real RIVN 10-K): a worked example
        # built from a REAL filer's language BLED into that filer's summaries — the model emitted
        # the example's re-tensed variant over the filing's own sentence, deterministically, on
        # the exact filer the slice targeted. The example must be fictional and marked.
        assert "illustrative only — NOT from the filing you are summarizing" in _OPENAI_SERVICE_SRC
        assert "Meridian platform" in _OPENAI_SERVICE_SRC  # fictional product, no golden-set filer
        assert "R2" not in _OPENAI_SERVICE_SRC             # the bled example must never return

    def test_output_tripwire_fragments_track_the_prompt_example(self):
        # Staff review (#626): the eval-side bleed tripwire must follow any edit to the worked
        # example, or it rots into gating spans the prompt no longer ships. Every gated fragment
        # must literally appear in the prompt's example (source/RIGHT + both WRONG variants), so
        # rewording the example breaks THIS test and drags EXAMPLE_BLEED_FRAGMENTS along.
        from evals.scorers import EXAMPLE_BLEED_FRAGMENTS

        src_low = _OPENAI_SERVICE_SRC.lower()
        # 3 verbatim-example spans (-i) + 2 copy-don't-compose spans (-k).
        assert len(EXAMPLE_BLEED_FRAGMENTS) >= 5
        for frag in EXAMPLE_BLEED_FRAGMENTS:
            assert frag in src_low, f"tripwire fragment no longer in the prompt example: {frag}"

    def test_compose_example_is_fictional_and_marked(self):
        # The -k example must follow the -i convention: fictional world, illustrative marker on
        # EVERY example (two markers now — the verbatim example and the compose example).
        assert _OPENAI_SERVICE_SRC.count("illustrative only — NOT from the filing you are summarizing") >= 2
        assert "Meridian demand exceeded capacity" in _OPENAI_SERVICE_SRC  # the WRONG composed span

    def test_blanket_rule_carves_out_the_risks_contract(self):
        # risks evidence is contractually looser BY DESIGN (excerpt OR citation, never empty) —
        # the blanket rule must scope itself or the prompt self-contradicts across three lines.
        assert "risks `supporting_evidence` keeps its own contract" in _OPENAI_SERVICE_SRC

    def test_evidence_fields_demand_prose_never_table_rows(self):
        # Evidence-as-prose (the #626 citation_fidelity ~0.51 discovery): table rows have no
        # single linear text form, so a row transcription can NEVER verify by exact search — and
        # the T4 read-time badge discards unverifiable excerpts, making table-row evidence pure
        # waste on the product surface. Both schema fields and the blanket rule must demand prose.
        assert "NEVER a transcription of table rows or cells" in _OPENAI_SERVICE_SRC  # P&L rows
        assert "NEVER a transcription of a footnote table's rows or cells" in _OPENAI_SERVICE_SRC
        assert "table has no single linear text form" in _OPENAI_SERVICE_SRC  # the rule clause
        assert "EVIDENCE IS PROSE" in _OPENAI_SERVICE_SRC  # its own rule, not spliced into quotes
        # One verbatim vocabulary (Gemini, #627): the evidence fields said "word-for-word" while
        # every other surface says CHARACTER-FOR-CHARACTER — the weaker phrase licenses
        # punctuation/hyphenation drift, a real near-miss source.
        assert "word-for-word" not in _OPENAI_SERVICE_SRC

    def test_evidence_forbids_composed_sentences(self):
        # Copy-don't-compose (#627 residual): after -j, the no-counterpart population was the
        # model COMPOSING fluent evidence sentences that restate figures instead of copying a
        # sentence that exists in the filing — form-compliant, provenance-non-compliant. The
        # prohibition must name supporting_evidence explicitly (commentary/impact are the model's
        # own analysis BY DESIGN and must stay composable).
        assert "COPY, don't COMPOSE" in _OPENAI_SERVICE_SRC  # the rule clause
        # One clause per field, bound by their distinct tails (skeptic on -k: a bare count>=2
        # would pass with one field's clause deleted and the phrase duplicated elsewhere).
        assert "the span must exist in the filing" in _OPENAI_SERVICE_SRC   # P&L rows field
        assert "the span must exist in the footnote" in _OPENAI_SERVICE_SRC  # footnotes field

    def test_quotes_is_an_empty_allowed_array(self):
        # The never-empty-arrays rule was forcing quote INVENTION when no copyable quote exists —
        # `quotes` must stay in the exception list at both rule sites.
        assert _OPENAI_SERVICE_SRC.count("`red_flags` / `highlights` / `quotes`") >= 1
        assert "`red_flags`, `highlights`, and `quotes`" in _OPENAI_SERVICE_SRC


class TestPreambleParity:
    def test_all_four_preambles_carry_the_mechanical_sentence(self):
        for form in ("10-K", "10-Q", "20-F", "6-K"):
            preamble = get_structured_prompt(form)
            assert "CHARACTER-FOR-CHARACTER" in preamble, form
            assert "forward_signals" in preamble, form

    def test_6k_gained_the_risk_evidence_line(self):
        assert "For risk factors, attach supporting evidence" in get_structured_prompt("6-K")

    def test_all_four_preambles_forbid_table_row_evidence(self):
        for form in ("10-K", "10-Q", "20-F", "6-K"):
            assert "never by transcribing table rows" in get_structured_prompt(form), form

    def test_all_four_preambles_forbid_composed_evidence(self):
        for form in ("10-K", "10-Q", "20-F", "6-K"):
            assert "never compose your own restatement of figures" in get_structured_prompt(form), form


class TestRecoveryParity:
    """The recovery re-ask authors the weakest-grounded population; its snippets had dropped the
    verbatim qualifiers AND two supporting_evidence fields entirely."""

    def test_forward_signals_snippet_demands_exact_copying(self):
        snippet = openai_service._get_section_schema_snippet("forward_signals")
        assert "copied CHARACTER-FOR-CHARACTER" in snippet
        assert "omit the quote if you cannot copy it exactly" in snippet

    def test_evidence_fields_restored_to_results_and_footnotes(self):
        for section in ("results_that_matter", "notable_footnotes"):
            snippet = openai_service._get_section_schema_snippet(section)
            assert "supporting_evidence" in snippet, section
            assert "CHARACTER-FOR-CHARACTER" in snippet, section
            # Evidence-as-prose parity: the re-ask authors the weakest-grounded population and
            # must carry the same table-row prohibition as the main schema.
            assert "never a table-row transcription" in snippet, section

    def test_risks_snippet_regained_its_qualifier(self):
        assert "non-empty excerpt or citation" in openai_service._get_section_schema_snippet("risks")

    def test_recovery_system_message_carries_the_verbatim_rule(self):
        # Asserted on the runtime constant, not inspect.getsource fragments — source-literal
        # re-wrapping kept forcing pin relaxations (skeptic finding, -j slice).
        from app.services.ai.section_recovery import RECOVERY_SYSTEM_MESSAGE as msg

        assert "character-for-character" in msg
        assert "omit the quote; set supporting_evidence to ''" in msg  # per-field escape
        assert "Risks supporting_evidence keeps its own contract" in msg  # looser-contract carve-out
        # Scoped prose demand (skeptic #1): recovery re-asks each section ALONE, so an unscoped
        # "evidence must be prose" would facially bind a risks-only re-ask, whose contract
        # deliberately allows a citation.
        assert "evidence in those two sections must be narrative prose" in msg
        assert "never a table-row transcription" in msg
        assert "never a sentence you compose yourself" in msg  # copy-don't-compose (#627 residual)

    def test_recovery_token_cap_covers_the_restored_fields(self):
        # Evidence fields lengthen recovery output; a truncated completion falls to JSON repair
        # and can turn a recoverable section into a hard miss. 350 → 500 with the fields.
        sig = inspect.signature(type(openai_service)._run_secondary_completion)
        assert sig.parameters["max_tokens"].default == 500
