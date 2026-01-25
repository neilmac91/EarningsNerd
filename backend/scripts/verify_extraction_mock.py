#!/usr/bin/env python3
"""
Mock Verification Script: SEC Filing Extraction Fix
====================================================
This script verifies the extraction fix using mock filing content.
This allows testing without network access.

Usage:
    python scripts/verify_extraction_mock.py
"""

import re
from bs4 import BeautifulSoup


# Mock 10-Q filing content simulating Apple's structure
MOCK_10Q_FILING = """
<html>
<head><title>Apple Inc. 10-Q</title></head>
<body>

<div>
UNITED STATES SECURITIES AND EXCHANGE COMMISSION
Washington, D.C. 20549
FORM 10-Q

QUARTERLY REPORT PURSUANT TO SECTION 13 OR 15(d) OF THE SECURITIES EXCHANGE ACT OF 1934
For the quarterly period ended July 1, 2023

Apple Inc.
</div>

<div>
PART I — FINANCIAL INFORMATION

ITEM 1. CONDENSED CONSOLIDATED FINANCIAL STATEMENTS

APPLE INC.
CONDENSED CONSOLIDATED STATEMENTS OF OPERATIONS (Unaudited)
(In millions, except number of shares which are reflected in thousands and per share amounts)

                                          Three Months Ended    Six Months Ended
                                          July 1,   June 25,   July 1,   June 25,
                                           2023      2022       2023      2022

Net sales:
  Products                               $60,584   $63,355   $133,299  $147,118
  Services                                21,213    19,604     42,033    39,242
    Total net sales                       81,797    82,959    175,332   186,360

Cost of sales:
  Products                                38,877    41,179     85,694    95,040
  Services                                 6,060     5,739     11,821    11,466
    Total cost of sales                   44,937    46,918     97,515   106,506

Gross margin                              36,860    36,041     77,817    79,854

Operating expenses:
  Research and development                 7,442     6,797     14,720    13,408
  Selling, general and administrative      5,973     6,012     12,029    12,260
    Total operating expenses              13,415    12,809     26,749    25,668

Operating income                          23,445    23,232     51,068    54,186

Other income/(expense), net                 (265)     (10)       (219)     (358)

Income before provision for income taxes  23,180    23,222     50,849    53,828

Provision for income taxes                 2,852     3,624      6,884     8,212

Net income                               $20,328   $19,598    $43,965   $45,616

Earnings per share:
  Basic                                    $1.27     $1.20      $2.74     $2.79
  Diluted                                  $1.26     $1.20      $2.73     $2.78

Shares used in computing earnings per share:
  Basic                                15,697,614 16,262,443 16,026,854 16,335,252
  Diluted                              15,775,021 16,365,351 16,107,785 16,435,093
</div>

<div>
APPLE INC.
CONDENSED CONSOLIDATED BALANCE SHEETS (Unaudited)
(In millions, except number of shares which are reflected in thousands and par value)

                                              July 1,    September 24,
                                               2023         2022
ASSETS:
Current assets:
  Cash and cash equivalents                  $28,408       $23,646
  Marketable securities                       31,185        24,658
  Accounts receivable, net                    22,710        28,184
  Inventories                                  7,351         4,946
  Vendor non-trade receivables               20,231        32,748
  Other current assets                        14,413        16,422
    Total current assets                     124,298       130,604

Non-current assets:
  Marketable securities                      104,461       120,805
  Property, plant and equipment, net          43,550        42,117
  Other non-current assets                    65,378        60,924
    Total non-current assets                 213,389       223,846

Total assets                                $337,687      $354,450

LIABILITIES AND SHAREHOLDERS' EQUITY:
Current liabilities:
  Accounts payable                           $46,699       $64,115
  Other current liabilities                   62,393        60,845
  Deferred revenue                             8,154         7,912
  Commercial paper                            5,985         9,982
  Term debt                                   10,944         9,822
    Total current liabilities               134,175       152,676

Non-current liabilities:
  Term debt                                   95,281        98,959
  Other non-current liabilities               51,823        49,142
    Total non-current liabilities           147,104       148,101

Total liabilities                           281,279       300,777

Shareholders' equity:
  Common stock and additional paid-in capital  68,184        64,849
  Retained earnings/(Accumulated deficit)    (11,776)      (11,176)
    Total shareholders' equity                56,408        53,673

Total liabilities and shareholders' equity  $337,687      $354,450
</div>

<div>
APPLE INC.
CONDENSED CONSOLIDATED STATEMENTS OF CASH FLOWS (Unaudited)
(In millions)

                                                     Six Months Ended
                                                    July 1,    June 25,
                                                     2023       2022

Cash, cash equivalents and restricted cash,
  beginning balances                               $24,977    $35,929

Operating activities:
  Net income                                        43,965     45,616
  Adjustments to reconcile net income:
    Depreciation and amortization                    5,631      5,569
    Share-based compensation expense                 4,973      3,989
    Other                                           (1,236)     (527)
  Changes in operating assets and liabilities:
    Accounts receivable, net                         5,474     (2,117)
    Inventories                                     (2,405)    (1,269)
    Vendor non-trade receivables                    12,517      7,992
    Other current and non-current assets             3,456       (55)
    Accounts payable                               (17,416)   (13,453)
    Other current and non-current liabilities        3,893      3,920
      Cash generated by operating activities        58,852     49,665

Investing activities:
  Purchases of marketable securities               (19,377)   (15,379)
  Proceeds from maturities of marketable securities 22,854     21,990
  Proceeds from sales of marketable securities       4,858      9,831
  Payments for acquisition of property, plant
    and equipment                                   (5,432)    (5,538)
  Other                                              (413)      (582)
      Cash generated by investing activities         2,490     10,322

Financing activities:
  Payments for taxes related to net share settlement
    of equity awards                                (2,876)    (4,206)
  Payments for dividends and dividend equivalents   (7,495)    (7,326)
  Repurchases of common stock                      (46,547)   (52,037)
  Proceeds from issuance of term debt                  —       5,465
  Repayments of term debt                           (1,000)    (3,750)
  Other                                               (46)       (63)
      Cash used in financing activities            (57,964)   (61,917)

Increase/(Decrease) in cash, cash equivalents and
  restricted cash                                    3,378     (1,930)

Cash, cash equivalents and restricted cash,
  ending balances                                  $28,355    $34,001
</div>

<div>
ITEM 2. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS

Fiscal 2023 Third Quarter Highlights

Total net sales decreased 1% or $1.2 billion during the third quarter of 2023 compared to the same quarter in 2022, driven by lower Products net sales, partially offset by higher Services net sales.

Products net sales decreased $2.8 billion or 4% during the third quarter of 2023 compared to the same quarter in 2022. The decrease was primarily driven by lower net sales of Mac and iPad, partially offset by higher net sales of iPhone.

Services net sales increased $1.6 billion or 8% during the third quarter of 2023 compared to the same quarter in 2022. The increase was primarily driven by higher net sales from advertising, the App Store and cloud services.

Results of Operations

Net Sales

Net sales decreased $1.2 billion or 1% during the third quarter of 2023 compared to the same quarter in 2022.

The following table shows net sales by category (in millions):

                      Three Months Ended
                    July 1, 2023  June 25, 2022  Change
iPhone               $42,626       $40,665        5%
Mac                   $6,840        $7,382       (7)%
iPad                  $5,791        $7,224      (20)%
Wearables, Home
  and Accessories     $8,284        $8,084        2%
Services             $21,213       $19,604        8%

Total net sales      $81,797       $82,959       (1)%

Gross Margin

Products gross margin percentage decreased during the third quarter of 2023 compared to the same quarter in 2022 due to the different mix of Products net sales, partially offset by cost savings.

Services gross margin percentage increased during the third quarter of 2023 compared to the same quarter in 2022 primarily driven by a different mix of Services net sales.

The Company's total gross margin was 45.0% and 43.4% for the third quarter of 2023 and 2022, respectively.

Operating Expenses

Total operating expenses increased $606 million or 5% during the third quarter of 2023 compared to the same quarter in 2022.

Research and development expense increased $645 million or 9% during the third quarter of 2023 compared to the same quarter in 2022 due primarily to increases in headcount-related expenses.

Liquidity and Capital Resources

The Company believes its balances of cash, cash equivalents and unrestricted marketable securities, which totaled $166.6 billion as of July 1, 2023, along with cash generated by ongoing operations and continued access to debt markets, will be sufficient to satisfy its cash requirements.

During the six months ended July 1, 2023, the Company generated $58.9 billion in cash from operating activities and received proceeds of $27.7 billion from maturities and sales of marketable securities.

The Company's capital expenditures were $5.4 billion during the six months ended July 1, 2023.

During the six months ended July 1, 2023, the Company repurchased $46.5 billion of its common stock and paid dividends and dividend equivalents of $7.5 billion.
</div>

<div>
ITEM 1A. RISK FACTORS

The Company's business, reputation, results of operations, financial condition and stock price can be affected by a number of factors, whether currently known or unknown, including those described below. When any one or more of these risks materialize from time to time, the Company's business, reputation, results of operations, financial condition and stock price can be materially and adversely affected.

Global and regional economic conditions could materially adversely affect the Company.

The Company has international operations with sales outside the U.S. representing a majority of the Company's total net sales. In addition, a portion of the Company's supply chain, and certain component suppliers, are located outside the U.S. As a result, the Company's business and operating results are subject to the risks of international business operations, including global and regional economic conditions.

The technology industry is highly competitive and the Company faces substantial competition.

The technology industry is highly competitive and the Company faces substantial competition in all of its product and service categories. The Company's competitors have increased significantly in recent years, and new competitors may enter the market at any time.

The Company's business can be affected by changes to foreign currency exchange rates.

The Company uses derivative instruments to partially offset its business exposure to foreign currency exchange risk. However, there is no guarantee that the Company's hedging activities will be effective.
</div>

<div>
ITEM 4. CONTROLS AND PROCEDURES

Evaluation of Disclosure Controls and Procedures

Based on an evaluation under the supervision and with the participation of the Company's management, the Company's principal executive officer and principal financial officer have concluded that the Company's disclosure controls and procedures as defined in Rules 13a-15(e) and 15d-15(e) under the Exchange Act were effective as of July 1, 2023.
</div>

<div>
PART II — OTHER INFORMATION

ITEM 1. LEGAL PROCEEDINGS

The Company is subject to various legal proceedings and claims that have arisen in the ordinary course of business. The Company does not expect any material impact on its results of operations from any ongoing legal proceedings.

ITEM 6. EXHIBITS

See Exhibit Index.
</div>

<div>
SIGNATURES

Pursuant to the requirements of the Securities Exchange Act of 1934, the Registrant has duly caused this report to be signed on its behalf by the undersigned thereunto duly authorized.

Date: August 4, 2023

APPLE INC.

By: /s/ Luca Maestri
    Luca Maestri
    Senior Vice President, Chief Financial Officer
</div>

</body>
</html>
"""


def extract_critical_sections_test(filing_text: str, filing_type: str = "10-Q") -> str:
    """
    This is the UPDATED extract_critical_sections logic.
    Copy of the fixed code for testing.
    """
    filing_type_key = (filing_type or "10-K").upper()

    # Remove HTML/XML tags for cleaner extraction
    try:
        soup = BeautifulSoup(filing_text, 'html.parser')
        filing_text_clean = soup.get_text(separator='\n', strip=False)
    except:
        filing_text_clean = filing_text

    critical_sections = []

    if filing_type_key == "10-Q":
        # PRIORITY 1: Extract Item 1 - Financial Statements (MOST CRITICAL for metrics)
        # FIXED: Use more specific lookaheads to avoid matching "MANAGEMENT" in content
        financial_patterns = [
            # Match Item 1 header, capture everything until Item 2 header
            r"ITEM\s*1\.?\s*[-–—]?\s*(?:CONDENSED\s+)?(?:CONSOLIDATED\s+)?FINANCIAL\s+STATEMENTS[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.?\s*[-–—]?\s*MANAGEMENT|\nITEM\s*2\.)",
            r"PART\s*I\s*[-–—]?\s*FINANCIAL\s+INFORMATION[^\n]*\n[\s\S]*?ITEM\s*1\.?[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.?\s*[-–—]?\s*MANAGEMENT|\nITEM\s*2\.)",
            r"CONDENSED\s+CONSOLIDATED\s+STATEMENTS\s+OF\s+(?:OPERATIONS|INCOME)[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.?\s*[-–—]?\s*MANAGEMENT|\nITEM\s*2\.)",
            r"(?:CONDENSED\s+)?CONSOLIDATED\s+BALANCE\s+SHEETS?[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.?\s*[-–—]?\s*MANAGEMENT|\nITEM\s*2\.)",
            r"FINANCIAL\s+STATEMENTS[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.?\s*[-–—]?\s*MANAGEMENT|\nITEM\s*2\.)",
        ]
        for pattern in financial_patterns:
            match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.MULTILINE)
            if match:
                financial_text = match.group(1).strip()
                critical_sections.append(f"ITEM 1 - FINANCIAL STATEMENTS:\n{financial_text[:35000]}")
                break

        # If no financial statements found via patterns, try to find the actual tables
        if not any("FINANCIAL STATEMENTS" in s for s in critical_sections):
            table_patterns = [
                r"((?:CONDENSED\s+)?CONSOLIDATED\s+STATEMENTS?\s+OF\s+OPERATIONS[\s\S]*?)(?=CONDENSED\s+CONSOLIDATED\s+BALANCE|\nITEM\s*2\.)",
                r"((?:THREE|SIX|NINE)\s+MONTHS\s+ENDED[\s\S]*?(?:Net\s+(?:income|loss)|Total\s+(?:revenue|net\s+sales))[\s\S]*?)(?=\nITEM\s*2\.)",
                r"(Revenue[s]?\s*[\$\d,\.]+[\s\S]*?(?:Net\s+income|Earnings\s+per\s+share)[\s\S]*?)(?=\nITEM\s*2\.)",
            ]
            for pattern in table_patterns:
                match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.MULTILINE)
                if match:
                    financial_text = match.group(1).strip()
                    critical_sections.append(f"FINANCIAL DATA:\n{financial_text[:35000]}")
                    break

        # PRIORITY 2: Extract Item 2 - MD&A
        # FIXED: Use [\s\S]*? for multiline matching and more specific lookaheads
        mda_patterns = [
            r"ITEM\s*2\.?\s*[-–—]?\s*MANAGEMENT['']?S?\s+DISCUSSION[^\n]*\n([\s\S]*?)(?=\nITEM\s*3\.?\s*[-–—]?|\nITEM\s*4\.?\s*[-–—]?|\nITEM\s*1A\.?\s*[-–—]?|\nPART\s*II|$)",
            r"ITEM\s*2\.?\s*MANAGEMENT['']?S?\s+DISCUSSION\s+AND\s+ANALYSIS[^\n]*\n([\s\S]*?)(?=\nITEM\s*3\.|\nITEM\s*4\.|\nITEM\s*1A\.|\nPART\s*II|$)",
            r"MANAGEMENT['']?S?\s+DISCUSSION\s+AND\s+ANALYSIS\s+OF\s+FINANCIAL[^\n]*\n([\s\S]*?)(?=\nITEM\s*3\.|\nITEM\s*1A\.|\nPART\s*II|$)",
        ]
        for pattern in mda_patterns:
            match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.MULTILINE)
            if match:
                mda_text = match.group(1).strip()
                critical_sections.append(f"ITEM 2 - MANAGEMENT'S DISCUSSION AND ANALYSIS:\n{mda_text[:30000]}")
                break

        # PRIORITY 3: Extract Item 1A - Risk Factors
        # FIXED: Use [\s\S]*? for multiline matching
        risk_patterns = [
            r"ITEM\s*1A\.?\s*[-–—]?\s*RISK\s+FACTORS[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.|\nITEM\s*3\.|\nPART\s*II|$)",
            r"RISK\s+FACTORS[^\n]*\n([\s\S]*?)(?=\nITEM\s*2\.|\nLEGAL|\nPART\s*II|$)",
        ]
        for pattern in risk_patterns:
            match = re.search(pattern, filing_text_clean, re.IGNORECASE | re.MULTILINE)
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
        print("WARNING: No sections found via patterns")
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
        (r"(?:cash\s+(?:flow|provided|generated)|operating\s+activities)", "Cash Flow"),
        (r"earnings\s+per\s+share", "EPS"),
        (r"gross\s+margin", "Gross Margin"),
    ]

    for pattern, name in keywords:
        match = re.search(pattern, extracted_text, re.IGNORECASE)
        results["checks"][name] = {
            "found": bool(match),
            "context": extracted_text[max(0, match.start()-30):match.end()+50].replace("\n", " ")[:80] if match else None
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

    # Check for MD&A section
    mda_found = bool(re.search(r"MANAGEMENT.*DISCUSSION|MD&A", extracted_text, re.IGNORECASE))
    results["checks"]["MD&A Section"] = {"found": mda_found}
    if not mda_found:
        results["all_passed"] = False

    # Find all dollar figures
    figures = re.findall(r"\$?\d{1,3}(?:,\d{3})*(?:\.\d+)?", extracted_text)
    results["dollar_figures_count"] = len(figures)
    results["checks"]["Dollar Figures Present (>10)"] = {
        "found": len(figures) > 10,
        "count": len(figures)
    }
    if len(figures) <= 10:
        results["all_passed"] = False

    # Check for specific Apple financial data
    apple_checks = [
        (r"\$?81,?797", "Total Net Sales ($81,797M)"),
        (r"\$?20,?328", "Net Income ($20,328M)"),
        (r"\$?1\.26", "Diluted EPS ($1.26)"),
        (r"\$?58,?852", "Operating Cash Flow ($58,852M)"),
    ]
    for pattern, name in apple_checks:
        match = re.search(pattern, extracted_text)
        results["checks"][name] = {"found": bool(match)}

    return results


def main():
    print("=" * 70)
    print("SEC Filing Extraction Fix - Mock Verification")
    print("=" * 70)
    print()

    print("Using mock AAPL 10-Q filing content...")
    print(f"Mock filing size: {len(MOCK_10Q_FILING):,} characters")

    # Run extraction
    print("\n" + "-" * 50)
    print("Running extract_critical_sections()...")
    print("-" * 50)

    extracted = extract_critical_sections_test(MOCK_10Q_FILING, "10-Q")

    # Check extraction results
    print("\n" + "-" * 50)
    print("Verifying extraction quality...")
    print("-" * 50)

    results = check_extraction(extracted)

    # Print results
    print("\nEXTRACTION CHECKS:")
    passed_count = 0
    failed_count = 0
    for check_name, check_result in results["checks"].items():
        status = "PASS" if check_result.get("found") else "FAIL"
        emoji = "✓" if check_result.get("found") else "✗"
        print(f"  [{emoji}] {status}: {check_name}")
        if check_result.get("found"):
            passed_count += 1
        else:
            failed_count += 1
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
    print(f"Results: {passed_count} passed, {failed_count} failed")
    print("=" * 70)

    if results["all_passed"]:
        print("✓ VERIFICATION PASSED - Extraction fix is working correctly!")
        print()
        print("Key improvements verified:")
        print("  1. Financial Statements (Item 1) are now extracted")
        print("  2. Revenue/Net Sales data is captured")
        print("  3. Net Income data is captured")
        print("  4. Cash Flow data is captured")
        print("  5. EPS data is captured")
        print("  6. MD&A section is included")
        print()
        print("The 'Not Disclosed' issue should now be resolved!")
        return True
    else:
        print("✗ VERIFICATION FAILED - Some checks did not pass.")
        print("  Review the output above to identify issues.")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
