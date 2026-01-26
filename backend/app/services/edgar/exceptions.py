"""
EdgarTools Exception Hierarchy

Provides a clean, consistent exception hierarchy for all SEC EDGAR operations.
Each exception includes context information for debugging and logging.
"""

from datetime import datetime
from typing import Any, Dict, Optional


class EdgarError(Exception):
    """
    Base class for all Edgar-related errors.

    Attributes:
        message: Human-readable error description
        code: Machine-readable error code for programmatic handling
        cause: Original exception that caused this error
        context: Additional context information (ticker, URL, etc.)
        timestamp: When the error occurred
    """

    def __init__(
        self,
        message: str,
        code: str = "EDGAR_ERROR",
        *,
        cause: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.cause = cause
        self.context = context or {}
        self.timestamp = datetime.utcnow()

    def __str__(self) -> str:
        parts = [self.message]
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"[{context_str}]")
        return " ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            "error": self.code,
            "message": self.message,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "cause": str(self.cause) if self.cause else None,
        }


# Network-level errors
class EdgarNetworkError(EdgarError):
    """
    Network-level failures (timeout, connection refused, DNS errors).

    Use this for transient errors that may succeed on retry.
    """

    def __init__(
        self,
        message: str,
        *,
        cause: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="EDGAR_NETWORK_ERROR",
            cause=cause,
            context=context,
        )


class EdgarRateLimitError(EdgarNetworkError):
    """
    SEC rate limit exceeded (HTTP 429).

    Includes retry_after hint for backoff logic.
    """

    def __init__(
        self,
        message: str = "SEC EDGAR rate limit exceeded",
        retry_after: int = 60,
        *,
        cause: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        ctx = context or {}
        ctx["retry_after_seconds"] = retry_after
        super().__init__(
            message=message,
            cause=cause,
            context=ctx,
        )
        self.code = "EDGAR_RATE_LIMITED"
        self.retry_after = retry_after


class EdgarTimeoutError(EdgarNetworkError):
    """
    Request timed out waiting for SEC EDGAR response.
    """

    def __init__(
        self,
        message: str = "SEC EDGAR request timed out",
        timeout_seconds: float = 30.0,
        *,
        cause: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        ctx = context or {}
        ctx["timeout_seconds"] = timeout_seconds
        super().__init__(
            message=message,
            cause=cause,
            context=ctx,
        )
        self.code = "EDGAR_TIMEOUT"
        self.timeout_seconds = timeout_seconds


# Not found errors
class EdgarNotFoundError(EdgarError):
    """
    Requested resource not found in SEC EDGAR.

    Base class for specific not-found errors.
    """

    def __init__(
        self,
        message: str,
        *,
        cause: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="EDGAR_NOT_FOUND",
            cause=cause,
            context=context,
        )


class CompanyNotFoundError(EdgarNotFoundError):
    """
    Company/ticker not found in SEC EDGAR.

    This typically means the ticker is invalid or the company
    is not registered with the SEC.
    """

    def __init__(
        self,
        ticker: str,
        *,
        cause: Optional[Exception] = None,
        suggestion: Optional[str] = None,
    ):
        context = {"ticker": ticker}
        if suggestion:
            context["suggestion"] = suggestion

        super().__init__(
            message=f"Company not found: {ticker}",
            cause=cause,
            context=context,
        )
        self.code = "COMPANY_NOT_FOUND"
        self.ticker = ticker


class FilingNotFoundError(EdgarNotFoundError):
    """
    Filing not found for the specified company and type.

    This may mean the company hasn't filed this type of report,
    or the accession number is invalid.
    """

    def __init__(
        self,
        ticker: str,
        filing_type: str,
        *,
        accession_number: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        context = {"ticker": ticker, "filing_type": filing_type}
        if accession_number:
            context["accession_number"] = accession_number

        message = f"No {filing_type} filing found for {ticker}"
        if accession_number:
            message = f"Filing {accession_number} not found for {ticker}"

        super().__init__(
            message=message,
            cause=cause,
            context=context,
        )
        self.code = "FILING_NOT_FOUND"
        self.ticker = ticker
        self.filing_type = filing_type
        self.accession_number = accession_number


# Parse errors
class EdgarParseError(EdgarError):
    """
    Failed to parse SEC document content.

    Base class for specific parse errors.
    """

    def __init__(
        self,
        message: str,
        *,
        cause: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="EDGAR_PARSE_ERROR",
            cause=cause,
            context=context,
        )


class XBRLParseError(EdgarParseError):
    """
    Failed to parse XBRL financial data.

    This may indicate malformed XBRL, unsupported tags,
    or missing required data.
    """

    def __init__(
        self,
        message: str,
        *,
        accession_number: Optional[str] = None,
        cause: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        ctx = context or {}
        if accession_number:
            ctx["accession_number"] = accession_number

        super().__init__(
            message=message,
            cause=cause,
            context=ctx,
        )
        self.code = "XBRL_PARSE_ERROR"
        self.accession_number = accession_number


class HTMLParseError(EdgarParseError):
    """
    Failed to parse HTML filing content.

    This may indicate malformed HTML or unexpected document structure.
    """

    def __init__(
        self,
        message: str,
        *,
        document_url: Optional[str] = None,
        cause: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        ctx = context or {}
        if document_url:
            ctx["document_url"] = document_url

        super().__init__(
            message=message,
            cause=cause,
            context=ctx,
        )
        self.code = "HTML_PARSE_ERROR"
        self.document_url = document_url


def translate_edgartools_exception(exc: Exception) -> EdgarError:
    """
    Translate EdgarTools library exceptions to our exception types.

    This provides a consistent exception interface regardless of
    the underlying library implementation.
    """
    error_str = str(exc).lower()

    # Check for rate limiting
    if "rate limit" in error_str or "429" in error_str:
        return EdgarRateLimitError(str(exc), cause=exc)

    # Check for not found
    if "not found" in error_str or "404" in error_str:
        if "company" in error_str or "ticker" in error_str:
            return CompanyNotFoundError("unknown", cause=exc)
        return EdgarNotFoundError(str(exc), cause=exc)

    # Check for timeout
    if "timeout" in error_str or "timed out" in error_str:
        return EdgarTimeoutError(str(exc), cause=exc)

    # Check for network errors
    if any(term in error_str for term in ["connection", "network", "dns", "ssl"]):
        return EdgarNetworkError(str(exc), cause=exc)

    # Check for parse errors
    if any(term in error_str for term in ["parse", "invalid", "malformed"]):
        return EdgarParseError(str(exc), cause=exc)

    # Default to generic EdgarError
    return EdgarError(str(exc), cause=exc)
