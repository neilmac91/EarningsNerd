# AI API Optimization Opportunities

**Document Created:** 2026-01-25
**Status:** Pending Implementation
**Reviewed By:** API Architect + AI Engineer Agents

---

## Executive Summary

Analysis of the filing summary generation system identified several optimization opportunities that could reduce latency by ~40% and costs by ~30%.

---

## Current State

### AI Call Pattern per Summary

| Stage | Method | Model | Max Tokens | Timeout | Purpose |
|-------|--------|-------|------------|---------|---------|
| 1 | `generate_structured_summary()` | gemini-3-pro-preview | 1500 | 75-90s | Extract JSON schema |
| 2 | `_recover_missing_sections()` | gemini-3-pro-preview | 350 | 12s each | Fill empty sections (0-9 calls) |
| 3 | `generate_editorial_markdown()` | gemini-3-pro-preview | 900 | 18s | Convert JSON to markdown |

**Total AI Calls:** 2-11 per summary (sequential)

### Token Usage

| Filing Type | Input Tokens (est.) | Output Tokens (est.) |
|-------------|---------------------|----------------------|
| 10-K | ~24,000 | ~3,500 |
| 10-Q | ~17,000 | ~3,000 |

### Current Latency

| Filing Type | Typical Latency |
|-------------|-----------------|
| 10-K | 45-90s |
| 10-Q | 30-75s |

---

## Optimization Opportunities

### 1. Parallelize Section Recovery (HIGH PRIORITY)

**Current:** Sequential per-section recovery in `_recover_missing_sections()`

**Location:** `backend/app/services/openai_service.py:1163-1228`

**Current Code:**
```python
for section_key in missing_sections:
    # ... one API call at a time
    content = await self._run_secondary_completion(filing_type_key, prompt)
```

**Optimized Code:**
```python
async def _recover_missing_sections(self, missing_sections, ...):
    tasks = []
    for section_key in missing_sections:
        task = self._recover_single_section(section_key, ...)
        tasks.append(task)
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # Process results
```

**Impact:** Reduce recovery stage from `12s * N` to `~12s` total

**Estimated Improvement:** -60% latency on recovery stage

---

### 2. Model Selection by Task (HIGH PRIORITY)

**Current:** All tasks use `gemini-3-pro-preview`

**Location:** `backend/app/services/openai_service.py:189-212`

**Recommended Configuration:**

| Task | Current Model | Recommended Model | Rationale |
|------|---------------|-------------------|-----------|
| Structured Extraction | gemini-3-pro-preview | gemini-3-pro-preview | Needs high accuracy |
| Section Recovery | gemini-3-pro-preview | **gemini-2.5-flash** | Simpler task, lower cost |
| Editorial Writer | gemini-3-pro-preview | **gemini-2.5-pro** | Creative but constrained |

**Implementation Point:** `_run_secondary_completion()` at lines 1116-1161

**Estimated Savings:** 30-50% token cost reduction for recovery + writer stages

---

### 3. Cache XBRL Metrics (MEDIUM PRIORITY)

**Current:** XBRL data fetched fresh each request

**Location:** `backend/app/services/xbrl_service.py:15-42`

**Recommendation:** Cache XBRL data per accession number (changes only quarterly)

**Implementation:**
```python
from functools import lru_cache
import hashlib

# In-memory cache with TTL
_xbrl_cache: Dict[str, Tuple[datetime, Dict]] = {}
XBRL_CACHE_TTL = timedelta(hours=24)

async def get_xbrl_data(self, accession_number: str, cik: str) -> Optional[Dict]:
    cache_key = f"{cik}:{accession_number}"

    if cache_key in _xbrl_cache:
        cached_time, cached_data = _xbrl_cache[cache_key]
        if datetime.now() - cached_time < XBRL_CACHE_TTL:
            return cached_data

    # Fetch and cache
    data = await self._fetch_xbrl_data(accession_number, cik)
    _xbrl_cache[cache_key] = (datetime.now(), data)
    return data
```

**Impact:** Eliminate redundant SEC API calls on retries

---

### 4. Fix Duplicate Prompt Lines (MEDIUM PRIORITY)

**Current:** Duplicate instruction at lines 2173-2174

**Location:** `backend/app/services/openai_service.py:2173-2174`

```python
"6. Only include bullets you can prove..."
"6. Only include bullets you can prove..."  # DUPLICATE!
```

**Fix:** Remove duplicate line

**Impact:** Minor token savings (~50 tokens per call)

---

### 5. Add Token Counting (LOW PRIORITY)

**Current:** No explicit token counting before API calls

**Recommendation:** Add pre-flight token estimation

**Implementation:**
```python
from tiktoken import encoding_for_model

def estimate_tokens(text: str, model: str = "gpt-4") -> int:
    enc = encoding_for_model(model)
    return len(enc.encode(text))

# Before API call
estimated_tokens = estimate_tokens(prompt)
if estimated_tokens > MAX_CONTEXT:
    prompt = truncate_prompt(prompt, MAX_CONTEXT)
    logger.info(f"Truncated prompt from {estimated_tokens} to {MAX_CONTEXT} tokens")
```

**Benefits:**
1. Choose appropriate model based on input size
2. Truncate proactively rather than relying on API truncation
3. Log actual vs estimated for cost tracking

---

### 6. Cache Structured Extraction Results (LOW PRIORITY)

**Current:** No caching of AI responses

**Recommendation:** Cache structured extraction for retry scenarios

**Implementation:**
```python
# Key: filing_id + content_hash
# Value: structured extraction result
# TTL: 1 hour (covers retry window)

async def generate_structured_summary(self, filing_text, ...):
    content_hash = hashlib.md5(filing_text[:10000].encode()).hexdigest()
    cache_key = f"structured:{filing_id}:{content_hash}"

    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    result = await self._call_ai_structured(...)
    await redis.setex(cache_key, 3600, json.dumps(result))
    return result
```

**Impact:** Faster retries, reduced cost on fallback scenarios

---

## Expected Outcomes After Optimization

| Metric | Current | After Optimization | Improvement |
|--------|---------|-------------------|-------------|
| AI Calls (effective) | 2-11 sequential | 2-3 parallel | -60% wall time |
| Latency (10-K) | 45-90s | 25-50s | ~40% faster |
| Latency (10-Q) | 30-75s | 20-40s | ~40% faster |
| Token Cost | Baseline | -30% | Flash for recovery |

---

## Implementation Priority

| Priority | Optimization | Effort | Impact |
|----------|-------------|--------|--------|
| 1 | Parallelize section recovery | Medium | High |
| 2 | Use Flash model for recovery | Low | High |
| 3 | Cache XBRL metrics | Low | Medium |
| 4 | Fix duplicate prompt | Trivial | Low |
| 5 | Add token counting | Medium | Low |
| 6 | Cache structured extraction | Medium | Low |

---

## Files to Modify

- `backend/app/services/openai_service.py` - Parallelization, model selection, token counting
- `backend/app/services/xbrl_service.py` - XBRL caching
- `backend/app/config.py` - Add cache configuration settings

---

## Notes

- All optimizations are backwards compatible
- Consider implementing behind feature flags for gradual rollout
- Monitor metrics before/after to validate improvements
