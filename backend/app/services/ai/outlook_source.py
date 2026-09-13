"""Bounded, contiguous Outlook source omitted by the selected MD&A prefix.

This deliberately recognizes one explicit section boundary pair, not guidance keywords.
It does not fetch, infer missing text, or certify complete forward-looking coverage.
"""
import re

OUTLOOK_LABEL = "SELECTED MD&A OUTLOOK SOURCE SUPPLEMENT"
OUTLOOK_FAMILY = "outlook_supplement"
MAX_OUTLOOK_SUPPLEMENT_CHARS = 6000
_START = re.compile(r"^OUTLOOK[ \t]*$", re.M)
_END = re.compile(r"^Cautionary Note on Forward-Looking Statements[ \t]*$", re.M)


def outlook_supplement(mda: str, existing_excerpt: str, prefix_cap: int) -> str:
    """Return a complete source block plus wrapper, or nothing on uncertain boundaries."""
    starts, ends = list(_START.finditer(mda)), list(_END.finditer(mda))
    if len(starts) != 1 or len(ends) != 1:
        return ""
    start, end = starts[0].start(), ends[0].start()
    if end <= start or end <= prefix_cap:
        return ""
    block = mda[start:end].strip()
    # Reject a heading/TOC stub; never expand the window to manufacture substance.
    if len(block) < 200 or not re.search(r"\.[ \t]*(?:\n|$)", block):
        return ""
    if block in existing_excerpt:
        return ""
    wrapped = f"\n\n{OUTLOOK_LABEL}:\n{block}"
    return wrapped if len(wrapped) <= MAX_OUTLOOK_SUPPLEMENT_CHARS else ""
