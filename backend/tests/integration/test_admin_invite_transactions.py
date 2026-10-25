"""E171: the invite row lock on PostgreSQL. The admin router's revoke and re-send of an invite read it under its row
lock from their check to their commit (``invite_service._unused_invite_locked``), so a registration that redeemed it
first is waited for and seen: the revoke refuses the redeemed invite instead of revoking it, and the re-send refuses it
instead of minting its replacement.

Since E171's invite slice the admin router runs both in the thread pool, where a registration on the same instance, as
on the other, can redeem the invite between the check and the write. The cases:

- the control: without the lock, a revoke or re-send that reads the invite while a redemption is uncommitted waits only
  at its own write, then revokes the redeemed invite, and the re-send mints a replacement for it, so the case after it
  is not passing on writes that never met;
- with the lock, each waits at its read for the redemption, sees its commit and refuses the redeemed invite, revoking
  and minting nothing;
- two admins' writes of one invite take turns: the second waits at its read for the first's lock and both commit. A
  shared lock (FOR SHARE) would let both read and then deadlock at their writes, one of them answering 500.

The re-send runs the route's unit, whose recipient check reads the invite first and keeps no reference to it, so the
locked read loads it afresh. Two more writes keep the invite they read before the lock, as a caller that held it would:
an entity query hands back an invite the session still holds unchanged, so the locked read must re-read the row
(``populate_existing``). Each case asserts that its write waited for the redemption's row lock, so a case whose write
never met the redemption fails rather than passes.
Each case owns a disposable schema, and its sessions name themselves after it (``application_name``), so a wait counts
only the case's own sessions. ADMIN_INVITE_CONCURRENCY_TEST_DATABASE_URL enables these cases in CI ("Verify admin invite
concurrency on PostgreSQL"); without the variable they skip.
"""
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.database import Base, SessionLocal
from app.models import InviteCode, User
from app.services import invite_service
from app.utils.datetimes import utcnow

# The case's other sessions waiting for a row another transaction has written ("transactionid") or locked ("tuple").
# The checking connection is the case's own, so its application_name is the case's schema.
WAITING = text(
    "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock' AND wait_event IN :events"
    " AND application_name = current_setting('application_name') AND pid <> pg_backend_pid()"
).bindparams(bindparam("events", expanding=True))
ROW = ("transactionid", "tuple")


@pytest.fixture
def postgres_engine():
    url = os.environ.get("ADMIN_INVITE_CONCURRENCY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("ADMIN_INVITE_CONCURRENCY_TEST_DATABASE_URL is not configured")
    assert make_url(url).get_backend_name() == "postgresql", "The admin invite gate requires PostgreSQL"
    schema = f"admin_invite_transactions_{uuid.uuid4().hex}"
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=30000",
                                              "application_name": schema})
    with engine.begin() as conn:
        conn.execute(CreateSchema(schema))
    try:
        Base.metadata.create_all(engine)
        with _session(engine) as db:
            db.add(User(email="invitee@example.com", is_active=True))
            db.add(InviteCode(code_hash="0" * 64, email="invitee@example.com", cohort="wave-1",
                              expires_at=utcnow() + timedelta(days=7)))
            db.commit()
        yield engine
    finally:
        with engine.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        engine.dispose()


def _session(bind) -> Session:
    """A session with production's settings (``SessionLocal``'s, which do not autoflush) on this case's engine (E132)."""
    return sessionmaker(**{**SessionLocal.kw, "bind": bind})()


def _ids(engine) -> tuple[int, int]:
    """The seeded invite's id and its invitee's."""
    with _session(engine) as db:
        return db.query(InviteCode.id).scalar(), db.query(User.id).scalar()


def _state(engine) -> tuple[bool, bool, int]:
    """Whether the seeded invite is redeemed and whether it is revoked, and how many invites there are."""
    with _session(engine) as db:
        seeded = db.query(InviteCode).order_by(InviteCode.id).first()
        return seeded.used_at is not None, seeded.is_revoked, db.query(InviteCode).count()


def _revoke(invite_id: int):
    def write(db: Session) -> InviteCode:
        return invite_service.revoke_invite(db, invite_id)
    return write


def _resend(invite_id: int):
    """The re-send route's unit without its readiness check: the recipient check, then the re-issue."""
    def write(db: Session) -> InviteCode:
        assert invite_service.invite_has_delivery_recipient(db, invite_id)
        invite, _raw, _link = invite_service.reissue_invite(db, invite_id, created_by=None, expires_in_hours=None)
        return invite
    return write


def _keeping_the_invite(make):
    """The write on a session that read the invite before the lock and keeps it until the write returns."""
    def keeping(invite_id: int):
        write = make(invite_id)

        def run(db: Session) -> InviteCode:
            kept = db.get(InviteCode, invite_id)  # read while the redemption is uncommitted, and held
            result = write(db)
            assert kept is not None
            return result
        return run
    return keeping


WRITES = {
    "revoke": _revoke,
    "re-send": _resend,
    "revoke, the invite kept": _keeping_the_invite(_revoke),
    "re-send, the invite kept": _keeping_the_invite(_resend),
}


def _run(engine, write):
    """Runs one write on a session of its own; returns (its result, None) or (None, the error it raised)."""
    try:
        with _session(engine) as db:
            return write(db), None
    except Exception as exc:  # noqa: BLE001 - the case asserts on what each write raised
        return None, exc


def _waiting(engine, sessions: int) -> bool:
    """Whether, within 5 s, at least ``sessions`` of the case's other sessions wait for a row's lock."""
    deadline = time.monotonic() + 5
    with engine.connect() as conn:
        while time.monotonic() < deadline:
            waiting = conn.execute(WAITING, {"events": list(ROW)}).scalar()
            conn.rollback()  # PostgreSQL reads pg_stat_activity once a transaction: each poll reads it afresh
            if waiting >= sessions:
                return True
            time.sleep(0.002)
    return False


class _Redemption:
    """A registration's redemption of the invite (``redeem_invite`` with ``commit=False``, as registration calls it),
    on a thread of its own, left uncommitted until ``commit``. A case enters it after its thread pool, so a failed
    assertion commits it before the pool waits for a write that waits for it."""

    def __init__(self, engine, invite_id: int, user_id: int):
        self.engine = engine
        self.invite_id = invite_id
        self.user_id = user_id
        self.redeemed = threading.Event()
        self.committing = threading.Event()
        self.thread = threading.Thread(target=self._redeem)

    def _redeem(self) -> None:
        with _session(self.engine) as db:
            if invite_service.redeem_invite(db, db.get(InviteCode, self.invite_id), db.get(User, self.user_id),
                                            commit=False):
                self.redeemed.set()
            self.committing.wait(timeout=30)
            db.commit()

    def __enter__(self) -> "_Redemption":
        self.thread.start()
        assert self.redeemed.wait(timeout=5), "the registration must redeem the invite"
        return self

    def __exit__(self, *exc) -> None:
        self.commit()

    def commit(self) -> None:
        self.committing.set()
        self.thread.join(timeout=30)


def _write_beside_a_redemption(engine, write) -> tuple[object, Exception | None]:
    """Starts the write while a registration's redemption of the invite is uncommitted, asserts it waits for that row,
    commits the redemption; returns the write's result and error."""
    invite_id, user_id = _ids(engine)
    with ThreadPoolExecutor(max_workers=1) as pool, _Redemption(engine, invite_id, user_id) as redemption:
        future = pool.submit(_run, engine, write(invite_id))
        waited = _waiting(engine, 1)
        redemption.commit()
        result, error = future.result(timeout=60)
    assert waited, "the write must wait for the row the uncommitted redemption wrote"
    return result, error


def _unlocked(db: Session, invite_id: int) -> InviteCode:
    """``_unused_invite_locked`` without its lock, as the revoke and the re-issue read the invite before E171."""
    invite = db.query(InviteCode).filter(InviteCode.id == invite_id).first()
    if not invite:
        raise invite_service.InviteNotFoundError(invite_id)
    if invite.used_at is not None:
        raise invite_service.InviteAlreadyRedeemedError(invite_id)
    return invite


@pytest.mark.parametrize("write", sorted(WRITES))
def test_without_the_lock_a_write_acts_on_an_invite_redeemed_meanwhile(postgres_engine, monkeypatch, write):
    """The control: read before the redemption commits, the invite looks unused, so the revoke revokes a redeemed
    invite and the re-send also mints its replacement."""
    monkeypatch.setattr(invite_service, "_unused_invite_locked", _unlocked)
    _, error = _write_beside_a_redemption(postgres_engine, WRITES[write])
    assert error is None, error
    assert _state(postgres_engine) == (True, True, 2 if write.startswith("re-send") else 1)


@pytest.mark.parametrize("write", ["revoke", "re-send"])
def test_two_writes_of_one_invite_take_turns(postgres_engine, write):
    """A revoke holds the invite's lock from its read; a second admin's revoke or re-send of the invite waits at its
    own locked read until the first commits, then acts on the revoked, unused invite, and both commit."""
    invite_id, _ = _ids(postgres_engine)
    first_read = threading.Event()
    release = threading.Event()

    def first(db: Session) -> InviteCode:
        invite = invite_service._unused_invite_locked(db, invite_id)
        first_read.set()
        release.wait(timeout=30)
        invite.is_revoked = True
        db.commit()
        return invite

    with ThreadPoolExecutor(max_workers=2) as pool:
        held = pool.submit(_run, postgres_engine, first)
        try:
            assert first_read.wait(timeout=5), "the first write must read the invite under its lock"
            second = pool.submit(_run, postgres_engine, WRITES[write](invite_id))
            waited = _waiting(postgres_engine, 1)
        finally:
            release.set()
        results = [held.result(timeout=60), second.result(timeout=60)]
    assert waited, "the second write must wait at its read for the first write's lock"
    assert [error for _, error in results] == [None, None]
    assert _state(postgres_engine) == (False, True, 2 if write == "re-send" else 1)


@pytest.mark.parametrize("write", sorted(WRITES))
def test_a_write_waits_for_a_redemption_and_refuses_the_redeemed_invite(postgres_engine, write):
    """With the lock, the write's read waits for the redemption, sees its commit and refuses: nothing is revoked or
    minted."""
    _, error = _write_beside_a_redemption(postgres_engine, WRITES[write])
    assert isinstance(error, invite_service.InviteAlreadyRedeemedError), error
    assert _state(postgres_engine) == (True, False, 1)
