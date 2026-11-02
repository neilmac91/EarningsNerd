"""PB-02: ``scripts/complimentary_access.py``, the operator command, and the privacy of what it prints.

The Ops log the command runs in is public, so the rule is that no report, refusal or log line carries an account id,
an address or the manifest's reason. These cases plant distinctive ids and addresses, drive every database command
(dry run, apply, readout, a refused apply, a failing unit) and look for them in stdout, stderr and every log record,
including one a dependency emits while the command runs. ``fingerprint`` and ``check`` run with an empty environment:
no settings, no database.
"""
import hashlib
import importlib.util
import json
import logging
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.database import SessionLocal
from app.models import AccountAgreement, AuditLog, ComplimentaryAccessGrant, InviteCode, User
from app.services import complimentary_access_service as service
from app.services.complimentary_access_manifest import email_fingerprint
from app.services.legal_readiness_service import ELIGIBILITY_VERSION, TERMS_VERSION

BACKEND = Path(__file__).resolve().parents[2]
SCRIPT = BACKEND / "scripts" / "complimentary_access.py"
_spec = importlib.util.spec_from_file_location("complimentary_access_script", SCRIPT)
command = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(command)

NOW = datetime(2030, 5, 1, 12, tzinfo=timezone.utc)
REASON = "Planted reason 7f3e"
# Ids no other row in the suite's database has, so finding one in output can only be a leak.
PLANTED_ID_BASE = 9_300_000


@pytest.fixture
def accounts():
    db = SessionLocal()
    db.query(ComplimentaryAccessGrant).delete(synchronize_session=False)
    db.commit()
    marker = uuid.uuid4().hex[:10]
    ids = []

    def make(n: int, **fields) -> User:
        user = User(id=PLANTED_ID_BASE + n, email=f"planted-{marker}-{n}@example.com", **fields)
        db.add(user)
        db.commit()
        ids.append(user.id)
        return user

    operator = make(0, is_admin=True, email_verified=True, is_active=True)
    testers = []
    for n in (1, 2, 3):
        tester = make(n, email_verified=n != 3, is_beta=True, is_active=True)
        db.add(InviteCode(code_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(), cohort="planted-invites",
                          email=tester.email, user_id=tester.id, used_at=NOW, expires_at=NOW + timedelta(days=7)))
        db.add(AccountAgreement(user_id=tester.id, adult_eligible=True, terms_accepted=True,
                                terms_version=TERMS_VERSION, eligibility_version=ELIGIBILITY_VERSION, accepted_at=NOW,
                                source="password"))
        testers.append(tester)
    db.commit()
    try:
        yield operator, testers
    finally:
        db.rollback()
        keys = [str(i) for i in ids]
        db.query(AuditLog).filter(AuditLog.entity_id.in_(keys) | AuditLog.user_id.in_(keys)).delete(
            synchronize_session=False)
        for model in (ComplimentaryAccessGrant, InviteCode, AccountAgreement):
            db.query(model).filter(model.user_id.in_(ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
        db.close()


def _manifest_file(tmp_path, action, operator, testers, review_days=60) -> Path:
    payload = {
        "action": action, "cohort": "private-beta-2026-11", "reason": REASON, "operator_account_id": operator.id,
        "accounts": [{"account_id": t.id, "email_sha256": email_fingerprint(t.email)} for t in testers],
    }
    if action == "grant":
        payload["review_on"] = (datetime.now(timezone.utc).date() + timedelta(days=review_days)).isoformat()
    path = tmp_path / f"{action}-{uuid.uuid4().hex}.json"
    path.write_text(json.dumps(payload))
    return path


def _run(capsys, caplog, *argv):
    caplog.set_level(logging.DEBUG)
    code = command.main(list(argv))
    out, err = capsys.readouterr()
    logged = "\n".join(record.getMessage() for record in caplog.records)
    caplog.clear()
    return code, out, err, logged


def _assert_nothing_planted(texts, operator, testers):
    published = "\n".join(texts)
    for account in [operator, *testers]:
        assert account.email not in published
        assert str(account.id) not in published
    assert REASON not in published


def test_every_report_and_log_line_carries_no_planted_id_or_address(accounts, tmp_path, capsys, caplog, monkeypatch):
    operator, testers = accounts
    grant = _manifest_file(tmp_path, "grant", operator, testers)
    real_dry_run = service.dry_run

    def chatty_dry_run(db, manifest, digest, **kwargs):
        # A dependency that logs what it reads: the command's output must not carry it.
        logging.getLogger("app.services.chatty").warning("read %s (%s)", testers[0].email, testers[0].id)
        return real_dry_run(db, manifest, digest, **kwargs)

    monkeypatch.setattr(service, "dry_run", chatty_dry_run)

    code, out, err, logged = _run(capsys, caplog, "dry-run", "--manifest", str(grant))
    assert code == 0
    report = json.loads(out)
    assert (report["outcomes"], report["refusals"]) == ({"eligible": 2, "refused": 1},
                                                         [{"entry": 3, "reasons": ["email_not_verified"]}])
    texts = [out, err, logged]

    code, out, err, logged = _run(capsys, caplog, "apply", "--manifest", str(grant),
                                  "--confirm-digest", report["manifest_sha256"], "--runner", "ops-run:1")
    assert (code, json.loads(out)["outcomes"]) == (0, {"granted": 2, "refused": 1})
    texts += [out, err, logged]

    code, out, err, logged = _run(capsys, caplog, "readout")
    assert (code, json.loads(out)["active_grants"]) == (0, 2)
    texts += [out, err, logged]

    revoke = _manifest_file(tmp_path, "revoke", operator, testers[:1])
    code, out, err, logged = _run(capsys, caplog, "apply", "--manifest", str(revoke), "--confirm-digest", "0" * 64)
    assert (code, json.loads(out)["refused"]) == (1, "digest_mismatch")
    texts += [out, err, logged]

    _assert_nothing_planted(texts, operator, testers)
    assert logging.root.manager.disable == logging.NOTSET  # logging comes back once the command returns


def test_a_failing_unit_reports_its_class_alone(accounts, tmp_path, capsys, caplog, monkeypatch):
    operator, testers = accounts
    grant = _manifest_file(tmp_path, "grant", operator, testers[:1])

    def failing_unit(db, manifest, digest, entry, **kwargs):
        raise RuntimeError(f"database said no for {testers[0].email} ({entry.account_id})")

    monkeypatch.setattr(service, "_grant_one", failing_unit)
    code, out, err, logged = _run(capsys, caplog, "dry-run", "--manifest", str(grant))
    digest = json.loads(out)["manifest_sha256"]

    code, out, err, logged = _run(capsys, caplog, "apply", "--manifest", str(grant), "--confirm-digest", digest)

    assert (code, json.loads(out)) == (2, {"failed": "RuntimeError"})
    _assert_nothing_planted([out, err, logged], operator, testers)


def test_refusals_exit_one_and_say_why_without_values(accounts, tmp_path, capsys, caplog):
    operator, testers = accounts
    not_admin = _manifest_file(tmp_path, "grant", testers[0], testers[1:2])
    code, out, *_ = _run(capsys, caplog, "dry-run", "--manifest", str(not_admin))
    assert (code, json.loads(out)) == (1, {"refused": "operator_not_authorized"})

    late = _manifest_file(tmp_path, "grant", operator, testers[:1], review_days=400)
    code, out, *_ = _run(capsys, caplog, "dry-run", "--manifest", str(late))
    assert (code, json.loads(out)["refused"]) == (1, "manifest")

    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps({"action": "grant", "accounts": [{"account_id": testers[0].id,
                                                                    "email_sha256": testers[0].email}]}))
    code, out, err, logged = _run(capsys, caplog, "dry-run", "--manifest", str(broken))
    assert (code, json.loads(out)["refused"]) == (1, "manifest")
    _assert_nothing_planted([out, err, logged], operator, testers)


def test_fingerprint_and_check_run_with_no_settings_and_no_database(tmp_path):
    env = {"PATH": os.environ.get("PATH", "")}
    fingerprints = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "fingerprint"], input=" One@Example.com\n\ntwo@example.com\n",
        capture_output=True, text=True, env=env, cwd=BACKEND, check=True,
    ).stdout.split()
    assert fingerprints == [email_fingerprint("one@example.com"), email_fingerprint("two@example.com")]

    manifest = tmp_path / "manifest.json"
    review_on = (datetime.now(timezone.utc).date() + timedelta(days=30)).isoformat()
    manifest.write_text(json.dumps({
        "action": "grant", "cohort": "private-beta-2026-11", "reason": "Private beta tester", "review_on": review_on,
        "operator_account_id": 1, "accounts": [{"account_id": 2, "email_sha256": fingerprints[0]}],
    }))
    checked = subprocess.run([sys.executable, "-I", str(SCRIPT), "check", "--manifest", str(manifest)],
                             capture_output=True, text=True, env=env, cwd=BACKEND)
    assert checked.returncode == 0, checked.stderr
    assert json.loads(checked.stdout)["entries"] == 1 and len(json.loads(checked.stdout)["manifest_sha256"]) == 64
