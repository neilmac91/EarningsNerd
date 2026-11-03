"""A deploy never resets the closed beta's operator switches (docs/ops/closed-beta-acceptance.md, section 7).

Opening collection, publishing the operator notice and turning screenshots on or off are the founder's live
decisions, made on the running service: the ``LEGAL_*`` settings by hand, the ``FEEDBACK_MEDIA_*`` ones through
the protected Ops applies (``ops/feedback_media/manage.py``). The rollback levers depend on those values staying
as the founder set them. An ordinary deploy carries an explicit additive environment map, and
``tests/unit/test_summary_rollout_preservation.py`` holds every deploy command to that shape, so a key the map
does not name keeps its live value. This gate keeps these keys out of every workflow, so no deploy map, job or
step can pin one, even to its default.

Reach: the workflow files. A script a workflow runs (the screenshot applies set their keys inside their approved
runs), an image's ``ENV``, a console edit and a key name built at run time are outside it. A traffic rollback
restores the older revision's own values; the runbook says so.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.config import Settings

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / ".github" / "workflows"
# Every setting the founder owns for the beta, read from Settings so a new notice field or media setting is
# covered the day it is added.
OPERATOR_SWITCHES = frozenset(name for name in Settings.model_fields if name.startswith(("LEGAL_", "FEEDBACK_MEDIA_")))


def _executable(text: str) -> str:
    """The workflow without its comment lines: a key named in a comment pins nothing."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def test_the_switch_set_holds_the_levers_the_runbook_names():
    assert {"LEGAL_COLLECTION_ENABLED", "LEGAL_OPERATOR_PUBLISHED", "FEEDBACK_MEDIA_ENABLED",
            "FEEDBACK_MEDIA_BUCKET"} <= OPERATOR_SWITCHES


def test_no_workflow_sets_an_operator_switch():
    workflows = sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])
    assert workflows, "no workflow files found"
    pinned = {}
    for path in workflows:
        executable = _executable(path.read_text(encoding="utf-8"))
        # Settings reads the environment without regard to case (``case_sensitive = False``), so neither does this.
        named = sorted(key for key in OPERATOR_SWITCHES if re.search(rf"\b{key}\b", executable, re.IGNORECASE))
        if named:
            pinned[path.name] = named
    assert not pinned, f"a deploy or step would reset the founder's beta switches: {pinned}"
