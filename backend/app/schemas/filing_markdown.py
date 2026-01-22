"""
Filing Markdown Response Schemas

Pydantic models for the 10-Q markdown API endpoint.
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class FilingMetadata(BaseModel):
    """Metadata about the filing"""
    ticker: str = Field(..., description="Stock ticker symbol")
    company_name: str = Field(..., description="Company name")
    filing_type: str = Field(..., description="Filing type (10-Q, 10-Q/A)")
    fiscal_period: str = Field("", description="Fiscal period (e.g., Q3 2024)")
    sections_extracted: List[str] = Field(
        default_factory=list,
        description="List of section types successfully extracted"
    )


class FilingMarkdownResponse(BaseModel):
    """Response schema for the filing markdown endpoint"""
    filing_date: str = Field(..., description="Date the filing was submitted to SEC")
    accession_number: str = Field(..., description="SEC accession number")
    markdown_content: str = Field(..., description="Clean, AI-ready markdown content")
    metadata: FilingMetadata = Field(..., description="Filing metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "filing_date": "2024-01-26",
                "accession_number": "0000320193-24-000006",
                "markdown_content": "# Apple Inc. - 10-Q (Q1 2024)\n\n## Filing Information\n...",
                "metadata": {
                    "ticker": "AAPL",
                    "company_name": "Apple Inc.",
                    "filing_type": "10-Q",
                    "fiscal_period": "Q1 2024",
                    "sections_extracted": [
                        "financial_statements",
                        "mdna",
                        "market_risk",
                        "controls",
                        "risk_factors"
                    ]
                }
            }
        }


class FilingListItem(BaseModel):
    """A single filing in the list response"""
    filing_type: str = Field(..., description="Filing type (10-Q, 10-Q/A)")
    filing_date: str = Field(..., description="Date filed with SEC")
    report_date: Optional[str] = Field(None, description="Period end date")
    accession_number: str = Field(..., description="SEC accession number")
    sec_url: str = Field(..., description="URL to view on SEC EDGAR")


class FilingListResponse(BaseModel):
    """Response schema for listing filings"""
    ticker: str = Field(..., description="Stock ticker symbol")
    company_name: str = Field(..., description="Company name")
    cik: str = Field(..., description="SEC CIK number")
    filings: List[FilingListItem] = Field(..., description="List of filings")
    total: int = Field(..., description="Total number of filings returned")


class FilingErrorResponse(BaseModel):
    """Error response schema"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    ticker: Optional[str] = Field(None, description="Ticker that caused the error")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "CompanyNotFound",
                "message": "Company not found for ticker: INVALID",
                "ticker": "INVALID"
            }
        }
