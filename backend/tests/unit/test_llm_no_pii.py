"""Regression guard: user PII must never reach the LLM.

The audit confirmed the AI service is fed only filing text + financial metrics, never the
app user's email/name/id. These tests lock that invariant so a future "personalization"
change can't silently start passing a User (or its fields) into a prompt builder.
"""
import inspect

from app.services import openai_service

# Param names that would indicate app-user identity leaking into a prompt path.
_PII_PARAM_NAMES = {"user", "current_user", "email", "user_id", "user_email", "username"}

# The methods that actually build prompts / call the model.
_LLM_ENTRYPOINTS = [
    "summarize_filing",
    "generate_structured_summary",
]


def test_ai_service_does_not_import_user_model():
    """If the AI service can't even see the User model, user PII can't reach a prompt via it."""
    assert not hasattr(openai_service, "User"), (
        "openai_service imported the User model — risk of user PII reaching the LLM"
    )


def test_llm_entrypoints_take_no_user_pii_params():
    cls = openai_service.OpenAIService
    for name in _LLM_ENTRYPOINTS:
        method = getattr(cls, name, None)
        assert method is not None, f"expected OpenAIService.{name} to exist (renamed?)"
        leaked = set(inspect.signature(method).parameters) & _PII_PARAM_NAMES
        assert not leaked, f"OpenAIService.{name} gained user-PII param(s): {leaked}"
