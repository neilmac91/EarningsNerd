# Filing Summary Generation - Comprehensive Improvement Plan

**Document Version:** 1.0
**Created:** 2026-01-25
**Status:** Ready for Implementation
**Priority:** CRITICAL - Business Impact

---

## Executive Summary

The filing summary generation feature is experiencing critical failures resulting in poor user experience. This document outlines the root causes, corrective actions, and implementation plan to achieve professional-grade financial analysis output.

### Current State (Unacceptable)
- "2/7 sections populated" for major companies like Apple
- Revenue/Net Income showing "Not available" or "$0.00M"
- Empty section tabs (Risks, MD&A, Guidance, etc.)
- AI analysis timing out consistently

### Target State (Professional Grade)
- 6/7+ sections populated for all 10-K/10-Q filings
- Accurate financial metrics with period-over-period comparisons
- Extracted risk factors with supporting evidence from filing
- MD&A insights directly quoted from management commentary
- All data is **objective and factual** - no opinions or predictions

---

## CRITICAL REQUIREMENT: Objectivity

### The Summary Must NEVER:
- Make investment recommendations ("buy," "sell," "hold")
- Predict future performance ("likely to grow," "expected to decline")
- Use subjective adjectives ("strong," "weak," "impressive," "concerning")
- Express opinions ("management seems confident," "this is good news")
- Speculate beyond what is explicitly stated in the filing

### The Summary MUST:
- Present only facts extracted directly from SEC filings
- Quote management statements verbatim when summarizing MD&A
- Cite specific filing sections (e.g., "Item 1A: Risk Factors")
- Use neutral language ("increased," "decreased," "unchanged")
- Include specific numbers with their reporting periods
- Distinguish between GAAP and non-GAAP metrics when applicable

### Example: Correct vs. Incorrect Output

**INCORRECT (Subjective):**
```
Apple reported strong revenue growth, demonstrating impressive market
resilience. The company's excellent management of supply chain issues
suggests continued success in the coming quarters.
```

**CORRECT (Objective):**
```
Apple reported revenue of $83.0B for Q3 FY2022, an increase of 2% compared
to $81.4B in Q3 FY2021. Per Item 7 (MD&A), management stated: "We experienced
supply constraints during the quarter that we estimate reduced revenue by
approximately $4 billion."
```

---

## Root Cause Analysis

### Bug #1: XBRL Accession Number Filter Fails Silently
**Location:** `backend/app/services/xbrl_service.py:87-94`

**Problem:** The accession number filter assumes the SEC API always includes an "accn" field in data items. When this field is missing or formatted differently, the filter returns no matches and falls back to the most recent 5 periods for the entire company - which may be from completely different filings.

**Evidence:**
```python
matching = [
    item for item in sorted_items
    if item.get("accn", "").replace("-", "") == normalized_accession
]
# If "accn" field doesn't exist, item.get("accn", "") returns ""
# "" != normalized_accession, so matching = []
# Falls back to wrong period data
```

**Impact:** Returns data from 2024-2025 for a 2022 filing request.

---

### Bug #2: Empty Dict Treated as Falsy
**Location:** `backend/app/services/fallback_summary.py:157`

**Problem:** In Python, an empty dictionary `{}` evaluates to `False` in boolean context. When XBRL extraction returns `{}` (all empty arrays), the fallback function skips processing entirely.

**Evidence:**
```python
if xbrl_data:  # {} is falsy - this entire block is SKIPPED
    # Process XBRL data...
    has_xbrl_data = True

# has_xbrl_data stays False, shows "Not available"
```

**Impact:** Even when XBRL service returns a result, empty arrays cause complete data loss.

---

### Bug #3: Limited GAAP Field Name Coverage
**Location:** `backend/app/services/xbrl_service.py:109`

**Problem:** Only 3 revenue field names are checked:
- `Revenues`
- `RevenueFromContractWithCustomerExcludingAssessedTax`
- `SalesRevenueNet`

Major companies like Apple may use different GAAP taxonomy fields.

**Impact:** Revenue extraction fails for companies using non-standard field names.

---

### Bug #4: Frontend Displays $0.00M for Missing Data
**Location:** Frontend chart components

**Problem:** When data is `null` or `undefined`, the frontend formats it as `$0.00M` instead of showing "Not available" or "N/A".

**Impact:** Users see misleading zero values instead of clear indication of missing data.

---

### Bug #5: AI Timeout Too Aggressive
**Location:** `backend/app/routers/summaries.py:547`

**Problem:** The 75-second timeout is still insufficient for complex filings that require:
1. Structured extraction (30-45s)
2. Missing section recovery (12s each × N sections)
3. Editorial markdown generation (18s)

**Impact:** AI analysis times out before completion, triggering low-quality fallback.

---

## Implementation Plan

### Phase 1: Critical Bug Fixes (P0)

#### 1.1 Fix Empty Dict Handling
**File:** `backend/app/services/fallback_summary.py`
**Lines:** Around 157

**Current Code:**
```python
if xbrl_data:
    # Process XBRL...
```

**Fixed Code:**
```python
def has_valid_xbrl_data(xbrl_data: Optional[Dict]) -> bool:
    """Check if XBRL data contains actual metric values."""
    if not xbrl_data:
        return False
    if not isinstance(xbrl_data, dict):
        return False
    # Check if any metric has actual data
    for key in ['revenue', 'net_income', 'earnings_per_share']:
        metric = xbrl_data.get(key, {})
        if isinstance(metric, dict) and metric.get('current', {}).get('value'):
            return True
        # Also check if it's a list with items
        if isinstance(metric, list) and len(metric) > 0:
            return True
    return False

# Usage:
has_xbrl_data = has_valid_xbrl_data(xbrl_data)
```

**Owner:** Backend Developer Agent
**Effort:** 30 minutes
**Testing:** Verify Apple 10-Q returns `has_xbrl_data=True` when data exists

---

#### 1.2 Expand GAAP Revenue Field Names
**File:** `backend/app/services/xbrl_service.py`
**Lines:** 109

**Current Code:**
```python
for revenue_key in ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"]:
```

**Fixed Code:**
```python
# Comprehensive list of revenue field names used by major companies
REVENUE_FIELD_NAMES = [
    # Standard revenue fields
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomer",
    # Net revenue variations
    "NetRevenues",
    "TotalRevenue",
    "TotalRevenues",
    "TotalNetRevenues",
    # Product/Service breakdowns
    "SalesRevenueGoodsNet",
    "SalesRevenueServicesNet",
    "RevenueFromSalesOfGoods",
    "RevenueFromServices",
    # Other variations
    "OperatingRevenue",
    "RegulatedAndUnregulatedOperatingRevenue",
]

for revenue_key in REVENUE_FIELD_NAMES:
    if revenue_key in us_gaap:
        # ... extraction logic
```

**Owner:** Backend Developer Agent
**Effort:** 30 minutes
**Testing:** Verify revenue extraction works for Apple, Microsoft, Google, Amazon

---

#### 1.3 Add Diagnostic Logging for XBRL Filter
**File:** `backend/app/services/xbrl_service.py`
**Lines:** 87-97

**Add Logging:**
```python
if normalized_accession:
    # Log sample of accession numbers found in data
    sample_accns = [item.get("accn", "MISSING") for item in sorted_items[:5]]
    logger.info(
        f"XBRL filter: target={normalized_accession}, "
        f"sample_accns={sample_accns}, total_items={len(sorted_items)}"
    )

    matching = [
        item for item in sorted_items
        if item.get("accn", "").replace("-", "") == normalized_accession
    ]

    if matching:
        logger.info(f"XBRL filter: found {len(matching)} matches for {normalized_accession}")
    else:
        logger.warning(
            f"XBRL filter: NO matches for {normalized_accession}. "
            f"Falling back to most recent {max_items} items."
        )
```

**Owner:** Backend Developer Agent
**Effort:** 30 minutes
**Testing:** Check logs for Apple 10-Q to diagnose filter behavior

---

### Phase 2: Data Quality Improvements (P1)

#### 2.1 Compute Period-Over-Period Changes
**File:** `backend/app/services/xbrl_service.py` (in `extract_standardized_metrics`)

**Add Function:**
```python
def compute_period_change(current_value: float, prior_value: float) -> Dict:
    """Compute change between periods - OBJECTIVE calculation only."""
    if prior_value is None or prior_value == 0:
        return {"absolute": None, "percentage": None}

    absolute_change = current_value - prior_value
    percentage_change = (absolute_change / abs(prior_value)) * 100

    return {
        "absolute": round(absolute_change, 2),
        "percentage": round(percentage_change, 2),
        # Note: We do NOT add subjective labels like "growth" or "decline"
    }
```

**Update Metric Entry:**
```python
def _build_metric_entry(series: List[Dict]) -> Dict:
    entry: Dict = {}
    if series:
        entry["current"] = series[0]
    if len(series) > 1:
        entry["prior"] = series[1]
        # Add computed change
        current_val = series[0].get("value")
        prior_val = series[1].get("value")
        if current_val is not None and prior_val is not None:
            entry["change"] = compute_period_change(current_val, prior_val)
    if series:
        entry["series"] = series
    return entry
```

**Owner:** Backend Developer Agent
**Effort:** 1 hour
**Testing:** Verify change calculations are mathematically correct

---

#### 2.2 Frontend: Fix $0.00M Display
**File:** Frontend financial display components

**Requirement:**
```typescript
// BEFORE: Shows $0.00M for null/undefined
formatCurrency(value) // value = null → "$0.00M"

// AFTER: Shows appropriate message
const formatMetricValue = (value: number | null | undefined): string => {
  if (value === null || value === undefined) {
    return "Data not available";
  }
  if (value === 0) {
    return "$0";  // Explicit zero is valid
  }
  return formatCurrency(value);
};
```

**Owner:** Frontend Developer Agent
**Effort:** 1 hour
**Testing:** Verify no "$0.00M" appears when data is actually missing

---

### Phase 3: AI Output Quality (P2)

#### 3.1 Objective Risk Factor Extraction
**File:** `backend/app/services/openai_service.py` (risk extraction prompt)

**Updated Prompt Requirements:**
```python
RISK_EXTRACTION_PROMPT = """
Extract the top 5 risk factors from Item 1A of this SEC filing.

CRITICAL REQUIREMENTS:
1. Report ONLY risks explicitly stated in the filing
2. Use NEUTRAL language - no subjective adjectives
3. Include DIRECT QUOTES as supporting evidence
4. DO NOT interpret, speculate, or editorialize

For each risk factor, provide:
{
  "title": "Brief factual title (5-10 words)",
  "summary": "One sentence factual summary of the risk",
  "supporting_quote": "Direct quote from filing (max 100 words)",
  "filing_section": "Item 1A: Risk Factors",
  "is_new_this_period": true/false  // Based on explicit disclosure
}

FORBIDDEN:
- Words like "significant," "major," "critical," "concerning"
- Predictions about likelihood or impact
- Comparisons to competitors not mentioned in filing
- Investment recommendations or implications

EXAMPLE OUTPUT:
{
  "title": "Supply chain concentration in Asia",
  "summary": "The company sources components from suppliers concentrated in Asia,
              primarily China, Taiwan, and South Korea.",
  "supporting_quote": "A significant concentration of our suppliers are located
                       in Asia, which exposes us to regional risks including
                       natural disasters, political instability, and trade restrictions.",
  "filing_section": "Item 1A: Risk Factors",
  "is_new_this_period": false
}
"""
```

**Owner:** AI Engineer Agent
**Effort:** 2 hours
**Testing:** Review output for subjective language, flag any opinions

---

#### 3.2 Objective MD&A Extraction
**File:** `backend/app/services/openai_service.py` (MD&A extraction prompt)

**Updated Prompt Requirements:**
```python
MDA_EXTRACTION_PROMPT = """
Extract key information from Item 7 (MD&A) of this SEC filing.

CRITICAL REQUIREMENTS:
1. Report ONLY what management explicitly stated
2. Use DIRECT QUOTES for all management commentary
3. DO NOT interpret management's tone or sentiment
4. DO NOT predict future performance

Structure:
{
  "revenue_discussion": {
    "management_statement": "Direct quote about revenue",
    "reported_factors": ["Factor 1 mentioned", "Factor 2 mentioned"],
    "quantified_impacts": [{"factor": "...", "amount": "...", "source": "quote"}]
  },
  "expense_discussion": {
    "management_statement": "Direct quote about expenses",
    "reported_changes": ["Change 1", "Change 2"]
  },
  "segment_performance": [
    {
      "segment_name": "As named in filing",
      "revenue": "$X",
      "change": "+/-X%",
      "management_commentary": "Direct quote"
    }
  ]
}

FORBIDDEN:
- Characterizing results as "strong," "weak," "disappointing"
- Inferring management confidence or concern
- Predicting next quarter performance
- Adding context not in the filing
"""
```

**Owner:** AI Engineer Agent
**Effort:** 2 hours
**Testing:** Review output for any interpretive language

---

#### 3.3 Objective Guidance Extraction
**File:** `backend/app/services/openai_service.py` (guidance extraction prompt)

**Updated Prompt Requirements:**
```python
GUIDANCE_EXTRACTION_PROMPT = """
Extract forward-looking statements from this SEC filing.

CRITICAL REQUIREMENTS:
1. Extract ONLY explicit guidance/outlook statements
2. Distinguish between quantified guidance and qualitative statements
3. Include the EXACT wording used by management
4. Note if guidance was provided, withdrawn, or not given

Structure:
{
  "quantified_guidance": [
    {
      "metric": "Revenue/EPS/etc.",
      "range_low": "$X",
      "range_high": "$Y",
      "period": "Q4 2022 / FY2023 / etc.",
      "exact_quote": "Management's exact words"
    }
  ],
  "qualitative_outlook": [
    {
      "topic": "Topic area",
      "management_statement": "Exact quote",
      "filing_location": "Item 7 / Earnings Call / etc."
    }
  ],
  "guidance_not_provided": ["List topics where company explicitly stated no guidance"],
  "guidance_withdrawn": ["List any guidance that was withdrawn with reason if stated"]
}

FORBIDDEN:
- Interpreting whether guidance is "conservative" or "aggressive"
- Predicting whether company will meet guidance
- Comparing to analyst expectations (not in filing)
- Adding opinions about guidance quality
"""
```

**Owner:** AI Engineer Agent
**Effort:** 2 hours
**Testing:** Verify all output is directly traceable to filing text

---

### Phase 4: Quality Assurance (P2)

#### 4.1 Automated Test Suite for Major Companies
**File:** `backend/tests/test_xbrl_extraction.py` (new file)

```python
import pytest
from app.services.xbrl_service import xbrl_service

# Test fixtures for major companies
MAJOR_COMPANY_FILINGS = [
    {"cik": "320193", "ticker": "AAPL", "name": "Apple"},
    {"cik": "789019", "ticker": "MSFT", "name": "Microsoft"},
    {"cik": "1652044", "ticker": "GOOGL", "name": "Alphabet"},
    {"cik": "1018724", "ticker": "AMZN", "name": "Amazon"},
    {"cik": "1045810", "ticker": "NVDA", "name": "NVIDIA"},
]

@pytest.mark.asyncio
async def test_xbrl_returns_revenue_for_major_companies():
    """Major companies must return non-empty revenue data."""
    for company in MAJOR_COMPANY_FILINGS:
        result = await xbrl_service.get_xbrl_data("latest", company["cik"])
        assert result is not None, f"{company['name']} returned None"
        assert len(result.get("revenue", [])) > 0, f"{company['name']} has no revenue"
        assert result["revenue"][0].get("value") > 0, f"{company['name']} revenue is zero"

@pytest.mark.asyncio
async def test_xbrl_values_are_reasonable():
    """Sanity check that values are in reasonable ranges."""
    result = await xbrl_service.get_xbrl_data("latest", "320193")  # Apple
    revenue = result["revenue"][0]["value"]
    # Apple's quarterly revenue should be between $50B and $150B
    assert 50_000_000_000 < revenue < 150_000_000_000, f"Apple revenue {revenue} seems wrong"

def test_no_subjective_language_in_output():
    """Verify AI output contains no subjective adjectives."""
    FORBIDDEN_WORDS = [
        "strong", "weak", "impressive", "disappointing", "concerning",
        "excellent", "poor", "significant", "major", "critical",
        "bullish", "bearish", "optimistic", "pessimistic",
        "buy", "sell", "hold", "recommend"
    ]

    # This would check actual AI output
    summary_text = get_sample_summary_output()
    for word in FORBIDDEN_WORDS:
        assert word.lower() not in summary_text.lower(), \
            f"Found subjective word '{word}' in summary"
```

**Owner:** QA Engineer Agent
**Effort:** 4 hours
**Testing:** Run against all major company filings

---

#### 4.2 Coverage Quality Gate
**File:** `backend/app/services/fallback_summary.py`

**Add Minimum Coverage Check:**
```python
def validate_summary_quality(summary: Dict) -> Tuple[bool, List[str]]:
    """Validate summary meets minimum quality standards.

    Returns:
        (passes_quality_gate, list_of_issues)
    """
    issues = []

    # Check coverage
    coverage = summary.get("raw_summary", {}).get("section_coverage", {})
    covered = coverage.get("covered_count", 0)
    total = coverage.get("total_count", 7)

    if covered < 3:
        issues.append(f"Coverage too low: {covered}/{total} sections")

    # Check financial data
    financials = summary.get("financial_highlights", {})
    if not financials or financials.get("table", [{}])[0].get("current_period") == "Not available":
        issues.append("Financial highlights missing")

    # Check for placeholder text
    risk_factors = summary.get("risk_factors", [])
    if risk_factors and risk_factors[0].get("summary", "").startswith("Risk factors for"):
        issues.append("Risk factors contain only placeholder text")

    passes = len(issues) == 0
    return passes, issues
```

**Owner:** QA Engineer Agent
**Effort:** 2 hours

---

## Agent Assignments

### Backend Developer Agent
| Task | Priority | Effort | Status |
|------|----------|--------|--------|
| Fix empty dict handling | P0 | 30 min | Pending |
| Expand GAAP field names | P0 | 30 min | Pending |
| Add diagnostic logging | P0 | 30 min | Pending |
| Compute period changes | P1 | 1 hour | Pending |

### Frontend Developer Agent
| Task | Priority | Effort | Status |
|------|----------|--------|--------|
| Fix $0.00M display | P1 | 1 hour | Pending |
| Show per-section status | P2 | 2 hours | Pending |

### AI Engineer Agent
| Task | Priority | Effort | Status |
|------|----------|--------|--------|
| Objective risk extraction prompt | P2 | 2 hours | Pending |
| Objective MD&A extraction prompt | P2 | 2 hours | Pending |
| Objective guidance extraction prompt | P2 | 2 hours | Pending |

### QA Engineer Agent
| Task | Priority | Effort | Status |
|------|----------|--------|--------|
| Major company test suite | P2 | 4 hours | Pending |
| Coverage quality gate | P2 | 2 hours | Pending |
| Subjective language detection | P2 | 2 hours | Pending |

---

## Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Section coverage (major companies) | 2/7 (29%) | 6/7 (86%) | Automated test |
| Revenue/Income availability | ~50% | 99% | Monitor "Not available" rate |
| AI completion rate (no timeout) | ~60% | 90% | Log analysis |
| Subjective language instances | Unknown | 0 | Automated scan |
| User retry rate | High | <10% | Analytics |

---

## Rollback Plan

All changes are designed to be backwards compatible. If issues arise:

1. **XBRL field names:** Revert to original 3 fields (no data loss, just less coverage)
2. **Empty dict fix:** Revert to `if xbrl_data:` (returns to current behavior)
3. **AI prompts:** Prompts are loaded from config, can be reverted without deploy
4. **Frontend display:** Feature flag can disable new display logic

---

## Appendix: Files to Modify

### Backend
- `/backend/app/services/xbrl_service.py` - XBRL extraction and field names
- `/backend/app/services/fallback_summary.py` - Empty dict handling, coverage calculation
- `/backend/app/services/openai_service.py` - AI prompts for objective extraction
- `/backend/app/routers/summaries.py` - Timeout configuration

### Frontend
- Financial display components - $0.00M fix
- Chart components - Null value handling
- Section status components - Loading state display

### Tests
- `/backend/tests/test_xbrl_extraction.py` - New test file
- `/backend/tests/test_summary_quality.py` - New test file

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-25 | Engineering Lead | Initial comprehensive plan |
