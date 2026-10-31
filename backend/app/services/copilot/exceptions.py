"""Copilot exceptions extracted without changing admission behavior."""
from __future__ import annotations


class _UnpublishableAnswer(ValueError):
    """A candidate cannot cross the publication boundary."""


class _RegenerableEvidenceMismatch(_UnpublishableAnswer):
    """A referenced excerpt failed or its ID was declared twice; labels, literals and source passed."""


class _RegenerableCitationTrailer(_UnpublishableAnswer):
    """Text after a well-formed citation array that is not the followups block; no excerpt was checked yet."""
