import time
from app.utils.datetimes import utcnow
from datetime import timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from app.models import Filing, Summary, SummaryGenerationProgress, User, FilingContentCache
from app.services.openai_service import openai_service
from app.services.subscription_service import increment_user_usage, get_current_month
from app.config import settings
from app.database import SessionLocal
import logging

logger = logging.getLogger(__name__)

# Minimum number of sections required for a "full" result
# Per execution plan: 3/7 sections minimum for full result designation
MINIMUM_SECTIONS_FOR_FULL_RESULT = 3

# All hideable sections (Executive Summary is never hidden)
HIDEABLE_SECTIONS = [
    "business_overview",
    "financial_highlights",
    "risk_factors",
    "management_discussion",
    "key_changes",
    "forward_guidance",
    "additional_disclosures",
]


def calculate_section_coverage(summary_data: Dict[str, Any]) -> Tuple[int, int, List[str], List[str]]:
    """Calculate section coverage for a summary.

    CRITICAL FIX: Properly detect placeholder/failure content that shouldn't count as "covered".
    The AI may return text like "Not Disclosed" which passes basic non-empty checks
    but represents a failure state, not actual content.

    Returns:
        Tuple of (covered_count, total_count, covered_sections, missing_sections)
    """
    # Placeholder patterns that indicate failure, NOT success
    PLACEHOLDER_PATTERNS = [
        "not disclosed", "not available", "unavailable", "n/a",
        "not found", "not provided", "no data", "could not",
        "unable to", "failed to", "missing", "pending",
        "being processed", "retry", "error",
        "not captured", "not extracted", "were not extracted",
    ]

    def _has_substantive_content(data: Any) -> bool:
        """Check if data contains actual substantive content, not placeholders."""
        if data is None:
            return False

        if isinstance(data, str):
            text = data.strip().lower()
            if not text or len(text) < 20:
                return False
            # Check for placeholder patterns
            for pattern in PLACEHOLDER_PATTERNS:
                if pattern in text and len(text) < 200:
                    # Short text containing placeholder = not substantive
                    return False
            return True

        if isinstance(data, list):
            # For lists (like risk_factors), check if any item has real content
            if not data:
                return False
            for item in data:
                if isinstance(item, dict):
                    # Check if dict has substantive string values
                    for val in item.values():
                        if isinstance(val, str) and len(val.strip()) > 20:
                            text_lower = val.strip().lower()
                            has_placeholder = any(p in text_lower for p in PLACEHOLDER_PATTERNS)
                            if not has_placeholder:
                                return True
                elif isinstance(item, str) and len(item.strip()) > 20:
                    return True
            return False

        if isinstance(data, dict):
            # For dicts (like financial_highlights), check for substantive nested data
            if not data:
                return False
            # Check common nested fields
            for key in ["table", "notes", "summary", "content"]:
                if key in data:
                    if _has_substantive_content(data[key]):
                        return True
            # Check all values
            for val in data.values():
                if isinstance(val, str) and len(val.strip()) > 50:
                    text_lower = val.strip().lower()
                    has_placeholder = any(p in text_lower for p in PLACEHOLDER_PATTERNS)
                    if not has_placeholder:
                        return True
                elif isinstance(val, (list, dict)) and val:
                    if _has_substantive_content(val):
                        return True
            return False

        return False

    total_sections = len(HIDEABLE_SECTIONS)
    covered_sections = []
    missing_sections = []

    for section in HIDEABLE_SECTIONS:
        section_data = summary_data.get(section)
        is_covered = _has_substantive_content(section_data)

        if is_covered:
            covered_sections.append(section)
        else:
            missing_sections.append(section)
            logger.debug(f"Section '{section}' not covered: {type(section_data).__name__}, "
                        f"sample: {str(section_data)[:100] if section_data else 'None'}")

    return len(covered_sections), total_sections, covered_sections, missing_sections


def _xbrl_value_appears(value: float, haystack_lower: str) -> bool:
    """Does an XBRL value appear in the summary text, in any common rendering (billions/
    millions/grouped)? Mirrors the eval harness's grounding check without importing it."""
    av = abs(value)
    candidates: set[str] = set()
    if av >= 1e9:
        for d in range(0, 4):  # 0-3 decimals: covers "383", "383.3", "383.29", "383.285"
            candidates.add(f"{av / 1e9:.{d}f}")
    if av >= 1e6:
        for d in range(0, 4):  # 0-3 decimals, grouped and ungrouped (e.g. "120.5", "1,250")
            candidates.add(f"{av / 1e6:.{d}f}")
            candidates.add(f"{av / 1e6:,.{d}f}")
    candidates.add(f"{int(round(av)):,}")
    return any(c.lower() in haystack_lower for c in candidates if len(c.replace(",", "")) >= 2)


# The full/partial bar for the 9-section structured taxonomy (S1 decision #2). A named LITERAL,
# not derived from the payload's ``total_count`` — that count floats, because openai unions
# ``_TRACKED_STRUCTURED_SECTIONS`` with whatever keys the model emitted, so a stray key would silently
# raise the bar. This is the conscious recalibration of the legacy 3/7 (~0.43) threshold for the
# fixed 9-section taxonomy.
MINIMUM_STRUCTURED_SECTIONS_FOR_FULL = 4


def _tracked_sections_for(schema_version: Any) -> Tuple[str, ...]:
    """The section-key taxonomy the quality badge counts, dispatched by schema version.

    Both tuples are the FROZEN per-version literals in ``summary_schema`` — deliberately NOT
    ``openai_service._TRACKED_STRUCTURED_SECTIONS``, which is the generation-side "what we emit now"
    and is re-pointed to v2 at the cutover. Keyed off the row's OWN ``raw_summary.schema_version`` so
    a v1 row assessed after the v2 cutover still counts its own historical v1 taxonomy — otherwise a
    naming collision would make every legacy row count 0/9 and tier "partial" (billing off). Both
    taxonomies are 9 sections, so the 4/9 bar is unchanged."""
    from app.services.summary_schema import TRACKED_SECTIONS_V1, TRACKED_SECTIONS_V2

    try:
        version = int(schema_version)
    except (TypeError, ValueError):
        version = 1
    return TRACKED_SECTIONS_V2 if version == 2 else TRACKED_SECTIONS_V1


def _verdict_coverage(summary_data: Dict[str, Any]) -> Tuple[int, int, int]:
    """(covered, total, min_full) for the quality verdict.

    Coverage over the row's structured taxonomy (v1 or v2, dispatched by ``schema_version`` —
    intersected with the snapshot's ``per_section`` so stray model keys can't move the count),
    gated at ``MINIMUM_STRUCTURED_SECTIONS_FOR_FULL`` (4/9). When the payload carries no
    ``per_section`` snapshot, falls back to the legacy 7 ``HIDEABLE_SECTIONS`` coverage at the 3/7
    bar. assess_quality's only caller is the user-facing SSE stream (summary_pipeline).
    """
    raw = summary_data.get("raw_summary") or {}
    snapshot = raw.get("section_coverage") or {}
    per_section = snapshot.get("per_section")
    if isinstance(per_section, dict):
        tracked = _tracked_sections_for(raw.get("schema_version"))
        covered = sum(1 for s in tracked if per_section.get(s))
        return covered, len(tracked), MINIMUM_STRUCTURED_SECTIONS_FOR_FULL
    covered, total, _, _ = calculate_section_coverage(summary_data)
    return covered, total, MINIMUM_SECTIONS_FOR_FULL_RESULT


def assess_quality(
    summary_data: Dict[str, Any],
    xbrl_metrics: Optional[Dict[str, Any]] = None,
    *,
    sic: Optional[str] = None,
) -> Dict[str, Any]:
    """Deterministic quality verdict for a generated summary (roadmap S4).

    Returns {tier: "full"|"partial", reasons, numeric_grounded, covered_count, total_count}.
    "partial" means thin section coverage OR financials that don't match the SEC-verified XBRL —
    the signal the UI surfaces honestly (quality badge) instead of silently stripping notices.

    Bank-aware top-line grounding (data-quality plan P0-2): a financial institution reports its
    top line as components (net interest income + noninterest income), and the pipeline's own
    grounding NOTE forbids the model from emitting a single "Revenue" figure — so demanding the
    XBRL ``revenue`` literal was a structural false alarm on every bank. The top-line check now
    passes when the ``revenue`` literal grounds OR (for a bank with both components extracted)
    both components ground — evaluated whether or not a ``revenue`` total exists, so a no-total
    bank (BAC/C/WFC) is checked on its components rather than silently skipped. For an FI filer
    whose components were not BOTH extracted there is no fair top-line pair to demand, so the
    top-line check is N/A; ``net_income`` grounding and section coverage still apply. Non-FI
    behavior is byte-identical. ``sic`` is the flag-independent FI signal (SIC 6000-6799)."""
    covered, total, min_full = _verdict_coverage(summary_data)
    reasons: List[str] = []

    numeric_grounded = True
    if xbrl_metrics:
        import json as _json

        from app.services.ai.fi_signals import fi_components_present, is_financial_sic

        haystack = (
            str(summary_data.get("business_overview") or "")
            + " "
            + _json.dumps(summary_data.get("financial_highlights") or {}, default=str)
        ).lower()

        def _metric_value(key: str) -> Optional[float]:
            node = xbrl_metrics.get(key)
            current = node.get("current", {}) if isinstance(node, dict) else {}
            value = current.get("value") if isinstance(current, dict) else None
            return value

        fi_filer = fi_components_present(xbrl_metrics) or is_financial_sic(sic)
        nii = _metric_value("net_interest_income")
        non_ii = _metric_value("noninterest_income")
        both_components = nii is not None and non_ii is not None

        def _components_ground() -> bool:
            return _xbrl_value_appears(float(nii), haystack) and _xbrl_value_appears(
                float(non_ii), haystack
            )

        checks: List[bool] = []
        revenue_value = _metric_value("revenue")

        # Top-line grounding.
        if fi_filer:
            if both_components:
                # A bank's top line IS its components — check them whether or not a `revenue`
                # total exists (a no-total bank BAC/C/WFC has none; JPM has one). A reported
                # total that grounds also passes, so a bank that quotes its consolidated revenue
                # instead of the components isn't penalized.
                grounded = _components_ground()
                if not grounded and revenue_value is not None:
                    grounded = _xbrl_value_appears(float(revenue_value), haystack)
                checks.append(grounded)
            # else: FI filer whose components were not BOTH extracted → top line is N/A. Demanding
            # the generic `revenue` total here is the original false alarm: the grounding NOTE
            # tells the model to report components (read from prose), never that total.
        elif revenue_value is not None:
            # Non-FI: unchanged — demand the revenue literal.
            checks.append(_xbrl_value_appears(float(revenue_value), haystack))

        net_income_value = _metric_value("net_income")
        if net_income_value is not None:
            checks.append(_xbrl_value_appears(float(net_income_value), haystack))

        if checks:
            numeric_grounded = all(checks)
            if not numeric_grounded:
                # Literal contract with the badge de-escalation in SummaryDisplay.tsx
                # (GROUNDING_REASON) — pinned on both sides (test_assess_quality_bank.py /
                # summary-quality-badge.spec.tsx); reword BOTH together or safeguard #5 dissolves.
                reasons.append("financial figures not grounded in SEC XBRL data")

    if covered < min_full:
        reasons.append(f"only {covered}/{total} sections populated")

    tier = "full" if (covered >= min_full and numeric_grounded) else "partial"
    return {
        "tier": tier,
        "reasons": reasons,
        "numeric_grounded": numeric_grounded,
        "covered_count": covered,
        "total_count": total,
    }


# Quality tiers ranked worst -> best. The keep-better refresh gate (T1.4) overwrites a stored
# summary ONLY when the new tier ranks >= the stored tier, so a 75s AI-timeout XBRL fallback
# (partial) can never silently downgrade a stored `full` during a bulk refresh. assess_quality only
# ever returns "full"/"partial" (a bare string, not an Enum); an unknown/absent tier (legacy rows
# written before quality was attached) ranks lowest so any real regeneration is an improvement.
_QUALITY_TIER_RANK = {"partial": 1, "full": 2}


def quality_tier_rank(tier: Optional[str]) -> int:
    """Rank a quality tier for the keep-better refresh gate; unknown/None ranks lowest (0)."""
    return _QUALITY_TIER_RANK.get(tier or "", 0)


def record_progress(
    db: Session,
    filing_id: int,
    stage: str,
    *,
    error: Optional[str] = None,
    section_coverage: Optional[Dict[str, Any]] = None,
) -> SummaryGenerationProgress:
    now = utcnow()
    progress = (
        db.query(SummaryGenerationProgress)
        .filter(SummaryGenerationProgress.filing_id == filing_id)
        .first()
    )

    if not progress:
        progress = SummaryGenerationProgress(
            filing_id=filing_id,
            stage=stage,
            started_at=now,
            updated_at=now,
            elapsed_seconds=0.0,
            error=error,
        )
        db.add(progress)
        if section_coverage is not None:
            progress.section_coverage = section_coverage
    else:
        progress.stage = stage
        if progress.started_at is None:
            progress.started_at = now
        progress.updated_at = now
        # Handle timezone-aware vs timezone-naive datetime comparison
        started_at = progress.started_at
        if started_at.tzinfo is None:
            # Convert timezone-naive to UTC if needed
            started_at = started_at.replace(tzinfo=timezone.utc)
        progress.elapsed_seconds = float((now - started_at).total_seconds())
        progress.error = error
        if section_coverage is not None:
            progress.section_coverage = section_coverage

    db.flush()
    db.commit()
    db.refresh(progress)
    return progress

def progress_as_dict(progress: SummaryGenerationProgress) -> Dict[str, Any]:
    elapsed = progress.elapsed_seconds
    if elapsed is None and progress.started_at:
        # Handle timezone-aware vs timezone-naive datetime comparison
        started_at = progress.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        elapsed = float((utcnow() - started_at).total_seconds())
    return {
        "stage": progress.stage,
        "elapsedSeconds": int(elapsed or 0),
        "error": progress.error,
        "updated_at": progress.updated_at.isoformat() if progress.updated_at else None,
        "sectionCoverage": progress.section_coverage,
    }

# An edgartools-parsed excerpt below this many chars is treated as "thin" (e.g. only a stub
# parsed), so we fall back to the legacy regex + dense-window extractor for more depth. Real
# filings parse to tens of thousands of chars, so this only catches near-empty edge cases.
_EDGARTOOLS_EXCERPT_MIN = 8000


def get_or_cache_excerpt(
    db: Session,
    filing: Filing,
    filing_text: Optional[str],
    sections: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    # ``sections`` (when provided) is edgartools-parsed section text; it lets us build a
    # high-precision excerpt even when ``filing_text`` is empty (e.g. a cache-hit path). We
    # still need one of the two inputs to produce anything.
    if not filing_text and not sections:
        return None

    # Get filing_id safely - it should be accessible even if filing is detached
    filing_id = filing.id if hasattr(filing, 'id') and filing.id else None
    if not filing_id:
        # If we can't get the ID, we can't proceed
        return None

    # Always query filing fresh with content_cache loaded to avoid detached session issues
    filing_reattached = db.query(Filing).options(joinedload(Filing.content_cache)).filter(Filing.id == filing_id).first()
    if not filing_reattached:
        # Filing not found - return None
        return None

    cache = filing_reattached.content_cache
    filing_type = filing_reattached.filing_type

    if cache and cache.critical_excerpt:
        return cache.critical_excerpt

    filing_type_key = (filing_type or "10-K").upper()

    # Prefer edgartools' native section parser (precise, robust to fragmented HTML); fall back
    # to the legacy regex + dense-window extractor when sections are unavailable or too thin.
    excerpt = None
    if sections and settings.USE_EDGARTOOLS_SECTIONS:
        excerpt = openai_service.assemble_excerpt_from_sections(
            sections, filing_type_key, filing_text=filing_text
        )
        if excerpt and len(excerpt) < _EDGARTOOLS_EXCERPT_MIN:
            excerpt = None
    if not excerpt:
        excerpt = openai_service.extract_critical_sections(filing_text or "", filing_type_key)
    if excerpt:
        if cache is None:
            cache = FilingContentCache(filing_id=filing_id, critical_excerpt=excerpt)
            db.add(cache)
        else:
            cache.critical_excerpt = excerpt
        db.flush()
        db.commit()
    return excerpt

async def generate_summary_background(
    filing_id: int, user_id: Optional[int], *, force_regenerate: bool = False
):
    """Background task to generate summary.

    ``force_regenerate=True`` (admin refresh-stale) skips the existing-summary short-circuit and
    threads the flag into the ONE orchestrator, which UPDATEs the stored row in place (preserving
    ``summaries.id`` so saved-summary bookmarks survive) under a keep-better quality gate.
    """
    
    # Create a new database session for the background task
    with SessionLocal() as db:
        logger.info(f"Starting summary generation for filing {filing_id}")
        # Eagerly load content_cache and company relationship to avoid detached session issues
        filing = db.query(Filing).options(
            joinedload(Filing.content_cache),
            joinedload(Filing.company)
        ).filter(Filing.id == filing_id).first()
        if not filing:
            logger.warning(f"Filing {filing_id} not found")
            return

        # Check if summary already exists (skipped under force_regenerate — a refresh must reach
        # the very row it is refreshing rather than short-circuit on it).
        existing = db.query(Summary).filter(Summary.filing_id == filing_id).first()
        if existing and not force_regenerate:
            logger.info(f"Summary already exists for filing {filing_id}")
            # If summary already exists, still increment usage if user generated it
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    month = get_current_month()
                    increment_user_usage(user.id, month, db)
            return
        
        # Check if OpenAI API key is configured
        if not settings.OPENAI_API_KEY:
            logger.warning(f"Warning: OpenAI API key not configured. Cannot generate summary for filing {filing_id}")
            # Create a placeholder summary indicating API key is missing
            summary = Summary(
                filing_id=filing_id,
                business_overview=(
                    "Summary generation requires OpenAI API key. "
                    "Please configure OPENAI_API_KEY in your .env file."
                ),
                financial_highlights=None,
                risk_factors=None,
                management_discussion=None,
                key_changes=None,
                raw_summary={"error": "OpenAI API key not configured"}
            )
            db.add(summary)
            try:
                db.commit()
            except IntegrityError:
                # A real summary already exists for this filing (filing_id UNIQUE) — the placeholder
                # is unnecessary; don't error the cron job (S1 decision #3).
                db.rollback()
            return
        
        # S1: the background/cron/pregenerate path drains the ONE orchestrator
        # (stream_filing_summary) headless — inheriting its filing-only generation, the
        # 9-section assess_quality verdict, partial-persistence, and filing_id-conflict handling.
        # Funnel telemetry is suppressed (a precompute run emits ZERO funnel events — T2 pin);
        # current_user=None skips the user-facing paywall gate, while usage still increments for a
        # signed-in user_id on a full result via the pipeline's own count_usage. The existing-summary
        # short-circuit above is the caller's job here (the pipeline does not re-check it).
        from app.services.summary_pipeline import stream_filing_summary

        drain_started = time.time()
        terminal_event: Optional[Dict[str, Any]] = None
        async for terminal_event in stream_filing_summary(
            filing_id=filing_id,
            current_user=None,
            user_id=user_id,
            telemetry_distinct_id=str(user_id) if user_id else "precompute",
            telemetry_entry_point=None,
            telemetry_ctx={},
            emit_funnel_telemetry=False,
            force_regenerate=force_regenerate,
        ):
            pass
        # With funnel telemetry suppressed for cron, this is the drain's ONLY per-filing signal in
        # the Cloud Run job logs. Crucially, the pipeline converts exceptions into terminal error
        # EVENTS (the job still exits 0), so without this line a failing pregenerate batch would
        # look identical to a successful one.
        terminal_type = (terminal_event or {}).get("type", "none")
        drain_secs = time.time() - drain_started
        log = logger.warning if terminal_type == "error" else logger.info
        log(f"[{filing_id}] drain terminal={terminal_type} duration={drain_secs:.1f}s")
        return

# Stages from which generation can no longer make progress on its own.
TERMINAL_STAGES = {"completed", "error", "partial"}

# A non-terminal progress row older than this is considered orphaned (a crashed/abandoned
# background task). The longest legitimate run is the 10-K global_timeout (120s) plus the
# stream pipeline (90s); 180s leaves comfortable headroom before we call it dead.
STALE_PROGRESS_SECONDS = 180


def mark_stale_progress_as_error(progress: SummaryGenerationProgress) -> bool:
    """Detect an orphaned (stuck) progress row and flip it to a retryable error in-place.

    Fire-and-forget background generation can die without recording a terminal state if it
    crashes before its inner guard runs. Rather than leave the UI spinning forever, surface
    a stale non-terminal row as an error the user can retry. Returns True if it mutated the
    row (caller is responsible for committing)."""
    if progress.stage in TERMINAL_STAGES:
        return False

    last_update = progress.updated_at or progress.started_at
    if last_update is None:
        return False
    if last_update.tzinfo is None:
        last_update = last_update.replace(tzinfo=timezone.utc)

    if (utcnow() - last_update).total_seconds() <= STALE_PROGRESS_SECONDS:
        return False

    progress.stage = "error"
    progress.error = "Generation stalled and was abandoned. Please retry."
    return True


def get_generation_progress_snapshot(filing_id: int) -> Optional[Dict[str, Any]]:
    """Return the persisted generation progress for a filing, if available."""
    with SessionLocal() as session:
        progress = (
            session.query(SummaryGenerationProgress)
            .filter(SummaryGenerationProgress.filing_id == filing_id)
            .first()
        )
        if not progress:
            return None
        return progress_as_dict(progress)
