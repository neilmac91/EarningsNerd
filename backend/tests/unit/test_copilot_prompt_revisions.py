"""Every model-facing Copilot composition is recorded with the source its measurement used.

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
    recorded = [tuple(cell.strip("`") for cell in row[:3]) for row in revision_rows()]
    assert current in recorded, (
        f"Copilot prompt bytes {current} have no row in the RUNBOOK's 'Copilot prompt revisions' table: "
        "add one that says what the live measurement ran on (sections or the regex fallback)")


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
