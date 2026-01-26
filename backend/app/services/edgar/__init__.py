"""
EdgarTools Integration Module

This module provides a clean, typed interface for SEC EDGAR operations
using the EdgarTools library. It replaces the previous custom implementation
that used sec-edgar-downloader, sec-parser, and arelle.

Usage:
    from app.services.edgar import (
        EdgarClient,
        FilingType,
        CompanyNotFoundError,
        FilingNotFoundError,
    )

    client = EdgarClient()
    filing = await client.get_latest_filing("AAPL", FilingType.FORM_10K)
"""

from .config import FilingType, EDGAR_IDENTITY
from .exceptions import (
    EdgarError,
    EdgarNetworkError,
    EdgarRateLimitError,
    EdgarNotFoundError,
    CompanyNotFoundError,
    FilingNotFoundError,
    EdgarParseError,
    XBRLParseError,
    HTMLParseError,
)
from .models import Company, Filing, FinancialMetric, XBRLData
from .client import EdgarClient, edgar_client
from .xbrl_service import (
    EdgarXBRLService,
    edgar_xbrl_service,
    clear_xbrl_cache,
    get_xbrl_cache_stats,
)

__all__ = [
    # Configuration
    "FilingType",
    "EDGAR_IDENTITY",
    # Client
    "EdgarClient",
    "edgar_client",
    # XBRL Service
    "EdgarXBRLService",
    "edgar_xbrl_service",
    "clear_xbrl_cache",
    "get_xbrl_cache_stats",
    # Exceptions
    "EdgarError",
    "EdgarNetworkError",
    "EdgarRateLimitError",
    "EdgarNotFoundError",
    "CompanyNotFoundError",
    "FilingNotFoundError",
    "EdgarParseError",
    "XBRLParseError",
    "HTMLParseError",
    # Models
    "Company",
    "Filing",
    "FinancialMetric",
    "XBRLData",
]
