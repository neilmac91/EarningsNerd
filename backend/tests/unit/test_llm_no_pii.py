"""Regression guard: user PII must never reach the LLM.

The audit confirmed the AI service is fed only filing text + financial metrics, never the
app user's email/name/id. These tests lock that invariant so a future "personalization"
change can't silently start passing a User (or its fields) into a prompt builder.

After the roadmap-S2 façade split, the prompt-building/extraction code lives in the
``app.services.ai`` package, so a façade-only ``hasattr`` check would go blind to a submodule
that imports User — the package walk below closes that hole.
"""
import importlib
import inspect
import pkgutil

from app.services import ai as ai_pkg
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


def test_no_ai_submodule_imports_user_model():
    """Walk every app.services.ai submodule (S2 split) and assert none bound the User model.

    The extraction/normalization/rendering/recovery/copilot helpers are exactly where a future
    "personalization" change would be tempted to reach for the app user — so the invariant has to
    hold per-submodule, not just on the façade module the old test above inspects.
    """
    offenders = [
        mod_info.name
        for mod_info in pkgutil.iter_modules(ai_pkg.__path__, ai_pkg.__name__ + ".")
        if hasattr(importlib.import_module(mod_info.name), "User")
    ]
    assert not offenders, (
        f"ai submodule(s) imported the User model — risk of user PII reaching the LLM: {offenders}"
    )


def test_llm_entrypoints_take_no_user_pii_params():
    cls = openai_service.OpenAIService
    for name in _LLM_ENTRYPOINTS:
        method = getattr(cls, name, None)
        assert method is not None, f"expected OpenAIService.{name} to exist (renamed?)"
        leaked = set(inspect.signature(method).parameters) & _PII_PARAM_NAMES
        assert not leaked, f"OpenAIService.{name} gained user-PII param(s): {leaked}"
