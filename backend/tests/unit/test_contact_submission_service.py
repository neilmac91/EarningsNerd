"""Contact submission persistence: a failed commit rolls back and is mapped, its cause kept.

The router answers ``ContactPersistenceError`` with the 500 (``test_contact_route.py``); these cases hold
the service's side of that boundary with a session stub, so no database is involved.
"""
import logging

import pytest

from app.services.contact_submission_service import ContactPersistenceError, persist_contact_submission

FIELDS = {
    "name": "Ada Lovelace",
    "email": "ada@example.com",
    "subject": "Question",
    "message": "Does the summary include segment data?",
    "ip_address": "hashed-ip",
}


class _Session:
    """Records the calls a persistence attempt makes; ``commit_error`` and ``rollback_error`` fail them."""

    def __init__(self, *, commit_error=None, rollback_error=None):
        self.commit_error, self.rollback_error = commit_error, rollback_error
        self.calls = []

    def add(self, row):
        self.calls.append("add")

    def commit(self):
        self.calls.append("commit")
        if self.commit_error is not None:
            raise self.commit_error

    def refresh(self, row):
        self.calls.append("refresh")

    def rollback(self):
        self.calls.append("rollback")
        if self.rollback_error is not None:
            raise self.rollback_error


def _persist(db):
    return persist_contact_submission(db, logger=logging.getLogger(__name__), **FIELDS)


def test_a_failed_commit_rolls_back_and_keeps_the_original_as_the_cause():
    original = RuntimeError("deadlock detected")
    db = _Session(commit_error=original)
    with pytest.raises(ContactPersistenceError) as raised:
        _persist(db)
    assert raised.value.__cause__ is original
    assert db.calls == ["add", "commit", "rollback"]


def test_a_failed_rollback_propagates_as_itself():
    rollback_failure = RuntimeError("connection lost during rollback")
    db = _Session(commit_error=RuntimeError("deadlock detected"), rollback_error=rollback_failure)
    with pytest.raises(RuntimeError) as raised:
        _persist(db)
    assert raised.value is rollback_failure
    assert db.calls == ["add", "commit", "rollback"]


def test_a_saved_row_is_refreshed_and_returned():
    db = _Session()
    row = _persist(db)
    assert db.calls == ["add", "commit", "refresh"]
    assert (row.name, row.email, row.status, row.ip_address) == ("Ada Lovelace", "ada@example.com", "new", "hashed-ip")
