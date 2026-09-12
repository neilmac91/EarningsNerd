"""deploy_check must accept the production AI provider and report the configured model (W8, ADR-0008).

The script used to carry its own Google/OpenRouter allowlist and reported DeepSeek's base URL as
invalid; it now defers to ``Settings.validate_openai_config`` so the two can never disagree.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

from app.config import Settings

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _deploy_check():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module("deploy_check")


def test_deepseek_base_url_is_recognized_and_google_is_still_accepted():
    mod = _deploy_check()
    good = Settings(OPENAI_API_KEY="sk-" + "x" * 40, OPENAI_BASE_URL="https://api.deepseek.com/v1")
    legacy = Settings(OPENAI_API_KEY="sk-" + "x" * 40, OPENAI_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/")
    bad = Settings(OPENAI_API_KEY="sk-" + "x" * 40, OPENAI_BASE_URL="https://example.invalid/v1")
    assert mod._base_url_recognized(good) is True
    assert mod._base_url_recognized(legacy) is True
    assert mod._base_url_recognized(bad) is False
    assert mod._base_url_recognized(Settings(OPENAI_API_KEY="sk-" + "x" * 40, OPENAI_BASE_URL="")) is False


def test_environment_check_reports_model_and_provider(monkeypatch, capsys):
    mod = _deploy_check()
    monkeypatch.setattr(mod.settings, "OPENAI_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setattr(mod.settings, "OPENAI_API_KEY", "sk-" + "x" * 40)
    monkeypatch.setattr(mod.settings, "AI_DEFAULT_MODEL", "deepseek-flash")
    mod.check_environment_variables()
    out = capsys.readouterr().out
    assert "AI_DEFAULT_MODEL" in out and "deepseek-flash" in out
    assert "Google AI Studio" not in out
