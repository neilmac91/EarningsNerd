# SEC 10-K Filing Pipeline Architecture Plan

## Executive Summary

This document outlines the architecture for a production-grade SEC 10-K filing pipeline that integrates with EarningsNerd's existing backend infrastructure. The design leverages the existing 10-Q pipeline patterns, extending them for 10-K specific requirements.

---

## 1. Directory Structure

```
backend/
├── app/
│   ├── services/
│   │   ├── sec_edgar.py          # [EXISTS] CIK lookup, filing metadata
│   │   ├── sec_client.py         # [EXTEND] Add 10-K facade methods
│   │   ├── sec_rate_limiter.py   # [EXISTS] Token bucket rate limiter
│   │   ├── filing_parser.py      # [EXTEND] Add 10-K section detection
│   │   ├── markdown_serializer.py # [EXTEND] Add 10-K section mapping
│   │   └── xbrl_service.py       # [EXISTS] XBRL extraction (shared)
│   │
│   ├── routers/
│   │   └── filings.py            # [EXTEND] Add /10k/markdown endpoint
│   │
│   ├── models/
│   │   └── __init__.py           # [EXISTS] FilingContentCache reused
│   │
│   └── schemas/
│       └── filings.py            # [EXTEND] Add 10-K response schemas
│
└── docs/
    └── plan_sec_pipeline.md      # This document
```

### Design Rationale

- **No new service files**: 10-K follows identical flow to 10-Q; section differences are handled via configuration
- **Reuse FilingContentCache**: Same table, differentiated by `filing_type` on the parent `Filing` record
- **Single endpoint extension**: Follows established pattern of `/api/filings/{ticker}/10k/markdown`

---

## 2. Rate Limit Strategy

### SEC EDGAR Enforcement
- **Hard Limit**: 10 requests/second per User-Agent
- **Consequence**: 403 Forbidden with IP blocking risk

### Existing Implementation (sec_rate_limiter.py)

```
┌─────────────────────────────────────────────────────────┐
│                  Token Bucket Algorithm                  │
├─────────────────────────────────────────────────────────┤
│  Bucket Capacity: 10 tokens                             │
│  Refill Rate: 10 tokens/second                          │
│  Strategy: Acquire token before each request            │
└─────────────────────────────────────────────────────────┘
```

### Throttling Approach

| Component | Value | Justification |
|-----------|-------|---------------|
| **Bucket Size** | 10 tokens | Match SEC's 10 req/sec |
| **Request Spacing** | 100ms minimum | `10 req/sec = 1 req/100ms` |
| **Burst Allowance** | Up to 10 queued | Handle batch operations |
| **Backoff Base** | 1.0 second | Per `SEC_BASE_BACKOFF_SECONDS` config |
| **Backoff Multiplier** | 2x exponential | 1s → 2s → 4s → 8s → 16s |
| **Max Retries** | 5 attempts | Per `SEC_MAX_RETRIES` config |
| **Jitter** | ±10% randomization | Prevent thundering herd |

### Code Pattern (Existing)

```python
# From sec_rate_limiter.py - already implemented
@retry(
    retry=retry_if_exception_type(RateLimitError),
    wait=wait_exponential(multiplier=1, min=1, max=32),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
async def fetch_with_rate_limit(self, url: str) -> Response:
    await self.limiter.acquire()  # Token bucket
    return await self._make_request(url)
```

### User-Agent Compliance

```python
# From config.py - already configured
SEC_USER_AGENT: str = "EarningsNerd/1.0 (contact@earningsnerd.io)"

# Applied in sec_edgar.py
headers = {
    "User-Agent": settings.SEC_USER_AGENT,
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate"
}
```

---

## 3. Data Flow

### Complete Pipeline Trace

```
┌────────────────────────────────────────────────────────────────────────┐
│                        10-K Pipeline Data Flow                         │
└────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────┐
                    │  "AAPL"     │  ← User input (ticker)
                    └──────┬──────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 1: CIK Lookup                                                    │
│ Endpoint: https://data.sec.gov/submissions/CIK{cik}.json             │
│ Cache: In-memory (24-hour TTL)                                        │
├──────────────────────────────────────────────────────────────────────┤
│ sec_edgar.py → get_company_info(ticker="AAPL")                       │
│ Response: { "cik": "0000320193", "name": "Apple Inc" }               │
└──────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 2: Filing Index Query                                            │
│ Endpoint: https://data.sec.gov/submissions/CIK0000320193.json        │
│ Filter: filings.recent where form == "10-K"                           │
├──────────────────────────────────────────────────────────────────────┤
│ sec_edgar.py → get_filings(cik, filing_type="10-K", limit=1)         │
│ Response: {                                                           │
│   "accessionNumber": "0000320193-23-000106",                         │
│   "filingDate": "2023-11-03",                                         │
│   "primaryDocument": "aapl-20230930.htm"                             │
│ }                                                                     │
└──────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 3: Construct Document URL                                        │
│ Pattern: /Archives/edgar/data/{cik}/{accession}/{primaryDoc}         │
├──────────────────────────────────────────────────────────────────────┤
│ URL: https://www.sec.gov/Archives/edgar/data/320193/                 │
│      000032019323000106/aapl-20230930.htm                             │
└──────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 4: HTML Fetch (Rate Limited)                                     │
│ Timeout: 120 seconds (10-K documents are large)                       │
├──────────────────────────────────────────────────────────────────────┤
│ sec_rate_limiter.py → fetch_with_rate_limit(url)                     │
│ Response: Raw HTML (typically 1-5 MB for 10-K)                       │
└──────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 5: Semantic Parsing (sec-parser)                                 │
│ Library: sec-parser >= 0.58.0                                         │
├──────────────────────────────────────────────────────────────────────┤
│ filing_parser.py → parse_10k(html_content)                           │
│ Output: {                                                             │
│   "sections": [                                                       │
│     { "type": "ITEM_1", "title": "Business", "content": "..." },     │
│     { "type": "ITEM_1A", "title": "Risk Factors", "content": "..." },│
│     { "type": "ITEM_7", "title": "MD&A", "content": "..." },         │
│     { "type": "ITEM_8", "title": "Financial Statements", ... }       │
│   ],                                                                  │
│   "tables": [ ... preserved as structured data ... ]                 │
│ }                                                                     │
└──────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 6: Markdown Serialization                                        │
│ Tables preserved: <table> → | col | col | format                     │
├──────────────────────────────────────────────────────────────────────┤
│ markdown_serializer.py → serialize_10k(parsed_sections)              │
│ Output: Complete Markdown document with:                              │
│   - Header metadata                                                   │
│   - Part I sections (Items 1, 1A, 1B, 2, 3, 4)                       │
│   - Part II sections (Items 5, 6, 7, 7A, 8, 9, 9A, 9B)               │
│   - Part III sections (Items 10, 11, 12, 13, 14)                     │
│   - Financial tables as valid Markdown                                │
└──────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 7: Database Caching                                              │
│ Table: filing_content_cache                                           │
├──────────────────────────────────────────────────────────────────────┤
│ FilingContentCache(                                                   │
│   filing_id=123,                                                      │
│   markdown_content="# Apple Inc 10-K...",                            │
│   markdown_sections={"item_1": "...", "item_7": "..."},              │
│   markdown_generated_at=datetime.utcnow()                            │
│ )                                                                     │
└──────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Markdown   │  → Ready for AI analysis
                    └─────────────┘
```

### 10-K Section Structure (vs 10-Q)

| Part | Item | 10-K Content | Equivalent in 10-Q |
|------|------|--------------|-------------------|
| I | 1 | Business | N/A |
| I | 1A | Risk Factors | Part II, Item 1A |
| I | 1B | Unresolved Staff Comments | N/A |
| I | 2 | Properties | N/A |
| I | 3 | Legal Proceedings | Part II, Item 1 |
| I | 4 | Mine Safety Disclosures | N/A |
| II | 5 | Market for Equity | N/A |
| II | 6 | Selected Financial Data | N/A |
| II | 7 | **MD&A** | Part I, Item 2 |
| II | 7A | Market Risk | Part I, Item 3 |
| II | 8 | **Financial Statements** | Part I, Item 1 |
| II | 9 | Disagreements with Accountants | N/A |
| II | 9A | Controls and Procedures | Part I, Item 4 |
| III | 10-14 | Directors, Compensation, etc. | N/A |
| IV | 15 | Exhibits | Part II, Item 6 |

---

## 4. Error Handling Matrix

### HTTP Error Recovery

| Status Code | Error Type | Recovery Action | Retry? | Max Attempts |
|-------------|------------|-----------------|--------|--------------|
| **200** | Success | Process response | N/A | N/A |
| **301/302** | Redirect | Follow redirect automatically | Yes | 3 |
| **400** | Bad Request | Log error, return client error | No | 0 |
| **403** | Forbidden | User-Agent issue or IP block; alert ops | No | 0 |
| **404** | Not Found | Filing doesn't exist; return null | No | 0 |
| **429** | Rate Limited | Exponential backoff with jitter | Yes | 5 |
| **500** | Server Error | Retry with backoff | Yes | 3 |
| **502/503/504** | Gateway Error | Retry with backoff | Yes | 5 |
| **Timeout** | Read Timeout | Increase timeout, retry | Yes | 2 |
| **Connection** | Network Error | Retry with backoff | Yes | 3 |

### Parsing Error Recovery

| Error Type | Detection | Recovery Action |
|------------|-----------|-----------------|
| **Empty HTML** | `len(content) < 1000` | Return error; likely redirect page |
| **Malformed HTML** | BeautifulSoup parse failure | Attempt raw text extraction |
| **sec-parser Failure** | Exception from library | Fallback to regex section detection |
| **No Sections Found** | `len(sections) == 0` | Return raw content; flag for review |
| **Table Parse Error** | Markdown table malformed | Preserve as HTML-in-markdown block |
| **Encoding Error** | UnicodeDecodeError | Try latin-1, then replace errors |
| **Memory Error** | Document > 50MB | Stream parse; truncate if needed |

### Application Error Mapping

```python
# Custom exceptions for clear error propagation
class SECPipelineError(Exception):
    """Base exception for SEC pipeline"""
    pass

class CIKNotFoundError(SECPipelineError):
    """Ticker has no CIK mapping"""
    status_code = 404

class FilingNotFoundError(SECPipelineError):
    """No 10-K filings exist for company"""
    status_code = 404

class RateLimitExceededError(SECPipelineError):
    """SEC rate limit hit after max retries"""
    status_code = 429
    retry_after = 60  # seconds

class ParsingError(SECPipelineError):
    """HTML parsing failed"""
    status_code = 502

class DocumentTooLargeError(SECPipelineError):
    """Filing exceeds size limit"""
    status_code = 413
```

### Error Response Format

```json
{
  "success": false,
  "error": {
    "code": "FILING_NOT_FOUND",
    "message": "No 10-K filings found for ticker XYZ",
    "details": {
      "ticker": "XYZ",
      "cik": "0001234567",
      "searched_filing_type": "10-K"
    }
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## 5. Integration Points

### 5.1 FastAPI Router Extension

```python
# routers/filings.py - New endpoint

@router.get(
    "/{ticker}/10k/markdown",
    response_model=FilingMarkdownResponse,
    summary="Get latest 10-K as Markdown",
    responses={
        404: {"description": "Company or filing not found"},
        429: {"description": "Rate limit exceeded"},
        502: {"description": "SEC EDGAR unavailable"}
    }
)
async def get_10k_markdown(
    ticker: str = Path(..., description="Stock ticker symbol"),
    force_refresh: bool = Query(False, description="Bypass cache"),
    db: Session = Depends(get_db)
) -> FilingMarkdownResponse:
    """
    Fetch and parse the latest SEC 10-K filing to Markdown format.

    - Financial tables preserved as Markdown tables
    - Sections extracted: Business, Risk Factors, MD&A, Financial Statements
    - Cached in database; use force_refresh=true to regenerate
    """
```

### 5.2 SEC Client Facade Extension

```python
# services/sec_client.py - New methods

class SECClient:
    async def get_latest_10k(self, ticker: str) -> Optional[Dict]:
        """Get metadata for most recent 10-K filing"""
        cik = await self.get_cik(ticker)
        filings = await self.edgar.get_filings(cik, filing_type="10-K", limit=1)
        return filings[0] if filings else None

    async def get_10k_filings(
        self,
        ticker: str,
        limit: int = 5
    ) -> List[Dict]:
        """Get list of 10-K filings for company"""
        cik = await self.get_cik(ticker)
        return await self.edgar.get_filings(cik, filing_type="10-K", limit=limit)

    async def parse_10k_to_markdown(
        self,
        ticker: str,
        accession_number: Optional[str] = None
    ) -> FilingMarkdownResult:
        """Full pipeline: fetch 10-K HTML and convert to Markdown"""
```

### 5.3 Database Caching (Existing Infrastructure)

```python
# Cache check pattern (same as 10-Q)

# 1. Query existing filing record
filing = db.query(Filing).join(Company).filter(
    Company.ticker == ticker.upper(),
    Filing.filing_type == "10-K"
).order_by(Filing.filing_date.desc()).first()

# 2. Check content cache
if filing and filing.content_cache:
    cache = filing.content_cache
    if cache.markdown_content and not force_refresh:
        return FilingMarkdownResponse(
            ticker=ticker,
            filing_type="10-K",
            markdown_content=cache.markdown_content,
            sections=cache.markdown_sections,
            cached=True,
            generated_at=cache.markdown_generated_at
        )

# 3. Generate fresh content
result = await sec_client.parse_10k_to_markdown(ticker)

# 4. Store in cache
cache = FilingContentCache(
    filing_id=filing.id,
    markdown_content=result.markdown_content,
    markdown_sections=result.sections,
    markdown_generated_at=datetime.utcnow()
)
db.merge(cache)
db.commit()
```

### 5.4 Redis Caching (Future Enhancement)

While Redis is configured but not actively used, here's the integration pattern for future implementation:

```python
# Potential Redis caching layer for hot data
class RedisCacheLayer:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
        self.ttl_filing_metadata = 3600      # 1 hour
        self.ttl_markdown_content = 86400    # 24 hours

    async def get_10k_markdown(self, ticker: str) -> Optional[str]:
        key = f"10k:markdown:{ticker.upper()}"
        return await self.redis.get(key)

    async def set_10k_markdown(self, ticker: str, content: str):
        key = f"10k:markdown:{ticker.upper()}"
        await self.redis.setex(key, self.ttl_markdown_content, content)
```

### 5.5 Processing Profile Configuration

```python
# 10-K specific processing settings
PROCESSING_PROFILES = {
    "10-K": {
        "document_timeout": 120.0,      # Longer timeout for large docs
        "xbrl_timeout": 6.0,            # Complex XBRL for annual filings
        "max_document_size_mb": 50,     # Size limit
        "include_exhibits": False,      # Exclude exhibit files
        "sections_priority": [          # Ordered by AI relevance
            "ITEM_7",   # MD&A (most critical for analysis)
            "ITEM_1A",  # Risk Factors
            "ITEM_8",   # Financial Statements
            "ITEM_1",   # Business Description
            "ITEM_7A",  # Market Risk
        ],
        "table_extraction": {
            "preserve_formatting": True,
            "max_columns": 20,
            "max_rows": 500
        }
    },
    "10-Q": {
        "document_timeout": 100.0,
        "xbrl_timeout": 3.0,
        # ... existing 10-Q profile
    }
}
```

---

## 6. Pydantic Schemas

```python
# schemas/filings.py - Response models

class FilingMarkdownResponse(BaseModel):
    ticker: str
    filing_type: Literal["10-K", "10-Q", "8-K"]
    accession_number: str
    filing_date: date
    period_end_date: date
    markdown_content: str
    sections: Dict[str, str]  # {"item_1": "...", "item_7": "..."}
    cached: bool
    generated_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "ticker": "AAPL",
                "filing_type": "10-K",
                "accession_number": "0000320193-23-000106",
                "filing_date": "2023-11-03",
                "period_end_date": "2023-09-30",
                "markdown_content": "# Apple Inc. 10-K\n\n## Item 1. Business...",
                "sections": {
                    "item_1": "Apple Inc. designs...",
                    "item_7": "This MD&A section..."
                },
                "cached": True,
                "generated_at": "2024-01-15T10:30:00Z"
            }
        }

class Filing10KListResponse(BaseModel):
    ticker: str
    company_name: str
    cik: str
    filings: List[Filing10KSummary]
    total_count: int

class Filing10KSummary(BaseModel):
    accession_number: str
    filing_date: date
    period_end_date: date
    fiscal_year: int
    document_url: str
    has_cached_markdown: bool
```

---

## 7. Testing Strategy

### Unit Tests
- CIK lookup with valid/invalid tickers
- Filing URL construction
- sec-parser section extraction
- Markdown table formatting
- Error handling for each failure mode

### Integration Tests
- Full pipeline: ticker → markdown (with mocked SEC responses)
- Database caching roundtrip
- Rate limiter behavior under load

### Contract Tests
- SEC EDGAR API response format validation
- Verify User-Agent compliance in requests

### Performance Benchmarks
- Parse time for varying document sizes
- Memory usage for large filings
- Cache hit/miss latency comparison

---

## 8. Monitoring & Observability

### Metrics to Track
- `sec_10k_fetch_duration_seconds` - End-to-end pipeline time
- `sec_10k_parse_duration_seconds` - sec-parser processing time
- `sec_10k_cache_hit_ratio` - Cache effectiveness
- `sec_rate_limit_retries_total` - Rate limiting events
- `sec_10k_document_size_bytes` - Filing sizes

### Logging Points
- INFO: Successful fetch/parse completions
- WARNING: Rate limit retries, cache misses
- ERROR: Parse failures, SEC API errors

---

## 9. Rollout Plan

### Phase 1: Core Implementation (This PR)
- [ ] Extend `sec_client.py` with 10-K methods
- [ ] Add 10-K section mapping to `filing_parser.py`
- [ ] Update `markdown_serializer.py` for 10-K structure
- [ ] Create `/api/filings/{ticker}/10k/markdown` endpoint
- [ ] Add Pydantic response schemas
- [ ] Write unit tests

### Phase 2: Production Hardening
- [ ] Load testing with realistic traffic
- [ ] Error alerting integration
- [ ] Documentation for API consumers

### Phase 3: Enhancements
- [ ] Redis caching layer
- [ ] Batch processing for multiple tickers
- [ ] Historical 10-K comparison features

---

## Appendix A: SEC EDGAR API Reference

### Endpoints Used

| Endpoint | Purpose | Rate Limited |
|----------|---------|--------------|
| `data.sec.gov/submissions/CIK{cik}.json` | Company info + filing index | Yes |
| `www.sec.gov/Archives/edgar/data/{cik}/{accession}/{doc}` | Filing HTML | Yes |
| `data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json` | XBRL data | Yes |

### Response Caching Headers
- SEC sets `Cache-Control: max-age=600` on submissions
- Our cache should respect or extend based on data staleness needs

---

## Appendix B: sec-parser Library Usage

```python
from sec_parser import SemanticTree
from sec_parser.processing_engine import TreeBuilder

def parse_10k(html_content: str) -> Dict:
    """Parse 10-K HTML using sec-parser semantic tree"""
    tree = SemanticTree.from_html(html_content)
    builder = TreeBuilder(tree)

    sections = {}
    for node in builder.nodes:
        if node.semantic_type.startswith("ITEM_"):
            sections[node.semantic_type.lower()] = node.text_content

    return {
        "sections": sections,
        "tables": [t.to_markdown() for t in tree.tables]
    }
```

---

*Document Version: 1.0*
*Created: 2024-01-22*
*Author: Claude (AI Pipeline Architect)*
*Status: AWAITING APPROVAL*
