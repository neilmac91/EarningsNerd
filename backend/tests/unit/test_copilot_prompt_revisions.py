"""Every Copilot system-message composition is recorded with the source its measurement used.

The RUNBOOK's "Copilot prompt revisions" table lists, by SHA-256 prefix, the first generation's system
message and the regeneration's system message after a decision-F rejection and after a citation
failure. A PR that edits any of those bytes must add the row, saying what its live measurement ran on.
#1111's revision shipped measured only on the regex fallback, because SEC's 403 had silently removed
sections from every eval source (tasks/review-evidence/copilot-table-excerpt-retry-2026-10-16/).
"""
import hashlib
import re
from pathlib import Path

from app.services import copilot_service
from app.services.copilot import prompt
from app.services.copilot.exceptions import _RegenerableEvidenceMismatch, _UnpublishableAnswer

# Every revision ever recorded, oldest first: (first generation, decision-F retry, citation retry). Append the
# new triple and its RUNBOOK row together. Editing either alone fails below; editing both rewrites history,
# which only review can refuse (the RUNBOOK's "append-only by review").
REVISIONS = [
    ("a88b6fb1de5b", "—", "—"),
    ("d46ef28f000a", "f3b340db1e35", "f3b340db1e35"),
    ("d46ef28f000a", "f3b340db1e35", "ae01453ef90d"),
    ("c221b7e3c5c2", "34d01dadbac0", "bf240eb01f4c"),
]
REPO = Path(__file__).resolve().parents[3]
RUNBOOK = REPO / "backend" / "evals" / "RUNBOOK.md"
HEADING = "**Copilot prompt revisions.**"


def _prefix(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def current_compositions() -> tuple[str, str, str]:
    """The three system messages the service can send, built through the service's own chooser."""
    quotation = _UnpublishableAnswer(next(iter(copilot_service._RETRYABLE_QUOTATION_FAILURES)))
    citation = _RegenerableEvidenceMismatch("Unverified or ambiguous referenced citation")
    retry = lambda exc: prompt.SYSTEM_PROMPT + "\n\n" + prompt._retry_guidance(  # noqa: E731
        exc, copilot_service._RETRYABLE_QUOTATION_FAILURES)
    return _prefix(prompt.SYSTEM_PROMPT), _prefix(retry(quotation)), _prefix(retry(citation))


def revision_rows() -> list[list[str]]:
    text = RUNBOOK.read_text()
    table = text[text.index(HEADING):].split("\n\n")[1]
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in table.splitlines()]
    assert rows[0][:3] == ["First generation", "Decision-F retry", "Citation retry"]
    return rows[2:]


def test_the_current_prompt_bytes_have_a_revision_row():
    current = current_compositions()
    assert current == REVISIONS[-1], (
        f"Copilot prompt bytes {current} are not the newest revision: append them to REVISIONS here and add "
        "their row to the RUNBOOK's 'Copilot prompt revisions' table, saying what the live measurement ran on")


def test_the_revision_table_is_the_append_only_history():
    recorded = [tuple(cell.strip("`") for cell in row[:3]) for row in revision_rows()]
    assert recorded == REVISIONS, "the RUNBOOK's revision rows must list REVISIONS, in order, one row each"


def test_every_revision_row_names_its_measurement_and_existing_evidence():
    for row in revision_rows():
        first, _f_retry, _citation_retry, introduced, measured_on, evidence = row
        assert re.fullmatch(r"`[0-9a-f]{12}`", first) and introduced and measured_on
        path = evidence.strip("`")
        assert (REPO / path).is_file(), f"revision row evidence {path} does not exist"


def test_a_quotation_retry_never_sees_the_citation_guidance():
    """The table-text guidance is chosen by the owned citation class; F retries keep their bytes."""
    _first, f_retry, citation_retry = current_compositions()
    assert f_retry != citation_retry
    assert prompt._retry_guidance(_UnpublishableAnswer("Unverified or ambiguous referenced citation"),
                                  copilot_service._RETRYABLE_QUOTATION_FAILURES) == ""
