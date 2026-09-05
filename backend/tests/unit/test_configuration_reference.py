"""Keep the operator's Settings inventory complete and its declared defaults truthful."""
import json
import re
from collections import Counter
from pathlib import Path

from app.config import Settings

REFERENCE = Path(__file__).resolve().parents[3] / "docs/CONFIGURATION.md"


def test_configuration_reference_covers_settings_and_defaults():
    # Only structured inventory rows count: a casual mention or commented-out example
    # must not conceal a missing operator-facing definition.
    rows = re.findall(r"^\| `([A-Z][A-Z0-9_]*)` \| `([^`]+)` \| (.+) \|$", REFERENCE.read_text(), re.MULTILINE)
    counts = Counter(name for name, _, _ in rows)
    fields = Settings.model_fields
    assert set(counts) == set(fields), (
        f"Settings inventory mismatch: missing={sorted(set(fields) - set(counts))}, "
        f"obsolete={sorted(set(counts) - set(fields))}"
    )
    assert all(count == 1 for count in counts.values()), f"Duplicate Settings rows: {counts}"
    for name, documented, guidance in rows:
        field = fields[name]
        expected = "required" if field.is_required() else json.dumps(field.default)
        assert documented == expected, f"{name}: documented default {documented}, code default {expected}"
        assert guidance.strip(), f"{name}: describe the purpose and any override caveats"
