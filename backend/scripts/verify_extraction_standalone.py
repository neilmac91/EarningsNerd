#!/usr/bin/env python3
"""
Standalone Verification Script: SEC Filing Extraction Fix
==========================================================
This script verifies that the extraction fix patterns are working correctly
without needing the full app configuration.

Usage:
    python scripts/verify_extraction_standalone.py

"""

import asyncio
import sys
import re
import httpx
from bs4 import BeautifulSoup


# SEC EDGAR rate limiting
SEC_HEADERS = {
    "User-Agent": "EarningsNerd contact@earningsnerd.io",
    "Accept-Encoding": "gzip, deflate",
}


async def fetch_aapl_10q():
    """Fetch AAPL's latest 10-Q filing from SEC EDGAR."""
    print("Fetching AAPL company data from SEC EDGAR...")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get company submissions
        submissions_url = "https://data.sec.gov/submissions/CIK0000320193.json"
        resp = await client.get(submissions_url, headers=SEC_HEADERS)
        resp.raise_for_status()
        data = resp.json()

        # Find recent 10-Q filings
        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        accession_numbers = filings.get("accessionNumber", [])
        filing_dates = filings.get("filingDate", [])
        primary_docs = filings.get("primaryDocument", [])

        # Find first 10-Q
        for i, form in enumerate(forms):
            if form == "10-Q":
                accession = accession_numbers[i].replace("-", "")
                cik = "320193"
                doc = primary_docs[i]
                date = filing_dates[i]

                doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{doc}"
                print(f"Found 10-Q filed {date}: {doc_url}")

                # Fetch the actual document
                print("Downloading filing document...")
                doc_resp = await client.get(doc_url, headers=SEC_HEADERS)
                doc_resp.raise_for_status()
                return doc_resp.text, date

    return None, None


def extract_critical_sections_test(filing_text: str, filing_type: str = "10-Q") -> str:
    """
    This is the UPDATED extract_critical_sections logic.
    Copy of the fixed code for standalone testing.
    """
    filing_type_key = (filing_type or "10-K").upper()

    # Remove HTML/XML tags for cleaner extraction
    try:
        soup = BeautifulSoup(filing_text, 'html.parser')
        filing_text_clean = soup.get_text(separator='\n', strip=False)
    except (TypeError, ValueError, AttributeError) as e:
        # Fallback to raw text if HTML parsing fails
        print(f"Warning: HTML parsing failed ({e}), using raw text")
        filing_text_clean = filing_text

    critical_sections = []

    if filing_type_key == "10-Q":
        # PRIORITY 1: Extract Item 1 - Financial Statements (MOST CRITICAL for metrics)
        financial_patterns = [
            r"ITEM\s*1\.?\s*[-–—]?\s*(?:CONDENSED\s+)?(?:CONSOLIDATED\s+)?FINANCIAL\s+STATEMENTS[^\n]*\n(.*?)(?=ITEM\s*2|NOTES\s+TO|MANAGEMENT|$)",
            r"PART\s*I\s*[-–—]?\s*FINANCIAL\s+INFORMATION[^\n]*\n.*?ITEM\s*1\.?[^\n]*\n(.*?)(?=ITEM\s*2|MANAGEMENT|$)",
            r"CONDENSED\s+CONSOLIDATED\s+STATEMENTS\s+OF\s+(?:OPERATIONS|INCOME)[^\n]*\n(.*?)(?=ITEM\s*2|MANAGEMENT|$)",
            r"(?:CONDENSED\s+)?CONSOLIDATED\s+BALANCE\s+SHEETS?[^\n]*\n(.*?)(?=ITEM\s*2|MANAGEMENT|$)",
            r"FINANCIAL\s+STATEMENTS[^\n]*\n(.*?)(?=ITEM\s*2|MANAGEMENT['']?S|$)",
        ]
        for pattern in financial_patterns:
            match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.DOTALL | re.MULTILINE)
            if match:
                financial_text = match.group(1).strip()
                critical_sections.append(f"ITEM 1 - FINANCIAL STATEMENTS:\n{financial_text[:35000]}")
                break

        # If no financial statements found via patterns, try to find the actual tables
        if not any("FINANCIAL STATEMENTS" in s for s in critical_sections):
            table_patterns = [
                r"((?:CONDENSED\s+)?CONSOLIDATED\s+STATEMENTS?\s+OF\s+OPERATIONS.*?)(?=CONDENSED\s+CONSOLIDATED\s+BALANCE|ITEM\s*2|$)",
                r"((?:THREE|SIX|NINE)\s+MONTHS\s+ENDED.*?(?:Net\s+(?:income|loss)|Total\s+(?:revenue|net\s+sales)).*?)(?=ITEM\s*2|$)",
                r"(Revenue[s]?\s*[\$\d,\.]+.*?(?:Net\s+income|Earnings\s+per\s+share).*?)(?=ITEM\s*2|$)",
            ]
            for pattern in table_patterns:
                match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.DOTALL | re.MULTILINE)
                if match:
                    financial_text = match.group(1).strip()
                    critical_sections.append(f"FINANCIAL DATA:\n{financial_text[:35000]}")
                    break

        # PRIORITY 2: Extract Item 2 - MD&A
        mda_patterns = [
            r"ITEM\s*2\.?\s*[-–—]?\s*MANAGEMENT['']?S?\s+DISCUSSION[^\n]*\n(.*?)(?=ITEM\s*3|ITEM\s*4|QUANTITATIVE|CONTROLS|$)",
            r"ITEM\s*2\.?\s*MANAGEMENT['']?S?\s+DISCUSSION\s+AND\s+ANALYSIS[^\n]*\n(.*?)(?=ITEM\s*3|ITEM\s*4|$)",
            r"MANAGEMENT['']?S?\s+DISCUSSION\s+AND\s+ANALYSIS\s+OF\s+FINANCIAL[^\n]*\n(.*?)(?=ITEM\s*3|QUANTITATIVE|CONTROLS|$)",
        ]
        for pattern in mda_patterns:
            match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.DOTALL | re.MULTILINE)
            if match:
                mda_text = match.group(1).strip()
                critical_sections.append(f"ITEM 2 - MANAGEMENT'S DISCUSSION AND ANALYSIS:\n{mda_text[:30000]}")
                break

        # PRIORITY 3: Extract Item 1A - Risk Factors
        risk_patterns = [
            r"ITEM\s*1A\.?\s*[-–—]?\s*RISK\s+FACTORS[^\n]*\n(.*?)(?=ITEM\s*2|ITEM\s*3|PART\s*II|$)",
            r"RISK\s+FACTORS[^\n]*\n(.*?)(?=ITEM\s*2|LEGAL|PART\s*II|$)",
        ]
        for pattern in risk_patterns:
            match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.DOTALL | re.MULTILINE)
            if match:
                risk_text = match.group(1).strip()
                critical_sections.append(f"ITEM 1A - RISK FACTORS:\n{risk_text[:15000]}")
                break

    # Combine all critical sections
    if critical_sections:
        combined = "\n\n" + "="*50 + "\n\n".join(critical_sections)
        print(f"Extracted {len(critical_sections)} critical sections, total {len(combined):,} chars")
        return combined
    else:
        # Enhanced fallback
        print("WARNING: No sections found via patterns, using enhanced fallback extraction")

        financial_keywords = [
            "total revenue", "net revenue", "net sales", "total net sales",
            "net income", "net earnings", "earnings per share", "diluted eps",
            "operating income", "gross profit", "cash flow", "total assets"
        ]

        best_start = 0
        best_score = 0
        chunk_size = 50000

        for i in range(0, min(len(filing_text_clean), 200000), 10000):
            chunk = filing_text_clean[i:i+chunk_size].lower()
            score = sum(1 for kw in financial_keywords if kw in chunk)
            if score > best_score:
                best_score = score
                best_start = i

        if best_score > 2:
            print(f"Fallback found {best_score} financial keywords at offset {best_start}")
            return filing_text_clean[best_start:best_start+chunk_size]

        print("WARNING: Using last-resort fallback: first 50000 chars of document")
        return filing_text_clean[:50000]


def check_extraction(extracted_text: str) -> dict:
    """Check if the extracted text contains required financial data."""
    results = {
        "total_length": len(extracted_text),
        "checks": {},
        "all_passed": True,
    }

    # Check for required keywords
    keywords = [
        (r"(?:total\s+)?(?:net\s+)?(?:revenue|sales)", "Revenue/Sales"),
        (r"(?:net\s+)?(?:income|earnings|profit)", "Net Income/Earnings"),
        (r"(?:cash\s+(?:flow|provided)|operating\s+activities)", "Cash Flow"),
    ]

    for pattern, name in keywords:
        match = re.search(pattern, extracted_text, re.IGNORECASE)
        results["checks"][name] = {
            "found": bool(match),
            "context": extracted_text[max(0, match.start()-30):match.end()+70].replace("\n", " ")[:100] if match else None
        }
        if not match:
            results["all_passed"] = False

    # Check for financial section header
    financial_section_patterns = [
        r"ITEM\s*1\s*[-–—]?\s*(?:CONDENSED\s+)?(?:CONSOLIDATED\s+)?FINANCIAL\s+STATEMENTS",
        r"FINANCIAL\s+STATEMENTS",
        r"FINANCIAL\s+DATA",
        r"STATEMENTS?\s+OF\s+(?:OPERATIONS|INCOME|EARNINGS)",
    ]
    financial_section_found = False
    for pattern in financial_section_patterns:
        if re.search(pattern, extracted_text, re.IGNORECASE):
            financial_section_found = True
            break

    results["checks"]["Financial Section Header"] = {"found": financial_section_found}
    if not financial_section_found:
        results["all_passed"] = False

    # Find all dollar figures
    figures = re.findall(r"\$?\d{1,3}(?:,\d{3})*(?:\.\d+)?", extracted_text)
    results["dollar_figures_count"] = len(figures)
    results["checks"]["Dollar Figures Present (>5)"] = {
        "found": len(figures) > 5,
        "count": len(figures)
    }
    if len(figures) <= 5:
        results["all_passed"] = False

    return results


async def main():
    print("=" * 70)
    print("SEC Filing Extraction Fix - Standalone Verification")
    print("=" * 70)
    print()

    try:
        # Fetch AAPL 10-Q
        filing_text, filing_date = await fetch_aapl_10q()

        if not filing_text:
            print("ERROR: Could not fetch AAPL 10-Q!")
            return False

        print(f"\nDownloaded filing: {len(filing_text):,} characters")

        # Run extraction
        print("\n" + "-" * 50)
        print("Running extract_critical_sections()...")
        print("-" * 50)

        extracted = extract_critical_sections_test(filing_text, "10-Q")

        # Check extraction results
        print("\n" + "-" * 50)
        print("Verifying extraction quality...")
        print("-" * 50)

        results = check_extraction(extracted)

        # Print results
        print("\nEXTRACTION CHECKS:")
        for check_name, check_result in results["checks"].items():
            status = "PASS" if check_result.get("found") else "FAIL"
            emoji = "✓" if check_result.get("found") else "✗"
            print(f"  [{emoji}] {status}: {check_name}")
            if check_result.get("context"):
                print(f"       Context: ...{check_result['context']}...")
            if check_result.get("count"):
                print(f"       Count: {check_result['count']}")

        # Print sample of extracted text
        print("\n" + "-" * 50)
        print("Sample of extracted text (first 1500 chars):")
        print("-" * 50)
        print(extracted[:1500])
        print("...")

        # Final verdict
        print("\n" + "=" * 70)
        if results["all_passed"]:
            print("✓ VERIFICATION PASSED - Extraction fix is working correctly!")
            print("=" * 70)
            return True
        else:
            print("✗ VERIFICATION FAILED - Some checks did not pass.")
            print("  Review the output above to identify issues.")
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
