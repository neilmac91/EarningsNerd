"""Per-task AI model routing (roadmap A11).

Section recovery may opt into a cheaper model via AI_SECTION_RECOVERY_MODEL /
AI_FAST_MODEL, defaulting to the Pro model so behavior is unchanged out of the box.
Extraction and the editorial writer always stay on the Pro model.
"""
import pytest

from app.config import settings
from app.services.openai_service import OpenAIService

PRO = settings.AI_DEFAULT_MODEL
FLASH = "gemini-2.5-flash"


def _fresh_service(monkeypatch, *, fast="", recovery=""):
    monkeypatch.setattr(settings, "AI_FAST_MODEL", fast)
    monkeypatch.setattr(settings, "AI_SECTION_RECOVERY_MODEL", recovery)
    # __init__ reads the settings above to build _task_models.
    return OpenAIService()


def test_recovery_defaults_to_pro_when_unset(monkeypatch):
    svc = _fresh_service(monkeypatch)  # both unset
    assert svc.get_model_for_task("section_recovery") == PRO


def test_recovery_uses_explicit_override(monkeypatch):
    svc = _fresh_service(monkeypatch, recovery=FLASH)
    assert svc.get_model_for_task("section_recovery") == FLASH


def test_recovery_falls_back_to_fast_model(monkeypatch):
    # No task-specific override, but a general fast model is set.
    svc = _fresh_service(monkeypatch, fast=FLASH)
    assert svc.get_model_for_task("section_recovery") == FLASH


def test_whitespace_only_values_fall_through_to_pro(monkeypatch):
    # A blank/whitespace env must not be treated as a real model name.
    svc = _fresh_service(monkeypatch, fast="   ", recovery="  ")
    assert svc.get_model_for_task("section_recovery") == PRO


def test_explicit_recovery_overrides_fast_model(monkeypatch):
    svc = _fresh_service(monkeypatch, fast="gemini-2.5-pro", recovery=FLASH)
    assert svc.get_model_for_task("section_recovery") == FLASH


@pytest.mark.parametrize("task", ["structured_extraction", "editorial_writer"])
def test_quality_tasks_stay_on_pro_even_with_fast_model(monkeypatch, task):
    svc = _fresh_service(monkeypatch, fast=FLASH, recovery=FLASH)
    assert svc.get_model_for_task(task) == PRO
