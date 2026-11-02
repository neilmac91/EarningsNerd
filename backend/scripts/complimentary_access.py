#!/usr/bin/env python3
"""
Grant or revoke complimentary Pro for invited private-beta accounts (PB-02), from a private manifest.

The procedure, the manifest's format and the end-date rules are in ``docs/ops/complimentary-access.md``; the checks and
writes are ``app/services/complimentary_access_service.py``. A grant sets ``User.is_pro`` for an invited, verified
account no billing state owns, records it in ``earningsnerd_complimentary_access_grants`` and writes an audit row,
in one commit per account; a revoke undoes only that grant. Nothing here calls Stripe or sends mail.

Every report is JSON on stdout and safe for a public log: counts, and refusals by their place in the manifest, never
an account id, an address or the manifest's reason. The manifest names real accounts: keep it out of the repository,
out of workflow inputs and out of logs.

Usage:
    # Offline, on the operator's machine (no settings, no database):
    #   one fingerprint per address read from stdin, in order
    python scripts/complimentary_access.py fingerprint < addresses.txt
    #   validate a manifest and print its digest
    python scripts/complimentary_access.py check --manifest manifest.json

    # Against the database (DATABASE_URL and the app's settings):
    python scripts/complimentary_access.py dry-run --manifest manifest.json
    python scripts/complimentary_access.py apply --manifest manifest.json --confirm-digest <sha256> --runner local
    python scripts/complimentary_access.py readout

Exit status: 0 when the command ran (a report may still list refusals), 1 when it refused to run (a manifest fault,
an operator who is not an active verified admin, a digest that is not the manifest's, a grant past the cap), 2 when
an account's unit failed unexpectedly (units committed before it stay; a rerun skips them).

Gate: tests/unit/test_complimentary_access_script.py (the report and every log line carry no planted id or address)
and tests/unit/test_complimentary_access_service.py. Retire: with the Ops operations that run it, once the beta's
last grant is revoked.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.complimentary_access_manifest import (  # noqa: E402  (imports no settings)
    ManifestError,
    check_review_window,
    email_fingerprint,
    load_manifest,
)

REFUSED = 1
FAILED = 2


def _print(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _refuse(error: str, **fields) -> int:
    _print({"refused": error, **fields})
    return REFUSED


def _read_manifest(path: str):
    raw = Path(path).read_bytes()
    return load_manifest(raw)


def _today():
    from app.utils.datetimes import utcnow

    return utcnow().date()


def cmd_fingerprint(_args: argparse.Namespace) -> int:
    for line in sys.stdin:
        if line.strip():
            print(email_fingerprint(line))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    try:
        manifest, digest = _read_manifest(args.manifest)
        check_review_window(manifest, _today())
    except ManifestError as exc:
        return _refuse("manifest", problems=exc.problems)
    _print({
        "action": manifest.action,
        "cohort": manifest.cohort,
        "entries": len(manifest.accounts),
        "review_on": manifest.review_on.isoformat() if manifest.action == "grant" else None,
        "manifest_sha256": digest,
    })
    return 0


def _database_command(args: argparse.Namespace) -> int:
    # Imported here so fingerprint and check run with no settings and no database.
    from app.database import SessionLocal
    from app.services import complimentary_access_service as service

    # The report is the only output: an application log record can carry an exception's text or an address, and
    # the Ops log is public (financial_revenue_preview.py does the same).
    logging.disable(logging.CRITICAL)
    db = SessionLocal()
    try:
        if args.command == "readout":
            _print(service.readout(db, today=_today()))
            return 0
        try:
            manifest, digest = _read_manifest(args.manifest)
            if args.command == "dry-run":
                report = service.dry_run(db, manifest, digest, today=_today())
            else:
                report = service.apply(
                    db, manifest, digest, confirm_digest=args.confirm_digest, today=_today(), runner=args.runner,
                )
        except ManifestError as exc:
            return _refuse("manifest", problems=exc.problems)
        except service.OperatorNotAuthorizedError:
            return _refuse("operator_not_authorized")
        except service.DigestMismatchError:
            return _refuse("digest_mismatch", manifest_sha256=digest)
        _print(report.as_dict())
        return REFUSED if report.stopped else 0
    except Exception as exc:  # an account's unit failed: report the class alone, never a message with values
        _print({"failed": type(exc).__name__})
        return FAILED
    finally:
        db.close()
        logging.disable(logging.NOTSET)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Complimentary Pro for invited private-beta accounts (PB-02).")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("fingerprint", help="Print each stdin address's fingerprint (offline).")
    check = commands.add_parser("check", help="Validate a manifest and print its digest (offline).")
    check.add_argument("--manifest", required=True, help="Path to the private manifest (JSON).")
    dry = commands.add_parser("dry-run", help="Report what an apply would do; writes nothing.")
    dry.add_argument("--manifest", required=True, help="Path to the private manifest (JSON).")
    apply = commands.add_parser("apply", help="Apply the manifest whose digest the dry run reported.")
    apply.add_argument("--manifest", required=True, help="Path to the private manifest (JSON).")
    apply.add_argument("--confirm-digest", required=True, help="The manifest_sha256 the dry run reported.")
    apply.add_argument("--runner", default=None, help="Provenance for the audit rows, e.g. ops-run:<id> or local.")
    commands.add_parser("readout", help="Counts of active grants, reviews due and drift; writes nothing.")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "fingerprint":
        return cmd_fingerprint(args)
    if args.command == "check":
        return cmd_check(args)
    return _database_command(args)


if __name__ == "__main__":
    sys.exit(main())
