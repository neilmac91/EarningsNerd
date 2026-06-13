# AI API Optimization Implementation Plan

**Document Created:** 2026-01-25
**Status:** Ready for Implementation
**Based On:** `docs/AI_API_OPTIMIZATIONS.md`
**Validated Against:** Actual codebase as of 2026-01-25

---

## Executive Summary

This document provides a **step-by-step implementation plan** for the 6 optimizations identified in `AI_API_OPTIMIZATIONS.md`. Each optimization has been validated against the actual codebase, with precise file locations, code changes, testing strategies, and rollback procedures.

**Expected Outcomes:**
- ~40% latency reduction (45-90s → 25-50s for 10-K filings)
- ~30% cost reduction (Flash model for recovery/writer stages)
- Improved reliability through caching and parallel processing

---

## Pre-Implementation Checklist

Before starting any implementation:

- [ ] Create feature branch: `git checkout -b feature/ai-api-optimizations`
- [ ] Ensure all existing tests pass: `pytest backend/tests/`
- [ ] Take baseline latency measurements (documented in section below)
- [ ] Backup current `openai_service.py` and `xbrl_service.py`
- [ ] Verify Redis is running for cache implementations

### Baseline Metrics to Capture

Run these commands and record results before any changes:

```bash
# Run the existing latency test
cd backend && pytest tests/integration/test_stream_latency.py -v --tb=short

# Record 5 sample summary generations with timing
# (Manual test in staging environment)
```

| Metric | Baseline Value | Date Captured |
|--------|---------------|---------------|
| 10-K Average Latency | ___ seconds | |
| 10-Q Average Latency | ___ seconds | |
| Average AI Calls per Summary | ___ | |
| Recovery Stage Duration (avg) | ___ seconds | |

---

## Implementation Phase 1: Quick Wins (Low Effort, Immediate Impact)

### 1.1 Fix Duplicate Prompt Lines

**Priority:** TRIVIAL
**Estimated Time:** 5 minutes
**Risk Level:** None
**File:** `backend/app/services/openai_service.py`

#### Validation

Current duplicate confirmed at lines 2173-2174:
```python
"6. Only include bullets you can prove..."
"6. Only include bullets you can prove..."  # DUPLICATE!
```

#### Implementation Steps

1. Open `backend/app/services/openai_service.py`
2. Navigate to line 2173-2174
3. Delete line 2174 (the duplicate)
4. Verify the remaining line is correct:
   ```python
   6. Only include bullets you can prove. Every risk or notable item must cite specific supporting evidence (exact filing excerpt or XBRL tag) in the `supporting_evidence` field.
   ```

#### Testing

```bash
# Syntax check
python -m py_compile backend/app/services/openai_service.py

# Run unit tests
pytest backend/tests/unit/ -v
```

#### Rollback

```bash
git checkout backend/app/services/openai_service.py
```

---

### 1.2 Add Model Selection by Task

**Priority:** HIGH
**Estimated Time:** 30 minutes
**Risk Level:** Low (models already defined)
**File:** `backend/app/services/openai_service.py`

#### Current State (Validated)

```python
# Lines 188-212
self._MODEL_GEMINI_3_PRO = "gemini-3-pro-preview"
self._MODEL_GEMINI_2_5_PRO = "gemini-2.5-pro"
self._MODEL_GEMINI_2_5_FLASH = "gemini-2.5-flash"

# Currently ALL tasks use gemini-3-pro-preview
```

#### Implementation Steps

**Step 1:** Add task-specific model configuration in `__init__` method (after line 212):

```python
# Add after line 212 in __init__
# Task-specific model selection for cost optimization
self._task_models = {
    "structured_extraction": self._MODEL_GEMINI_3_PRO,   # Needs high accuracy
    "section_recovery": self._MODEL_GEMINI_2_5_FLASH,    # Simpler task, lower cost
    "editorial_writer": self._MODEL_GEMINI_2_5_PRO,      # Creative but constrained
}
```

**Step 2:** Add helper method after `get_model_for_filing` (after line 223):

```python
def get_model_for_task(self, task_type: str, filing_type: Optional[str] = None) -> str:
    """Return the appropriate model for a specific task type.

    Task types:
    - structured_extraction: Primary JSON extraction (needs highest accuracy)
    - section_recovery: Fill missing sections (simpler, use Flash)
    - editorial_writer: Convert to markdown (creative, use Pro)

    Falls back to filing-type model if task not recognized.
    """
    if task_type in self._task_models:
        return self._task_models[task_type]
    return self.get_model_for_filing(filing_type)
```

**Step 3:** Update `_run_secondary_completion` method (line 1128):

```python
# Change line 1128 FROM:
models_to_try = [self.get_model_for_filing(filing_type_key)] + self._fallback_models

# TO:
models_to_try = [self.get_model_for_task("section_recovery", filing_type_key)] + self._fallback_models
```

**Step 4:** Update `generate_editorial_markdown` method (find the model selection, around line 1940):

```python
# In generate_editorial_markdown, update model selection to use:
model = self.get_model_for_task("editorial_writer", filing_type_key)
```

#### Testing

```bash
# Unit tests
pytest backend/tests/unit/ -v

# Integration test - verify model selection
pytest backend/tests/integration/test_summaries_flow.py -v

# Manual verification - add temporary logging:
# In get_model_for_task, add:
# logger.info(f"Task {task_type}: using model {model}")
```

#### Verification Checklist

- [ ] Recovery calls use `gemini-2.5-flash`
- [ ] Editorial calls use `gemini-2.5-pro`
- [ ] Structured extraction still uses `gemini-3-pro-preview`
- [ ] Fallback chain still works if primary model fails

#### Rollback

```bash
git checkout backend/app/services/openai_service.py
```

---

## Implementation Phase 2: Medium Effort Optimizations

### 2.1 Cache XBRL Metrics

**Priority:** MEDIUM
**Estimated Time:** 45 minutes
**Risk Level:** Low
**Files:**
- `backend/app/services/xbrl_service.py`
- `backend/app/config.py`

#### Current State (Validated)

The `get_xbrl_data` method (lines 46-73) fetches fresh data on every request with no caching.

#### Implementation Steps

**Step 1:** Add cache configuration to `backend/app/config.py` (before `settings = Settings()`):

```python
# Add after line 96 (after STREAM_TIMEOUT)

# Cache Settings
XBRL_CACHE_TTL_HOURS: int = 24  # XBRL data rarely changes
STRUCTURED_EXTRACTION_CACHE_TTL_SECONDS: int = 3600  # 1 hour for retry window
```

**Step 2:** Update `backend/app/services/xbrl_service.py`:

```python
# Replace the imports section (lines 1-8) with:
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import httpx
import re
import logging
from bs4 import BeautifulSoup
from app.config import settings

logger = logging.getLogger(__name__)

# Module-level cache for XBRL data
# Key: "{cik}:{accession_number}"
# Value: (cached_datetime, data_dict)
_xbrl_cache: Dict[str, Tuple[datetime, Optional[Dict]]] = {}


def _get_cache_ttl() -> timedelta:
    """Get cache TTL from settings, with fallback."""
    ttl_hours = getattr(settings, 'XBRL_CACHE_TTL_HOURS', 24)
    return timedelta(hours=ttl_hours)


def clear_xbrl_cache() -> int:
    """Clear the XBRL cache. Returns number of entries cleared."""
    global _xbrl_cache
    count = len(_xbrl_cache)
    _xbrl_cache.clear()
    return count


def get_xbrl_cache_stats() -> Dict[str, int]:
    """Get cache statistics for monitoring."""
    now = datetime.now()
    ttl = _get_cache_ttl()
    valid_count = sum(1 for cached_time, _ in _xbrl_cache.values()
                      if now - cached_time < ttl)
    return {
        "total_entries": len(_xbrl_cache),
        "valid_entries": valid_count,
        "expired_entries": len(_xbrl_cache) - valid_count,
    }
```

**Step 3:** Update the `get_xbrl_data` method in `XBRLService` class:

```python
async def get_xbrl_data(self, accession_number: str, cik: str) -> Optional[Dict]:
    """Extract XBRL data from SEC filing with caching."""
    global _xbrl_cache

    # Build cache key
    cache_key = f"{cik}:{accession_number}"
    ttl = _get_cache_ttl()

    # Check cache first
    if cache_key in _xbrl_cache:
        cached_time, cached_data = _xbrl_cache[cache_key]
        if datetime.now() - cached_time < ttl:
            logger.debug(f"XBRL cache hit for {cache_key}")
            return cached_data
        else:
            logger.debug(f"XBRL cache expired for {cache_key}")
            del _xbrl_cache[cache_key]

    # Cache miss - fetch from SEC
    try:
        cik_padded = str(cik).zfill(10)
        facts_url = f"{self.base_url}/api/xbrl/companyfacts/CIK{cik_padded}.json"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                facts_url,
                headers={"User-Agent": self.user_agent},
                timeout=30.0
            )

            if response.status_code == 200:
                data = response.json()
                result = self._parse_xbrl_facts(data, target_accession=accession_number)
            else:
                result = await self._extract_from_filing_html(accession_number, cik)

        # Cache the result (even if None, to avoid repeated failed lookups)
        _xbrl_cache[cache_key] = (datetime.now(), result)
        logger.debug(f"XBRL cached for {cache_key}")

        # Periodic cache cleanup (every 100 entries)
        if len(_xbrl_cache) > 100 and len(_xbrl_cache) % 100 == 0:
            _cleanup_expired_cache()

        return result

    except Exception as e:
        logger.error(f"Error fetching XBRL data: {str(e)}", exc_info=True)
        return None


def _cleanup_expired_cache() -> None:
    """Remove expired entries from cache."""
    global _xbrl_cache
    now = datetime.now()
    ttl = _get_cache_ttl()
    expired_keys = [
        key for key, (cached_time, _) in _xbrl_cache.items()
        if now - cached_time >= ttl
    ]
    for key in expired_keys:
        del _xbrl_cache[key]
    if expired_keys:
        logger.info(f"Cleaned up {len(expired_keys)} expired XBRL cache entries")
```

#### Testing

```bash
# Unit test for caching
cat > backend/tests/unit/test_xbrl_cache.py << 'EOF'
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
from app.services.xbrl_service import (
    XBRLService,
    _xbrl_cache,
    clear_xbrl_cache,
    get_xbrl_cache_stats,
)

@pytest.fixture
def xbrl_service():
    clear_xbrl_cache()
    return XBRLService()

@pytest.mark.asyncio
async def test_xbrl_cache_hit(xbrl_service):
    """Test that cached data is returned on second call."""
    cik = "0000320193"
    accession = "0000320193-24-000123"

    with patch.object(xbrl_service, '_fetch_from_sec', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {"revenue": [{"value": 100}]}

        # First call - should fetch
        result1 = await xbrl_service.get_xbrl_data(accession, cik)
        assert result1 is not None

        # Second call - should use cache (mock not called again)
        result2 = await xbrl_service.get_xbrl_data(accession, cik)
        assert result2 == result1

        # Verify fetch was only called once
        assert mock_fetch.call_count == 1

def test_cache_stats():
    """Test cache statistics."""
    clear_xbrl_cache()
    stats = get_xbrl_cache_stats()
    assert stats["total_entries"] == 0
EOF

pytest backend/tests/unit/test_xbrl_cache.py -v
```

#### Rollback

```bash
git checkout backend/app/services/xbrl_service.py
git checkout backend/app/config.py
rm backend/tests/unit/test_xbrl_cache.py
```

---

### 2.2 Parallelize Section Recovery

**Priority:** HIGH (Biggest Impact)
**Estimated Time:** 1-2 hours
**Risk Level:** Medium (concurrent API calls may hit rate limits)
**File:** `backend/app/services/openai_service.py`

#### Current State (Validated)

Lines 1163-1228: Sequential `for` loop processing each missing section one at a time.

```python
# Current (lines 1179-1227)
for section_key in missing_sections:
    # ... process one at a time
    content = await self._run_secondary_completion(filing_type_key, prompt)
```

#### Implementation Steps

**Step 1:** Add a semaphore configuration to `__init__` (after line 212):

```python
# Add to __init__ after line 212
# Concurrency control for parallel recovery
self._recovery_semaphore = asyncio.Semaphore(3)  # Max 3 concurrent recovery calls
```

**Step 2:** Create a helper method for single section recovery (add before `_recover_missing_sections`):

```python
async def _recover_single_section(
    self,
    section_key: str,
    filing_type_key: str,
    extracted_sections: Dict[str, str],
    filing_sample: str,
    metadata: Dict[str, Any],
) -> Tuple[str, Optional[Any]]:
    """Recover a single missing section. Returns (section_key, recovered_value or None)."""
    schema_snippet = self._get_section_schema_snippet(section_key)
    if not schema_snippet:
        return section_key, None

    context = self._build_section_context(section_key, extracted_sections, filing_sample)
    if not context:
        return section_key, None

    company_name = metadata.get("company_name", "The company")
    filing_type_label = metadata.get("filing_type", filing_type_key)
    reporting_period = metadata.get("reporting_period", "the reported period")

    prompt = f"""Company: {company_name}
Filing type: {filing_type_label}
Reporting period: {reporting_period}

Populate only the `{section_key}` portion of the structured summary schema shown below. Use concrete facts from the excerpt. If figures are missing, supply concise qualitative statements rather than placeholders.

SCHEMA:
{schema_snippet}

FILING EXCERPT:
{context}

Return JSON containing only the `{section_key}` key."""

    try:
        # Use semaphore to limit concurrent API calls
        async with self._recovery_semaphore:
            content = await self._run_secondary_completion(filing_type_key, prompt)
    except Exception as secondary_error:
        logger.warning(f"Secondary fill for {section_key} failed: {secondary_error}")
        return section_key, None

    if not content:
        return section_key, None

    cleaned = self._clean_json_payload(content)
    if not cleaned:
        return section_key, None

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        try:
            repaired = self._repair_json(cleaned)
            parsed = json.loads(repaired)
            logger.info(f"JSON repair successful for secondary fill: {section_key}")
        except json.JSONDecodeError:
            logger.warning(f"Secondary fill for {section_key} returned unfixable JSON: {cleaned[:200]}")
            return section_key, None

    section_value = parsed.get(section_key)
    if section_value is not None and not self._section_is_empty(section_value):
        return section_key, section_value

    return section_key, None
```

**Step 3:** Replace the `_recover_missing_sections` method (lines 1163-1228):

```python
async def _recover_missing_sections(
    self,
    missing_sections: List[str],
    filing_type_key: str,
    extracted_sections: Dict[str, str],
    filing_sample: str,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """Recover missing sections in parallel for improved latency."""
    import asyncio

    recovered: Dict[str, Any] = {}
    if not missing_sections:
        return recovered

    # Create tasks for all missing sections
    tasks = [
        self._recover_single_section(
            section_key,
            filing_type_key,
            extracted_sections,
            filing_sample,
            metadata,
        )
        for section_key in missing_sections
    ]

    # Execute all recovery tasks in parallel (with semaphore limiting concurrency)
    logger.info(f"Starting parallel recovery for {len(tasks)} sections")
    start_time = asyncio.get_event_loop().time()

    results = await asyncio.gather(*tasks, return_exceptions=True)

    elapsed = asyncio.get_event_loop().time() - start_time
    logger.info(f"Parallel recovery completed in {elapsed:.2f}s for {len(tasks)} sections")

    # Process results
    for result in results:
        if isinstance(result, Exception):
            logger.warning(f"Section recovery task failed: {result}")
            continue
        if isinstance(result, tuple) and len(result) == 2:
            section_key, section_value = result
            if section_value is not None:
                recovered[section_key] = section_value

    return recovered
```

**Step 4:** Add import at top of file if not present:

```python
from typing import Tuple  # Add Tuple to existing typing import
```

#### Testing

```bash
# Create specific test for parallel recovery
cat > backend/tests/unit/test_parallel_recovery.py << 'EOF'
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.openai_service import OpenAIService

@pytest.fixture
def openai_service():
    with patch('app.services.openai_service.settings') as mock_settings:
        mock_settings.OPENAI_API_KEY = "test-key"
        mock_settings.OPENAI_BASE_URL = "https://test.api"
        service = OpenAIService()
        service._recovery_semaphore = asyncio.Semaphore(3)
        return service

@pytest.mark.asyncio
async def test_parallel_recovery_faster_than_sequential(openai_service):
    """Verify parallel execution is faster than sequential."""
    # Mock the secondary completion to take 0.1s each
    call_count = 0
    async def mock_completion(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return '{"test_section": {"value": "test"}}'

    with patch.object(openai_service, '_run_secondary_completion', side_effect=mock_completion):
        with patch.object(openai_service, '_get_section_schema_snippet', return_value='{}'):
            with patch.object(openai_service, '_build_section_context', return_value='context'):
                with patch.object(openai_service, '_clean_json_payload', side_effect=lambda x: x):
                    with patch.object(openai_service, '_section_is_empty', return_value=False):

                        start = asyncio.get_event_loop().time()
                        result = await openai_service._recover_missing_sections(
                            missing_sections=["section1", "section2", "section3"],
                            filing_type_key="10-K",
                            extracted_sections={},
                            filing_sample="sample",
                            metadata={"company_name": "Test Co"},
                        )
                        elapsed = asyncio.get_event_loop().time() - start

                        # Should complete in ~0.1s (parallel) not 0.3s (sequential)
                        assert elapsed < 0.25, f"Parallel execution took {elapsed}s, expected < 0.25s"
                        assert call_count == 3

@pytest.mark.asyncio
async def test_semaphore_limits_concurrency(openai_service):
    """Verify semaphore limits concurrent API calls."""
    max_concurrent = 0
    current_concurrent = 0

    async def mock_completion(*args, **kwargs):
        nonlocal max_concurrent, current_concurrent
        current_concurrent += 1
        max_concurrent = max(max_concurrent, current_concurrent)
        await asyncio.sleep(0.05)
        current_concurrent -= 1
        return '{"test": "value"}'

    # Set semaphore to 2
    openai_service._recovery_semaphore = asyncio.Semaphore(2)

    with patch.object(openai_service, '_run_secondary_completion', side_effect=mock_completion):
        with patch.object(openai_service, '_get_section_schema_snippet', return_value='{}'):
            with patch.object(openai_service, '_build_section_context', return_value='context'):
                with patch.object(openai_service, '_clean_json_payload', side_effect=lambda x: x):
                    with patch.object(openai_service, '_section_is_empty', return_value=False):

                        await openai_service._recover_missing_sections(
                            missing_sections=["s1", "s2", "s3", "s4", "s5"],
                            filing_type_key="10-K",
                            extracted_sections={},
                            filing_sample="sample",
                            metadata={},
                        )

                        # Max concurrent should be limited to semaphore value
                        assert max_concurrent <= 2, f"Max concurrent was {max_concurrent}, expected <= 2"
EOF

pytest backend/tests/unit/test_parallel_recovery.py -v
```

#### Rate Limit Considerations

The semaphore limits concurrent calls to 3, but monitor for rate limit errors:

```python
# If rate limits are hit, reduce semaphore value:
self._recovery_semaphore = asyncio.Semaphore(2)  # More conservative
```

#### Rollback

```bash
git checkout backend/app/services/openai_service.py
rm backend/tests/unit/test_parallel_recovery.py
```

---

## Implementation Phase 3: Lower Priority Optimizations

### 3.1 Add Token Counting

**Priority:** LOW
**Estimated Time:** 1 hour
**Risk Level:** Low
**Files:**
- `backend/app/services/openai_service.py`
- `backend/requirements.txt`

#### Implementation Steps

**Step 1:** Add tiktoken to requirements (note: may not work perfectly with Gemini, but provides estimates):

```bash
echo "tiktoken>=0.5.0" >> backend/requirements.txt
pip install tiktoken
```

**Step 2:** Add token estimation utility in `openai_service.py` (after imports):

```python
import tiktoken

# Token estimation (uses GPT-4 encoding as approximation for Gemini)
_token_encoder = None

def _get_token_encoder():
    global _token_encoder
    if _token_encoder is None:
        try:
            _token_encoder = tiktoken.encoding_for_model("gpt-4")
        except Exception:
            _token_encoder = tiktoken.get_encoding("cl100k_base")
    return _token_encoder

def estimate_tokens(text: str) -> int:
    """Estimate token count for text. Uses GPT-4 encoding as approximation."""
    if not text:
        return 0
    try:
        encoder = _get_token_encoder()
        return len(encoder.encode(text))
    except Exception:
        # Fallback: rough estimate of 4 chars per token
        return len(text) // 4
```

**Step 3:** Add pre-flight token check before main API calls (in `generate_structured_summary`):

```python
# Before the main API call, add:
estimated_input_tokens = estimate_tokens(system_prompt + user_prompt)
logger.info(f"Estimated input tokens: {estimated_input_tokens}")

MAX_INPUT_TOKENS = 28000  # Leave room for output
if estimated_input_tokens > MAX_INPUT_TOKENS:
    logger.warning(f"Input exceeds {MAX_INPUT_TOKENS} tokens ({estimated_input_tokens}). Truncating.")
    # Truncate filing_sample to fit
    excess = estimated_input_tokens - MAX_INPUT_TOKENS
    chars_to_remove = excess * 4  # Approximate
    filing_sample = filing_sample[:-chars_to_remove]
```

#### Testing

```bash
pytest backend/tests/unit/ -v -k "token"
```

---

### 3.2 Cache Structured Extraction Results (Redis)

**Priority:** LOW
**Estimated Time:** 1-2 hours
**Risk Level:** Medium (requires Redis)
**Files:**
- `backend/app/services/openai_service.py`
- `backend/app/config.py`

#### Prerequisites

- Redis must be running and configured
- `REDIS_URL` environment variable set

#### Implementation Steps

**Step 1:** Add Redis client utility:

```python
# Add to openai_service.py after imports
import hashlib
import redis.asyncio as redis

_redis_client = None

async def _get_redis_client():
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(settings.REDIS_URL)
            await _redis_client.ping()
        except Exception as e:
            logger.warning(f"Redis not available for caching: {e}")
            _redis_client = False  # Mark as unavailable
    return _redis_client if _redis_client else None
```

**Step 2:** Add caching wrapper for structured extraction:

```python
async def _get_cached_extraction(self, filing_id: int, content_hash: str) -> Optional[Dict]:
    """Check Redis cache for existing extraction result."""
    client = await _get_redis_client()
    if not client:
        return None

    cache_key = f"structured:{filing_id}:{content_hash}"
    try:
        cached = await client.get(cache_key)
        if cached:
            logger.info(f"Cache hit for structured extraction: {filing_id}")
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Redis cache read failed: {e}")
    return None

async def _cache_extraction(self, filing_id: int, content_hash: str, result: Dict) -> None:
    """Cache extraction result in Redis."""
    client = await _get_redis_client()
    if not client:
        return

    cache_key = f"structured:{filing_id}:{content_hash}"
    ttl = getattr(settings, 'STRUCTURED_EXTRACTION_CACHE_TTL_SECONDS', 3600)
    try:
        await client.setex(cache_key, ttl, json.dumps(result))
        logger.debug(f"Cached structured extraction: {filing_id}")
    except Exception as e:
        logger.warning(f"Redis cache write failed: {e}")
```

**Step 3:** Integrate caching into the extraction flow:

```python
# In generate_structured_summary, before the API call:
content_hash = hashlib.md5(filing_text[:10000].encode()).hexdigest()
cached = await self._get_cached_extraction(filing_id, content_hash)
if cached:
    return cached

# After successful extraction:
await self._cache_extraction(filing_id, content_hash, result)
```

---

## Testing Strategy

### Unit Tests

```bash
# Run all unit tests
pytest backend/tests/unit/ -v

# Run specific optimization tests
pytest backend/tests/unit/test_parallel_recovery.py -v
pytest backend/tests/unit/test_xbrl_cache.py -v
```

### Integration Tests

```bash
# Test full summary flow
pytest backend/tests/integration/test_summaries_flow.py -v

# Test streaming with heartbeat
pytest backend/tests/integration/test_summary_stream_heartbeat.py -v
```

### Performance Tests

```bash
# Latency tests
pytest backend/tests/integration/test_stream_latency.py -v

# Concurrent streams (to verify semaphore)
pytest backend/tests/performance/test_concurrent_streams.py -v
```

### Manual Verification

1. Generate a 10-K summary and time it
2. Generate a 10-Q summary and time it
3. Regenerate the same filing (should use cache)
4. Check logs for:
   - "parallel recovery" messages
   - "cache hit" messages
   - Model names being used

---

## Rollback Plan

### Complete Rollback

```bash
git checkout main -- backend/app/services/openai_service.py
git checkout main -- backend/app/services/xbrl_service.py
git checkout main -- backend/app/config.py
git checkout main -- backend/requirements.txt
```

### Partial Rollback (by feature)

| Feature | Files to Revert |
|---------|----------------|
| Parallel Recovery | `openai_service.py` lines 1163-1228 |
| Model Selection | `openai_service.py` lines 189-224 |
| XBRL Cache | `xbrl_service.py` |
| Token Counting | `openai_service.py` (remove tiktoken code), `requirements.txt` |
| Redis Cache | `openai_service.py` (remove redis code) |

---

## Monitoring & Validation

### Metrics to Track Post-Implementation

| Metric | Target | How to Measure |
|--------|--------|----------------|
| 10-K Latency | < 50s (was 45-90s) | Timing in logs |
| 10-Q Latency | < 35s (was 30-75s) | Timing in logs |
| Recovery Stage Time | < 15s (was 12s * N) | "parallel recovery completed" log |
| XBRL Cache Hit Rate | > 50% | Cache stats endpoint |
| API Cost | -30% | Billing dashboard |

### Add Monitoring Endpoint (Optional)

```python
# In backend/app/routers/health.py or similar
@router.get("/api/health/cache-stats")
async def get_cache_stats():
    from app.services.xbrl_service import get_xbrl_cache_stats
    return {
        "xbrl_cache": get_xbrl_cache_stats(),
        "timestamp": datetime.utcnow().isoformat(),
    }
```

---

## Implementation Schedule

| Phase | Items | Estimated Time |
|-------|-------|----------------|
| **Phase 1** | Fix duplicate prompt, Model selection | 1 hour |
| **Phase 2** | XBRL caching, Parallel recovery | 3 hours |
| **Phase 3** | Token counting, Redis caching | 2-3 hours |
| **Testing** | Full test suite, manual verification | 2 hours |
| **Total** | All optimizations | 8-9 hours |

---

## Sign-Off Checklist

Before merging to main:

- [ ] All existing tests pass
- [ ] New tests added and passing
- [ ] Latency improvements verified (before/after comparison)
- [ ] No new error types in logs
- [ ] Rate limits not being hit
- [ ] Code reviewed by second engineer
- [ ] Documentation updated
- [ ] Rollback tested

---

## Appendix: File Change Summary

| File | Changes |
|------|---------|
| `backend/app/services/openai_service.py` | Parallel recovery, model selection, token counting, duplicate fix |
| `backend/app/services/xbrl_service.py` | XBRL caching with TTL |
| `backend/app/config.py` | Cache TTL settings |
| `backend/requirements.txt` | Add tiktoken |
| `backend/tests/unit/test_parallel_recovery.py` | New test file |
| `backend/tests/unit/test_xbrl_cache.py` | New test file |

---

*Document prepared for EarningsNerd AI API Optimization Initiative*
