# SEC 10-Q Pipeline Implementation Plan

## Executive Summary

This document outlines the implementation plan for a backend pipeline that fetches, parses, and serves SEC 10-Q filings as clean, AI-ready Markdown. The goal is **data cleanliness for LLM context** - transforming raw SEC HTML into semantic, structured Markdown optimized for AI summarization.

---

## 1. Current State Analysis

### Existing Infrastructure

Your EarningsNerd platform already has significant SEC integration:

| Component | Location | Status |
|-----------|----------|--------|
| `SECEdgarService` | `backend/app/services/sec_edgar.py` | Functional |
| XBRL Extraction | `backend/app/services/xbrl_service.py` | Functional |
| Filing Router | `backend/app/routers/filings.py` | Functional |
| Pipeline Extract | `backend/pipeline/extract.py` | Functional |

**Installed Dependencies:**
- `sec-edgar-downloader==5.0.3` (fetching)
- `beautifulsoup4==4.12.3` (HTML parsing)
- `arelle-release==2.27.0` (XBRL)
- `httpx==0.26.0` (async HTTP)

### What's Missing

1. **Semantic HTML → Markdown Conversion**: Current system extracts raw text/sections but doesn't produce clean, structured Markdown
2. **`sec-parser` Library**: Not installed - provides semantic document structure from AlphaSense
3. **Robust Rate Limiting**: Basic implementation exists, needs exponential backoff
4. **Dedicated Markdown Endpoint**: No endpoint returns `{filing_date, accession_number, markdown_content}`

---

## 2. Architecture Decision

### Recommendation: Enhance Existing FastAPI Backend

**NOT a separate microservice.** Your backend is already Python/FastAPI with all necessary infrastructure. Adding a microservice would introduce:
- Network latency between services
- Deployment complexity
- Data synchronization issues
- Unnecessary operational overhead

**Recommended Approach:**
```
┌─────────────────────────────────────────────────────────────────┐
│                    Existing FastAPI Backend                      │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                  New Components (Phase 2)                    ││
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐││
│  │  │ SECClient   │→ │ FilingParser │→ │ MarkdownSerializer  │││
│  │  │ (enhanced)  │  │ (sec-parser) │  │ (semantic output)   │││
│  │  └─────────────┘  └──────────────┘  └─────────────────────┘││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              Existing Components (Enhanced)                  ││
│  │  • SECEdgarService (add retry/backoff)                      ││
│  │  • FilingContentCache (store markdown)                      ││
│  │  • Rate Limiter (respect SEC 10 req/sec)                    ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Alternative Architectures (Not Recommended)

| Option | Pros | Cons |
|--------|------|------|
| **Separate FastAPI Microservice** | Isolation | Network latency, deployment complexity, shared DB issues |
| **Next.js Server Action with Python** | Unified codebase | Runtime limitations, cold starts, dependency conflicts |
| **Dockerized Container** | Portable | Already have Docker setup, adds unnecessary layer |
| **Serverless (AWS Lambda)** | Auto-scaling | Cold starts, 15min timeout, package size limits |

---

## 3. Library Selection

### Fetching: `edgartools` vs `sec-edgar-downloader`

| Criteria | `edgartools` | `sec-edgar-downloader` |
|----------|--------------|------------------------|
| **Maintenance** | Active (2024 commits) | Active |
| **CIK Lookup** | Built-in `Company.lookup()` | Requires manual mapping |
| **Filing Access** | High-level API | Lower-level, more control |
| **Dependencies** | Heavier (pandas, etc.) | Lighter |
| **Your Current Setup** | Not installed | **Already installed** |
| **Rate Limiting** | Built-in | Manual |
| **10-Q Support** | Excellent | Excellent |

**Recommendation: Keep `sec-edgar-downloader` + Enhance `SECEdgarService`**

Rationale:
1. Already installed and integrated in your codebase
2. Your `SECEdgarService` already has CIK mapping via SEC's `company_tickers.json`
3. Adding `edgartools` would duplicate functionality
4. Can add robust rate limiting to existing service

### Parsing: `sec-parser` vs `sec-api` vs Custom BeautifulSoup

| Criteria | `sec-parser` (AlphaSense) | `sec-api` | Custom BS4 |
|----------|---------------------------|-----------|------------|
| **Semantic Structure** | Excellent | Good | Manual |
| **Section Detection** | Auto (MD&A, Risk Factors) | API-based | Regex/heuristics |
| **Table Handling** | Preserves structure | Varies | Manual |
| **Cost** | Free/Open-source | Paid API | Free |
| **Maintenance** | Active | Commercial | Self |
| **10-Q Optimization** | Yes | Yes | Manual |

**Recommendation: `sec-parser` (AlphaSense)**

```python
# sec-parser produces a semantic tree:
from sec_parser import SemanticTree

tree = SemanticTree.from_html(html_content)
for section in tree.sections:
    print(f"{section.title}: {section.text[:100]}...")
```

Key advantages:
- Understands SEC document structure (Item 1, Item 2, etc.)
- Handles nested tables correctly
- Identifies MD&A, Risk Factors, Financial Statements sections
- Output is structured and easy to serialize to Markdown

---

## 4. Data Flow Architecture

```
┌──────────┐    ┌──────────────┐    ┌─────────────┐    ┌────────────┐
│ Frontend │───▶│ /api/filings │───▶│ SECClient   │───▶│ SEC EDGAR  │
│          │    │ /markdown    │    │ (enhanced)  │    │ API        │
└──────────┘    └──────────────┘    └─────────────┘    └────────────┘
                       │                   │
                       │                   ▼
                       │            ┌─────────────┐
                       │            │ Raw HTML    │
                       │            └─────────────┘
                       │                   │
                       │                   ▼
                       │            ┌─────────────────┐
                       │            │ FilingParser    │
                       │            │ (sec-parser)    │
                       │            └─────────────────┘
                       │                   │
                       │                   ▼
                       │            ┌─────────────────┐
                       │            │ Semantic Tree   │
                       │            └─────────────────┘
                       │                   │
                       │                   ▼
                       │            ┌─────────────────────┐
                       │            │ MarkdownSerializer  │
                       │            └─────────────────────┘
                       │                   │
                       ▼                   ▼
                ┌──────────────────────────────┐
                │ JSON Response:               │
                │ {                            │
                │   filing_date: "2024-01-15", │
                │   accession_number: "...",   │
                │   markdown_content: "# ..."  │
                │ }                            │
                └──────────────────────────────┘
```

---

## 5. SEC Compliance Requirements

### User-Agent Header (Critical)

The SEC requires a properly formatted User-Agent header:

```python
# Current (needs update):
USER_AGENT = "EarningsNerd earningsnerd@example.com"

# Required format:
USER_AGENT = "EarningsNerd/1.0 (contact@earningsnerd.io)"
# OR
USER_AGENT = "Sample Company Name AdminContact@<sample company domain>.com"
```

**Action:** Update `backend/app/services/sec_edgar.py` line 20 and `backend/app/services/xbrl_service.py` line 13.

### Rate Limiting (10 requests/second)

SEC enforces a strict 10 requests/second limit. Exceeding this results in IP blocking.

**Current Implementation:** Basic rate limiter exists in `services/rate_limiter.py`

**Required Enhancement:**
```python
class SECRateLimiter:
    """SEC-compliant rate limiter with exponential backoff"""

    MAX_REQUESTS_PER_SECOND = 10
    MAX_RETRIES = 5
    BASE_BACKOFF_SECONDS = 1.0

    async def execute_with_backoff(self, request_fn):
        for attempt in range(self.MAX_RETRIES):
            try:
                await self._wait_for_slot()
                return await request_fn()
            except RateLimitExceeded:
                backoff = self.BASE_BACKOFF_SECONDS * (2 ** attempt)
                await asyncio.sleep(backoff)
        raise SECRateLimitError("Max retries exceeded")
```

### CIK Mapping

**Current Implementation:** Working correctly via `company_tickers.json` with 24-hour caching.

**Location:** `backend/app/services/sec_edgar.py:27-63`

No changes needed for CIK mapping.

---

## 6. Edge Cases & Non-Standard Filings

### Common Edge Cases

| Edge Case | Solution |
|-----------|----------|
| **Amended Filings (10-Q/A)** | Include "10-Q/A" in filing types, flag as amended |
| **Foreign Filers (20-F instead of 10-Q)** | Detect form type, apply different parsing rules |
| **Missing Sections** | Graceful degradation - return available sections only |
| **Malformed HTML** | Use BeautifulSoup's `html.parser` with error recovery |
| **Inline XBRL** | Extract from `<ix:*>` tags before markdown conversion |
| **Multi-document Filings** | Identify primary document via index.json |
| **Large Filings (>10MB)** | Stream processing, section-by-section parsing |
| **Tables as Images** | Log warning, skip or attempt OCR (future) |

### Non-Standard Filing Structures

Some companies use non-standard section headers:

```python
# Standard: "Item 2. Management's Discussion and Analysis"
# Variations:
MDNA_PATTERNS = [
    r"Item\s*2\.?\s*Management['']?s?\s*Discussion",
    r"MD&A",
    r"Management['']?s?\s*Discussion\s*and\s*Analysis",
    r"MANAGEMENT['']?S?\s*DISCUSSION",
]
```

**Strategy:** Use `sec-parser`'s semantic detection first, fall back to regex patterns.

---

## 7. Output Format Specification

### API Response Schema

```typescript
interface FilingMarkdownResponse {
  filing_date: string;        // ISO 8601: "2024-01-15"
  accession_number: string;   // "0001193125-24-012345"
  markdown_content: string;   // Clean, semantic Markdown
  metadata: {
    ticker: string;
    company_name: string;
    filing_type: string;      // "10-Q", "10-Q/A"
    fiscal_period: string;    // "Q3 2024"
    sections_extracted: string[];
  };
}
```

### Markdown Structure

```markdown
# {Company Name} - {Filing Type} ({Fiscal Period})

## Filing Information
- **Filed:** {filing_date}
- **Period Ending:** {period_end_date}
- **Accession Number:** {accession_number}

---

## Part I - Financial Information

### Item 1. Financial Statements

#### Condensed Consolidated Balance Sheets
| Assets | Current Period | Prior Period |
|--------|---------------|--------------|
| Cash   | $X,XXX        | $X,XXX       |
...

### Item 2. Management's Discussion and Analysis

{Clean prose extracted from MD&A section}

**Key Highlights:**
- Revenue: ${amount} ({change}% YoY)
- Operating Income: ${amount}
...

### Item 3. Quantitative and Qualitative Disclosures About Market Risk

{Risk disclosures}

### Item 4. Controls and Procedures

{Controls section}

---

## Part II - Other Information

### Item 1. Legal Proceedings
{If present}

### Item 1A. Risk Factors
{Risk factors with bullet points}

### Item 6. Exhibits
{Exhibit list}

---

*Source: SEC EDGAR - {sec_url}*
```

---

## 8. Implementation Plan (Phase 2)

### File Structure

```
backend/
├── app/
│   ├── services/
│   │   ├── sec_edgar.py          # Enhanced (add rate limiting)
│   │   ├── sec_client.py         # NEW: High-level client facade
│   │   ├── filing_parser.py      # NEW: sec-parser integration
│   │   └── markdown_serializer.py # NEW: Semantic → Markdown
│   ├── routers/
│   │   └── filings.py            # Enhanced (add markdown endpoint)
│   └── schemas/
│       └── filing_markdown.py    # NEW: Response models
├── requirements.txt              # Add sec-parser
└── tests/
    └── test_filing_parser.py     # NEW: Parser tests
```

### Step-by-Step Implementation

#### Step 1: Install Dependencies
```bash
cd backend
pip install sec-parser
# Add to requirements.txt: sec-parser>=0.30.0
```

#### Step 2: Create `SECClient` Facade
```python
# backend/app/services/sec_client.py
class SECClient:
    """High-level SEC filing client with rate limiting and parsing"""

    def __init__(self):
        self.edgar = sec_edgar_service  # Existing service
        self.rate_limiter = SECRateLimiter()

    async def get_cik(self, ticker: str) -> str:
        """Map ticker to CIK"""
        results = await self.edgar.search_company(ticker)
        if not results:
            raise CompanyNotFoundError(ticker)
        return results[0]["cik"]

    async def get_latest_10q(self, ticker: str) -> dict:
        """Get latest 10-Q filing metadata"""
        cik = await self.get_cik(ticker)
        filings = await self.edgar.get_filings(cik, ["10-Q"], limit=1)
        if not filings:
            raise FilingNotFoundError(ticker, "10-Q")
        return filings[0]

    async def parse_filing_to_markdown(self, document_url: str) -> str:
        """Fetch and parse filing to clean Markdown"""
        html = await self.rate_limiter.execute_with_backoff(
            lambda: self.edgar.get_filing_document(document_url)
        )
        return self._convert_to_markdown(html)
```

#### Step 3: Create `FilingParser` Service
```python
# backend/app/services/filing_parser.py
from sec_parser import SemanticTree, TreeBuilder

class FilingParser:
    """Parse SEC filings into semantic structure"""

    def parse(self, html: str) -> SemanticTree:
        """Parse HTML into semantic tree"""
        tree = SemanticTree.from_html(html)
        return tree

    def extract_sections(self, tree: SemanticTree) -> dict:
        """Extract standard 10-Q sections"""
        sections = {
            "financial_statements": None,
            "mdna": None,
            "market_risk": None,
            "controls": None,
            "risk_factors": None,
            "legal_proceedings": None,
        }
        # Map sec-parser sections to our structure
        for section in tree.sections:
            # Detection logic...
        return sections
```

#### Step 4: Create `MarkdownSerializer` Service
```python
# backend/app/services/markdown_serializer.py
class MarkdownSerializer:
    """Convert semantic sections to clean Markdown"""

    def serialize(self, sections: dict, metadata: dict) -> str:
        """Convert parsed sections to Markdown"""
        md_parts = [
            self._render_header(metadata),
            self._render_financial_statements(sections.get("financial_statements")),
            self._render_mdna(sections.get("mdna")),
            self._render_risk_factors(sections.get("risk_factors")),
            self._render_footer(metadata),
        ]
        return "\n\n".join(filter(None, md_parts))

    def _render_table(self, table_data: list) -> str:
        """Convert table to Markdown table format"""
        # Handle complex SEC tables...
```

#### Step 5: Add API Endpoint
```python
# backend/app/routers/filings.py (add to existing)

@router.get("/{ticker}/10q/markdown")
async def get_10q_markdown(
    ticker: str,
    db: Session = Depends(get_db)
) -> FilingMarkdownResponse:
    """Get latest 10-Q as clean Markdown"""
    client = SECClient()

    # Get filing metadata
    filing = await client.get_latest_10q(ticker)

    # Check cache first
    cached = await _get_cached_markdown(db, filing["accession_number"])
    if cached:
        return cached

    # Parse and convert
    markdown = await client.parse_filing_to_markdown(filing["document_url"])

    # Cache result
    await _cache_markdown(db, filing["accession_number"], markdown)

    return FilingMarkdownResponse(
        filing_date=filing["filing_date"],
        accession_number=filing["accession_number"],
        markdown_content=markdown,
    )
```

---

## 9. Testing Strategy

### Unit Tests
```python
# tests/test_filing_parser.py
def test_parse_standard_10q():
    """Test parsing a standard 10-Q filing"""
    html = load_fixture("aapl_10q_2024.html")
    parser = FilingParser()
    tree = parser.parse(html)

    assert tree.sections is not None
    assert any("Management" in s.title for s in tree.sections)

def test_parse_amended_10q():
    """Test parsing 10-Q/A (amended filing)"""
    ...

def test_handle_malformed_html():
    """Test graceful handling of malformed HTML"""
    ...
```

### Integration Tests
```python
# tests/test_sec_client.py
async def test_get_cik_apple():
    client = SECClient()
    cik = await client.get_cik("AAPL")
    assert cik == "0000320193"

async def test_rate_limiting():
    """Test that rate limiter respects SEC limits"""
    ...
```

### Fixtures
Store sample filings for reproducible tests:
```
tests/fixtures/
├── aapl_10q_2024.html
├── msft_10q_2024.html
├── amended_10q_example.html
└── malformed_filing.html
```

---

## 10. Caching Strategy

### Database Schema Enhancement

```python
# Enhance FilingContentCache model
class FilingContentCache(Base):
    __tablename__ = "filing_content_cache"

    id = Column(Integer, primary_key=True)
    filing_id = Column(Integer, ForeignKey("filings.id"))
    critical_excerpt = Column(Text)          # Existing
    markdown_content = Column(Text)          # NEW
    markdown_generated_at = Column(DateTime) # NEW
    sections_json = Column(JSON)             # NEW: Parsed sections
```

### Cache Flow
1. Request comes in for ticker's 10-Q markdown
2. Check `filing_content_cache.markdown_content`
3. If cached and < 24 hours old, return cached
4. Otherwise, fetch → parse → serialize → cache → return

---

## 11. Monitoring & Observability

### Logging Points
```python
logger.info(f"Fetching 10-Q for {ticker}, CIK: {cik}")
logger.info(f"SEC request: {url}, attempt {attempt}")
logger.warning(f"Rate limited, backing off {backoff}s")
logger.error(f"Failed to parse filing: {accession_number}", exc_info=True)
```

### Metrics to Track
- SEC API request latency
- Rate limit hits per hour
- Parse success/failure rate
- Cache hit rate
- Markdown generation time

---

## 12. Rollout Plan

### Phase 2a: Core Implementation (Week 1)
- [ ] Install `sec-parser` dependency
- [ ] Create `SECClient` facade with rate limiting
- [ ] Create `FilingParser` service
- [ ] Create `MarkdownSerializer` service
- [ ] Add `/api/filings/{ticker}/10q/markdown` endpoint

### Phase 2b: Testing & Refinement (Week 2)
- [ ] Write unit tests for parser
- [ ] Write integration tests for SEC client
- [ ] Test with 20+ different company filings
- [ ] Handle edge cases identified in testing

### Phase 2c: Caching & Performance (Week 3)
- [ ] Implement database caching
- [ ] Add cache invalidation logic
- [ ] Performance optimization
- [ ] Load testing

### Phase 2d: Production Deployment
- [ ] Update production dependencies
- [ ] Deploy to Render
- [ ] Monitor for issues
- [ ] Documentation update

---

## 13. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SEC API changes | Low | High | Monitor SEC announcements, abstract API layer |
| `sec-parser` breaking changes | Medium | Medium | Pin version, have fallback parser |
| Rate limit blocking | Medium | High | Implement proper backoff, request queuing |
| Large filing timeout | Medium | Medium | Streaming parser, chunk processing |
| Non-standard filing formats | High | Low | Graceful degradation, log and skip |

---

## 14. Success Criteria

1. **Accuracy:** Markdown output correctly represents 95%+ of filing content
2. **Completeness:** All standard 10-Q sections extracted when present
3. **Performance:** Response time < 5 seconds for cached, < 30 seconds for uncached
4. **Reliability:** < 0.1% error rate on valid tickers
5. **Compliance:** Zero SEC rate limit violations

---

## Appendix A: Sample API Request/Response

### Request
```bash
GET /api/filings/AAPL/10q/markdown
Authorization: Bearer {token}
```

### Response
```json
{
  "filing_date": "2024-01-26",
  "accession_number": "0000320193-24-000006",
  "markdown_content": "# Apple Inc. - 10-Q (Q1 2024)\n\n## Filing Information\n- **Filed:** January 26, 2024\n- **Period Ending:** December 30, 2023\n...",
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
```

---

## Appendix B: sec-parser Quick Reference

```python
from sec_parser import SemanticTree
from sec_parser.processing_engine import HtmlTag

# Parse HTML
tree = SemanticTree.from_html(html_content)

# Iterate sections
for node in tree:
    print(f"Type: {type(node).__name__}")
    print(f"Text preview: {node.text[:100]}...")

# Get specific section types
from sec_parser.semantic_elements import (
    TextElement,
    TitleElement,
    TableElement,
)

for node in tree:
    if isinstance(node, TitleElement):
        print(f"Section: {node.text}")
```

---

**Document Version:** 1.0
**Author:** Claude (AI Assistant)
**Date:** January 21, 2026
**Status:** Awaiting Approval
