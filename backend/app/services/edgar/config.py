"""
EdgarTools Configuration

Contains configuration constants and enums for SEC filing operations.
"""

import os
from enum import Enum
from typing import List, Optional


# SEC EDGAR identity - required by SEC for API access
# Load from environment variable with sensible default
EDGAR_IDENTITY = os.environ.get("EDGAR_IDENTITY", "neil@earningsnerd.io")


class FilingType(str, Enum):
    """
    SEC filing types supported by EarningsNerd.

    Using an enum eliminates magic strings throughout the codebase
    and provides IDE autocompletion and type safety.
    """

    # Annual Reports
    FORM_10K = "10-K"
    FORM_10K_AMENDED = "10-K/A"

    # Quarterly Reports
    FORM_10Q = "10-Q"
    FORM_10Q_AMENDED = "10-Q/A"

    # Current Reports (material events)
    FORM_8K = "8-K"
    FORM_8K_AMENDED = "8-K/A"

    # Insider Trading
    FORM_3 = "3"      # Initial statement of beneficial ownership
    FORM_4 = "4"      # Changes in beneficial ownership
    FORM_5 = "5"      # Annual statement of beneficial ownership

    # Institutional Holdings
    FORM_13F = "13F-HR"  # Quarterly holdings report
    FORM_13F_AMENDED = "13F-HR/A"

    # Unknown/Other - fallback for unrecognized filing types
    UNKNOWN = "UNKNOWN"

    @property
    def is_annual(self) -> bool:
        """Check if this is an annual filing type."""
        return self in (FilingType.FORM_10K, FilingType.FORM_10K_AMENDED)

    @property
    def is_quarterly(self) -> bool:
        """Check if this is a quarterly filing type."""
        return self in (FilingType.FORM_10Q, FilingType.FORM_10Q_AMENDED)

    @property
    def is_insider(self) -> bool:
        """Check if this is an insider trading filing."""
        return self in (FilingType.FORM_3, FilingType.FORM_4, FilingType.FORM_5)

    @property
    def is_institutional(self) -> bool:
        """Check if this is an institutional holdings filing."""
        return self in (FilingType.FORM_13F, FilingType.FORM_13F_AMENDED)

    @property
    def is_amended(self) -> bool:
        """Check if this is an amended filing."""
        return "/A" in self.value

    @classmethod
    def financial_reports(cls) -> List["FilingType"]:
        """Return all financial report types (10-K and 10-Q)."""
        return [
            cls.FORM_10K, cls.FORM_10K_AMENDED,
            cls.FORM_10Q, cls.FORM_10Q_AMENDED,
        ]

    @classmethod
    def from_string(cls, value: str, strict: bool = True) -> "FilingType":
        """
        Convert a string to FilingType, handling common variations.

        Args:
            value: Filing type string (e.g., "10-K", "10K", "10-k")
            strict: If True, raise ValueError for unknown types.
                   If False, return UNKNOWN for unrecognized types.

        Returns:
            Corresponding FilingType enum

        Raises:
            ValueError: If strict=True and the string doesn't match any filing type
        """
        normalized = value.upper().strip()

        # Handle variations without hyphen
        variations = {
            "10K": cls.FORM_10K,
            "10Q": cls.FORM_10Q,
            "8K": cls.FORM_8K,
        }

        if normalized in variations:
            return variations[normalized]

        # Try direct match
        for filing_type in cls:
            if filing_type.value.upper() == normalized:
                return filing_type

        if strict:
            raise ValueError(f"Unknown filing type: {value}")
        return cls.UNKNOWN


# Thread pool configuration for async operations
# Configurable via environment variables for production tuning
EDGAR_THREAD_POOL_SIZE = int(os.environ.get("EDGAR_THREAD_POOL_SIZE", "4"))
EDGAR_DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("EDGAR_DEFAULT_TIMEOUT_SECONDS", "30.0"))
