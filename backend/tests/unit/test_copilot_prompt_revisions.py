"""Every Copilot system-message composition is recorded with the source its measurement used.

The RUNBOOK's "Copilot prompt revisions" table lists, by SHA-256 prefix, the first generation's system
message and the regeneration's system message after a decision-F rejection, after a citation failure
and after text following the citation array. A PR that edits any of those bytes must add the row, saying
what its live measurement ran on. #1111's revision shipped measured only on the regex fallback, because
SEC's 403 had silently removed sections from every eval source
(tasks/review-evidence/copilot-table-excerpt-retry-2026-10-16/).
"""
import hashlib
import re
from pathlib import Path

from app.services import copilot_service
from app.services.copilot import prompt
from app.services.copilot.exceptions import _RegenerableEvidenceMismatch, _UnpublishableAnswer

# Every revision ever recorded, oldest first: (first generation, decision-F retry, citation retry, trailer
# retry). Append the new tuple and its RUNBOOK row together. Editing either alone fails below; editing both
# rewrites history, which only review can refuse (the RUNBOOK's "append-only by review").
REVISIONS = [
    ("a88b6fb1de5b", "—", "—", "—"),
    ("d46ef28f000a", "f3b340db1e35", "f3b340db1e35", "—"),
    ("d46ef28f000a", "f3b340db1e35", "ae01453ef90d", "—"),
    ("c221b7e3c5c2", "34d01dadbac0", "bf240eb01f4c", "—"),
    ("c221b7e3c5c2", "34d01dadbac0", "bf240eb01f4c", "863fb9b91a4e"),
]
COLUMNS = ["First generation", "Decision-F retry", "Citation retry", "Trailer retry"]
REPO = Path(__file__).resolve().parents[3]
RUNBOOK = REPO / "backend" / "evals" / "RUNBOOK.md"
HEADING = "**Copilot prompt revisions.**"


def _prefix(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _retry(exc: Exception) -> str:
    return prompt.SYSTEM_PROMPT + "\n\n" + prompt._retry_guidance(exc, copilot_service._RETRYABLE_QUOTATION_FAILURES)


def _trailer_rejection() -> Exception:
    """What the envelope parser itself raises for a note and a second array after the citation array."""
    try:
        copilot_service._parse_citations("[]\nNote: corrected below.\n===CITATIONS===\n[]")
    except _UnpublishableAnswer as exc:
        return exc
    raise AssertionError("text after the citation array was admitted")


def current_compositions() -> tuple[str, str, str, str]:
    """The four system messages the service can send, built through the service's own chooser."""
    quotation = _UnpublishableAnswer(next(iter(copilot_service._RETRYABLE_QUOTATION_FAILURES)))
    citation = _RegenerableEvidenceMismatch("Unverified or ambiguous referenced citation")
    return (_prefix(prompt.SYSTEM_PROMPT), _prefix(_retry(quotation)), _prefix(_retry(citation)),
            _prefix(_retry(_trailer_rejection())))


def revision_rows() -> list[list[str]]:
    text = RUNBOOK.read_text()
    table = text[text.index(HEADING):].split("\n\n")[1]
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in table.splitlines()]
    assert rows[0][:4] == COLUMNS
    return rows[2:]


def test_the_current_prompt_bytes_have_a_revision_row():
    current = current_compositions()
    assert current == REVISIONS[-1], (
        f"Copilot prompt bytes {current} are not the newest revision: append them to REVISIONS here and add "
        "their row to the RUNBOOK's 'Copilot prompt revisions' table, saying what the live measurement ran on")


def test_the_revision_table_is_the_append_only_history():
    recorded = [tuple(cell.strip("`") for cell in row[:4]) for row in revision_rows()]
    assert recorded == REVISIONS, "the RUNBOOK's revision rows must list REVISIONS, in order, one row each"


def test_every_revision_row_names_its_measurement_and_existing_evidence():
    for row in revision_rows():
        first, _f_retry, _citation_retry, _trailer_retry, introduced, measured_on, evidence = row
        assert re.fullmatch(r"`[0-9a-f]{12}`", first) and introduced and measured_on
        path = evidence.strip("`")
        assert (REPO / path).is_file(), f"revision row evidence {path} does not exist"


def test_a_quotation_retry_never_sees_the_citation_guidance():
    """The table-text guidance is chosen by the owned citation class; F retries keep their bytes."""
    _first, f_retry, citation_retry, trailer_retry = current_compositions()
    assert len({f_retry, citation_retry, trailer_retry}) == 3
    assert prompt._retry_guidance(_UnpublishableAnswer("Unverified or ambiguous referenced citation"),
                                  copilot_service._RETRYABLE_QUOTATION_FAILURES) == ""


def test_every_owned_retry_class_sends_a_recorded_composition():
    """A new owned retry class cannot send bytes this table does not hash.

    Every subclass of ``_UnpublishableAnswer`` and every retryable decision-F reason is put through the
    service's chooser; each regeneration it would start must be one of the recorded retry columns. A
    retry chosen from a new reason string on the base class is outside this check (review-checked).
    """
    def owned(cls: type) -> list[type]:
        return [found for sub in cls.__subclasses__() for found in (sub, *owned(sub))]

    rejections = [cls("owned reason") for cls in owned(_UnpublishableAnswer)]
    rejections += [_UnpublishableAnswer(reason) for reason in copilot_service._RETRYABLE_QUOTATION_FAILURES]
    sent = {_prefix(_retry(exc)) for exc in rejections
            if prompt._retry_guidance(exc, copilot_service._RETRYABLE_QUOTATION_FAILURES)}
    assert sent == set(current_compositions()[1:])
