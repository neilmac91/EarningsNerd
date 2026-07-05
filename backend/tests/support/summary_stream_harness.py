"""Single-sourced test harness for the summary-generation anchors (T1/T2/T3/T5 + the frames
regen script).

Before this module the boundary-mock set, the canonical AI payload, the Company+Filing seed, and
the in-flight reset were copy-pasted across `test_summary_stream_contract.py`,
`test_background_generation_characterization.py`, `test_guest_quota_route.py`, and
`scripts/gen_summary_stream_frames.py`. When `stream_filing_summary` gains or renames a boundary,
one edit here now updates every anchor + the recorded fixture in lockstep (per the PR #547 review).

Importable from tests (rootdir = backend, on sys.path) and from the regen script
(`PYTHONPATH=backend`): ``from tests.support.summary_stream_harness import ...``.
"""
import uuid
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock

# The canonical "complete" AI payload the mocked ``summarize_filing`` returns. ONE definition — the
# stream tests, the background tests, and the fixture regen script all render from this exact dict,
# so the recorded frames can't drift from what the anchors assert.
CANONICAL_PAYLOAD = {
    "status": "complete",
    "business_overview": "# Summary\n\nAcme Corp designs and sells widgets worldwide.",
    "financial_highlights": {"revenue": "1B", "notes": "Revenue increased 12% year over year."},
    "risk_factors": [{"summary": "Supply-chain risk.", "supporting_evidence": "Item 1A."}],
    "management_discussion": "MD&A covers results of operations and financial condition.",
    "key_changes": "Higher R&D investment.",
    "raw_summary": {
        "sections": {"business_overview": "Acme Corp designs and sells widgets."},
        "section_coverage": {"covered_count": 5, "total_count": 7},
    },
}

_FILING_DOC_TEXT = "FILING DOCUMENT TEXT " * 40


@contextmanager
def stream_boundaries(*, payload=None, patch_usage_limit=True):
    """Patch the network/AI/excerpt seams in ``summary_pipeline``'s namespace so the SSE generator
    runs offline + instantly (no heartbeats). Yields the ``summarize_filing`` AsyncMock.

    ``patch_usage_limit=False`` leaves the real ``check_usage_limit`` in place — used by the
    expired-trial / quota tests that need the actual usage gate to fire.
    """
    from app.services import summary_pipeline

    summarize = AsyncMock(return_value=CANONICAL_PAYLOAD if payload is None else payload)
    with ExitStack() as stack:
        p = stack.enter_context
        p(_patch(summary_pipeline.sec_edgar_service, "get_filing_document",
                 AsyncMock(return_value=_FILING_DOC_TEXT)))
        p(_patch(summary_pipeline.xbrl_service, "get_xbrl_data", AsyncMock(return_value=None)))
        p(_patch(summary_pipeline.xbrl_service, "get_filing_sections", AsyncMock(return_value=None)))
        p(_patch(summary_pipeline, "get_or_cache_excerpt", lambda *a, **k: "EXCERPT"))
        p(_patch(summary_pipeline.openai_service, "summarize_filing", summarize))
        p(_patch(summary_pipeline.settings, "STREAM_HEARTBEAT_INTERVAL", 999))
        if patch_usage_limit:
            p(_patch(summary_pipeline, "check_usage_limit", lambda user, session: (True, 0, None)))
        yield summarize


@contextmanager
def background_boundaries(*, payload=None):
    """Patch the seams in ``summary_generation_service``'s namespace for the background/cron path.
    Yields the ``summarize_filing`` AsyncMock (inspect ``.call_args`` for e.g. previous_filings)."""
    from app.services import summary_generation_service as bg

    summarize = AsyncMock(return_value=CANONICAL_PAYLOAD if payload is None else payload)
    with ExitStack() as stack:
        p = stack.enter_context
        p(_patch(bg.sec_edgar_service, "get_filing_document", AsyncMock(return_value=_FILING_DOC_TEXT)))
        p(_patch(bg.xbrl_service, "get_xbrl_data", AsyncMock(return_value=None)))
        p(_patch(bg.xbrl_service, "get_filing_sections", AsyncMock(return_value=None)))
        p(_patch(bg, "get_or_cache_excerpt", lambda *a, **k: "EXCERPT"))
        p(_patch(bg.openai_service, "summarize_filing", summarize))
        yield summarize


def _patch(target, attr, value):
    from unittest.mock import patch
    return patch.object(target, attr, value)


def seed_company_filing(*, filing_type="10-K", prior=False):
    """Seed a unique Company + Filing (+ optionally a prior same-type filing for YoY paths).
    Returns the current filing's id."""
    from app.database import SessionLocal
    from app.models import Company, Filing

    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        company = Company(cik=f"cik{suffix}", ticker=f"HR{suffix[:4].upper()}", name="Harness Co")
        db.add(company)
        db.commit()
        db.refresh(company)
        if prior:
            db.add(Filing(
                company_id=company.id, accession_number=f"acc-prior-{suffix}", filing_type=filing_type,
                filing_date=datetime(2025, 1, 15, tzinfo=timezone.utc),
                document_url=f"https://sec.example/{suffix}/prior.htm", sec_url=f"https://sec.example/{suffix}/p/",
            ))
        filing = Filing(
            company_id=company.id, accession_number=f"acc-{suffix}", filing_type=filing_type,
            filing_date=datetime(2026, 1, 15, tzinfo=timezone.utc),
            document_url=f"https://sec.example/{suffix}/d.htm", sec_url=f"https://sec.example/{suffix}/",
        )
        db.add(filing)
        db.commit()
        db.refresh(filing)
        return filing.id


def reset_inflight():
    """Clear the module-global in-flight registry (a leaked slot reroutes the next generation down
    the dedup/join path)."""
    from app.services import summary_pipeline

    summary_pipeline._inflight_generations.clear()


def reset_rate_limiters():
    """ONE public seam for clearing the auth rate limiters + the DB login-lockout before a test.

    Anchors call this instead of reaching into five private ``_hits`` attributes on the limiter
    singletons — so when S3 (auth extraction) moves those symbols, only this helper changes, not
    every auth anchor.
    """
    from app.database import SessionLocal
    from app.models import LoginAttempt
    from app.routers import auth as auth_module

    for name in (
        "LOGIN_LIMITER", "REGISTER_LIMITER", "RESET_REQUEST_LIMITER",
        "RESEND_VERIFY_LIMITER", "RESET_RESEND_IP_LIMITER",
    ):
        limiter = getattr(auth_module, name, None)
        if limiter is not None and hasattr(limiter, "_hits"):
            limiter._hits.clear()
    with SessionLocal() as db:
        db.query(LoginAttempt).delete()
        db.commit()
