"""Backports of upstream edgartools fixes that the pinned release lacks.

edgartools stays at 5.58.0 while issue #1063 holds the upgrade (the Ford affix and boundary
regressions of 5.59.1 persist through 5.62.0). An upstream fix that our extraction path reaches is
backported here, one function per fix. Each one first checks whether the installed release already
behaves correctly and does nothing if it does, so taking the upgrade leaves this module inert. The
PR that takes the upgrade deletes the backport: ``tests/unit/test_edgartools_compat.py`` fails once
the installed release no longer needs it.
"""
import logging

from edgar._filings import Filing

logger = logging.getLogger(__name__)

# The probe only builds URL strings; constructing a Filing makes no request.
_PROBE = dict(
    cik=1, company="probe", form="10-K", filing_date="2026-01-01", accession_no="0000000001-26-000001"
)

# Filing.homepage_url as the pinned release defines it, kept so the gate can tell when an
# upgrade has made the backport redundant.
ORIGINAL_HOMEPAGE_URL = Filing.homepage_url


def _in_folder_homepage_url(self: Filing) -> str:
    return f"{self.base_dir}/{self.accession_no}-index.html"


def _builds_in_folder_url(prop: property) -> bool:
    probe = Filing(**_PROBE)
    return prop.fget(probe) == _in_folder_homepage_url(probe)


def backport_homepage_url() -> bool:
    """Point ``Filing.homepage_url`` at the index page inside the accession folder.

    Since about 2026-10-06, SEC answers the short index URL
    ``/Archives/edgar/data/<cik>/<accession>-index.html`` with 403 "Access Denied"; the same page
    inside the accession folder still answers 200. edgartools 5.61.0 moved ``homepage_url`` there
    (upstream GH #1421). At 5.58.0, ``Filing.html()`` re-reads an inline-XBRL primary document
    (it starts with an XML prolog) through the homepage, so every 10-K, 10-Q and 20-F section read
    in ``xbrl_sections._extract_sections_sync`` failed, and both the summary excerpt and the
    eval harness fell back to the regex extractor.

    Returns True when it replaced the property, False when the installed release already builds
    the in-folder URL (an upgrade, or a second call).
    """
    if _builds_in_folder_url(Filing.homepage_url):
        return False
    Filing.homepage_url = property(
        _in_folder_homepage_url, doc="The filing index page inside the accession folder."
    )
    logger.info("edgartools backport applied: Filing.homepage_url uses the accession folder")
    return True


def apply_edgartools_backports() -> None:
    """Apply every backport. Idempotent; called once when the edgar client module loads."""
    backport_homepage_url()
