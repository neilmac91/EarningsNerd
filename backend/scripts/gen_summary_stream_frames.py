"""Regenerate ``tests/fixtures/summary_stream_frames.json`` — the recorded SSE frame sequence that
pins the producer/consumer contract shared by the backend stream test (T1) and the frontend parser
test (T10). Run from ``backend/``:

    python scripts/gen_summary_stream_frames.py

It drives the REAL ``stream_filing_summary`` generator with the SEC/XBRL/AI/excerpt boundaries
mocked (offline), then writes the frames with volatile fields (``summary_id``, timing) normalized.
"""
import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

# This runs OUTSIDE pytest/conftest, so set the same mock env before importing the app.
os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-long-enough-123")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-mocking")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_mock_stripe_key_12345")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_mock_stripe_webhook_12345")
os.environ.setdefault("SKIP_REDIS_INIT", "true")
os.environ.setdefault("PWNED_PASSWORD_CHECK_ENABLED", "false")

from app.database import SessionLocal, engine  # noqa: E402
from app.models import Base, Company, Filing  # noqa: E402
from app.services import summary_pipeline  # noqa: E402

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "summary_stream_frames.json"

_PAYLOAD = {
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


def _seed() -> int:
    Base.metadata.create_all(bind=engine)
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        company = Company(cik=f"cik{suffix}", ticker=f"GEN{suffix[:3].upper()}", name="Frames Gen Co")
        db.add(company)
        db.commit()
        db.refresh(company)
        filing = Filing(
            company_id=company.id, accession_number=f"acc-{suffix}", filing_type="10-K",
            filing_date=datetime(2026, 1, 15, tzinfo=timezone.utc),
            document_url=f"https://sec.example/{suffix}/d.htm", sec_url=f"https://sec.example/{suffix}/",
        )
        db.add(filing)
        db.commit()
        db.refresh(filing)
        return filing.id


def _normalize(event: dict) -> dict:
    event = dict(event)
    if "summary_id" in event:
        event["summary_id"] = 12345
    if "elapsed_seconds" in event:
        event["elapsed_seconds"] = 0
    return event


async def main() -> None:
    summary_pipeline._inflight_generations.clear()
    filing_id = _seed()
    with patch.object(summary_pipeline.sec_edgar_service, "get_filing_document", AsyncMock(return_value="FILING DOCUMENT TEXT " * 40)), \
         patch.object(summary_pipeline.xbrl_service, "get_xbrl_data", AsyncMock(return_value=None)), \
         patch.object(summary_pipeline.xbrl_service, "get_filing_sections", AsyncMock(return_value=None)), \
         patch.object(summary_pipeline, "get_or_cache_excerpt", lambda *a, **k: "EXCERPT"), \
         patch.object(summary_pipeline, "check_usage_limit", lambda user, session: (True, 0, None)), \
         patch.object(summary_pipeline.openai_service, "summarize_filing", AsyncMock(return_value=_PAYLOAD)), \
         patch.object(summary_pipeline.settings, "STREAM_HEARTBEAT_INTERVAL", 999):
        frames = [
            _normalize(ev)
            async for ev in summary_pipeline.stream_filing_summary(
                filing_id=filing_id, current_user=None, user_id=None,
                telemetry_distinct_id="t", telemetry_entry_point=None, telemetry_ctx={},
            )
        ]
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(frames, indent=2) + "\n")
    print(f"wrote {len(frames)} frames to {FIXTURE}")


if __name__ == "__main__":
    asyncio.run(main())
