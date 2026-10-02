"""Tracked example env files hold placeholders only (rule 12 gate).

An example file is committed to a public repository, so a value pasted into it is published. Every
`KEY=value` line in a tracked example env file must be empty, a visible placeholder, or a documented
non-secret default. Known provider key formats and JWTs are rejected outright, and any long,
high-entropy value without a placeholder marker is rejected as well.
"""
import math
import re
import subprocess
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

CREDENTIAL_SHAPES = (
    re.compile(r"sk-or-v1-[0-9a-f]{40,}"),           # OpenRouter
    re.compile(r"\bsk-[A-Za-z0-9_-]{32,}"),           # OpenAI-compatible provider keys
    re.compile(r"\bsb_(secret|publishable)_[A-Za-z0-9]{10,}"),  # Supabase
    re.compile(r"\b(sk|rk|pk)_(live|test)_[A-Za-z0-9]{16,}"),   # Stripe
    re.compile(r"\bwhsec_[A-Za-z0-9]{16,}"),          # Stripe/Svix webhook secrets
    re.compile(r"\bre_[A-Za-z0-9]{20,}"),             # Resend
    re.compile(r"\bphx_[A-Za-z0-9]{20,}"),            # PostHog personal keys
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"),          # Google API keys
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),      # GitHub tokens
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWT
)
DSN_WITH_PASSWORD = re.compile(r"^[a-z][a-z0-9+]*://[^:/\s]+:(?P<password>[^@\s]+)@")
DSN_PLACEHOLDER_PASSWORDS = {"password", "pass", "pwd", "user", "changeme", "example", "your-password", "<password>", "secret"}
URL_SCHEME = re.compile(r"^[a-z][a-z0-9+]*://")
PLACEHOLDER_MARKERS = ("your", "example", "change", "placeholder", "xxx", "...", "<", "replace", "here", "dummy", "mock", "test", "local", "optional")


def _tracked_example_env_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return sorted(
        ROOT / line for line in out.splitlines()
        if "example" in Path(line).name.lower() and "env" in Path(line).name.lower()
    )


def _entropy(value: str) -> float:
    counts = Counter(value)
    return -sum(c / len(value) * math.log2(c / len(value)) for c in counts.values())


def _offending_lines(text: str) -> list[str]:
    offenders = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")  # drop an inline comment
        if not value or value.startswith("#"):
            continue
        dsn = DSN_WITH_PASSWORD.search(value)
        if dsn and dsn.group("password").lower() not in DSN_PLACEHOLDER_PASSWORDS:
            offenders.append(f"line {number} ({key.strip()}): connection string with a non-placeholder password")
            continue
        if any(shape.search(value) for shape in CREDENTIAL_SHAPES):
            offenders.append(f"line {number} ({key.strip()}): credential-shaped value")
            continue
        lowered = value.lower()
        free_text = " " in value or URL_SCHEME.match(value) is not None
        if len(value) >= 24 and not free_text and _entropy(value) > 3.5 \
                and not any(marker in lowered for marker in PLACEHOLDER_MARKERS):
            offenders.append(f"line {number} ({key.strip()}): long high-entropy value without a placeholder marker")
    return offenders


def test_tracked_example_env_files_exist():
    assert _tracked_example_env_files(), "expected at least backend/.env.example to be tracked"


@pytest.mark.parametrize("path", _tracked_example_env_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_example_env_file_holds_only_placeholders(path):
    offenders = _offending_lines(path.read_text(encoding="utf-8"))
    assert not offenders, f"{path.relative_to(ROOT)} must hold placeholders only: {offenders}"


@pytest.mark.parametrize("value", [
    "sk-or-v1-" + "a1" * 32,
    "sb_secret_" + "Zz9" * 8,
    "sk_live_" + "Ab3" * 8,
    "whsec_" + "Qq1" * 8,
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.abcdefghijklmnop",
    "postgresql://appuser:Sup3rSecret@10.0.0.5:5432/app",
    "postgresql://appuser:9f8e7d6c5b4a@localhost:5432/app",
    "Vq7Kp2Lm9Xz4Rt8Wn3Yb6Hd1Jf5Gs0Ac",
])
def test_detector_rejects_credential_shaped_values(value):
    assert _offending_lines(f"KEY={value}\n")


@pytest.mark.parametrize("value", ["", "your-key-here", "sk-your-openai-key", "http://localhost:8000",
                                   "whsec_...", "change-me-in-production", "sqlite:///./earningsnerd.db",
                                   "postgresql://user:password@localhost:5432/earningsnerd",
                                   "EarningsNerd/1.0 (contact@earningsnerd.io)", "          # Apple Services ID"])
def test_detector_accepts_placeholders(value):
    assert not _offending_lines(f"KEY={value}\n")
