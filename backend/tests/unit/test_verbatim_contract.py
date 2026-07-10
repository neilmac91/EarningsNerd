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

_OPENAI_SERVICE_SRC = Path("app/services/openai_service.py").read_text()


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
        assert '"We expect R2 will be foundational" (re-tensed)' in _OPENAI_SERVICE_SRC
        assert "(words removed inside the span)" in _OPENAI_SERVICE_SRC

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

    def test_risks_snippet_regained_its_qualifier(self):
        assert "non-empty excerpt or citation" in openai_service._get_section_schema_snippet("risks")

    def test_recovery_system_message_carries_the_verbatim_rule(self):
        src = inspect.getsource(type(openai_service)._run_secondary_completion)
        assert "character-for-character" in src
        assert "omit it if you cannot copy it" in src  # substring safe across literal breaks

    def test_recovery_token_cap_covers_the_restored_fields(self):
        # Evidence fields lengthen recovery output; a truncated completion falls to JSON repair
        # and can turn a recoverable section into a hard miss. 350 → 500 with the fields.
        sig = inspect.signature(type(openai_service)._run_secondary_completion)
        assert sig.parameters["max_tokens"].default == 500
