"""Copilot exceptions extracted without changing admission behavior."""
from __future__ import annotations


class _UnpublishableAnswer(ValueError):
    """A candidate cannot cross the publication boundary."""


class _RegenerableEvidenceMismatch(_UnpublishableAnswer):
    """Only referenced excerpt matching failed; identity, label and source checks passed."""
