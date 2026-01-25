# Filing Summary Improvement - Staff Engineer Execution Plan

**Document Version:** 2.0
**Created:** 2026-01-25
**Author:** Staff Engineer Review
**Status:** READY FOR EXECUTION
**Priority:** P0 - CRITICAL BUSINESS IMPACT

---

## Executive Summary

After a thorough code review of the existing implementation against the improvement plan, I've identified that **several critical fixes have already been implemented**, but significant gaps remain. This execution plan acknowledges completed work, identifies remaining tasks, adds Staff-level recommendations, and provides a comprehensive testing strategy.

---

## Part 1: Assessment of Original Plan

### Already Implemented (Verified in Codebase)

| Fix | Status | Location | Verification |
|-----|--------|----------|--------------|
| XBRL Revenue Field Names Expansion | ✅ DONE | `backend/app/services/xbrl_service.py:62-88` | 24 field names including NetSales, TotalRevenue, etc. |
| Empty Dict Handling (`has_valid_xbrl_data`) | ✅ DONE | `backend/app/services/fallback_summary.py:8-31` | Properly checks for actual data, not just truthiness |
| XBRL Diagnostic Logging | ✅ DONE | `backend/app/services/xbrl_service.py:201-220` | Logs sample accession numbers and match counts |
| Frontend $0.00M Fix | ✅ DONE | `frontend/components/StatCard.tsx:22-43` | Returns "N/A" for null/undefined/NaN |
| Format Utilities Handle Missing Data | ✅ DONE | `frontend/lib/format.ts:3-15` | MISSING_TOKENS set handles edge cases |
| Test for Placeholder Text | ✅ DONE | `frontend/tests/unit/no-placeholder-text.spec.tsx` | Verifies "Not available" doesn't appear |

### Remaining Tasks (Not Yet Implemented)

| Task | Priority | Original Owner | Status |
|------|----------|----------------|--------|
| Period-over-period change computation | P1 | Backend Developer | NOT STARTED |
| Objective Risk Extraction Prompt | P2 | AI Engineer | NOT STARTED |
| Objective MD&A Extraction Prompt | P2 | AI Engineer | NOT STARTED |
| Objective Guidance Extraction Prompt | P2 | AI Engineer | NOT STARTED |
| Major Companies Test Suite | P2 | QA Engineer | NOT STARTED |
| Coverage Quality Gate | P2 | QA Engineer | NOT STARTED |
| Subjective Language Detection Test | P2 | QA Engineer | NOT STARTED |

---

## Part 2: Staff Engineer Critical Gaps Identified

### Gap 1: Missing EPS/Net Income Field Name Coverage

**Problem:** The plan expanded revenue field names but EPS and Net Income extraction still uses limited field names.

**Impact:** Similar silent failures for EPS data as we saw with revenue.

**Recommendation:** Add comprehensive field name lists for:
- `EarningsPerShareBasic`, `EarningsPerShareDiluted`, `EarningsPerShareBasicAndDiluted`
- `NetIncomeLoss`, `ProfitLoss`, `NetIncomeLossAvailableToCommonStockholdersBasic`
- `OperatingIncomeLoss`, `IncomeLossFromContinuingOperations`

### Gap 2: No Cache Invalidation Strategy + Partial Result Handling

**Problem:** Existing summaries with poor quality data will persist indefinitely. Partial results are being cached and served to other users.

**Impact:** Users who previously generated bad summaries will continue seeing them. Users receiving partial results have degraded experience.

**Recommendation:**
1. Add `summary_version` field to Summary model
2. Implement cache bust endpoint for admin use
3. Consider auto-regeneration for summaries below quality threshold
4. **NEW: Implement Full/Partial Result Designation System**

#### Full vs Partial Result Specification

| Designation | Criteria | Caching Behavior | User Experience |
|-------------|----------|------------------|-----------------|
| **Full Result** | ≥3/7 sections populated, no errors, AI completed | ✅ Cached and served to other users | Standard display |
| **Partial Result** | <3/7 sections OR timeout OR error during generation | ❌ NEVER cached, deleted immediately | "Retry Full Analysis" button shown |

#### Critical Requirements

1. **Goal: 0% Partial Results** - Partial results should be SUPER RARE. The system should be engineered to complete successfully in the vast majority of cases.

2. **Partial Results Are NOT Cached:**
   - Partial results must NEVER be stored in the Summary table
   - Partial results must NEVER be served to other users
   - When a partial result occurs, it is returned to the requesting user ONLY, then discarded

3. **User Experience for Partial Results:**
   ```
   ┌─────────────────────────────────────────────────────┐
   │  ⚠️ Partial Analysis Complete                       │
   │                                                     │
   │  We were only able to analyze some sections of      │
   │  this filing. This may be due to filing complexity  │
   │  or temporary service limitations.                  │
   │                                                     │
   │  [Show Partial Results]  [Retry Full Analysis]     │
   │                                                     │
   └─────────────────────────────────────────────────────┘
   ```

4. **Backend Implementation:**
   ```python
   class SummaryResult:
       result_type: Literal["full", "partial"]
       coverage_count: int  # e.g., 5
       coverage_total: int  # e.g., 7
       sections: Dict[str, Any]
       partial_reason: Optional[str]  # "timeout", "api_error", "insufficient_data"

   async def generate_summary(filing_id: int) -> SummaryResult:
       result = await ai_service.generate(filing_id)

       coverage = count_populated_sections(result)

       if coverage >= 3 and not result.had_errors:
           # FULL RESULT - Cache it
           save_to_database(result)
           return SummaryResult(result_type="full", ...)
       else:
           # PARTIAL RESULT - Do NOT cache
           logger.warning(f"Partial result for filing {filing_id}: {coverage}/7 sections")
           return SummaryResult(
               result_type="partial",
               partial_reason=determine_reason(result),
               ...
           )
   ```

5. **Monitoring & Alerting:**
   - Track partial result rate in PostHog/analytics
   - Alert if partial result rate exceeds 5% over 24h period
   - Dashboard shows real-time full vs partial ratio

### Gap 3: No Chaos/Failure Mode Testing

**Problem:** Plan doesn't address what happens when external services fail mid-operation.

**Impact:** Silent failures, partial data, user confusion.

**Recommendation:** Add explicit tests for:
- SEC API timeout mid-request
- OpenAI rate limit errors
- XBRL data with malformed JSON
- Network failures during streaming

### Gap 4: No Observability Plan

**Problem:** Beyond logging, there's no strategy for metrics, dashboards, or alerting.

**Impact:** We won't know if fixes are working in production.

**Recommendation:**
1. Add Prometheus/StatsD metrics for:
   - Summary coverage ratio distribution
   - XBRL extraction success rate
   - Section population rate by type
2. Create Grafana dashboard for summary quality
3. Set up PagerDuty alerts for quality regression

### Gap 5: No Contract Testing

**Problem:** Frontend and backend can drift apart, causing silent failures.

**Impact:** Frontend expects specific JSON structure that backend might change.

**Recommendation:** Add Pact or TypeScript schema validation to ensure API contracts are honored.

### Gap 6: Timeout Strategy Still Incomplete

**Problem:** Plan mentions 75s timeout is insufficient but the code uses 90s now. No adaptive strategy.

**Impact:** Simple filings wait unnecessarily, complex filings still timeout.

**Recommendation:** Implement adaptive timeout based on:
- Filing size (character count)
- Company market cap tier
- Filing type (10-K vs 10-Q)

### Gap 7: No A/B Testing or Gradual Rollout

**Problem:** Changes go live immediately with no safety net.

**Impact:** Bugs affect 100% of users instantly.

**Recommendation:** Implement feature flags for:
- New prompt versions
- XBRL field name expansions
- Quality gate enforcement

---

## Part 3: Comprehensive Execution Plan

### Phase 0: Foundation & Observability (Pre-requisite)

**Goal:** Establish baseline metrics and monitoring BEFORE making changes.

**Agent:** DevOps Automator + QA Engineer

| Task | Description | Testing |
|------|-------------|---------|
| 0.1 | Add summary quality metrics to PostHog | Verify events fire correctly |
| 0.2 | Create quality baseline report (current state) | Document metrics for 100 filings |
| 0.3 | Set up Sentry alerts for summary failures | Trigger test alert |
| 0.4 | Add coverage_ratio tracking to database | Verify column migration |

**Verification Gate:**
- [ ] Dashboard shows real-time quality metrics
- [ ] Baseline report documents current state
- [ ] Alerts fire for test scenarios

---

### Phase 1: Data Quality Improvements (P0 - Critical)

**Goal:** Ensure XBRL extraction returns accurate data for all major companies.

**Agent:** Backend Developer

| Task | File | Description | Test Case |
|------|------|-------------|-----------|
| 1.1 | `xbrl_service.py` | Add EPS field names expansion | Test AAPL, MSFT, NVDA return EPS |
| 1.2 | `xbrl_service.py` | Add Net Income field names expansion | Test AMZN, META return net income |
| 1.3 | `xbrl_service.py` | Add period-over-period change computation | Verify math is correct |
| 1.4 | `xbrl_service.py` | Add data quality logging (values, periods) | Logs show actual numbers |

**Code Change - 1.1 EPS Field Names:**
```python
EPS_FIELD_NAMES = [
    "EarningsPerShareBasic",
    "EarningsPerShareDiluted",
    "EarningsPerShareBasicAndDiluted",
    "BasicEarningsLossPerShare",
    "DilutedEarningsLossPerShare",
    "NetIncomeLossPerBasicShare",
    "NetIncomeLossPerDilutedShare",
]
```

**Code Change - 1.2 Net Income Field Names:**
```python
NET_INCOME_FIELD_NAMES = [
    "NetIncomeLoss",
    "ProfitLoss",
    "NetIncomeLossAvailableToCommonStockholdersBasic",
    "NetIncomeLossAvailableToCommonStockholdersDiluted",
    "IncomeLossFromContinuingOperationsAfterTax",
    "IncomeLossFromContinuingOperations",
    "ComprehensiveIncomeNetOfTax",
]
```

**Code Change - 1.3 Period Change Computation:**
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
    }
```

**Verification Gate:**
```bash
# Run automated test suite
pytest backend/tests/test_xbrl_extraction.py -v
# Expected: All 5 major companies return revenue, net income, EPS
```

---

### Phase 2: AI Prompt Objectivity (P1 - High)

**Goal:** Ensure all AI output is factual, neutral, and directly traceable to filing text.

**Agent:** AI Engineer

| Task | File | Description | Test Case |
|------|------|-------------|-----------|
| 2.1 | `openai_service.py` | Update risk extraction prompt for objectivity | No subjective words in output |
| 2.2 | `openai_service.py` | Update MD&A extraction prompt for objectivity | Direct quotes with citations |
| 2.3 | `openai_service.py` | Update guidance extraction prompt for objectivity | Only explicit guidance included |
| 2.4 | `prompts/*.md` | Update system prompts with FORBIDDEN words list | Prompts reject subjective language |

**FORBIDDEN_WORDS List:**
```python
FORBIDDEN_WORDS = [
    # Subjective adjectives
    "strong", "weak", "impressive", "disappointing", "concerning",
    "excellent", "poor", "significant", "major", "critical",
    "robust", "solid", "healthy", "troubled", "struggling",
    # Investment language
    "bullish", "bearish", "optimistic", "pessimistic",
    "buy", "sell", "hold", "recommend", "undervalued", "overvalued",
    # Predictive language
    "likely", "probably", "expected to", "poised to", "set to",
    "will likely", "should see", "on track to",
]
```

**CRITICAL EXCEPTION - Filing Quotes:**
Forbidden words ARE permitted when directly quoted from the company's SEC filing, subject to these rules:

1. **Attribution Required:** Must use explicit attribution (e.g., "Management described revenue growth as 'strong'" NOT just "strong revenue growth")
2. **Same Context:** The word must be used in the same context as the original filing
3. **Direct Quotes Preferred:** Paraphrasing with synonyms is acceptable, but direct quotes are preferred
4. **Future Enhancement:** Programmatic validation against original filing text is a future improvement (not implemented in v1)

**Example - Correct Usage:**
```
✅ "Management characterized Q4 performance as 'strong' in their earnings call remarks"
✅ "The company stated that demand remained 'robust' according to their 10-K filing"
❌ "The company showed strong performance" (no attribution)
❌ "Revenue was impressive this quarter" (editorializing)
```

**Prompt Template Update:**
```python
RISK_EXTRACTION_PROMPT = """
Extract the top 5 risk factors from Item 1A of this SEC filing.

CRITICAL REQUIREMENTS:
1. Report ONLY risks explicitly stated in the filing
2. Use NEUTRAL language - no subjective adjectives
3. Include DIRECT QUOTES as supporting evidence (max 100 words each)
4. DO NOT interpret, speculate, or editorialize
5. Cite specific filing sections (e.g., "Item 1A: Risk Factors")

FORBIDDEN WORDS (never use these):
{forbidden_words}

For each risk factor, provide:
{{
  "title": "Brief factual title (5-10 words, no adjectives)",
  "summary": "One sentence factual summary of the risk",
  "supporting_quote": "Direct quote from filing (max 100 words)",
  "filing_section": "Item 1A: Risk Factors",
  "is_new_this_period": true/false
}}
"""
```

**Verification Gate:**
```bash
# Run subjective language test
pytest backend/tests/test_summary_quality.py::test_no_subjective_language -v
# Expected: 0 forbidden words in output
```

---

### Phase 3: Quality Assurance Infrastructure (P1 - High)

**Goal:** Build automated testing that catches regressions before production.

**Agent:** QA Engineer + Integration Tester

| Task | File | Description | Test Case |
|------|------|-------------|-----------|
| 3.1 | `test_xbrl_extraction.py` | Create major companies test suite | AAPL, MSFT, GOOGL, AMZN, NVDA pass |
| 3.2 | `test_summary_quality.py` | Create subjective language detector | Detects all forbidden words |
| 3.3 | `test_summary_quality.py` | Create coverage quality gate | Fails if coverage < 3/7 |
| 3.6 | Frontend components | Hide empty subsections dynamically | Empty sections not rendered |
| 3.7 | `openai_service.py` | Executive Summary includes all section summaries | Exec summary references hidden sections |
| 3.4 | `test_integration_sec.py` | Create VCR-recorded SEC tests | Tests run without network |
| 3.5 | `test_failure_modes.py` | Create chaos tests | Graceful handling of failures |

**Test File - test_xbrl_extraction.py:**
```python
import pytest
from app.services.xbrl_service import xbrl_service

MAJOR_COMPANY_FILINGS = [
    {"cik": "320193", "ticker": "AAPL", "name": "Apple"},
    {"cik": "789019", "ticker": "MSFT", "name": "Microsoft"},
    {"cik": "1652044", "ticker": "GOOGL", "name": "Alphabet"},
    {"cik": "1018724", "ticker": "AMZN", "name": "Amazon"},
    {"cik": "1045810", "ticker": "NVDA", "name": "NVIDIA"},
]

@pytest.mark.asyncio
@pytest.mark.parametrize("company", MAJOR_COMPANY_FILINGS, ids=lambda c: c["ticker"])
async def test_xbrl_returns_revenue(company):
    """Major companies must return non-empty revenue data."""
    result = await xbrl_service.get_xbrl_data("latest", company["cik"])
    assert result is not None, f"{company['name']} returned None"
    assert len(result.get("revenue", [])) > 0, f"{company['name']} has no revenue"

@pytest.mark.asyncio
@pytest.mark.parametrize("company", MAJOR_COMPANY_FILINGS, ids=lambda c: c["ticker"])
async def test_xbrl_returns_net_income(company):
    """Major companies must return net income data."""
    result = await xbrl_service.get_xbrl_data("latest", company["cik"])
    assert result is not None
    assert len(result.get("net_income", [])) > 0, f"{company['name']} has no net income"

@pytest.mark.asyncio
@pytest.mark.parametrize("company", MAJOR_COMPANY_FILINGS, ids=lambda c: c["ticker"])
async def test_xbrl_returns_eps(company):
    """Major companies must return EPS data."""
    result = await xbrl_service.get_xbrl_data("latest", company["cik"])
    assert result is not None
    assert len(result.get("earnings_per_share", [])) > 0, f"{company['name']} has no EPS"
```

**Test File - test_summary_quality.py:**
```python
import pytest
import re

FORBIDDEN_WORDS = [
    "strong", "weak", "impressive", "disappointing", "concerning",
    "excellent", "poor", "significant", "major", "critical",
    "bullish", "bearish", "optimistic", "pessimistic",
    "buy", "sell", "hold", "recommend",
]

def check_for_subjective_language(text: str) -> list:
    """Return list of forbidden words found in text."""
    if not text:
        return []
    text_lower = text.lower()
    found = []
    for word in FORBIDDEN_WORDS:
        # Match whole words only
        if re.search(rf'\b{word}\b', text_lower):
            found.append(word)
    return found

def test_no_subjective_language_in_risk_factors(sample_summary):
    """Risk factors must not contain subjective language."""
    for risk in sample_summary.get("risk_factors", []):
        summary_text = risk.get("summary", "")
        found = check_for_subjective_language(summary_text)
        assert not found, f"Found subjective words: {found}"

def test_coverage_quality_gate(sample_summary):
    """Summary must have at least 3/7 sections populated."""
    coverage = sample_summary.get("raw_summary", {}).get("section_coverage", {})
    covered = coverage.get("covered_count", 0)
    total = coverage.get("total_count", 7)
    assert covered >= 3, f"Coverage too low: {covered}/{total}"
```

---

### Phase 3.1: Coverage Quality Gate & Dynamic Section Hiding (P0 - Critical)

**Goal:** Hide empty sections gracefully and ensure Executive Summary provides complete context.

**Agent:** Frontend Developer + Backend Developer

#### Coverage Quality Gate Specification

| Rule | Specification |
|------|---------------|
| Minimum Coverage | 3/7 sections must have substantive data |
| Below Minimum | Summary marked as "partial result" (see Cache Invalidation) |
| Hideable Sections | All sections EXCEPT Executive Summary |
| Hidden Section Handling | Executive Summary explicitly notes unavailable sections |

#### Hideable Sections (7 Total)
1. Business Overview
2. Financial Highlights
3. Risk Factors
4. Management Discussion (MD&A)
5. Key Changes (Year-over-Year)
6. Forward Guidance
7. Additional Disclosures

**Note:** Executive Summary is NEVER hidden - it is always rendered.

#### Executive Summary Must Include

When a section has no data, the Executive Summary MUST explicitly note it:

```json
{
  "executive_summary": {
    "overview": "Apple Inc. reported Q4 2025 results...",
    "key_points": ["Revenue increased 12%...", "..."],
    "sections_available": ["business_overview", "financial_highlights", "risk_factors", "mda"],
    "sections_unavailable": [
      {
        "section": "forward_guidance",
        "note": "No forward guidance was disclosed in this filing"
      },
      {
        "section": "key_changes",
        "note": "Year-over-year comparisons were not available for this filing period"
      }
    ]
  }
}
```

#### Frontend Implementation

```typescript
// Dynamic section rendering - hide empty sections
const renderSection = (sectionKey: string, data: SectionData | null) => {
  // Don't render if no data (except Executive Summary which is always shown)
  if (!data && sectionKey !== 'executive_summary') {
    return null;
  }

  return <SectionComponent key={sectionKey} data={data} />;
};

// Executive Summary must show unavailable sections notice
const ExecutiveSummary = ({ summary }: Props) => {
  const { sections_unavailable } = summary.executive_summary;

  return (
    <div>
      {/* Main summary content */}
      <SummaryContent data={summary.executive_summary} />

      {/* Note about unavailable sections */}
      {sections_unavailable?.length > 0 && (
        <div className="text-muted-foreground text-sm mt-4">
          <p className="font-medium">Not included in this filing:</p>
          <ul>
            {sections_unavailable.map(({ section, note }) => (
              <li key={section}>{note}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
```

#### Backend Prompt Update

Add to AI system prompt:
```
EXECUTIVE SUMMARY REQUIREMENTS:
1. The Executive Summary MUST provide a complete overview of the filing
2. For EVERY section that cannot be populated, include in sections_unavailable:
   - "No forward guidance was disclosed in this filing"
   - "Year-over-year comparisons were not available for this filing period"
   - "Risk factors were not itemized in this filing"
   - etc.
3. The Executive Summary should summarize ALL available sections, not just highlights
```

#### Test Cases

```python
def test_hidden_sections_noted_in_executive_summary(sample_summary):
    """Executive Summary must note all unavailable sections."""
    exec_summary = sample_summary.get("executive_summary", {})
    sections_unavailable = exec_summary.get("sections_unavailable", [])

    # Count actual empty sections
    hideable_sections = [
        "business_overview", "financial_highlights", "risk_factors",
        "management_discussion", "key_changes", "forward_guidance", "additional_disclosures"
    ]

    empty_sections = [
        s for s in hideable_sections
        if not sample_summary.get(s)
    ]

    # Every empty section must be noted in Executive Summary
    noted_sections = [item["section"] for item in sections_unavailable]
    for section in empty_sections:
        assert section in noted_sections, f"Empty section '{section}' not noted in Executive Summary"

def test_minimum_coverage_for_full_result(sample_summary):
    """Summary needs 3/7 sections for 'full result' designation."""
    coverage = calculate_coverage(sample_summary)
    is_full_result = sample_summary.get("result_type") == "full"

    if coverage < 3:
        assert not is_full_result, "Summary with <3 sections should be 'partial'"
    else:
        assert is_full_result, "Summary with >=3 sections should be 'full'"
```

**Verification Gate:**
```bash
# Run full test suite
pytest backend/tests/ -v --tb=short
# Expected: 100% pass rate
```

---

### Phase 4: Integration & Performance Testing (P2 - Medium)

**Goal:** Validate end-to-end flows and ensure performance targets are met.

**Agent:** Integration Tester + Performance Tester

| Task | Description | Success Criteria |
|------|-------------|------------------|
| 4.1 | Full pipeline E2E test (search → filing → summary) | <30s for cached, <90s for new |
| 4.2 | SEC API failure recovery test | Graceful degradation |
| 4.3 | OpenAI timeout handling test | Fallback summary returned |
| 4.4 | Load test summary endpoint | Handle 50 concurrent requests |
| 4.5 | XBRL extraction performance test | <5s for any company |

**Performance Targets:**
| Metric | Target | Acceptable | Unacceptable |
|--------|--------|------------|--------------|
| Summary generation (new) | <30s | <60s | >90s |
| Summary retrieval (cached) | <200ms | <500ms | >1000ms |
| XBRL extraction | <5s | <10s | >15s |
| Section coverage | 6/7 (86%) | 4/7 (57%) | <3/7 (43%) |

**Verification Gate:**
```bash
# Run performance tests
pytest backend/tests/test_performance.py -v
# Run load test
k6 run backend/tests/load_test.js
```

---

### Phase 5: Security & Compliance (P2 - Medium)

**Goal:** Ensure changes don't introduce security vulnerabilities.

**Agent:** Security Auditor

| Task | Description | Test Case |
|------|-------------|-----------|
| 5.1 | Review new prompts for injection risks | No user input in prompts |
| 5.2 | Verify rate limiting still enforced | 5 req/min per user |
| 5.3 | Check error messages don't leak internal details | Generic errors only |
| 5.4 | Verify no PII in logs | Audit log output |

**Verification Gate:**
```bash
# Run security scan
bandit -r backend/app -x tests
# Run OWASP ZAP scan
```

---

### Phase 6: Deployment & Monitoring (P1 - High)

**Goal:** Safe rollout with instant rollback capability.

**Agent:** DevOps Automator

| Task | Description | Verification |
|------|-------------|--------------|
| 6.1 | Deploy to staging environment | Staging tests pass |
| 6.2 | Run full regression suite on staging | 100% pass |
| 6.3 | Deploy to production (canary 10%) | Monitor error rates |
| 6.4 | Expand to 50% if metrics green | Coverage ratio stable |
| 6.5 | Full rollout if metrics green for 24h | All users |
| 6.6 | Monitor quality dashboard for 7 days | No regression |

**Rollback Triggers:**
- Error rate > 1%
- Average coverage ratio drops > 10%
- p95 latency > 90 seconds
- Sentry alerts firing

**Verification Gate:**
```bash
# Monitor dashboard for 7 days
# Expected: Coverage ratio >= 6/7 for major companies
```

---

## Part 4: Agent Assignments Summary

### Backend Developer Agent
| Phase | Task | Effort | Priority |
|-------|------|--------|----------|
| 1 | EPS field names expansion | 1h | P0 |
| 1 | Net Income field names expansion | 1h | P0 |
| 1 | Period-over-period change computation | 2h | P1 |
| 1 | Data quality logging | 1h | P1 |
| 3.1 | Implement full/partial result designation | 3h | P0 |
| 3.1 | Partial result deletion (no caching) | 2h | P0 |
| 3.1 | Executive Summary unavailable sections | 2h | P1 |

### Frontend Developer Agent
| Phase | Task | Effort | Priority |
|-------|------|--------|----------|
| 3.1 | Dynamic section hiding for empty sections | 3h | P0 |
| 3.1 | Executive Summary unavailable sections display | 2h | P1 |
| 3.1 | Partial result UI with "Retry Full Analysis" button | 3h | P0 |
| 3.1 | Coverage indicator component | 1h | P2 |

### AI Engineer Agent
| Phase | Task | Effort | Priority |
|-------|------|--------|----------|
| 2 | Objective risk extraction prompt | 2h | P1 |
| 2 | Objective MD&A extraction prompt | 2h | P1 |
| 2 | Objective guidance extraction prompt | 2h | P1 |
| 2 | System prompts update | 1h | P1 |

### QA Engineer Agent
| Phase | Task | Effort | Priority |
|-------|------|--------|----------|
| 3 | Major companies test suite | 4h | P1 |
| 3 | Subjective language detector | 2h | P1 |
| 3 | Coverage quality gate | 2h | P1 |
| 3 | Chaos/failure mode tests | 3h | P2 |

### Integration Tester Agent
| Phase | Task | Effort | Priority |
|-------|------|--------|----------|
| 3 | VCR-recorded SEC tests | 4h | P2 |
| 4 | E2E pipeline tests | 4h | P2 |

### Performance Tester Agent
| Phase | Task | Effort | Priority |
|-------|------|--------|----------|
| 4 | Load test summary endpoint | 4h | P2 |
| 4 | XBRL performance baseline | 2h | P2 |

### Security Auditor Agent
| Phase | Task | Effort | Priority |
|-------|------|--------|----------|
| 5 | Prompt injection review | 2h | P2 |
| 5 | Rate limiting verification | 1h | P2 |
| 5 | Error message audit | 1h | P2 |

### DevOps Automator Agent
| Phase | Task | Effort | Priority |
|-------|------|--------|----------|
| 0 | Quality metrics setup | 4h | P0 |
| 6 | Staged deployment | 4h | P1 |
| 6 | Monitoring dashboard | 4h | P1 |

---

## Part 5: Success Metrics

| Metric | Current (Baseline) | Target | Measurement |
|--------|-------------------|--------|-------------|
| Section coverage (major companies) | 2/7 (29%) | 6/7 (86%) | Automated test |
| Revenue availability | ~70% | 99% | Monitor "Not available" rate |
| Net Income availability | ~60% | 95% | Monitor "Not available" rate |
| EPS availability | ~50% | 95% | Monitor "Not available" rate |
| AI completion rate (no timeout) | ~70% | 95% | Log analysis |
| Subjective language instances | Unknown | 0* | Automated scan |
| User retry rate | ~30% | <10% | Analytics |
| p95 summary generation time | ~45s | <30s | APM metrics |
| **Partial result rate** | Unknown | **<1%** | Analytics |
| **Full result cache hit rate** | Unknown | >80% | Database metrics |

*Exception: Forbidden words allowed when directly quoted from filing with proper attribution

---

## Part 6: Rollback Plan

All changes are designed to be backwards compatible:

1. **XBRL field names:** Additional fields are additive; removal returns to current behavior
2. **AI prompts:** Prompts loaded from config files; instant revert without deploy
3. **Tests:** Tests don't affect production; can be disabled in CI if blocking
4. **Feature flags:** All major changes behind flags; instant disable capability

### Emergency Rollback Procedure:
```bash
# 1. Disable feature flag (instant)
curl -X POST https://api.earningsnerd.io/admin/flags -d '{"summary_v2": false}'

# 2. Revert deployment (if needed)
git revert HEAD
git push origin main

# 3. Clear cached summaries (if contaminated)
curl -X POST https://api.earningsnerd.io/admin/cache/clear
```

---

## Part 7: Timeline & Milestones

### Week 1: Foundation
- [ ] Phase 0: Observability setup complete
- [ ] Phase 1: Data quality improvements complete
- [ ] All Phase 1 tests passing

### Week 2: AI Quality
- [ ] Phase 2: AI prompt improvements complete
- [ ] Phase 3: QA infrastructure complete
- [ ] All Phase 2 & 3 tests passing

### Week 3: Integration & Deployment
- [ ] Phase 4: Integration testing complete
- [ ] Phase 5: Security audit complete
- [ ] Phase 6: Staged deployment complete

### Week 4: Monitoring & Validation
- [ ] 7-day production monitoring complete
- [ ] Success metrics achieved
- [ ] Documentation updated

---

## Appendix: Files to Create/Modify

### New Files
- `backend/tests/test_xbrl_extraction.py` - Major company test suite
- `backend/tests/test_summary_quality.py` - Quality gate tests
- `backend/tests/test_failure_modes.py` - Chaos tests
- `backend/tests/test_integration_sec.py` - VCR integration tests
- `backend/tests/test_partial_results.py` - Partial result handling tests
- `backend/tests/load_test.js` - k6 load test script
- `frontend/components/PartialResultBanner.tsx` - Partial result UI component
- `frontend/components/UnavailableSections.tsx` - Executive Summary unavailable sections display

### Modified Files
- `backend/app/services/xbrl_service.py` - EPS/Net Income field names, period change
- `backend/app/services/openai_service.py` - Objective prompts, Executive Summary requirements
- `backend/app/services/summary_generation_service.py` - Full/partial result designation, no-cache for partial
- `backend/app/routers/summaries.py` - Return result_type in response
- `backend/app/models/__init__.py` - Add result_type field to Summary model (or handle separately)
- `backend/prompts/10k-analyst-agent.md` - Updated with forbidden words + attribution rules + Executive Summary requirements
- `backend/prompts/10q-analyst-agent.md` - Updated with forbidden words + attribution rules + Executive Summary requirements
- `frontend/features/summaries/SummaryDisplay.tsx` - Dynamic section hiding
- `frontend/features/summaries/ExecutiveSummary.tsx` - Show unavailable sections note

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-25 | Engineering Lead | Initial plan |
| 2.0 | 2026-01-25 | Staff Engineer | Added gap analysis, execution plan, testing strategy |
| 2.1 | 2026-01-25 | Staff Engineer | Added: (1) Filing quote exception for forbidden words with attribution requirement, (2) Dynamic section hiding with 3/7 minimum coverage, (3) Executive Summary must note unavailable sections, (4) Full/partial result designation system with 0% partial target, (5) Partial results never cached, (6) "Retry Full Analysis" UI for partial results |
