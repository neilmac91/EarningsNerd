"""Scheduled retention purge for the rows the policy promises to delete on a clock.

`docs/DATA_RETENTION_POLICY.md` schedules: search history one year (§2.3), failed-login state
seven days (§2.2), contact-form submissions one year (§2.5), plus the two token tables whose
rows are dead once expired or revoked (§2.2). Everything here is data hygiene with no
user-facing behaviour: the rows are already invisible or unusable by the time they qualify.

Deliberately NOT here (founder-held or a product decision, never a silent purge): account
deletion for inactivity, waitlist signups and referral data, audit logs, usage counters and
billing rows. The job records counts only (`track_job`), never ids or addresses.

Every delete is bounded (`batch_size` rows per statement, committed per batch) so a first run
over a large backlog never holds one long transaction, and `dry_run` reports the counts each
target would delete without deleting anything.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from app.models import ContactSubmission, LoginAttempt, OAuthState, RefreshToken, UserSearch
from app.utils.datetimes import utcnow

logger = logging.getLogger(__name__)

SEARCH_HISTORY_DAYS = 365
LOGIN_ATTEMPT_DAYS = 7
REFRESH_TOKEN_GRACE_DAYS = 30
CONTACT_SUBMISSION_DAYS = 365
DEFAULT_BATCH_SIZE = 5000


@dataclass(frozen=True)
class PurgeTarget:
    name: str
    model: Any
    key: Any  # the primary-key column used to delete in bounded batches
    predicate: Any


def purge_targets(now: datetime) -> list[PurgeTarget]:
    """The rows that qualify at ``now`` (aware UTC), one target per policy row."""
    # OAuthState.expires_at and the RefreshToken stamps are the sanctioned naive-UTC columns
    # (app/utils/datetimes.py): compare them with a naive projection of the same instant.
    naive_now = now.replace(tzinfo=None)
    return [
        PurgeTarget(
            "search_history", UserSearch, UserSearch.id,
            UserSearch.created_at < now - timedelta(days=SEARCH_HISTORY_DAYS),
        ),
        PurgeTarget(
            "login_attempts", LoginAttempt, LoginAttempt.email_hash,
            and_(
                LoginAttempt.updated_at < now - timedelta(days=LOGIN_ATTEMPT_DAYS),
                or_(LoginAttempt.locked_until.is_(None), LoginAttempt.locked_until < now),
            ),
        ),
        PurgeTarget("oauth_states", OAuthState, OAuthState.id, OAuthState.expires_at < naive_now),
        PurgeTarget(
            "refresh_tokens", RefreshToken, RefreshToken.id,
            or_(
                RefreshToken.expires_at < naive_now - timedelta(days=REFRESH_TOKEN_GRACE_DAYS),
                RefreshToken.revoked_at < naive_now - timedelta(days=REFRESH_TOKEN_GRACE_DAYS),
            ),
        ),
        PurgeTarget(
            "contact_submissions", ContactSubmission, ContactSubmission.id,
            ContactSubmission.created_at < now - timedelta(days=CONTACT_SUBMISSION_DAYS),
        ),
    ]


def _purge(db: Session, target: PurgeTarget, *, dry_run: bool, batch_size: int) -> int:
    if dry_run:
        return int(db.execute(select(func.count()).select_from(target.model).where(target.predicate)).scalar() or 0)
    total = 0
    while True:
        keys = [row[0] for row in db.execute(select(target.key).where(target.predicate).limit(batch_size)).all()]
        if not keys:
            return total
        # Re-apply the predicate: a row refreshed between the select and the delete (a login
        # failure recorded on a stale email_hash) is live again and must survive.
        result = db.execute(
            delete(target.model)
            .where(target.key.in_(keys), target.predicate)
            .execution_options(synchronize_session=False)
        )
        db.commit()
        total += int(result.rowcount or 0)
        if len(keys) < batch_size:
            return total


def run_retention_purge(
    db: Session, *, dry_run: bool = False, now: datetime | None = None, batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict:
    """Apply every policy target; returns ``{"<target>_purged": n, ...}`` (counts only)."""
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    now = now or utcnow()
    stats: dict = {"dry_run": dry_run}
    for target in purge_targets(now):
        count = _purge(db, target, dry_run=dry_run, batch_size=batch_size)
        stats[f"{target.name}_purged"] = count
        logger.info("retention purge %s: %s rows%s", target.name, count, " (dry run)" if dry_run else "")
    return stats
