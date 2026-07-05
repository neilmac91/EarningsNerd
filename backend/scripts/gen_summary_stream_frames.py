"""Regenerate ``tests/fixtures/summary_stream_frames.json`` — the recorded SSE frame sequence that
pins the producer/consumer contract shared by the backend stream test (T1,
``tests/integration/test_summary_stream_contract.py``) and the frontend parser test (T10).

Run from ``backend/`` (self-bootstraps ``backend`` onto ``sys.path``, so no ``PYTHONPATH`` needed)::

    python scripts/gen_summary_stream_frames.py

It drives the REAL ``stream_filing_summary`` generator with the SEC/XBRL/AI/excerpt boundaries
mocked offline via the SHARED harness (``tests.support.summary_stream_harness``) — the exact same
``stream_boundaries`` / ``seed_company_filing`` / ``CANONICAL_PAYLOAD`` the T1 test drives, so the
recorded fixture can never drift from what the anchors assert. Volatile fields (``summary_id``,
``elapsed_seconds``) are masked by ``normalize_frame`` so a re-run reproduces a byte-identical file.

``normalize_frame`` is imported by the T1 test: the recorded fixture and the test's live parity
check mask with ONE function, so ``masked-live == recorded`` holds by construction.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# This runs OUTSIDE pytest/conftest. Put ``backend`` on sys.path (running ``scripts/foo.py`` only
# adds ``scripts/`` — not the backend root — so ``app`` and ``tests`` would not import) and set the
# same mock env conftest would, before importing the app.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-long-enough-123")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-mocking")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_mock_stripe_key_12345")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_mock_stripe_webhook_12345")
os.environ.setdefault("SKIP_REDIS_INIT", "true")
os.environ.setdefault("PWNED_PASSWORD_CHECK_ENABLED", "false")

from app.database import engine  # noqa: E402
from app.models import Base  # noqa: E402
from app.services.summary_pipeline import stream_filing_summary  # noqa: E402
from tests.support.summary_stream_harness import (  # noqa: E402
    reset_inflight,
    seed_company_filing,
    stream_boundaries,
)

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "summary_stream_frames.json"


def normalize_frame(event: dict) -> dict:
    """Mask ONLY the volatile fields so a re-run reproduces a byte-identical fixture and the T1
    parity test can compare live frames field-by-field against it.

    Masked: ``summary_id`` (a DB autoincrement id) and ``elapsed_seconds`` (a wall-clock counter).
    Everything structural — ``type``, ``stage``, ``message``, ``percent``, and the key set itself —
    is preserved verbatim, so a renamed message, a changed percent, or an added/dropped key is a
    hard failure rather than something the mask quietly absorbs.
    """
    masked = dict(event)
    if "summary_id" in masked:
        masked["summary_id"] = 12345
    if "elapsed_seconds" in masked:
        masked["elapsed_seconds"] = 0
    return masked


async def record_frames() -> list[dict]:
    """Drive the real generator offline through the shared harness; return the masked frame list.

    Kept separate from ``main`` (which only handles file I/O) so the recording is a pure function
    of the harness — the same seams the T1 test asserts against.
    """
    Base.metadata.create_all(bind=engine)
    reset_inflight()
    with stream_boundaries():
        filing_id = seed_company_filing()
        return [
            normalize_frame(ev)
            async for ev in stream_filing_summary(
                filing_id=filing_id, current_user=None, user_id=None,
                telemetry_distinct_id="t", telemetry_entry_point=None, telemetry_ctx={},
            )
        ]


async def main() -> None:
    frames = await record_frames()
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(frames, indent=2) + "\n")
    print(f"wrote {len(frames)} frames to {FIXTURE}")


if __name__ == "__main__":
    asyncio.run(main())
