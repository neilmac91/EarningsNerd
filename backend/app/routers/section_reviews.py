"""The Pro review of a filing's Item 1A wording changes (E17, PR B): labels and the receipt.

Mounted under ``/api/summaries`` beside the change report that lists the changes. HTTP only: the
entitlement gate is ``require_entitlement("section_changes")`` (the same flag that serves the full
change list), the work is ``section_review_service``, and its domain errors map to statuses here.
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_entitlement
from app.models import User
from app.services import section_review_service as reviews

router = APIRouter()

REVIEW_FEATURE = "Risk factor wording review"
_reviewer = require_entitlement("section_changes", REVIEW_FEATURE)


class LabelUpdate(BaseModel):
    item_id: str = Field(min_length=1, max_length=64)
    # None clears the label.
    label: Optional[Literal["reviewed", "follow_up"]] = None


@router.get("/filing/{filing_id}/wording-review")
async def get_wording_review(
    filing_id: int,
    current_user: User = Depends(_reviewer),
    db: Session = Depends(get_db),
):
    """The reader's labels, progress and (once the queue is complete) the frozen receipt for the
    filing's Item 1A wording changes; ``status: unavailable`` with no items when there is nothing
    to review yet."""
    try:
        return await run_in_threadpool(reviews.review_state, db, current_user.id, filing_id)
    except reviews.FilingNotFound:
        raise HTTPException(status_code=404, detail="Filing not found")


@router.put("/filing/{filing_id}/wording-review/labels")
async def put_wording_label(
    filing_id: int,
    body: LabelUpdate,
    current_user: User = Depends(_reviewer),
    db: Session = Depends(get_db),
):
    """Label one change (or clear it) and return the review as it now stands. Labelling the last
    change completes the review and freezes its receipt."""
    try:
        return await run_in_threadpool(
            reviews.set_label, db, current_user.id, filing_id, body.item_id, body.label
        )
    except reviews.FilingNotFound:
        raise HTTPException(status_code=404, detail="Filing not found")
    except reviews.ReviewUnavailable:
        raise HTTPException(status_code=409, detail="This filing has no wording comparison to review yet")
    except reviews.UnknownItem:
        raise HTTPException(status_code=422, detail="Unknown change id")
    except reviews.InvalidLabel:
        # Unreachable through LabelUpdate's Literal, which answers first; the domain error maps all the same.
        raise HTTPException(status_code=422, detail="Unknown label")
