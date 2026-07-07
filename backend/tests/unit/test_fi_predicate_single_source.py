"""P0-2 structural guardrail (repo rule 12): ONE financial-institution predicate.

The bank grounding NOTE (xbrl_narrative), the deterministic bank-revenue guard (bank_guards)
and the quality verdict (assess_quality) must all consult ``fi_signals.fi_components_present``
— the incident class this closes was exactly these sites drifting apart (the instruction told
the model "no single revenue number" while the checker demanded one). Also pins the SIC band
against instance_extractor's so the local copy can never drift.
"""
import inspect

from app.services.ai import bank_guards, fi_signals, xbrl_narrative
from app.services.edgar import instance_extractor
from app.services import summary_generation_service


def test_note_emitter_and_bank_guard_share_the_predicate_object():
    assert xbrl_narrative.fi_components_present is fi_signals.fi_components_present
    assert bank_guards.fi_components_present is fi_signals.fi_components_present


def test_assess_quality_imports_the_shared_predicate():
    src = inspect.getsource(summary_generation_service.assess_quality)
    assert "from app.services.ai.fi_signals import" in src
    assert "fi_components_present" in src


def test_sic_band_matches_instance_extractor():
    assert fi_signals.FINANCIAL_SIC_LOW == instance_extractor.FINANCIAL_SIC_LOW
    assert fi_signals.FINANCIAL_SIC_HIGH == instance_extractor.FINANCIAL_SIC_HIGH


def test_predicate_semantics():
    assert fi_signals.fi_components_present({"net_interest_income": {"current": {}}}) is True
    assert fi_signals.fi_components_present({"noninterest_income": {"current": {}}}) is True
    assert fi_signals.fi_components_present({"revenue": {"current": {}}}) is False
    assert fi_signals.fi_components_present(None) is False
    assert fi_signals.is_financial_sic("6021") is True
    assert fi_signals.is_financial_sic("6799") is True
    assert fi_signals.is_financial_sic("3571") is False
    assert fi_signals.is_financial_sic(None) is False
    assert fi_signals.is_financial_sic("") is False
    assert fi_signals.is_financial_sic("garbage") is False
