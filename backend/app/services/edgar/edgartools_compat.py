"""Keep section extraction lossless while using edgartools 5.62.0.

5.62.0's TOC section extractor renders whole tables before walking their HTML.
That renderer discards columns containing percent/parenthesis affixes, zero-value
em dashes and list bullets, and removes the spacer-row breaks at prose/table
boundaries (issue #1063). Keep its existing element-wise fallback for sections:
this is the 5.58.0 extraction representation on which our summary baseline was
measured. It retains every cell and row break, including long layout-table prose.

Document-wide rendering remains upstream's; this compatibility hook affects only
TOC-resolved section tables. It intentionally preserves the existing concatenated
adjacent-cell representation, rather than introducing unmeasured model-input
changes. Remove the hook only with content-preservation and baseline evidence.
The obsolete homepage URL backport is gone: 5.62.0 already fixes that upstream.
"""
from typing import Optional

from lxml.etree import _Element
from edgar.documents.extractors.toc_section_extractor import SECSectionExtractor


def _walk_section_table(
    self: SECSectionExtractor, table: _Element, clean: bool,
) -> Optional[str]:
    """Choose the upstream element-wise path; None is its explicit fallback signal."""
    return None


def apply_edgartools_backports() -> None:
    """Install the section compatibility hook, idempotently, before any parsing."""
    SECSectionExtractor._render_table = _walk_section_table
