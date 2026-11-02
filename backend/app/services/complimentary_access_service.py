"""Complimentary Pro for invited private-beta accounts (PB-02): the operator's grant, revoke and readout.

The plan stays in ``entitlements.py``. An account no billing state owns (no ``Subscription`` row, no Stripe
customer or subscription id) is Pro while ``User.is_pro`` is True, and a grant sets that flag for an account an
operator names in a private manifest. The grant's ledger row (``ComplimentaryAccessGrant``) records that the
grant set it, so a revoke clears only that Pro, never a paying account's, and Billing can say the access is
complimentary (:func:`serves_complimentary_pro`).

The operator runs it through ``scripts/complimentary_access.py`` (``docs/ops/complimentary-access.md``):

* a **manifest** names the action (grant or revoke), the cohort, the reason, the operator's admin account and at
  most :data:`MAX_ACTIVE_GRANTS` accounts, each by its id and the SHA-256 of its address, so a mistyped id is
  refused instead of granting a stranger;
* a **dry run** reports, without writing, what an apply would do: counts by outcome and every refusal by its
  place in the manifest, never an id or an address, with the manifest's digest;
* an **apply** runs only the manifest whose digest it is handed, and treats each account as one unit: under the
  grants' lock and the account's row lock it reads the account again, then writes the ledger row, the flag and
  their audit row in one commit, or nothing. A rerun changes nothing an earlier run changed, except that a grant
  manifest with another review date moves the active grants of the accounts it names to that date (and changes
  nothing else); an account it does not name keeps its date.

Nothing here calls Stripe or sends mail. A grant never touches billing state, and a revoke of an account that
has gained a Subscription row since its grant closes the ledger row and leaves the flag to the webhook that owns it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AccountAgreement, ComplimentaryAccessGrant, InviteCode, Subscription, User
from app.services.audit_service import create_audit_log
from app.services.complimentary_access_manifest import (
    MAX_ACTIVE_GRANTS, GrantManifest, Manifest, ManifestAccount, RevokeManifest, check_review_window,
    check_runner_label, email_fingerprint,
)
from app.services.entitlements import get_plan, is_pro_user, pro_from_mirror
from app.utils.datetimes import utcnow

# The key of the PostgreSQL advisory lock every grant and revoke unit takes first: "COMPGRNT" in ASCII.
GRANT_LOCK_KEY = 0x434F4D5047524E54

# The audit actions, spelled again as literals at their three create_audit_log calls (legalTruth.spec.tsx's reader).
AUDIT_GRANTED = "complimentary_access_granted"
AUDIT_REVIEW_MOVED = "complimentary_access_review_moved"
AUDIT_REVOKED = "complimentary_access_revoked"


class OperatorNotAuthorizedError(Exception):
    """The manifest's operator is not an active admin account with a verified address; nothing was read or
    written for any account."""


class DigestMismatchError(Exception):
    """The apply was handed a digest that is not the manifest's own: it runs only the manifest its dry run
    reported."""


def _operator_label(db: Session, operator_account_id: int) -> str:
    operator = db.get(User, operator_account_id)
    if operator is None or not operator.is_admin or not operator.is_active or not operator.email_verified:
        raise OperatorNotAuthorizedError()
    return f"account:{operator.id}"


def _lock_grants(db: Session) -> None:
    """Take the grants' lock for the rest of the caller's transaction (PB-02).

    Every grant and revoke unit takes it first, so units run one at a time across processes, and the count of
    active grants a grant reads under it cannot be overtaken by another grant before this unit commits: two applies
    racing at the cap grant one account between them, not two. It is a transaction-level advisory lock, released at
    the commit or rollback, so it never outlives the unit on a pooled connection (as ``waitlist_service`` and
    ``admin_filing_service`` take theirs). SQLite has no advisory locks; the operator command runs in one process
    there."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(select(func.pg_advisory_xact_lock(GRANT_LOCK_KEY)))


def holds_stripe_identity(user: User) -> bool:
    """The account holds a Stripe customer or subscription id, so a Stripe event can find it
    (``subscription_sync._find_user``): a grant refuses it, and the readout counts an active grant whose account has
    gained one. It does not decide a revoke: the webhook writes ``is_pro`` only through a Subscription row, so a revoke
    leaves the flag to the webhook only when that row exists (:attr:`_Account.billing_owned`), and clears the grant's
    Pro beside a Stripe id alone. Read only, never written here."""
    return bool(user.stripe_customer_id or user.stripe_subscription_id)


@dataclass(frozen=True)
class _Account:
    """What one evaluation reads about an account; under the account's row lock when an apply reads it."""

    user: Optional[User]
    subscription: Optional[Subscription] = None
    grant: Optional[ComplimentaryAccessGrant] = None
    invite: Optional[InviteCode] = None
    has_agreement: bool = False

    @property
    def active_grant(self) -> Optional[ComplimentaryAccessGrant]:
        return self.grant if self.grant is not None and self.grant.revoked_at is None else None

    @property
    def billing_owned(self) -> bool:
        """The webhook owns the account's ``is_pro``: a Subscription row exists. Every webhook writer of the flag goes
        through the row (``subscription_sync._get_or_create_subscription``; the retired reverse trial creates one too),
        so with no row a set flag can only be the grant's, even beside a Stripe customer a checkout stored after the
        grant committed, and a revoke clears it."""
        return self.subscription is not None


def _read_account(db: Session, account_id: int, *, lock: bool) -> _Account:
    query = db.query(User).filter(User.id == account_id)
    if lock:
        # The account's users row lock, FOR NO KEY UPDATE, as refresh_token_service.lock_user_tokens and
        # verify_email_token take it: a second unit for the account, its deletion and any other write to its row
        # wait for this unit's commit, and the reads below see the commit of whoever held the lock before.
        query = query.with_for_update(key_share=True)
    user = query.populate_existing().first()
    if user is None:
        return _Account(user=None)
    return _Account(
        user=user,
        subscription=db.query(Subscription).filter(Subscription.user_id == account_id).populate_existing().first(),
        grant=(
            db.query(ComplimentaryAccessGrant)
            .filter(ComplimentaryAccessGrant.user_id == account_id)
            .populate_existing()
            .first()
        ),
        invite=(
            db.query(InviteCode)
            .filter(InviteCode.user_id == account_id, InviteCode.used_at.isnot(None))
            .order_by(InviteCode.id)
            .first()
        ),
        has_agreement=db.query(AccountAgreement.id).filter(AccountAgreement.user_id == account_id).first() is not None,
    )


def _identity_refusal(account: _Account, entry: ManifestAccount) -> Optional[str]:
    if account.user is None:
        return "account_not_found"
    if email_fingerprint(account.user.email) != entry.email_sha256:
        # A mistyped id names someone else's account, or the address changed: nothing more is read about it.
        return "identity_mismatch"
    return None


def _grant_outcome(account: _Account, entry: ManifestAccount, manifest: GrantManifest) -> tuple[str, list[str]]:
    """``eligible``; ``already_granted`` (this cohort's grant set the account's Pro, with this review date);
    ``review_date_moves`` (the same, with another review date, which the apply moves to the manifest's); or
    ``refused`` with every reason that applies."""
    identity = _identity_refusal(account, entry)
    if identity:
        return "refused", [identity]
    user = account.user
    refusals = []
    if not user.is_active:
        refusals.append("account_inactive")
    if not user.email_verified:
        refusals.append("email_not_verified")
    if not user.is_beta:
        refusals.append("not_invited_beta")
    if account.invite is None:
        refusals.append("no_redeemed_invite")
    if not account.has_agreement:
        refusals.append("no_signup_agreement")
    if account.subscription is not None:
        refusals.append("subscription_exists")
    if holds_stripe_identity(user):
        refusals.append("stripe_identity")
    active = account.active_grant
    if active is None:
        if is_pro_user(user):
            refusals.append("pro_from_another_source")
    else:
        if active.cohort != manifest.cohort:
            refusals.append("granted_in_another_cohort")
        if not pro_from_mirror(user):
            refusals.append("grant_without_pro")
    if refusals:
        return "refused", refusals
    if active is None:
        return "eligible", []
    return ("already_granted" if active.review_on == manifest.review_on else "review_date_moves"), []


def _revoke_outcome(account: _Account, entry: ManifestAccount, manifest: RevokeManifest) -> tuple[str, list[str]]:
    """``revocable``, ``revocable_billing_owned`` (the flag is the webhook's now), ``not_granted``, or ``refused``."""
    identity = _identity_refusal(account, entry)
    if identity:
        return "refused", [identity]
    active = account.active_grant
    if active is None:
        return "not_granted", []
    if active.cohort != manifest.cohort:
        return "refused", ["granted_in_another_cohort"]
    return ("revocable_billing_owned" if account.billing_owned else "revocable"), []


def _evaluate(account: _Account, entry: ManifestAccount, manifest: Manifest) -> tuple[str, list[str]]:
    if isinstance(manifest, GrantManifest):
        return _grant_outcome(account, entry, manifest)
    return _revoke_outcome(account, entry, manifest)


def _state(account: _Account) -> dict:
    """The account's plan state for an audit row's before and after."""
    user = account.user
    grant = account.grant
    return {
        "is_pro": bool(user.is_pro),
        "plan": get_plan(user).value,
        "grant": "none" if grant is None else ("active" if grant.revoked_at is None else "revoked"),
    }


def _active_grant_count(db: Session) -> int:
    return db.query(func.count(ComplimentaryAccessGrant.id)).filter(ComplimentaryAccessGrant.revoked_at.is_(None)).scalar() or 0


@dataclass
class Report:
    """What a dry run would do or an apply did, safe for a public log: counts, and refusals by their 1-based place
    in the manifest. It never carries an account id, an address or the manifest's reason."""

    action: str
    mode: str
    manifest_sha256: str
    cohort: str
    entries: int
    active_grants_before: int
    active_grants_after: int
    cap: int = MAX_ACTIVE_GRANTS
    review_on: Optional[str] = None
    outcomes: dict = field(default_factory=dict)
    refusals: list = field(default_factory=list)
    stopped: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "action": self.action,
            "mode": self.mode,
            "manifest_sha256": self.manifest_sha256,
            "cohort": self.cohort,
            "review_on": self.review_on,
            "entries": self.entries,
            "cap": self.cap,
            "active_grants_before": self.active_grants_before,
            "active_grants_after": self.active_grants_after,
            "outcomes": dict(sorted(self.outcomes.items())),
            "refusals": self.refusals,
            "stopped": self.stopped,
        }


def _report(manifest: Manifest, digest: str, mode: str, before: int) -> Report:
    return Report(
        action=manifest.action,
        mode=mode,
        manifest_sha256=digest,
        cohort=manifest.cohort,
        entries=len(manifest.accounts),
        active_grants_before=before,
        active_grants_after=before,
        review_on=manifest.review_on.isoformat() if isinstance(manifest, GrantManifest) else None,
    )


def _tally(report: Report, position: int, outcome: str, refusals: list[str]) -> None:
    report.outcomes[outcome] = report.outcomes.get(outcome, 0) + 1
    if refusals:
        report.refusals.append({"entry": position, "codes": refusals})


def dry_run(db: Session, manifest: Manifest, digest: str, *, today: date) -> Report:
    """Evaluate every account in the manifest without writing, and report what an apply would do. A grant that would
    take the active grants past the cap stops the whole manifest (``stopped: cap_exceeded``): nothing is granted
    until the operator narrows it or revokes others first. Raises :class:`ManifestError` for a review date out of
    its window and :class:`OperatorNotAuthorizedError` for an operator who is not an active, verified admin."""
    try:
        check_review_window(manifest, today)
        _operator_label(db, manifest.operator_account_id)
        report = _report(manifest, digest, "dry-run", _active_grant_count(db))
        newly = 0
        for position, entry in enumerate(manifest.accounts, start=1):
            outcome, refusals = _evaluate(_read_account(db, entry.account_id, lock=False), entry, manifest)
            _tally(report, position, outcome, refusals)
            if outcome == "eligible":
                newly += 1
            elif outcome in ("revocable", "revocable_billing_owned"):
                newly -= 1
        report.active_grants_after = report.active_grants_before + newly
        if report.active_grants_after > MAX_ACTIVE_GRANTS:
            report.stopped = "cap_exceeded"
            report.active_grants_after = report.active_grants_before
        return report
    finally:
        db.rollback()  # the read transaction ends here, before the caller reports or applies


def _audit_details(
    *, operator: str, runner: Optional[str], manifest: Manifest, digest: str, account: _Account, before: dict,
    after: dict, billing_owned: Optional[bool] = None,
) -> dict:
    """What a grant's or a revoke's audit row records: the cohort, reason and manifest it ran from, the operator, the
    run's provenance, the invite the account redeemed, and the account's plan state before and after."""
    details = {
        "cohort": manifest.cohort,
        "reason": manifest.reason,
        "manifest_sha256": digest,
        "operator": operator,
        "runner": runner,
        "invite_cohort": account.invite.cohort if account.invite is not None else None,
        "before": before,
        "after": after,
    }
    if isinstance(manifest, GrantManifest):
        details["review_on"] = manifest.review_on.isoformat()
    if billing_owned is not None:
        details["billing_owned"] = billing_owned
    return details


def _grant_one(
    db: Session, manifest: GrantManifest, digest: str, entry: ManifestAccount, *, operator: str, runner: Optional[str],
) -> tuple[str, list[str]]:
    try:
        _lock_grants(db)
        account = _read_account(db, entry.account_id, lock=True)
        outcome, refusals = _grant_outcome(account, entry, manifest)
        if outcome == "review_date_moves":
            return _move_review_date(db, manifest, digest, account, operator=operator, runner=runner)
        if outcome != "eligible":
            db.rollback()
            return outcome, refusals
        if _active_grant_count(db) >= MAX_ACTIVE_GRANTS:
            db.rollback()
            return "refused", ["cap_reached"]
        user = account.user
        before = _state(account)
        grant = account.grant or ComplimentaryAccessGrant(user_id=user.id)
        grant.cohort = manifest.cohort
        grant.reason = manifest.reason
        grant.review_on = manifest.review_on
        grant.granted_at = utcnow()
        grant.granted_by = operator
        grant.manifest_sha256 = digest
        grant.revoked_at = None
        grant.revoked_by = None
        grant.revoke_reason = None
        if account.grant is None:
            db.add(grant)
        user.is_pro = True
        after = {"is_pro": True, "plan": get_plan(user).value, "grant": "active"}
        # Mandatory: staged in this unit's transaction, so the row commits with the change it records or neither does.
        # The action is spelled here, as legalTruth.spec.tsx reads every audit action the backend writes.
        create_audit_log(
            db, action="complimentary_access_granted", user_id=manifest.operator_account_id, entity_type="user",
            entity_id=str(user.id), mandatory=True,
            details=_audit_details(operator=operator, runner=runner, manifest=manifest, digest=digest,
                                   account=account, before=before, after=after),
        )
        db.commit()
        return "granted", []
    except Exception:
        db.rollback()
        raise


def _move_review_date(
    db: Session, manifest: GrantManifest, digest: str, account: _Account, *, operator: str, runner: Optional[str],
) -> tuple[str, list[str]]:
    """Move an active grant's review date to the manifest's, with its audit row in the same commit, under the unit's
    locks. The account's Pro, the grant's provenance and the cap stay as they are: nothing expires on the date
    (docs/ops/complimentary-access.md, "End date"), so the move changes only when the readout counts the grant due."""
    grant = account.active_grant
    state = _state(account)
    before = {**state, "review_on": grant.review_on.isoformat()}
    grant.review_on = manifest.review_on
    after = {**state, "review_on": manifest.review_on.isoformat()}
    create_audit_log(
        db, action="complimentary_access_review_moved", user_id=manifest.operator_account_id, entity_type="user",
        entity_id=str(account.user.id), mandatory=True,
        details=_audit_details(operator=operator, runner=runner, manifest=manifest, digest=digest, account=account,
                               before=before, after=after),
    )
    db.commit()
    return "review_date_moved", []


def _revoke_one(
    db: Session, manifest: RevokeManifest, digest: str, entry: ManifestAccount, *, operator: str, runner: Optional[str],
) -> tuple[str, list[str]]:
    try:
        _lock_grants(db)
        account = _read_account(db, entry.account_id, lock=True)
        outcome, refusals = _revoke_outcome(account, entry, manifest)
        if outcome not in ("revocable", "revocable_billing_owned"):
            db.rollback()
            return outcome, refusals
        user = account.user
        grant = account.active_grant
        before = _state(account)
        grant.revoked_at = utcnow()
        grant.revoked_by = operator
        grant.revoke_reason = manifest.reason
        billing_owned = outcome == "revocable_billing_owned"
        if not billing_owned:
            # Only the grant's own Pro: an account with billing state keeps whatever its webhook set.
            user.is_pro = False
        after = {"is_pro": bool(user.is_pro), "plan": get_plan(user).value, "grant": "revoked"}
        create_audit_log(
            db, action="complimentary_access_revoked", user_id=manifest.operator_account_id, entity_type="user",
            entity_id=str(user.id), mandatory=True,
            details=_audit_details(operator=operator, runner=runner, manifest=manifest, digest=digest,
                                   account=account, before=before, after=after, billing_owned=billing_owned),
        )
        db.commit()
        return ("revoked_billing_untouched" if billing_owned else "revoked"), []
    except Exception:
        db.rollback()
        raise


def apply(
    db: Session, manifest: Manifest, digest: str, *, confirm_digest: str, today: date, runner: Optional[str] = None,
) -> Report:
    """Apply the manifest whose digest the operator confirmed, one account per unit, in manifest order.

    The dry run's checks run first (:func:`dry_run`); a manifest it stops is not applied. Each account is then read
    again under the grants' lock and its row lock and re-evaluated, so a change since the dry run (a new
    subscription, a deletion, a racing apply that filled the cap) is refused rather than overwritten; an eligible
    account's ledger row, ``is_pro`` and audit row commit together. A unit that raises rolls back alone and the
    error propagates: units committed before it stay, and a rerun skips them as ``already_granted`` or
    ``not_granted``."""
    if confirm_digest != digest:
        raise DigestMismatchError()
    check_runner_label(runner)
    plan = dry_run(db, manifest, digest, today=today)
    if plan.stopped:
        plan.mode = "apply"
        return plan
    try:
        operator = _operator_label(db, manifest.operator_account_id)
    finally:
        db.rollback()
    report = _report(manifest, digest, "apply", plan.active_grants_before)
    unit = _grant_one if isinstance(manifest, GrantManifest) else _revoke_one
    for position, entry in enumerate(manifest.accounts, start=1):
        outcome, refusals = unit(db, manifest, digest, entry, operator=operator, runner=runner)
        _tally(report, position, outcome, refusals)
    try:
        report.active_grants_after = _active_grant_count(db)
    finally:
        db.rollback()
    return report


def readout(db: Session, *, today: date) -> dict:
    """Counts for the operator, safe for a public log. Active grants by cohort and those whose review date has come;
    and three kinds of drift: an active grant whose account is no longer Pro through it (a subscription row decides
    its plan, or something cleared the flag), an active grant whose account now holds a Stripe id (a Stripe event can
    reach it), and a revoked grant whose account is still Pro through the ``is_pro`` fallback alone. Reads only."""
    try:
        grants = db.query(ComplimentaryAccessGrant).all()
        active = [grant for grant in grants if grant.revoked_at is None]
        revoked = [grant for grant in grants if grant.revoked_at is not None]
        by_cohort: dict[str, int] = {}
        for grant in active:
            by_cohort[grant.cohort] = by_cohort.get(grant.cohort, 0) + 1
        return {
            "cap": MAX_ACTIVE_GRANTS,
            "active_grants": len(active),
            "revoked_grants": len(revoked),
            "active_by_cohort": dict(sorted(by_cohort.items())),
            "due_for_review": sum(1 for grant in active if grant.review_on <= today),
            "active_without_complimentary_pro": sum(1 for grant in active if not pro_from_mirror(grant.user)),
            "active_with_stripe_identity": sum(1 for grant in active if holds_stripe_identity(grant.user)),
            "revoked_still_pro": sum(1 for grant in revoked if pro_from_mirror(grant.user)),
        }
    finally:
        db.rollback()


def serves_complimentary_pro(db: Session, user: User) -> bool:
    """True when the account's Pro is a complimentary grant's: entitlements resolves it through the ``is_pro``
    mirror (no subscription row decides the plan) and an active grant set that mirror. Billing then names the
    access as complimentary, with no renewal, price or trial, and offers no checkout."""
    if not pro_from_mirror(user):
        return False
    return (
        db.query(ComplimentaryAccessGrant.id)
        .filter(ComplimentaryAccessGrant.user_id == user.id, ComplimentaryAccessGrant.revoked_at.is_(None))
        .first()
        is not None
    )
