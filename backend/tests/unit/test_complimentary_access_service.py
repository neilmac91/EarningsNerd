"""PB-02: the operator's complimentary Pro grant, revoke and readout (``complimentary_access_service``) and its manifest.

A grant sets the ``is_pro`` mirror ``entitlements.get_plan`` falls back to for an account no billing state owns, and its
ledger row records that it did, so a revoke clears only that Pro. These cases pin the manifest's strictness and its
redacted faults, every refusal, the one-commit unit (ledger row, flag and audit row, or nothing), reruns, the cap, the
digest the apply runs, the operator check, what a unit re-reads under its locks, revoke's two outcomes, Stripe never
being reached, deletion, the readout and Billing's predicate.

SQLite renders neither ``FOR NO KEY UPDATE`` nor the advisory lock, so a race test here passes with or without them:
``test_units_take_the_grants_lock_then_the_accounts_row_lock_and_a_dry_run_takes_neither`` pins both calls with a spy
and ``test_the_grants_lock_is_a_transaction_scoped_advisory_lock_on_postgresql`` the SQL it emits
(lessons/test-pin-a-row-lock-with-a-statement-spy.md). The re-read cases show what SQLite can: a unit refuses what
changed after its dry run.
"""
import ast
import hashlib
import importlib
import json
import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import stripe
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Query

from app.database import SessionLocal
from app.models import AccountAgreement, AuditLog, ComplimentaryAccessGrant, InviteCode, Subscription, User
from app.services import audit_service, complimentary_access_service as service
from app.services.complimentary_access_manifest import (
    MAX_ACTIVE_GRANTS,
    ManifestError,
    check_review_window,
    email_fingerprint,
    load_manifest,
)
from app.services.entitlements import Plan, get_entitlements, get_plan
from app.services.legal_readiness_service import ELIGIBILITY_VERSION, TERMS_VERSION
from app.services.user_account_service import delete_account

REPO = Path(__file__).resolve().parents[3]
# A day far from the wall clock: the service is handed "today", so no case depends on when it runs.
TODAY = date(2030, 6, 1)
REVIEW_ON = date(2030, 8, 1)
COHORT = "private-beta-2026-11"
REASON = "Private beta tester"
# A synthetic salt (32 hex digits): a real manifest's is secret randomness the operator draws.
SALT = "5a" * 16
NOW = datetime(2030, 5, 1, 12, tzinfo=timezone.utc)
INVITE_COHORT = "pb02-invites"


class World:
    """Accounts this module creates, each with a unique address, removed with everything naming them afterwards."""

    def __init__(self, db):
        self.db = db
        self.ids: list[int] = []

    def user(self, **fields) -> User:
        email = fields.pop("email", None) or f"pb02-{uuid.uuid4().hex}@example.com"
        user = User(email=email, **fields)
        self.db.add(user)
        self.db.commit()
        self.ids.append(user.id)
        return user

    def tester(self, *, invite: bool = True, agreement: bool = True, **fields) -> User:
        """An invited account that finished its own signup and verification: eligible unless a field says otherwise."""
        user = self.user(**{"email_verified": True, "is_beta": True, "is_active": True, **fields})
        if invite:
            self.db.add(InviteCode(
                code_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(), email=user.email, cohort=INVITE_COHORT,
                user_id=user.id, used_at=NOW, expires_at=NOW + timedelta(days=7),
            ))
        if agreement:
            self.db.add(AccountAgreement(
                user_id=user.id, adult_eligible=True, terms_accepted=True, terms_version=TERMS_VERSION,
                eligibility_version=ELIGIBILITY_VERSION, accepted_at=NOW, source="password",
            ))
        self.db.commit()
        return user

    def operator(self, **fields) -> User:
        return self.user(**{"is_admin": True, "email_verified": True, "is_active": True, **fields})

    def manifest(self, action: str, accounts, *, operator_id: int, cohort: str = COHORT, reason: str = REASON,
                 review_on: date = REVIEW_ON):
        return load_manifest(_raw(action, [_entry(account) for account in accounts], operator_id=operator_id,
                                  cohort=cohort, reason=reason, review_on=review_on))

    def cleanup(self) -> None:
        db = self.db
        db.rollback()
        keys = [str(i) for i in self.ids]
        db.query(AuditLog).filter((AuditLog.entity_id.in_(keys)) | (AuditLog.user_id.in_(keys))).delete(
            synchronize_session=False)
        for model in (ComplimentaryAccessGrant, InviteCode, AccountAgreement, Subscription):
            db.query(model).filter(model.user_id.in_(self.ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(self.ids)).delete(synchronize_session=False)
        db.commit()


def _entry(account) -> dict:
    if isinstance(account, dict):
        return account
    return {"account_id": account.id, "email_sha256": email_fingerprint(account.email)}


def _raw(action: str, accounts: list, *, operator_id: int = 1, cohort: str = COHORT, reason: str = REASON,
         review_on: date = REVIEW_ON, salt: str = SALT) -> bytes:
    payload = {"action": action, "cohort": cohort, "reason": reason, "operator_account_id": operator_id,
               "salt": salt, "accounts": accounts}
    if action == "grant":
        payload["review_on"] = review_on.isoformat()
    return json.dumps(payload).encode()


def _fake_entry(n: int) -> dict:
    return {"account_id": n, "email_sha256": hashlib.sha256(f"fake-{n}".encode()).hexdigest()}


@pytest.fixture
def world():
    db = SessionLocal()
    # The cap counts every active grant in the database, so each case starts from none (this module alone grants).
    db.query(ComplimentaryAccessGrant).delete(synchronize_session=False)
    db.commit()
    created = World(db)
    try:
        yield created
    finally:
        created.cleanup()
        db.close()


def _apply(world, manifest_and_digest, **kwargs):
    manifest, digest = manifest_and_digest
    return service.apply(world.db, manifest, digest, confirm_digest=digest, today=TODAY, **kwargs)


def _committed(user_id: int):
    """The account's committed state, read in a session of its own."""
    with SessionLocal() as fresh:
        user = fresh.get(User, user_id)
        if user is None:
            return None
        grant = fresh.query(ComplimentaryAccessGrant).filter_by(user_id=user_id).one_or_none()
        actions = [row.action for row in fresh.query(AuditLog).filter(
            AuditLog.entity_id == str(user_id), AuditLog.action.like("complimentary_access_%")).order_by(AuditLog.id)]
        return SimpleNamespace(
            is_pro=user.is_pro, plan=get_plan(user), entitlements=get_entitlements(user),
            copilot_free_taste_used=user.copilot_free_taste_used,
            grant=None if grant is None else SimpleNamespace(
                cohort=grant.cohort, reason=grant.reason, review_on=grant.review_on, granted_by=grant.granted_by,
                granted_at=grant.granted_at, manifest_sha256=grant.manifest_sha256, revoked_at=grant.revoked_at,
                revoked_by=grant.revoked_by, revoke_reason=grant.revoke_reason),
            actions=actions,
        )


# --------------------------------------------------------------------------- the manifest


def test_a_manifest_names_at_most_twenty_accounts():
    accounts = [_fake_entry(n) for n in range(1, MAX_ACTIVE_GRANTS + 2)]
    with pytest.raises(ManifestError) as refused:
        load_manifest(_raw("grant", accounts))
    assert any(problem.startswith("grant.accounts:") for problem in refused.value.problems)
    manifest, _ = load_manifest(_raw("grant", accounts[:MAX_ACTIVE_GRANTS]))
    assert len(manifest.accounts) == MAX_ACTIVE_GRANTS == 20


@pytest.mark.parametrize("repeated", ["account_id", "email_sha256"])
def test_a_manifest_names_each_account_and_address_once(repeated):
    first, second = _fake_entry(1), _fake_entry(2)
    second[repeated] = first[repeated]
    with pytest.raises(ManifestError) as refused:
        load_manifest(_raw("grant", [first, second]))
    assert refused.value.problems == [
        f"grant: names an {'account id' if repeated == 'account_id' else 'address fingerprint'} more than once"
    ]


# An address and an id planted in malformed manifests: a fault that carried either would leak it into the public log.
PLANTED_ADDRESS = "planted.tester@example.com"
PLANTED_ID = 9_300_017


def _planted(**changes) -> bytes:
    payload = json.loads(_raw("grant", [_fake_entry(1)]))
    payload.update(changes)
    return json.dumps(payload).encode()


_NOT_AN_ACTION = ["manifest: must be grant or revoke"]
_NOT_JSON = ["manifest: is not valid JSON"]
_REPEATED = ["manifest: names a key twice in one object"]


@pytest.mark.parametrize("raw, problems", [
    # The discriminator: pydantic's message quotes the tag it found, whatever its type.
    (_planted(action=PLANTED_ADDRESS), _NOT_AN_ACTION),
    (_planted(action=PLANTED_ID), _NOT_AN_ACTION),
    (_planted(action={PLANTED_ADDRESS: PLANTED_ID}), _NOT_AN_ACTION),
    (_planted(action=[PLANTED_ADDRESS]), _NOT_AN_ACTION),
    (_planted(action=None), _NOT_AN_ACTION),
    # A repeated key, which every parser here resolves to its last value: refused, naming no key.
    (_planted()[:-1] + f', "action": "{PLANTED_ADDRESS}"}}'.encode(), _REPEATED),
    (_planted()[:-1] + f', "accounts": [{{"account_id": {PLANTED_ID}, "email_sha256": "{PLANTED_ADDRESS}"}}]}}'.encode(),
     _REPEATED),
    (('{"action": "grant", "cohort": "c-1", "reason": "Private beta tester", "review_on": "2030-08-01", '
      '"operator_account_id": 1, "accounts": [{"account_id": %d, "email_sha256": "%s", "account_id": %d}]}'
      % (PLANTED_ID, PLANTED_ADDRESS, PLANTED_ID)).encode(), _REPEATED),
    (json.dumps({"cohort": COHORT, "accounts": [{"account_id": PLANTED_ID, "email_sha256": PLANTED_ADDRESS}]}).encode(),
     _NOT_AN_ACTION),
    # Malformed JSON: cut off inside an address, trailed by one, broken UTF-8 beside one; an address as the manifest.
    (_planted()[:-30] + PLANTED_ADDRESS.encode(), _NOT_JSON),
    (_planted() + f" {PLANTED_ADDRESS} {PLANTED_ID}".encode(), _NOT_JSON),
    (_planted()[:-1] + f', "note": "{PLANTED_ADDRESS}'.encode() + b'\xff"}', _NOT_JSON),
    (json.dumps(PLANTED_ADDRESS).encode(), ["manifest: must be an object"]),
    # Unknown keys, values of the wrong type or format, and this module's own validators.
    (json.dumps({
        "action": "grant", "cohort": "Not A Slug", "reason": "Private beta tester", "review_on": PLANTED_ADDRESS,
        "operator_account_id": str(PLANTED_ID), "salt": SALT, PLANTED_ADDRESS: PLANTED_ID,
        "accounts": [{"account_id": PLANTED_ID, "email_sha256": PLANTED_ADDRESS, PLANTED_ADDRESS: 1}],
    }).encode(), [
        "grant.<unexpected key>: is not a manifest key",
        "grant.cohort: does not match its format",
        "grant.operator_account_id: must be an integer",
        "grant.accounts.0.email_sha256: does not match its format",
        "grant.accounts.0.<unexpected key>: is not a manifest key",
        "grant.review_on: must be a date (YYYY-MM-DD)",
    ]),
    (_planted(accounts=PLANTED_ADDRESS), ["grant.accounts: must be a list"]),
    (_planted(accounts=[PLANTED_ADDRESS]), ["grant.accounts.0: must be an object"]),
    (_planted(reason=f" {PLANTED_ADDRESS}"), ["grant.reason: must be printable text without surrounding spaces"]),
    (_planted(salt=PLANTED_ADDRESS), ["grant.salt: does not match its format"]),
    (_planted(salt=PLANTED_ID), ["grant.salt: must be a string"]),
    (_planted(accounts=[{**_fake_entry(1), "account_id": PLANTED_ID}, {**_fake_entry(2), "account_id": PLANTED_ID}]),
     ["grant: names an account id more than once"]),
])
def test_a_fault_names_its_place_and_kind_never_the_value(raw, problems):
    with pytest.raises(ManifestError) as refused:
        load_manifest(raw)
    assert sorted(refused.value.problems) == sorted(problems)
    for planted in (PLANTED_ADDRESS, "planted.tester", str(PLANTED_ID), "Not A Slug", _fake_entry(1)["email_sha256"],
                    _fake_entry(2)["email_sha256"], SALT):
        assert planted not in str(refused.value)


@pytest.mark.parametrize("change", [
    {"action": "extend"},  # no such action
    {"operator_account_id": "1"},  # a string where JSON carries an integer: never coerced
    {"review_on": "next month"},
    {"reason": " Padded"},
    {"reason": "Line\nbreak"},
    {"accounts": []},
    {"salt": "5a" * 15 + "5"},  # 31 hex digits: under 128 bits
    {"salt": "5A" * 16},  # upper case
    {"salt": "5g" * 16},  # not hex
    {"salt": "5a" * 64 + "5"},  # over 128 digits
])
def test_a_manifest_is_strict_json(change):
    payload = json.loads(_raw("grant", [_fake_entry(1)]))
    payload.update(change)
    with pytest.raises(ManifestError):
        load_manifest(json.dumps(payload).encode())


def test_a_revoke_manifest_carries_no_review_date():
    with pytest.raises(ManifestError):
        load_manifest(json.dumps({**json.loads(_raw("revoke", [_fake_entry(1)])), "review_on": "2030-08-01"}).encode())
    manifest, _ = load_manifest(_raw("revoke", [_fake_entry(1)]))
    assert manifest.action == "revoke"


def test_the_digest_is_canonical_and_moves_with_every_field():
    accounts = [_fake_entry(1), _fake_entry(2)]
    _, digest = load_manifest(_raw("grant", accounts))
    reordered = json.dumps(dict(reversed(list(json.loads(_raw("grant", accounts)).items())))).encode()
    assert load_manifest(reordered)[1] == digest
    variants = [
        _raw("grant", list(reversed(accounts))), _raw("grant", accounts[:1]), _raw("revoke", accounts),
        _raw("grant", accounts, operator_id=2), _raw("grant", accounts, cohort="private-beta-2026-12"),
        _raw("grant", accounts, reason="Another reason"), _raw("grant", accounts, review_on=REVIEW_ON + timedelta(1)),
        _raw("grant", accounts, salt="f" * 32),
    ]
    assert len({load_manifest(raw)[1] for raw in variants} | {digest}) == len(variants) + 1


def test_the_digest_covers_a_secret_salt_so_its_public_copy_names_no_one():
    """Every report prints the digest to the public Ops log, and every other field can be guessed (a stock reason, the
    founder's id, sequential ids, a candidate address's fingerprint): without a salt, the digest of a one-account
    manifest is matched to its tester by hashing guesses offline. The salt is required and inside the canonical form,
    so what a guesser rebuilds from the public fields is not the digest."""
    entry = _fake_entry(1)
    _, digest = load_manifest(_raw("grant", [entry]))
    public = {key: value for key, value in json.loads(_raw("grant", [entry])).items() if key != "salt"}
    rebuilt = hashlib.sha256(json.dumps(public, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert rebuilt != digest
    assert load_manifest(_raw("grant", [entry], salt="f" * 32))[1] != digest
    with pytest.raises(ManifestError) as refused:
        load_manifest(json.dumps(public).encode())
    assert refused.value.problems == ["grant.salt: is required"]


def test_a_cohort_is_an_opaque_code_that_names_no_one():
    """Every report and the readout print the cohort to the public Ops log, so it is a fixed scheme with no free letter:
    private-beta-YYYY-MM, with an optional wave. A slug that could hold a name, a workplace or a description is
    refused."""
    for cohort in ("private-beta-2026-11", "private-beta-2026-11-w2", "private-beta-2027-01-w12"):
        assert load_manifest(_raw("grant", [_fake_entry(1)], cohort=cohort))[0].cohort == cohort
    for cohort in ("jane-doe-acme", "acme-corp-friends", "private-beta-2026-13", "private-beta-2026-1",
                   "private-beta-2026-11-wave2", "private-beta-2026-11-w0", "Private-Beta-2026-11",
                   "private-beta-2026-11-jane", "private-beta-2026-11\n"):
        with pytest.raises(ManifestError) as refused:
            load_manifest(_raw("grant", [_fake_entry(1)], cohort=cohort))
        assert refused.value.problems == ["grant.cohort: does not match its format"], cohort


def test_the_review_date_falls_after_today_and_within_a_year():
    for review_on, accepted in [(TODAY, False), (TODAY - timedelta(1), False), (TODAY + timedelta(1), True),
                                (TODAY + timedelta(366), True), (TODAY + timedelta(367), False)]:
        manifest, _ = load_manifest(_raw("grant", [_fake_entry(1)], review_on=review_on))
        if accepted:
            check_review_window(manifest, TODAY)
        else:
            with pytest.raises(ManifestError):
                check_review_window(manifest, TODAY)


def test_the_fingerprint_matches_how_accounts_store_addresses():
    assert email_fingerprint("  Tester.One@Example.COM\n") == hashlib.sha256(b"tester.one@example.com").hexdigest()


def test_the_runbooks_example_manifest_runs_once_its_salt_is_drawn():
    runbook = (REPO / "docs" / "ops" / "complimentary-access.md").read_text()
    example = re.search(r"```json\n(.*?)```", runbook, re.S)
    assert example, "docs/ops/complimentary-access.md shows a synthetic example manifest in a json block"
    # As written, the example is refused: its salt is a placeholder, so no manifest runs with a published salt.
    with pytest.raises(ManifestError) as refused:
        load_manifest(example.group(1).encode())
    assert refused.value.problems == ["grant.salt: does not match its format"]
    manifest, digest = load_manifest(json.dumps({**json.loads(example.group(1)), "salt": SALT}).encode())
    assert manifest.action == "grant" and len(manifest.accounts) >= 1 and len(digest) == 64
    assert "@" not in example.group(1), "the example carries fingerprints, never an address"
    # Synthetic, which the manifest gate below relies on when it allows this one file: each fingerprint is a reserved
    # .invalid address's, never a person's.
    assert [account.email_sha256 for account in manifest.accounts] == [
        email_fingerprint(f"tester-{n}@example.invalid") for n in ("one", "two")]


# Where nothing of the repository's own is kept: dependencies, build output, test reports and caches.
_NOT_THE_REPOSITORY = {".git", "node_modules", ".venv", "venv", ".next", "test-results", "playwright-report",
                       "__pycache__", ".pytest_cache", ".ruff_cache"}


# The operator's raw address list, by any name that says so in a plain-text form: addresses.txt, email_addresses.csv,
# beta-addresses (no suffix), and an editor's or a copy's leftovers of one (addresses.txt~, .addresses.txt.swp).
_ADDRESS_LIST_SUFFIXES = {"", ".txt", ".csv", ".tsv", ".lst", ".list"}
_BACKUP_SUFFIXES = ("~", ".bak", ".orig", ".old", ".tmp", ".swp", ".save")
# One address alone on its line, as the list holds them; a line of prose that mentions one is not.
_ADDRESS_LINE = re.compile(r"[^\s@<>\"',;:()]+@[^\s@<>\"',;:()]+\.[A-Za-z]{2,}")
# The key that names an address's fingerprint, however a draft spells it: email_sha256, emailSha256, EMAIL-SHA256,
# "email sha256".
_FINGERPRINT_KEY = re.compile(rb"(?i)email[\s_-]*sha[\s_-]*256")
# A SHA-256 in hex, in either case, that is not part of a longer run of hex digits.
_SHA256_HEX = re.compile(rb"(?<![0-9A-Fa-f])[0-9A-Fa-f]{64}(?![0-9A-Fa-f])")
# The runbook example's two fingerprints, of reserved .invalid addresses
# (test_the_runbooks_example_manifest_runs_once_its_salt_is_drawn holds the example to them): no person's.
_SYNTHETIC_FINGERPRINTS = frozenset(email_fingerprint(f"tester-{n}@example.invalid").encode() for n in ("one", "two"))


def _tree(root: Path):
    for folder, subfolders, files in os.walk(root):
        # A folder with its own .git (an agent's worktree under .claude/worktrees/, a nested checkout) is another tree:
        # its copy of the runbook is not this repository's.
        subfolders[:] = [name for name in subfolders
                         if name not in _NOT_THE_REPOSITORY and not (Path(folder) / name / ".git").exists()]
        for name in files:
            yield Path(folder) / name


def _files_with_fingerprints(root: Path) -> list[str]:
    """Each file under ``root`` that names an address fingerprint's key and holds a SHA-256 in hex other than the
    runbook example's two synthetic ones. A manifest the command runs, a draft it refuses (an extra key, 21 accounts, a
    trailing comma, a key spelled another way, the accounts under another name) and a roster with an ``email_sha256``
    column all hold what a list of candidate addresses matches, whatever their form: the reader looks at the bytes, so
    no format, fence or quoting is named. A file that never names the key, or that disguises the value (encoded, split
    in pieces), is not looked for: the gate stops a manifest saved or pasted by mistake, not one hidden. It reports
    paths, never a value."""
    found = []
    for path in _tree(root):
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        # The key ends in "256", and a plain search for it spares most files the case-blind one.
        if b"256" in raw and _FINGERPRINT_KEY.search(raw) and any(
                value not in _SYNTHETIC_FINGERPRINTS for value in _SHA256_HEX.findall(raw)):
            found.append(path.relative_to(root).as_posix())
    return sorted(found)


def _without_backup_suffixes(name: str) -> str:
    while any(name.lower().endswith(suffix) and len(name) > len(suffix) for suffix in _BACKUP_SUFFIXES):
        name = next(name[: -len(suffix)] for suffix in _BACKUP_SUFFIXES if name.lower().endswith(suffix))
    return name


def _is_address_list(path: Path) -> bool:
    """A file named as the list (or a backup of one), or, whatever its name, a small text file whose every non-blank
    line is one address, a byte-order mark and CRLF line ends allowed."""
    name = _without_backup_suffixes(path.name)
    if "addresses" in name.lower() and Path(name).suffix.lower() in _ADDRESS_LIST_SUFFIXES:
        return True
    try:
        raw = path.read_bytes()
    except OSError:
        return False
    if len(raw) > 65_536 or b"@" not in raw or b"\0" in raw:
        return False
    # A byte-order mark is no whitespace, so the first line keeps it and still reads as an address.
    lines = [line.strip() for line in raw.decode("utf-8", "replace").splitlines()]
    lines = [line for line in lines if line]
    return bool(lines) and all(_ADDRESS_LINE.fullmatch(line) for line in lines)


def _address_lists(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in _tree(root) if _is_address_list(path))


def test_the_gates_read_every_form_a_manifest_or_an_address_list_is_saved_in_and_skip_what_is_not_this_tree(tmp_path):
    runbook = (REPO / "docs" / "ops" / "complimentary-access.md").read_text()
    example = re.search(r"```json\n(.*?)```", runbook, re.S).group(1)
    # The example with a person's fingerprints in place of its synthetic ones: what a real manifest holds.
    manifest = example
    for n, address in (("one", "someone@example.com"), ("two", "another@example.com")):
        manifest = manifest.replace(email_fingerprint(f"tester-{n}@example.invalid"), email_fingerprint(address))
    assert manifest != example
    fields = json.loads(manifest)
    entries = fields["accounts"]
    fingerprint = entries[0]["email_sha256"]

    def draft(**changes) -> str:
        return json.dumps({**fields, **changes}, indent=2)

    for rel, text in {
        # A manifest the command would run, saved or pasted in any form, the example's own place included.
        "ops/saved.json": manifest, "docs/pasted.md": runbook.replace(example, manifest),
        "docs/ops/complimentary-access.md": runbook.replace(example, manifest),
        "docs/two.md": f"{runbook}\nWave 2:\n\n```json\n{manifest}```\n",
        "docs/bare-fence.md": f"Notes\n```\n{manifest}```\n", "docs/text-fence.md": f"```text\n{manifest}```\n",
        "docs/tilde.md": f"~~~json\n{manifest}~~~\n", "docs/crlf.md": f"```json\n{manifest}```\n".replace("\n", "\r\n"),
        "docs/inline-fence.md": f"Paste it between ``` fences:\n\n```json\n{manifest}```\n",
        "ops/grant.sh": f"cat <<'JSON' | python scripts/complimentary_access.py check --manifest /dev/stdin\n{manifest}JSON\n",
        "tasks/notes.py": f"MANIFEST = \'\'\'{manifest}\'\'\'\n",
        "tasks/notes.yml": "manifest: |\n" + "".join(f"  {line}\n" for line in manifest.splitlines()),
        "tasks/manifest.txt": manifest, "tasks/manifest.json.bak": manifest,
        "tasks/wrapped.json": json.dumps({"wave": {"manifest": fields}}),
        "tasks/escaped.json": json.dumps({"pasted": manifest}),
        # Drafts the command refuses, which hold the same fingerprints.
        "backend/scripts/draft-names.json": draft(accounts=[{**entry, "name": "Someone"} for entry in entries]),
        "backend/scripts/draft-21.json": draft(accounts=[{**entries[0], "account_id": n} for n in range(1, 22)]),
        "backend/scripts/draft-comma.json": draft()[:-2] + ",\n}\n",
        "backend/scripts/draft-upper.json": manifest.replace('"email_sha256"', '"EMAIL_SHA256"'),
        "backend/scripts/draft-camel.json": manifest.replace('"email_sha256"', '"emailSha256"'),
        "backend/scripts/draft-elsewhere.json": json.dumps(
            {**{key: value for key, value in fields.items() if key != "accounts"}, "testers": entries}),
        "tasks/draft.json5": f"{{\n  // wave 1\n  accounts: [{{account_id: 1001, email_sha256: '{fingerprint}'}}],\n}}\n",
        "tasks/roster.csv": f"account_id,email_sha256\n1001,{fingerprint.upper()}\n",
        # Not a fingerprint, or not this tree's: the synthetic example anywhere, the key with no value, a longer run of
        # hex digits, a SHA-256 under no fingerprint key, a dependency and another checkout.
        "docs/example-copy.md": runbook, "docs/other.md": "email_sha256 is a key, and {not json} here",
        "docs/longer.md": f"email_sha256 is not {fingerprint}{fingerprint}",
        "tasks/receipt.json": json.dumps({"source_sha256": fingerprint}),
        "frontend/node_modules/pkg/fixture.json": manifest,
        ".claude/worktrees/agent/docs/runbook.md": runbook.replace(example, manifest),
        ".claude/worktrees/agent/.git": "gitdir: elsewhere\n",
        # The address list, by the names that say so, an editor's backups of one, and by its content alone.
        "tasks/addresses.txt": "someone@example.invalid\n", "tasks/beta/Addresses-wave2.txt": "x\n",
        "tasks/email_addresses.csv": "x\n", "tasks/tester-addresses": "x\n", "tasks/ip_addresses.py": "x = 1\n",
        "backend/addresses.txt~": "x\n", "backend/addresses.txt.bak": "x\n", "backend/.addresses.txt.swp": "x\n",
        "tasks/addresses.txt.orig.bak": "x\n", "tasks/testers.txt": "\ufeffSomeone@Example.com\r\n\r\nanother@example.com\r\n",
        "tasks/list": "someone@example.com\n",
        "tasks/contacts.md": "Write to someone@example.com\nor to another@example.com.\n",
        "backend/app/public_email_addresses.json": json.dumps({"support": "support@example.com"}),
        "frontend/node_modules/pkg/emails.txt": "someone@example.com\n",
        ".claude/worktrees/agent/addresses.txt": "x\n",
    }.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(text.encode())
    assert _files_with_fingerprints(tmp_path) == sorted([
        "ops/saved.json", "docs/pasted.md", "docs/ops/complimentary-access.md", "docs/two.md", "docs/bare-fence.md",
        "docs/text-fence.md", "docs/tilde.md", "docs/crlf.md", "docs/inline-fence.md", "ops/grant.sh", "tasks/notes.py",
        "tasks/notes.yml", "tasks/manifest.txt", "tasks/manifest.json.bak", "tasks/wrapped.json", "tasks/escaped.json",
        "backend/scripts/draft-names.json", "backend/scripts/draft-21.json", "backend/scripts/draft-comma.json",
        "backend/scripts/draft-upper.json", "backend/scripts/draft-camel.json", "backend/scripts/draft-elsewhere.json",
        "tasks/draft.json5", "tasks/roster.csv"])
    assert _address_lists(tmp_path) == sorted([
        "tasks/addresses.txt", "tasks/beta/Addresses-wave2.txt", "tasks/email_addresses.csv", "tasks/tester-addresses",
        "backend/addresses.txt~", "backend/addresses.txt.bak", "backend/.addresses.txt.swp",
        "tasks/addresses.txt.orig.bak", "tasks/testers.txt", "tasks/list"])


def test_no_file_in_the_repository_is_a_manifest_but_the_runbooks_synthetic_example():
    """A real manifest names accounts by id and by an unsalted SHA-256 of their address, which anyone holding a list of
    candidate addresses can match, and the repository is public: the runbook's rule never to commit one is held here
    (rule 12), for a draft the command would refuse as much as for one it runs, since both hold the fingerprints. The
    only ones allowed are the runbook example's two, and
    test_the_runbooks_example_manifest_runs_once_its_salt_is_drawn holds them to reserved .invalid addresses, so a real
    manifest in the example's place, or anywhere else, fails. Pasting one into an issue or a pull request stays a
    review check."""
    found = _files_with_fingerprints(REPO)
    assert found == [], (
        "a file in the repository holds an address fingerprint; keep real manifests and their drafts in the founder's "
        f"private store (docs/ops/complimentary-access.md, \"The manifest\"): {found}"
    )


def test_no_file_in_the_repository_is_the_operators_address_list():
    """The raw addresses the founder fingerprints stay in the private store with the manifest (the runbook's
    procedure): a file named as that list fails here, wherever it is saved. The ignore rules at the root and under
    backend/ are a backstop for its usual places, not the gate."""
    assert _address_lists(REPO) == [], "keep the address list in the founder's private store, outside the repository"


# --------------------------------------------------------------------------- dry run and refusals


def test_a_dry_run_counts_outcomes_and_names_each_refusal_by_place_without_writing(world):
    operator = world.operator()
    eligible = world.tester()
    unverified = world.tester(email_verified=False)
    uninvited = world.tester(is_beta=False, invite=False)
    manifest, digest = world.manifest("grant", [eligible, unverified, uninvited], operator_id=operator.id)

    report = service.dry_run(world.db, manifest, digest, today=TODAY).as_dict()

    assert report == {
        "action": "grant", "mode": "dry-run", "manifest_sha256": digest, "cohort": COHORT,
        "review_on": REVIEW_ON.isoformat(), "entries": 3, "cap": MAX_ACTIVE_GRANTS, "active_grants_before": 0,
        "active_grants_after": 1, "outcomes": {"eligible": 1, "refused": 2},
        "refusals": [{"entry": 2, "codes": ["email_not_verified"]},
                     {"entry": 3, "codes": ["not_invited_beta", "no_redeemed_invite"]}],
        "stopped": None,
    }
    for account in (eligible, unverified, uninvited):
        state = _committed(account.id)
        assert (state.is_pro, state.grant, state.actions) == (False, None, [])
    published = json.dumps(report)
    assert "account_id" not in published and REASON not in published and SALT not in published
    for account in (eligible, unverified, uninvited):
        assert account.email not in published and email_fingerprint(account.email) not in published


def _subscription(user_id: int, status: str) -> Subscription:
    return Subscription(user_id=user_id, plan="pro" if status in ("active", "trialing") else "free", status=status,
                        trial_end=None)  # no end: a trialing row then grants Pro whatever the real clock says


@pytest.mark.parametrize("fields, expected", [
    ({"is_active": False}, ["account_inactive"]),
    ({"email_verified": False}, ["email_not_verified"]),
    ({"is_beta": False}, ["not_invited_beta"]),
    ({"invite": False}, ["no_redeemed_invite"]),
    ({"agreement": False}, ["no_signup_agreement"]),
    ({"stripe_customer_id": "cus_pb02_test"}, ["stripe_identity"]),
    ({"stripe_subscription_id": "sub_pb02_test"}, ["stripe_identity"]),
    ({"is_pro": True}, ["pro_from_another_source"]),
])
def test_a_grant_refuses_an_account_this_path_cannot_own(world, fields, expected):
    operator = world.operator()
    tester = world.tester(**fields)
    manifest = world.manifest("grant", [tester], operator_id=operator.id)

    assert service.dry_run(world.db, *manifest, today=TODAY).refusals == [{"entry": 1, "codes": expected}]
    report = _apply(world, manifest)
    assert (report.outcomes, report.refusals) == ({"refused": 1}, [{"entry": 1, "codes": expected}])
    state = _committed(tester.id)
    assert (state.is_pro, state.grant, state.actions) == (fields.get("is_pro", False), None, [])


@pytest.mark.parametrize("status", ["active", "trialing", "canceled", "past_due", "incomplete"])
def test_a_grant_refuses_an_account_with_a_subscription_row_of_any_status(world, status):
    operator = world.operator()
    tester = world.tester(is_pro=status in ("active", "trialing"))
    world.db.add(_subscription(tester.id, status))
    world.db.commit()
    manifest = world.manifest("grant", [tester], operator_id=operator.id)

    report = _apply(world, manifest)

    expected = ["subscription_exists"] + (["pro_from_another_source"] if status in ("active", "trialing") else [])
    assert report.refusals == [{"entry": 1, "codes": expected}]
    state = _committed(tester.id)
    assert (state.grant, state.actions) == (None, [])


def test_an_id_that_names_no_account_or_another_persons_account_is_refused(world):
    operator = world.operator()
    tester, stranger = world.tester(), world.tester()
    # A mistyped id: the entry names the stranger's id with the tester's address.
    entries = [{"account_id": max(world.ids) + 10_000, "email_sha256": email_fingerprint("missing@example.com")},
               {"account_id": stranger.id, "email_sha256": email_fingerprint(tester.email)}]
    manifest = load_manifest(_raw("grant", entries, operator_id=operator.id))

    report = _apply(world, manifest)

    assert report.refusals == [{"entry": 1, "codes": ["account_not_found"]},
                               {"entry": 2, "codes": ["identity_mismatch"]}]
    assert (_committed(stranger.id).is_pro, _committed(stranger.id).grant) == (False, None)


def test_an_address_change_since_the_manifest_was_written_is_refused(world):
    operator = world.operator()
    tester = world.tester()
    manifest = world.manifest("grant", [tester], operator_id=operator.id)
    tester.email = f"changed-{uuid.uuid4().hex}@example.com"
    world.db.commit()

    report = _apply(world, manifest)

    assert report.refusals == [{"entry": 1, "codes": ["identity_mismatch"]}]
    assert _committed(tester.id).grant is None


# --------------------------------------------------------------------------- apply


def test_an_apply_grants_pro_and_commits_its_ledger_row_and_audit_row_together(world):
    operator = world.operator()
    tester = world.tester(copilot_free_taste_used=2)
    manifest = world.manifest("grant", [tester], operator_id=operator.id)
    digest = manifest[1]

    report = _apply(world, manifest, runner="ops-run:42")

    assert (report.mode, report.outcomes, report.refusals, report.active_grants_after) == ("apply", {"granted": 1}, [], 1)
    state = _committed(tester.id)
    assert (state.is_pro, state.plan) == (True, Plan.PRO)
    assert state.entitlements.monthly_summary_limit is None and state.entitlements.can_export
    assert state.entitlements.copilot and state.entitlements.can_analyze_trends
    assert state.entitlements.realtime_alerts and state.entitlements.eightk_coverage
    grant = state.grant
    assert (grant.cohort, grant.reason, grant.review_on, grant.granted_by, grant.manifest_sha256, grant.revoked_at) == (
        COHORT, REASON, REVIEW_ON, f"account:{operator.id}", digest, None)
    with SessionLocal() as fresh:
        audit = fresh.query(AuditLog).filter(AuditLog.entity_id == str(tester.id)).one()
        assert (audit.action, audit.user_id, audit.user_email, audit.entity_type, audit.status) == (
            service.AUDIT_GRANTED, str(operator.id), None, "user", "success")
        assert audit.details == {
            "cohort": COHORT, "reason": REASON, "review_on": REVIEW_ON.isoformat(), "manifest_sha256": digest,
            "operator": f"account:{operator.id}", "runner": "ops-run:42", "invite_cohort": INVITE_COHORT,
            "before": {"is_pro": False, "plan": "free", "grant": "none"},
            "after": {"is_pro": True, "plan": "pro", "grant": "active"},
        }
    assert state.copilot_free_taste_used == 2


def test_a_grant_whose_audit_row_fails_writes_nothing(world, monkeypatch):
    operator = world.operator()
    tester = world.tester()
    manifest = world.manifest("grant", [tester], operator_id=operator.id)

    def failing_audit(*_args, **_kwargs):
        raise RuntimeError("audit insert failed")

    monkeypatch.setattr(service, "create_audit_log", failing_audit)
    with pytest.raises(RuntimeError):
        _apply(world, manifest)

    state = _committed(tester.id)
    assert (state.is_pro, state.grant, state.actions) == (False, None, [])


@pytest.mark.parametrize("step", ["grant", "move", "revoke"])
def test_a_unit_whose_real_audit_insert_fails_raises_and_changes_nothing(world, monkeypatch, step):
    """Each audit row is mandatory (``create_audit_log(mandatory=True)``): it joins the unit's transaction and its
    failure raises. Without the flag, the real function would roll the unit back itself and swallow the error, and the
    report would say granted, moved or revoked for a change that never committed. The insert fails here inside the
    real function, so the flag is what is tested."""
    operator = world.operator()
    tester = world.tester()
    if step != "grant":
        _apply(world, world.manifest("grant", [tester], operator_id=operator.id))
    before = _committed(tester.id)
    manifest = {
        "grant": lambda: world.manifest("grant", [tester], operator_id=operator.id),
        "move": lambda: world.manifest("grant", [tester], operator_id=operator.id, review_on=REVIEW_ON + timedelta(7)),
        "revoke": lambda: world.manifest("revoke", [tester], operator_id=operator.id),
    }[step]()

    def unrecordable(**_fields):
        raise RuntimeError("audit insert failed")

    monkeypatch.setattr(audit_service, "AuditLog", unrecordable)
    with pytest.raises(RuntimeError, match="audit insert failed"):
        _apply(world, manifest)

    after = _committed(tester.id)
    assert (after.is_pro, after.grant, after.actions) == (before.is_pro, before.grant, before.actions)


def test_a_rerun_changes_nothing_it_already_changed(world):
    operator = world.operator()
    tester = world.tester()
    manifest = world.manifest("grant", [tester], operator_id=operator.id)
    _apply(world, manifest)
    first = _committed(tester.id)

    again = _apply(world, manifest)

    assert (again.outcomes, again.refusals) == ({"already_granted": 1}, [])
    state = _committed(tester.id)
    assert state.grant.granted_at == first.grant.granted_at and state.actions == [service.AUDIT_GRANTED]


def test_a_grant_manifest_with_another_review_date_moves_the_date_and_nothing_else(world):
    """The founder extends or shortens the beta by applying the cohort's grant manifest with a new review date: each
    active grant moves to it, with an audit row of its own, while its Pro, its provenance and the cap stay as they are.
    Before, the apply reported the new date and kept the old one, so the readout counted the grant due on the old."""
    operator = world.operator()
    tester, unnamed = world.tester(), world.tester()
    _apply(world, world.manifest("grant", [tester, unnamed], operator_id=operator.id))
    first = _committed(tester.id)
    later = REVIEW_ON + timedelta(days=60)
    # The move covers the accounts the manifest names: the cohort's other grant keeps its date.
    moved = world.manifest("grant", [tester], operator_id=operator.id, reason="Beta extended", review_on=later)

    planned = service.dry_run(world.db, *moved, today=TODAY)
    assert (planned.outcomes, planned.active_grants_after) == ({"review_date_moves": 1}, 2)
    assert _committed(tester.id).grant.review_on == REVIEW_ON  # the dry run writes nothing

    applied = _apply(world, moved)
    assert (applied.outcomes, applied.refusals, applied.active_grants_after) == ({"review_date_moved": 1}, [], 2)
    state = _committed(tester.id)
    assert state.grant.review_on == later
    assert (state.is_pro, state.plan, state.grant.granted_at, state.grant.reason, state.grant.manifest_sha256) == (
        True, Plan.PRO, first.grant.granted_at, REASON, first.grant.manifest_sha256)
    assert state.actions == [service.AUDIT_GRANTED, service.AUDIT_REVIEW_MOVED]
    row = world.db.query(AuditLog).filter(
        AuditLog.entity_id == str(tester.id), AuditLog.action == service.AUDIT_REVIEW_MOVED).one()
    assert (row.details["before"]["review_on"], row.details["after"]["review_on"], row.details["reason"]) == (
        REVIEW_ON.isoformat(), later.isoformat(), "Beta extended")
    assert _committed(unnamed.id).grant.review_on == REVIEW_ON
    assert service.readout(world.db, today=REVIEW_ON)["due_for_review"] == 1  # the unnamed grant alone
    assert service.readout(world.db, today=later)["due_for_review"] == 2

    again = _apply(world, moved)  # the same manifest again changes nothing
    assert again.outcomes == {"already_granted": 1} and _committed(tester.id).actions == state.actions


def test_an_apply_runs_only_the_manifest_its_dry_run_reported(world):
    operator = world.operator()
    tester = world.tester()
    manifest, digest = world.manifest("grant", [tester], operator_id=operator.id)

    with pytest.raises(service.DigestMismatchError):
        service.apply(world.db, manifest, digest, confirm_digest="0" * 64, today=TODAY)
    assert _committed(tester.id).grant is None


@pytest.mark.parametrize("operator_fields", [{"is_admin": False}, {"is_active": False}, {"email_verified": False}, None])
def test_an_operator_who_is_not_an_active_verified_admin_runs_nothing(world, operator_fields):
    tester = world.tester()
    operator_id = world.operator(**operator_fields).id if operator_fields else max(world.ids) + 10_000
    manifest, digest = world.manifest("grant", [tester], operator_id=operator_id)

    with pytest.raises(service.OperatorNotAuthorizedError):
        service.dry_run(world.db, manifest, digest, today=TODAY)
    with pytest.raises(service.OperatorNotAuthorizedError):
        service.apply(world.db, manifest, digest, confirm_digest=digest, today=TODAY)
    assert _committed(tester.id).grant is None


def test_a_review_date_out_of_its_window_runs_nothing(world):
    operator = world.operator()
    tester = world.tester()
    manifest = world.manifest("grant", [tester], operator_id=operator.id, review_on=TODAY)

    with pytest.raises(ManifestError):
        _apply(world, manifest)
    assert _committed(tester.id).grant is None


def test_a_runner_label_is_short_plain_text(world):
    operator = world.operator()
    tester = world.tester()
    manifest = world.manifest("grant", [tester], operator_id=operator.id)

    with pytest.raises(ManifestError):
        _apply(world, manifest, runner="ops run with spaces and an address@example.com")
    assert _committed(tester.id).grant is None


def test_the_cap_holds_at_twenty_active_grants_across_cohorts(world):
    operator = world.operator()
    testers = [world.tester() for _ in range(MAX_ACTIVE_GRANTS)]
    assert _apply(world, world.manifest("grant", testers[:12], operator_id=operator.id)).outcomes == {"granted": 12}
    second = world.manifest("grant", testers[12:], operator_id=operator.id, cohort="private-beta-2026-11-w2")
    assert _apply(world, second).outcomes == {"granted": 8}
    extra = world.tester()
    over = world.manifest("grant", [extra], operator_id=operator.id)

    plan = service.dry_run(world.db, *over, today=TODAY)
    report = _apply(world, over)

    assert (plan.stopped, plan.active_grants_before, plan.active_grants_after) == ("cap_exceeded", 20, 20)
    assert (report.mode, report.stopped, report.outcomes) == ("apply", "cap_exceeded", {"eligible": 1})
    assert _committed(extra.id).grant is None
    # Revoking one makes room for one.
    assert _apply(world, world.manifest("revoke", testers[:1], operator_id=operator.id)).outcomes == {"revoked": 1}
    assert _apply(world, over).outcomes == {"granted": 1}


def test_a_unit_refuses_what_changed_since_its_dry_run(world, monkeypatch):
    operator = world.operator()
    subscribed, customer, untouched = world.tester(), world.tester(), world.tester()
    manifest = world.manifest("grant", [subscribed, customer, untouched], operator_id=operator.id)
    real_dry_run = service.dry_run

    def dry_run_then_another_writer(db, *args, **kwargs):
        plan = real_dry_run(db, *args, **kwargs)
        assert plan.outcomes == {"eligible": 3}
        with SessionLocal() as other:  # between the dry run and the units, as a webhook or checkout would
            other.add(Subscription(user_id=subscribed.id, plan="free", status="incomplete"))
            other.get(User, customer.id).stripe_customer_id = "cus_raced_pb02"
            other.commit()
        return plan

    monkeypatch.setattr(service, "dry_run", dry_run_then_another_writer)
    report = _apply(world, manifest)

    assert report.outcomes == {"granted": 1, "refused": 2}
    assert report.refusals == [{"entry": 1, "codes": ["subscription_exists"]},
                               {"entry": 2, "codes": ["stripe_identity"]}]
    assert [_committed(a.id).is_pro for a in (subscribed, customer, untouched)] == [False, False, True]


def test_a_unit_refuses_a_grant_when_a_racing_apply_filled_the_cap(world, monkeypatch):
    operator = world.operator()
    testers = [world.tester() for _ in range(MAX_ACTIVE_GRANTS - 1)]
    _apply(world, world.manifest("grant", testers, operator_id=operator.id))
    racer, late = world.tester(), world.tester()
    late_manifest = world.manifest("grant", [late], operator_id=operator.id)
    racer_manifest = world.manifest("grant", [racer], operator_id=operator.id)
    real_dry_run = service.dry_run

    def dry_run_then_a_racing_apply(db, manifest, digest, **kwargs):
        plan = real_dry_run(db, manifest, digest, **kwargs)
        if digest == late_manifest[1]:
            with SessionLocal() as other:
                racer_plan = real_dry_run(other, *racer_manifest, today=TODAY)
                assert racer_plan.outcomes == {"eligible": 1}
                other_operator = service._operator_label(other, operator.id)
                assert service._grant_one(other, racer_manifest[0], racer_manifest[1], racer_manifest[0].accounts[0],
                                          operator=other_operator, runner=None) == ("granted", [])
        return plan

    monkeypatch.setattr(service, "dry_run", dry_run_then_a_racing_apply)
    report = _apply(world, late_manifest)

    assert (report.outcomes, report.refusals) == ({"refused": 1}, [{"entry": 1, "codes": ["cap_reached"]}])
    assert (_committed(racer.id).is_pro, _committed(late.id).is_pro) == (True, False)


# --------------------------------------------------------------------------- revoke


def test_a_revoke_removes_the_grants_pro_and_restores_free(world):
    operator = world.operator()
    tester = world.tester(copilot_free_taste_used=1)
    _apply(world, world.manifest("grant", [tester], operator_id=operator.id))
    revoke = world.manifest("revoke", [tester], operator_id=operator.id, reason="Private beta ended")

    assert service.dry_run(world.db, *revoke, today=TODAY).outcomes == {"revocable": 1}
    report = _apply(world, revoke)

    assert (report.outcomes, report.active_grants_after) == ({"revoked": 1}, 0)
    state = _committed(tester.id)
    assert (state.is_pro, state.plan) == (False, Plan.FREE)
    assert state.entitlements.monthly_summary_limit == 5 and not state.entitlements.can_export
    assert not state.entitlements.copilot and not state.entitlements.can_analyze_trends
    assert state.copilot_free_taste_used == 1  # Pro's questions never spent the Free allowance
    assert (state.grant.revoked_by, state.grant.revoke_reason) == (f"account:{operator.id}", "Private beta ended")
    assert state.grant.revoked_at is not None
    assert state.actions == [service.AUDIT_GRANTED, service.AUDIT_REVOKED]
    with SessionLocal() as fresh:
        audit = fresh.query(AuditLog).filter(AuditLog.entity_id == str(tester.id),
                                             AuditLog.action == service.AUDIT_REVOKED).one()
        assert (audit.details["before"], audit.details["after"], audit.details["billing_owned"]) == (
            {"is_pro": True, "plan": "pro", "grant": "active"},
            {"is_pro": False, "plan": "free", "grant": "revoked"}, False)


def test_a_revoke_leaves_billing_state_and_its_pro_to_the_webhook(world):
    operator = world.operator()
    tester = world.tester()
    _apply(world, world.manifest("grant", [tester], operator_id=operator.id))
    # Later the account subscribed: the webhook bound a paid subscription and keeps the mirror.
    world.db.add(Subscription(user_id=tester.id, plan="pro", status="active", stripe_customer_id="cus_paid_pb02"))
    world.db.get(User, tester.id).stripe_customer_id = "cus_paid_pb02"
    world.db.commit()

    report = _apply(world, world.manifest("revoke", [tester], operator_id=operator.id, reason="Private beta ended"))

    assert report.outcomes == {"revoked_billing_untouched": 1}
    state = _committed(tester.id)
    assert (state.is_pro, state.plan, state.grant.revoked_at is not None) == (True, Plan.PRO, True)
    with SessionLocal() as fresh:
        row = fresh.query(Subscription).filter_by(user_id=tester.id).one()
        assert (row.status, row.plan, row.stripe_customer_id) == ("active", "pro", "cus_paid_pb02")
        audit = fresh.query(AuditLog).filter(AuditLog.entity_id == str(tester.id),
                                             AuditLog.action == service.AUDIT_REVOKED).one()
        assert audit.details["billing_owned"] is True and audit.details["after"]["is_pro"] is True


def test_a_revoke_clears_the_grants_pro_beside_a_stripe_customer_a_checkout_stored_after_it(world):
    # A checkout reads the account's entitlement before it claims a Stripe customer, so one that read the account just
    # before its grant committed can store a customer after it. With no Subscription row no webhook writes the flag,
    # so the Pro is still the grant's, and the revoke clears it.
    operator = world.operator()
    tester = world.tester()
    _apply(world, world.manifest("grant", [tester], operator_id=operator.id))
    world.db.get(User, tester.id).stripe_customer_id = "cus_claimed_after_grant"
    world.db.commit()

    report = _apply(world, world.manifest("revoke", [tester], operator_id=operator.id, reason="Private beta ended"))

    assert report.outcomes == {"revoked": 1}
    state = _committed(tester.id)
    assert (state.is_pro, state.plan) == (False, Plan.FREE)
    assert service.readout(world.db, today=TODAY)["revoked_still_pro"] == 0


def test_a_revoke_rerun_or_an_ungranted_account_changes_nothing(world):
    operator = world.operator()
    granted, ungranted = world.tester(), world.tester()
    _apply(world, world.manifest("grant", [granted], operator_id=operator.id))
    revoke = world.manifest("revoke", [granted, ungranted], operator_id=operator.id, reason="Private beta ended")

    assert _apply(world, revoke).outcomes == {"revoked": 1, "not_granted": 1}
    assert _apply(world, revoke).outcomes == {"not_granted": 2}
    assert _committed(granted.id).actions == [service.AUDIT_GRANTED, service.AUDIT_REVOKED]
    assert _committed(ungranted.id).actions == []


def test_a_revoke_refuses_a_grant_of_another_cohort(world):
    operator = world.operator()
    tester = world.tester()
    _apply(world, world.manifest("grant", [tester], operator_id=operator.id))

    report = _apply(world, world.manifest("revoke", [tester], operator_id=operator.id, cohort="private-beta-2026-12"))

    assert report.refusals == [{"entry": 1, "codes": ["granted_in_another_cohort"]}]
    assert _committed(tester.id).is_pro is True


def test_a_grant_refuses_an_account_another_cohort_holds(world):
    operator = world.operator()
    tester = world.tester()
    _apply(world, world.manifest("grant", [tester], operator_id=operator.id))

    report = _apply(world, world.manifest("grant", [tester], operator_id=operator.id, cohort="private-beta-2026-12"))

    assert report.refusals == [{"entry": 1, "codes": ["granted_in_another_cohort"]}]
    assert _committed(tester.id).grant.cohort == COHORT


def test_a_grant_whose_pro_another_writer_cleared_is_reported_not_restored(world):
    operator = world.operator()
    tester = world.tester()
    manifest = world.manifest("grant", [tester], operator_id=operator.id)
    _apply(world, manifest)
    world.db.get(User, tester.id).is_pro = False
    world.db.commit()

    report = _apply(world, manifest)

    assert report.refusals == [{"entry": 1, "codes": ["grant_without_pro"]}]
    assert _committed(tester.id).is_pro is False


def test_a_regrant_after_a_revoke_reopens_the_accounts_row(world):
    operator = world.operator()
    tester = world.tester()
    _apply(world, world.manifest("grant", [tester], operator_id=operator.id))
    _apply(world, world.manifest("revoke", [tester], operator_id=operator.id, reason="Private beta paused"))
    regrant = world.manifest("grant", [tester], operator_id=operator.id, reason="Private beta resumed")

    assert _apply(world, regrant).outcomes == {"granted": 1}

    state = _committed(tester.id)
    assert (state.is_pro, state.grant.reason, state.grant.manifest_sha256) == (True, "Private beta resumed", regrant[1])
    assert (state.grant.revoked_at, state.grant.revoked_by, state.grant.revoke_reason) == (None, None, None)
    assert state.actions == [service.AUDIT_GRANTED, service.AUDIT_REVOKED, service.AUDIT_GRANTED]
    with SessionLocal() as fresh:
        assert fresh.query(ComplimentaryAccessGrant).filter_by(user_id=tester.id).count() == 1


class _Untouchable:
    def __init__(self, name):
        self._name = name

    def __getattr__(self, attribute):
        raise AssertionError(f"stripe.{self._name}.{attribute} was reached")


def test_grant_and_revoke_never_reach_stripe(world, monkeypatch):
    for name in ("Customer", "Subscription", "checkout", "billing_portal", "Invoice", "PaymentIntent", "Refund"):
        monkeypatch.setattr(stripe, name, _Untouchable(name))
    operator = world.operator()
    tester = world.tester()

    assert _apply(world, world.manifest("grant", [tester], operator_id=operator.id)).outcomes == {"granted": 1}
    assert _apply(world, world.manifest("revoke", [tester], operator_id=operator.id)).outcomes == {"revoked": 1}


# --------------------------------------------------------------------------- locks


def test_units_take_the_grants_lock_then_the_accounts_row_lock_and_a_dry_run_takes_neither(world, monkeypatch):
    operator = world.operator()
    first, second = world.tester(), world.tester()
    grant = world.manifest("grant", [first, second], operator_id=operator.id)
    calls = []
    real_for_update = Query.with_for_update
    real_lock = service._lock_grants

    def spy_for_update(query, *args, **kwargs):
        calls.append(("row", query.column_descriptions[0]["entity"], kwargs.get("key_share")))
        return real_for_update(query, *args, **kwargs)

    def spy_lock(db):
        calls.append(("grants",))
        real_lock(db)

    monkeypatch.setattr(Query, "with_for_update", spy_for_update)
    monkeypatch.setattr(service, "_lock_grants", spy_lock)

    service.dry_run(world.db, *grant, today=TODAY)
    assert calls == []
    _apply(world, grant)
    unit = [("grants",), ("row", User, True)]
    assert calls == unit * 2
    calls.clear()
    _apply(world, world.manifest("revoke", [first, second], operator_id=operator.id))
    assert calls == unit * 2


def test_the_grants_lock_is_a_transaction_scoped_advisory_lock_on_postgresql():
    executed = []

    def session_on(dialect):
        return SimpleNamespace(get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name=dialect)),
                               execute=executed.append)

    service._lock_grants(session_on("sqlite"))
    assert executed == []
    service._lock_grants(session_on("postgresql"))
    sql = str(executed[0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert sql == f"SELECT pg_advisory_xact_lock({service.GRANT_LOCK_KEY}) AS pg_advisory_xact_lock_1"
    assert service.GRANT_LOCK_KEY == int.from_bytes(b"COMPGRNT", "big")


def test_every_advisory_lock_in_the_backend_takes_a_named_key_of_its_own():
    """Two advisory locks with one key serialize each other: a grant would queue behind a filing insert or a whole
    recovery pass. Every advisory-lock call under app/ passes a module-level ``*_LOCK_KEY`` constant, and the constants
    are pairwise distinct, so a lock added later is checked against the grants' without this test changing."""
    app = REPO / "backend" / "app"
    keys, calls = {}, []
    for path in sorted(app.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        module = ".".join(path.relative_to(REPO / "backend").with_suffix("").parts)
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id.endswith("LOCK_KEY") for target in node.targets):
                for target in node.targets:
                    keys[f"{module}.{target.id}"] = getattr(importlib.import_module(module), target.id)
        calls += [(path.relative_to(REPO).as_posix(), ast.unparse(node)) for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and "advisory" in node.func.attr and not (
                      len(node.args) == 1 and isinstance(node.args[0], ast.Name) and node.args[0].id.endswith("LOCK_KEY"))]
    assert calls == [], f"an advisory lock whose key is not a module-level *_LOCK_KEY constant: {calls}"
    assert keys["app.services.complimentary_access_service.GRANT_LOCK_KEY"] == service.GRANT_LOCK_KEY
    assert len(keys) >= 5, keys
    shared = {key: [name for name, value in keys.items() if value == key] for key in set(keys.values())}
    assert all(len(names) == 1 for names in shared.values()), {k: v for k, v in shared.items() if len(v) > 1}


# --------------------------------------------------------------------------- deletion, readout, Billing


def test_deleting_a_granted_account_removes_its_grant_and_keeps_its_audit_rows(world):
    operator = world.operator()
    tester = world.tester()
    _apply(world, world.manifest("grant", [tester], operator_id=operator.id))

    delete_account(world.db, tester.id, third_party_results={"stripe": "none"})

    assert _committed(tester.id) is None
    with SessionLocal() as fresh:
        assert fresh.query(ComplimentaryAccessGrant).filter_by(user_id=tester.id).count() == 0
        rows = fresh.query(AuditLog).filter(AuditLog.entity_id == str(tester.id)).order_by(AuditLog.id)
        assert [row.action for row in rows] == [service.AUDIT_GRANTED, "user_deleted"]


def test_the_readout_counts_active_grants_reviews_due_and_drift(world):
    operator = world.operator()
    testers = [world.tester() for _ in range(3)]
    _apply(world, world.manifest("grant", testers[:2], operator_id=operator.id))
    _apply(world, world.manifest("grant", testers[2:], operator_id=operator.id, cohort="private-beta-2026-11-w2",
                                 review_on=REVIEW_ON + timedelta(days=30)))
    _apply(world, world.manifest("revoke", testers[1:2], operator_id=operator.id))
    # Drift of each kind: a row now decides the first account's plan, something set the revoked account's flag again,
    # and a Stripe customer now names the third.
    world.db.add(Subscription(user_id=testers[0].id, plan="free", status="canceled"))
    world.db.get(User, testers[1].id).is_pro = True
    world.db.get(User, testers[2].id).stripe_customer_id = "cus_readout_drift"
    world.db.commit()

    before_review = service.readout(world.db, today=TODAY)
    on_review = service.readout(world.db, today=REVIEW_ON)

    assert before_review == {
        "cap": MAX_ACTIVE_GRANTS, "active_grants": 2, "revoked_grants": 1,
        "active_by_cohort": {COHORT: 1, "private-beta-2026-11-w2": 1}, "due_for_review": 0,
        "active_without_complimentary_pro": 1, "active_with_stripe_identity": 1, "revoked_still_pro": 1,
    }
    assert on_review["due_for_review"] == 1


def test_billing_names_complimentary_pro_only_while_the_grant_decides_the_plan(world):
    operator = world.operator()
    granted, canceled, paid, other_pro, revoked = (world.tester() for _ in range(5))
    _apply(world, world.manifest("grant", [granted, canceled, paid, revoked], operator_id=operator.id))
    _apply(world, world.manifest("revoke", [revoked], operator_id=operator.id))
    world.db.add_all([Subscription(user_id=canceled.id, plan="free", status="canceled"),
                      Subscription(user_id=paid.id, plan="pro", status="active")])
    world.db.get(User, other_pro.id).is_pro = True
    world.db.commit()

    with SessionLocal() as fresh:
        served = {name: service.serves_complimentary_pro(fresh, fresh.get(User, account.id)) for name, account in [
            ("granted", granted), ("canceled", canceled), ("paid", paid), ("other_pro", other_pro),
            ("revoked", revoked)]}

    assert served == {"granted": True, "canceled": False, "paid": False, "other_pro": False, "revoked": False}
