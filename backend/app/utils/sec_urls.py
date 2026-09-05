"""SEC URL construction + validation (pure string helpers — NO network I/O).

The single home for the EDGAR archive-URL convention (``lessons/sec-filing-url-format.md``):

    https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/

with the CIK's leading zeros stripped (``320193``, not ``0000320193``) and the accession number's
dashes removed (``000032019323000077``). Every builder (edgar client, EFTS search hits, the Filing
model's insert fallback, the repair script) goes through :func:`build_sec_archive_url`, and the
Filing model validates ``sec_url``/``document_url`` against :data:`SEC_ARCHIVE_URL_RE` at the
boundary so a malformed or placeholder URL can never reach the database.

Lives in ``app/utils`` rather than ``app/services/edgar`` on purpose: ``app/models`` imports it,
and importing anything under ``app.services.edgar`` runs that package's ``__init__`` (edgartools +
the client singleton) at model-import time. This module has no dependencies. It is one of the few
sanctioned homes for the ``sec.gov`` literal outside the edgar service layer — see
``tests/unit/test_sec_gov_importers_allowlist.py``.
"""
import re
from urllib.parse import urlsplit

SEC_ARCHIVE_BASE_URL = "https://www.sec.gov/Archives/edgar/data/"

# Canonical archive URL: CIK without leading zeros (so never the "0" placeholder), 18-digit
# dashless accession folder, then an optional document path (index URLs end at the folder slash).
SEC_ARCHIVE_URL_RE = re.compile(
    r"^https://www\.sec\.gov/Archives/edgar/data/[1-9]\d*/\d{18}/\S*$"
)

_ACCESSION_DIGITS = 18


def normalize_cik(cik: str) -> str:
    """Return the CIK as a bare decimal string (leading zeros stripped).

    Raises ``ValueError`` for anything that is not a positive integer — including the ``"0"`` /
    ``"0000000000"`` placeholder, which is exactly the fabricated value the Filing model used to
    write when its company relationship was not loaded.
    """
    cleaned = str(cik or "").strip().lstrip("0")
    if not cleaned.isdigit():
        raise ValueError(f"Invalid SEC CIK {cik!r}: expected a positive integer")
    return cleaned


def normalize_accession(accession_number: str) -> str:
    """Return the accession number as its 18-digit dashless folder form."""
    cleaned = str(accession_number or "").strip().replace("-", "")
    if not (cleaned.isdigit() and len(cleaned) == _ACCESSION_DIGITS):
        raise ValueError(
            f"Invalid SEC accession number {accession_number!r}: "
            f"expected {_ACCESSION_DIGITS} digits (dashes optional)"
        )
    return cleaned


def build_sec_archive_url(cik: str, accession_number: str) -> str:
    """Build the filing's archive index URL from its CIK and accession number.

    Raises ``ValueError`` on a malformed CIK or accession — callers at the SEC boundary decide
    whether to skip the filing or fail loudly; nobody gets a placeholder URL.
    """
    return f"{SEC_ARCHIVE_BASE_URL}{normalize_cik(cik)}/{normalize_accession(accession_number)}/"


def is_sec_archive_url(url: object) -> bool:
    """True iff ``url`` is a canonical archive URL (index URL or a document under the folder)."""
    return isinstance(url, str) and SEC_ARCHIVE_URL_RE.match(url) is not None


def is_acceptable_filing_url(url: object) -> bool:
    """Boundary rule for ``Filing.sec_url`` / ``Filing.document_url``.

    Must be an absolute http(s) URL with a host; and if that host is on ``sec.gov`` it must be the
    canonical archive form (:func:`is_sec_archive_url`) — which rejects the historical ``cik=0``
    placeholder, zero-padded CIKs, dashed accession folders and legacy ``cgi-bin/viewer`` links.
    Non-SEC hosts are tolerated so hermetic test fixtures (``https://sec.example/…``) and any future
    mirror can carry a filing row; every production URL is built by :func:`build_sec_archive_url`
    and therefore takes the strict branch.
    """
    if not isinstance(url, str):
        return False
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return False
    host = (parts.hostname or "").lower()
    if host == "sec.gov" or host.endswith(".sec.gov"):
        return is_sec_archive_url(url)
    return True


def companyfacts_url(cik: str) -> str:
    """The XBRL companyfacts JSON endpoint for a CIK (10-digit zero-padded, per SEC's API)."""
    return f"https://data.sec.gov/api/xbrl/companyfacts/CIK{normalize_cik(cik).zfill(10)}.json"
