#!/usr/bin/env python3
"""
Verification Script: SEC Filing Extraction Fix
================================================
This script verifies that the extraction fix is working correctly by:
1. Fetching a real SEC filing (AAPL 10-Q)
2. Running the extract_critical_sections() function
3. Checking that financial data is present in the extracted text
4. Reporting pass/fail status

Usage:
    python scripts/verify_extraction_fix.py

Expected Output:
    - Financial Statements section should be extracted
    - Revenue/Net Sales figures should be present
    - Net Income figures should be present
    - Pass/Fail status for each check
"""

import asyncio
import sys
import re
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.openai_service import OpenAIService
from app.services.sec_edgar import sec_edgar_service


# Financial keywords that MUST be present in a valid extraction
REQUIRED_KEYWORDS_10Q = [
    # Revenue indicators
    (r"(?:total\s+)?(?:net\s+)?(?:revenue|sales)", "Revenue/Sales"),
    # Income indicators
    (r"(?:net\s+)?(?:income|earnings|profit)", "Net Income/Earnings"),
    # Cash flow indicators (may not always be in condensed statements)
    (r"(?:cash\s+(?:flow|provided)|operating\s+activities)", "Cash Flow"),
]

FINANCIAL_FIGURES_PATTERN = r"\$?\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:\s*(?:million|billion|M|B))?"


def check_extraction(extracted_text: str, filing_type: str = "10-Q") -> dict:
    """
    Check if the extracted text contains required financial data.

    Returns a dict with pass/fail status for each check.
    """
    results = {
        "total_length": len(extracted_text),
        "checks": {},
        "all_passed": True,
        "financial_figures_found": [],
    }

    # Check for required keywords
    keywords = REQUIRED_KEYWORDS_10Q
    for pattern, name in keywords:
        match = re.search(pattern, extracted_text, re.IGNORECASE)
        results["checks"][name] = {
            "found": bool(match),
            "context": extracted_text[max(0, match.start()-50):match.end()+100] if match else None
        }
        if not match:
            results["all_passed"] = False

    # Check for financial section header
    financial_section_patterns = [
        r"ITEM\s*1\s*[-–—]?\s*(?:CONDENSED\s+)?(?:CONSOLIDATED\s+)?FINANCIAL\s+STATEMENTS",
        r"FINANCIAL\s+STATEMENTS",
        r"STATEMENTS?\s+OF\s+(?:OPERATIONS|INCOME|EARNINGS)",
    ]
    financial_section_found = False
    for pattern in financial_section_patterns:
        if re.search(pattern, extracted_text, re.IGNORECASE):
            financial_section_found = True
            break

    results["checks"]["Financial Section Header"] = {
        "found": financial_section_found,
        "context": None
    }
    if not financial_section_found:
        results["all_passed"] = False

    # Find all dollar figures
    figures = re.findall(FINANCIAL_FIGURES_PATTERN, extracted_text)
    results["financial_figures_found"] = figures[:20]  # First 20 figures

    results["checks"]["Dollar Figures Present"] = {
        "found": len(figures) > 5,
        "count": len(figures)
    }
    if len(figures) <= 5:
        results["all_passed"] = False

    return results


async def main():
    print("=" * 70)
    print("SEC Filing Extraction Verification Script")
    print("=" * 70)
    print()

    # Initialize services
    openai_service = OpenAIService()

    # Test with AAPL 10-Q
    print("1. Fetching AAPL 10-Q filing from SEC EDGAR...")
    print("-" * 50)

    try:
        # Get AAPL filings
        filings = await sec_edgar_service.get_filings("AAPL", filing_type="10-Q", count=1)

        if not filings:
            print("ERROR: No AAPL 10-Q filings found!")
            return False

        filing = filings[0]
        print(f"   Found filing: {filing.get('accession_number')}")
        print(f"   Filing date: {filing.get('filing_date')}")
        print(f"   Document URL: {filing.get('document_url')}")

        # Fetch the actual document
        print("\n2. Downloading filing document...")
        print("-" * 50)

        filing_text = await sec_edgar_service.get_filing_document(filing.get('document_url'))

        if not filing_text:
            print("ERROR: Could not download filing document!")
            return False

        print(f"   Downloaded {len(filing_text):,} characters")

        # Run extraction
        print("\n3. Running extract_critical_sections()...")
        print("-" * 50)

        extracted = openai_service.extract_critical_sections(filing_text, "10-Q")

        print(f"   Extracted {len(extracted):,} characters")

        # Check extraction results
        print("\n4. Verifying extraction quality...")
        print("-" * 50)

        results = check_extraction(extracted, "10-Q")

        # Print results
        print("\n   EXTRACTION CHECKS:")
        for check_name, check_result in results["checks"].items():
            status = "PASS" if check_result.get("found") else "FAIL"
            print(f"   [{status}] {check_name}")
            if check_result.get("context"):
                context = check_result["context"][:100].replace("\n", " ")
                print(f"         Context: ...{context}...")
            if check_result.get("count"):
                print(f"         Count: {check_result['count']}")

        # Print sample financial figures
        if results["financial_figures_found"]:
            print(f"\n   Sample financial figures found:")
            for fig in results["financial_figures_found"][:10]:
                print(f"      - {fig}")

        # Print first 500 chars of extracted text
        print("\n5. Sample of extracted text (first 1000 chars):")
        print("-" * 50)
        print(extracted[:1000])
        print("...")

        # Final verdict
        print("\n" + "=" * 70)
        if results["all_passed"]:
            print("VERIFICATION PASSED - Extraction fix is working correctly!")
            print("=" * 70)
            return True
        else:
            print("VERIFICATION FAILED - Some checks did not pass.")
            print("Review the output above to identify issues.")
            print("=" * 70)
            return False

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
