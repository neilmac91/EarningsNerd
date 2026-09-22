"""Offline E7 preflight and blinded packet builder; never invokes a provider or judge.

The accepted accession manifest is immutable. Human materials and source bytes live outside
the repository. This module checks their declared identity and integrity before a paid run or
review packet can be considered ready. Attestations remain human claims, not machine proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import secrets
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse


APPROVED_MANIFEST_SHA256 = "68242a2c1c57da8d445bc4e1aca104017cffaffe8bbebf131228cde8ea94ba66"
COMPARATOR_HOLDOUT_IDS = frozenset({"H01", "H03", "H05", "H07", "H09", "H14", "H18", "H23", "H26", "H29"})
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ACCESSION = re.compile(r"\d{10}-\d{2}-\d{6}\Z")
_FRESHNESS = timedelta(hours=24)
_ARTIFACTS = ("canonical", "rendered", "export")
_PRICING_FIELDS = {"model", "base_url", "official_source", "verified_at", "valid_until",
                   "uncached_input_per_million", "max_output_per_million"}
_CANONICAL_COLUMNS = frozenset({
    "id", "filing_id", "business_overview", "financial_highlights", "risk_factors",
    "management_discussion", "key_changes", "raw_summary", "schema_version",
    "prompt_version", "created_at", "updated_at",
})
_CANONICAL_PRODUCT_FIELDS = (
    "business_overview", "financial_highlights", "risk_factors",
    "management_discussion", "key_changes", "raw_summary",
)
# These keys name execution artifacts, regardless of where they occur. Generic words
# such as model, provider, arm and draw can also be legitimate filing content; removing
# them recursively would alter the canonical output presented to a reviewer.
_EXECUTION_KEY_TEXT = re.compile(
    r'"(?:config_sha256|source_commit|content_stamp|dependency_lock_sha256|base_url|prompt_version)"\s*:'
)


def _positive_price(value: Any) -> bool:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return False
    return not isinstance(value, bool) and amount.is_finite() and amount > 0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name}: expected JSON object")
    return value


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None


def _safe_file(root: Path, relative: Any) -> Path:
    """Resolve a relative, regular file without traversal or symlinks."""
    if not isinstance(relative, str) or not relative:
        raise ValueError("missing relative file path")
    part = PurePosixPath(relative)
    if part.is_absolute() or any(piece in {".", "..", ""} for piece in part.parts):
        raise ValueError("unsafe relative file path")
    root = root.resolve(strict=True)
    path = root.joinpath(*part.parts)
    cursor = root
    for piece in part.parts:
        cursor = cursor / piece
        if cursor.is_symlink():
            raise ValueError("symlink in file path")
    if not path.is_file() or not path.resolve(strict=True).is_relative_to(root):
        raise ValueError("file missing or outside evidence root")
    return path


def _evidence(root: Path, record: Any) -> tuple[Path, dict[str, Any] | None]:
    if not isinstance(record, dict) or not _SHA256.fullmatch(str(record.get("sha256", ""))):
        raise ValueError("evidence record needs path and SHA256")
    path = _safe_file(root, record.get("path"))
    if _sha256(path) != record["sha256"]:
        raise ValueError("evidence SHA256 mismatch")
    return path, _json(path) if path.suffix == ".json" else None


def review_evidence_inventory(prerequisites_path: Path, prereq: dict[str, Any]) -> dict[str, Any]:
    """Freeze review commitments and evidence bytes, excluding renewable execution receipts."""
    if prereq.get("schema_version") == 2 and prereq.get("review_protocol") == "ai_assisted":
        from evals.acceptance_ai_protocol import ai_review_evidence_inventory

        return ai_review_evidence_inventory(prerequisites_path, prereq)
    prerequisites_path = Path(prerequisites_path).resolve(strict=True)

    def reference(record: Any) -> dict[str, Any]:
        path, _ = _evidence(prerequisites_path.parent, record)
        return {"record": record, "resolved_path": str(path.resolve(strict=True)),
                "bytes_sha256": _sha256(path)}

    briefs = prereq["reference_briefs"]
    return {
        "prerequisites_path": str(prerequisites_path),
        "reviewers": prereq["reviewers"], "adjudicator": prereq["adjudicator"],
        "reference_briefs": sorted(
            ({"accession_number": item["accession_number"], **reference(item)} for item in briefs),
            key=lambda item: item["accession_number"],
        ),
        "exposure_attestation": reference(prereq["exposure_attestation"]),
    }


def verify_review_evidence_binding(programme_root: Path, prerequisites_path: Path | None = None) -> None:
    """Reject changed review evidence before collection or packet construction."""
    ledger = Path(programme_root) / "budget.sqlite3"
    if ledger.is_symlink() or not ledger.is_file():
        raise ValueError("programme review evidence binding ledger missing")
    try:
        with sqlite3.connect(ledger.as_uri() + "?mode=ro", uri=True) as db:
            row = db.execute("SELECT value FROM binding WHERE id=1").fetchone()
        binding = json.loads(row[0]) if row else None
        frozen = binding["review_evidence"]
        bound_path = Path(frozen["prerequisites_path"])
        if prerequisites_path is not None and Path(prerequisites_path).resolve(strict=True) != bound_path:
            raise ValueError("review evidence prerequisites path differs from programme binding")
        current = review_evidence_inventory(bound_path, _json(bound_path))
    except (sqlite3.Error, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("programme review evidence binding is unavailable") from error
    if current != frozen:
        raise ValueError("review evidence differs from programme binding")


def _validate_observation_receipt(
    kind: str, record: dict[str, Any], evidence: dict[str, Any] | None, observed: datetime,
) -> datetime:
    """Bind inline balance/quota claims to the retained typed observation receipt.

    Hash/content agreement proves what was retained, not the observer's authority
    or that a provider authenticated this locally supplied receipt.
    """
    receipt_observed = _utc(evidence.get("observed_at")) if evidence else None
    if (evidence is None or type(evidence.get("schema_version")) is not int or
            evidence["schema_version"] != 1 or evidence.get("kind") != kind or
            receipt_observed is None or receipt_observed != observed):
        raise ValueError("observation receipt schema, kind or timestamp differs")
    if kind == "balance":
        amount = evidence.get("available_usd")
        if (evidence.get("provider") != "deepseek" or evidence.get("currency") != "USD" or
                not isinstance(amount, (int, float)) or not _positive_price(amount) or
                not _positive_price(record.get("available_usd")) or
                Decimal(str(amount)) != Decimal(str(record["available_usd"]))):
            raise ValueError("balance receipt identity or available USD differs")
    elif (evidence.get("quota_available") is not True or
          evidence.get("contract_version") != record.get("contract_version") or
          evidence.get("model") != record.get("model")):
        raise ValueError("Fable receipt quota, contract or model differs")
    return receipt_observed


def _issue(issues: list[dict[str, str]], code: str, detail: str) -> None:
    issues.append({"code": code, "detail": detail})


def inspect_readiness(
    manifest_path: Path,
    archive_root: Path,
    prerequisites_path: Path,
    *,
    expected_manifest_sha: str = APPROVED_MANIFEST_SHA256,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a machine-readable preflight; missing evidence is a finding, not an exception.

    ``archive_root`` is the work directory *containing* ``e7-sources``. Evidence paths in
    prerequisites are relative to the prerequisites JSON's parent. Paid readiness requires
    fresh price, balance and Fable receipts; packet readiness keeps those three historical
    receipts but does not expire them after generation.
    """
    from evals.acceptance_worker import archive_binding_hold

    issues: list[dict[str, str]] = []
    source_hold = archive_binding_hold()
    if source_hold:
        _issue(issues, "structured_source_binding_unavailable", source_hold)
    paid_only: list[dict[str, str]] = []
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    manifest_path = Path(manifest_path)
    prerequisites_path = Path(prerequisites_path)
    if not manifest_path.is_file():
        return {"schema_version": 1, "issues": [{"code": "missing_manifest", "detail": str(manifest_path)}],
                "ready_for_paid_execution": False, "ready_for_packets": False}
    manifest_sha = _sha256(manifest_path)
    if manifest_sha != expected_manifest_sha:
        _issue(issues, "manifest_sha_mismatch", "accepted manifest bytes changed")
    try:
        manifest = _json(manifest_path)
    except (ValueError, OSError) as exc:
        _issue(issues, "invalid_manifest", type(exc).__name__)
        manifest = {}
    filings = manifest.get("filings")
    if not isinstance(filings, list):
        filings = []
    accessions: list[str] = []
    ids: list[str] = []
    packet_count = 0
    source_roles: dict[str, set[str]] = {}
    source_hashes: dict[str, dict[str, str]] = {}
    for filing in filings:
        if not isinstance(filing, dict):
            _issue(issues, "invalid_filing", "manifest filing is not an object")
            continue
        accession = filing.get("accession_number")
        holdout_id = filing.get("holdout_id")
        if not isinstance(accession, str) or not _ACCESSION.fullmatch(accession):
            _issue(issues, "invalid_accession", str(holdout_id))
            continue
        accessions.append(accession)
        ids.append(str(holdout_id))
        if filing.get("repeats") != [1, 2, 3]:
            _issue(issues, "invalid_draws", accession)
        packets = filing.get("source_packets")
        if not isinstance(packets, list):
            packets = []
        packet_count += len(packets)
        roles = {p.get("role") for p in packets if isinstance(p, dict)}
        source_roles[accession] = {r for r in roles if isinstance(r, str)}
        source_hashes[accession] = {p["role"]: p["sha256"] for p in packets
                                    if isinstance(p, dict) and isinstance(p.get("role"), str)
                                    and isinstance(p.get("sha256"), str)}
        if not {"primary", "index", "complete_submission"}.issubset(roles):
            _issue(issues, "missing_source_role", accession)
    if len(filings) != 30 or len(set(accessions)) != 30 or set(ids) != {f"H{i:02d}" for i in range(1, 31)}:
        _issue(issues, "manifest_identities", "expected 30 unique approved accession slots")
    if packet_count != 92 or manifest.get("required_candidate_outputs") != 90:
        _issue(issues, "manifest_counts", "expected 92 source packets and 90 candidate outputs")
    audit = manifest.get("exclusion_audit") or {}
    if audit.get("candidate_accession_matches") != {} or audit.get("candidate_structured_issuer_matches_in_eval_or_review_paths") != {}:
        _issue(issues, "exclusion_audit", "retained exclusion audit has candidate matches")

    verified_sources = 0
    archive_root = Path(archive_root)
    if not archive_root.is_dir() or archive_root.is_symlink():
        _issue(issues, "missing_source_archive", "source archive work directory unavailable")
    else:
        for filing in filings:
            if not isinstance(filing, dict):
                continue
            for packet in filing.get("source_packets", []):
                try:
                    path = _safe_file(archive_root, packet["path"])
                    if _sha256(path) != packet["sha256"] or path.stat().st_size != packet["bytes"]:
                        raise ValueError("source hash or byte size mismatch")
                    verified_sources += 1
                except (KeyError, OSError, TypeError, ValueError) as exc:
                    _issue(issues, "source_packet_invalid", f"{filing.get('accession_number')}: {type(exc).__name__}")

    prereq: dict[str, Any] = {}
    if prerequisites_path.is_file():
        try:
            prereq = _json(prerequisites_path)
        except (ValueError, OSError) as exc:
            _issue(issues, "invalid_prerequisites", type(exc).__name__)
    else:
        _issue(issues, "missing_prerequisites", "human and execution evidence file unavailable")
    base = prerequisites_path.parent
    version = prereq.get("schema_version")
    ai_mode = type(version) is int and version == 2 and prereq.get("review_protocol") == "ai_assisted"
    if (type(version) is not int or version not in {1, 2} or
            (prereq.get("schema_version") == 2 and not ai_mode) or
            prereq.get("approved_manifest_sha256") != expected_manifest_sha):
        _issue(issues, "prerequisite_manifest_binding", "preflight must bind approved manifest SHA")

    brief_frozen: dict[str, datetime] = {}
    exposure_status = None
    evidence_limitations: list[str] = []
    if ai_mode:
        from evals.acceptance_ai_protocol import validate_ai_prerequisites

        ai_issues, brief_frozen, exposure_status, evidence_limitations = validate_ai_prerequisites(
            prereq, base, accessions, source_hashes, now,
        )
        issues.extend(ai_issues)
    else:
        reviewers = prereq.get("reviewers")
        if not isinstance(reviewers, list):
            reviewers = []
        adjudicator = prereq.get("adjudicator")
        people = reviewers + ([adjudicator] if isinstance(adjudicator, dict) else [])
        ids_people = [p.get("id") for p in people if isinstance(p, dict)]
        names = [p.get("name") for p in people if isinstance(p, dict)]
        if (len(reviewers) != 2 or len(people) != 3 or
                any(not isinstance(v, str) or not v.strip() for v in ids_people + names) or
                len(set(ids_people)) != 3 or len(set(names)) != 3):
            _issue(issues, "human_roles", "two distinct named reviewers and one adjudicator required")
        for person in people:
            if (not isinstance(person, dict) or not str(person.get("competence", "")).strip() or
                    not isinstance(person.get("committed_hours"), (int, float)) or
                    isinstance(person.get("committed_hours"), bool) or person["committed_hours"] <= 0 or
                    _utc(person.get("commitment_date")) is None or
                    _utc(person.get("commitment_date")) > now):
                _issue(issues, "human_commitment", "each person needs competence, hours and dated commitment")
                break

        briefs = prereq.get("reference_briefs")
        if not isinstance(briefs, list):
            briefs = []
        if len(briefs) != 30 or {b.get("accession_number") for b in briefs if isinstance(b, dict)} != set(accessions):
            _issue(issues, "reference_brief_coverage", "one frozen brief per approved accession required")
        brief_frozen: dict[str, datetime] = {}
        for item in briefs:
            accession = item.get("accession_number") if isinstance(item, dict) else None
            try:
                _, brief = _evidence(base, item)
                if brief is None or brief.get("accession_number") != accession:
                    raise ValueError("brief accession mismatch")
                authors = brief.get("reviewer_ids")
                if (set(authors or []) != set(ids_people[:2]) or len(authors or []) != 2 or
                        brief.get("adjudicator_id") != (ids_people[2] if len(ids_people) == 3 else None) or
                        brief.get("independent_source_review_attested") is not True):
                    raise ValueError("independent authorship/adjudication missing")
                frozen = _utc(brief.get("frozen_at"))
                if frozen is None or frozen > now:
                    raise ValueError("brief freeze timestamp invalid")
                material = brief.get("material_issues")
                if not isinstance(material, list) or not material:
                    raise ValueError("brief needs material issues")
                for issue in material:
                    if (not isinstance(issue, dict) or issue.get("source_role") not in source_roles.get(accession, set()) or
                            any((not isinstance(issue.get(key), str) or not issue[key].strip()) for key in
                                ("issue", "source_locator", "expected_numbers_basis", "importance", "disclosure_limits"))):
                        raise ValueError("brief issue lacks source or assessment fields")
                brief_frozen[accession] = frozen
            except (TypeError, KeyError, OSError, ValueError) as exc:
                _issue(issues, "reference_brief_invalid", f"{accession}: {type(exc).__name__}")

        try:
            _, exposure = _evidence(base, prereq.get("exposure_attestation"))
            if (exposure is None or not str(exposure.get("custodian_name", "")).strip() or
                    _utc(exposure.get("signed_at")) is None or _utc(exposure.get("signed_at")) > now or
                    set(exposure.get("checked_accessions", [])) != set(accessions) or
                    len(exposure.get("checked_accessions", [])) != 30 or
                    exposure.get("untracked_sources_checked") is not True or
                    exposure.get("unseen_confirmed") is not True or
                    exposure.get("exposed_accessions") != [] or
                    not str(exposure.get("external_artifact_inventory", "")).strip()):
                raise ValueError("exposure attestation incomplete")
        except (TypeError, OSError, ValueError) as exc:
            _issue(issues, "exposure_attestation_invalid", type(exc).__name__)

    config_hashes: dict[str, str] = {}
    config_models: dict[str, str] = {}
    config_bases: dict[str, str] = {}
    for arm in ("candidate", "comparator"):
        try:
            record = prereq.get(f"{arm}_config")
            _, config = _evidence(base, record)
            base_url = urlparse(str(config.get("base_url", ""))) if config else urlparse("")
            if (config is None or not re.fullmatch(r"[0-9a-f]{40}", str(config.get("source_commit", ""))) or
                    not all(str(config.get(k, "")).strip() for k in ("content_stamp", "provider", "model", "base_url")) or
                    str(config.get("provider", "")).casefold() != "deepseek" or
                    not str(config.get("model", "")).startswith("deepseek-") or
                    base_url.scheme != "https" or base_url.hostname != "api.deepseek.com" or
                    base_url.username or base_url.password or base_url.query or base_url.fragment or
                    base_url.path.rstrip("/") != "/v1" or
                    not isinstance(config.get("effective_flags"), dict) or not config["effective_flags"] or
                    not isinstance(config.get("effective_settings"), dict) or not config["effective_settings"] or
                    not _SHA256.fullmatch(str(config.get("dependency_lock_sha256", ""))) or
                    _utc(config.get("frozen_at")) is None or _utc(config.get("frozen_at")) > now):
                raise ValueError("effective configuration incomplete")
            config_hashes[arm] = record["sha256"]
            config_models[arm] = config["model"]
            config_bases[arm] = config["base_url"]
        except (OSError, TypeError, ValueError) as exc:
            _issue(issues, "config_invalid", f"{arm}: {type(exc).__name__}")

    for kind in ("pricing", "balance", "fable"):
        record = prereq.get(kind)
        try:
            _, evidence = _evidence(base, record)
            observed = _utc(record.get("observed_at"))
            if observed is None or observed > now:
                raise ValueError("observation time invalid")
            price_url = urlparse(str(record.get("official_url", "")))
            if kind == "pricing" and (price_url.scheme != "https" or
                                      price_url.hostname not in {"deepseek.com", "api-docs.deepseek.com"}):
                raise ValueError("official price source missing")
            if kind == "pricing":
                verified = _utc(evidence.get("verified_at")) if evidence else None
                expires = _utc(evidence.get("valid_until")) if evidence else None
                if (evidence is None or set(evidence) != _PRICING_FIELDS or
                        set(config_models.values()) != {evidence.get("model")} or
                        len(config_models) != 2 or set(config_bases.values()) != {evidence.get("base_url")} or
                        len(config_bases) != 2 or evidence.get("official_source") != record.get("official_url") or
                        verified is None or verified > observed or expires is None or expires <= verified or
                        any(not _positive_price(evidence.get(key)) for key in
                            ("uncached_input_per_million", "max_output_per_million"))):
                    raise ValueError("pricing artifact does not match frozen model/base and official tariff")
                if now - verified > _FRESHNESS:
                    _issue(paid_only, "stale_pricing_verification", "official tariff verification older than 24 hours")
                if expires <= now:
                    _issue(paid_only, "expired_pricing", "pricing artifact validity ended")
            if kind == "balance" and (not isinstance(record.get("available_usd"), (int, float)) or
                                      isinstance(record.get("available_usd"), bool) or record["available_usd"] <= 0):
                raise ValueError("balance observation missing")
            if kind == "fable" and (record.get("quota_available") is not True or
                                    record.get("contract_version") != "2" or
                                    record.get("model") != "cli:claude-fable-5-1"):
                raise ValueError("Fable quota/model/contract observation missing")
            if kind in {"balance", "fable"}:
                observed = _validate_observation_receipt(kind, record, evidence, observed)
            if now - observed > _FRESHNESS:
                _issue(paid_only, f"stale_{kind}", "observation older than 24 hours")
        except (OSError, TypeError, ValueError) as exc:
            _issue(issues, f"{kind}_invalid", type(exc).__name__)
    for kind, flag in (("development_smoke", "completed"), ("budget_control", "verified")):
        try:
            record = prereq.get(kind)
            _evidence(base, record)
            if record.get(flag) is not True:
                raise ValueError(f"{kind} not complete")
            if kind == "development_smoke" and (not _ACCESSION.fullmatch(str(record.get("accession_number", ""))) or
                                                record["accession_number"] in accessions):
                raise ValueError("development smoke must use a non-holdout accession")
            if kind == "budget_control":
                worst_case = record.get("full_run_worst_case_usd")
                if (not re.fullmatch(r"[0-9a-f]{40}", str(record.get("reviewed_commit", ""))) or
                        not isinstance(worst_case, (int, float)) or isinstance(worst_case, bool) or worst_case < 0):
                    raise ValueError("budget control needs reviewed commit and full-run estimate")
                if worst_case > 10 and (not str(record.get("incomplete_stop_risk_accepted_by", "")).strip() or
                                        _utc(record.get("incomplete_stop_risk_accepted_at")) is None or
                                        _utc(record.get("incomplete_stop_risk_accepted_at")) > now):
                    raise ValueError("full-run estimate exceeds $10 without dated incomplete-stop risk acceptance")
        except (OSError, TypeError, ValueError) as exc:
            _issue(issues, f"{kind}_invalid", type(exc).__name__)

    return {
        "schema_version": 2 if ai_mode else 1,
        "review_protocol": "ai_assisted" if ai_mode else "human",
        "exposure_status": exposure_status,
        "evidence_limitations": evidence_limitations,
        "manifest_sha256": manifest_sha,
        "approved_accessions": len(set(accessions)),
        "source_packets_verified": verified_sources,
        "reference_briefs_verified": len(brief_frozen),
        "config_sha256": config_hashes,
        "issues": issues + paid_only,
        "ready_for_packets": not issues,
        "ready_for_paid_execution": not (issues or paid_only),
    }


def _check_output_records(
    manifest: dict[str, Any], records: list[Any], base: Path,
    config_hashes: dict[str, str], brief_frozen: dict[str, datetime],
) -> list[dict[str, Any]]:
    by_id = {f["holdout_id"]: f["accession_number"] for f in manifest["filings"]}
    expected = {(acc, "candidate", draw) for acc in by_id.values() for draw in (1, 2, 3)}
    expected |= {(by_id[hid], "comparator", draw) for hid in COMPARATOR_HOLDOUT_IDS for draw in (1, 2, 3)}
    identities: list[tuple[str, str, int]] = []
    checked: list[dict[str, Any]] = []
    used_artifacts: set[Path] = set()
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("output record must be an object")
        accession, arm, draw = row.get("accession_number"), row.get("arm"), row.get("draw")
        if (not isinstance(accession, str) or not isinstance(arm, str) or
                not isinstance(draw, int) or isinstance(draw, bool)):
            raise ValueError("output identity types invalid")
        identities.append((accession, arm, draw))
        if row.get("error") is not None or row.get("status") != "completed":
            raise ValueError("output error or incomplete status")
        created = _utc(row.get("created_at"))
        if created is None or created <= brief_frozen.get(accession, datetime.max.replace(tzinfo=timezone.utc)):
            raise ValueError("output predates frozen human brief")
        if row.get("config_sha256") != config_hashes.get(arm):
            raise ValueError("output config fingerprint mismatch")
        previews = row.get("preview_paths")
        hashes = row.get("artifact_sha256")
        if (not isinstance(previews, list) or not isinstance(hashes, dict) or
                row.get("preview_count") != len(previews) or row.get("previews_truncated") is not False or
                row.get("retry_preview_attempts_omitted") != 0):
            raise ValueError("preview evidence incomplete")
        paths: dict[str, Path] = {}
        for key in _ARTIFACTS:
            path = _safe_file(base, row.get(f"{key}_path"))
            if hashes.get(key) != _sha256(path):
                raise ValueError("output artifact SHA256 mismatch")
            if path in used_artifacts:
                raise ValueError("output artifact reused by another identity")
            used_artifacts.add(path)
            paths[key] = path
        for i, relative in enumerate(previews):
            path = _safe_file(base, relative)
            if hashes.get(f"preview_{i}") != _sha256(path):
                raise ValueError("preview SHA256 mismatch")
            if path in used_artifacts:
                raise ValueError("preview artifact reused by another identity")
            used_artifacts.add(path)
            paths[f"preview_{i}"] = path
        checked.append({"row": row, "paths": paths})
    if len(records) != 120 or len(set(identities)) != 120 or set(identities) != expected:
        raise ValueError("expected exact 90 candidate and 30 comparator output identities")
    return checked


def _reviewer_artifact(source: Path, key: str, row: dict[str, Any],
                       config: dict[str, Any], holdout_id: str) -> bytes:
    """Project known DB columns, then reject remaining execution identity markers.

    Narrative bytes are never rewritten. The known export generation-date metadata
    is omitted from the reviewer projection; any remaining execution marker stops it.
    """
    if key == "canonical":
        value = _json(source)
        if set(value) != _CANONICAL_COLUMNS or not isinstance(value["raw_summary"], dict):
            raise ValueError("canonical artifact differs from reviewed production Summary shape")
        # The complete original JSON remains in the custodian mapping. Omit only the
        # identified database/execution columns; never edit raw_summary or other product
        # fields, even when they happen to contain words such as 'model' or 'provider'.
        product = {name: value[name] for name in _CANONICAL_PRODUCT_FIELDS}
        data = json.dumps(product, ensure_ascii=False, indent=2).encode("utf-8")
    else:
        data = source.read_bytes()
    text = data.decode("utf-8")
    if key == "export":
        # This exact header comes from ExportService.generate_pdf_html. Retain the filing
        # dates and all substantive content; the original export remains custodian-side.
        text = re.sub(r"(Period End: [^<]+?) · Generated [A-Z][a-z]+ [0-9]{2}, [0-9]{4}(?=<br>Source: SEC EDGAR)",
                      r"\1", text, count=1)
        if re.search(r"Generated [A-Z][a-z]+ [0-9]{2}, [0-9]{4}", text):
            raise ValueError("unrecognized export generation-date metadata")
        data = text.encode("utf-8")
    markers = {str(row["config_sha256"]), str(config["content_stamp"]),
               str(config["source_commit"]), str(config["model"]), str(config["base_url"]),
               f"{holdout_id}-{row['arm']}-{row['draw']}"}
    if _EXECUTION_KEY_TEXT.search(text) or any(marker and marker in text for marker in markers):
        raise ValueError(f"reviewer artifact exposes execution identity: {key}")
    return data


def build_blinded_packets(
    manifest_path: Path, archive_root: Path, prerequisites_path: Path,
    outputs_path: Path, reviewer_root: Path, custodian_root: Path,
    *, expected_manifest_sha: str = APPROVED_MANIFEST_SHA256,
) -> dict[str, Any]:
    """Copy verified sources/outputs into two blind reviewer directories.

    The output JSON must be the complete durable collector index. Reconstruct it read-only
    before trusting its record or preview inventory. Neither destination may exist; execution
    evidence, mapping and random seed are custodian-only.
    """
    readiness = inspect_readiness(manifest_path, archive_root, prerequisites_path,
                                  expected_manifest_sha=expected_manifest_sha)
    if not readiness["ready_for_packets"]:
        raise ValueError("preflight incomplete: " + ",".join(i["code"] for i in readiness["issues"]))
    manifest = _json(Path(manifest_path))
    prereq = _json(Path(prerequisites_path))
    ai_mode = prereq.get("schema_version") == 2 and prereq.get("review_protocol") == "ai_assisted"
    brief_records = (prereq["ai_assisted"]["reconciled_references"] if ai_mode
                     else prereq["reference_briefs"])
    briefs = {b["accession_number"]: _json(_safe_file(Path(prerequisites_path).parent, b["path"]))
              for b in brief_records}
    brief_frozen = {acc: _utc(brief["frozen_at"]) for acc, brief in briefs.items()}
    output_obj = _json(Path(outputs_path))
    # Import lazily: the collector shares this module's frozen manifest/slot constants.
    from evals.acceptance_outputs import inspect_outputs

    output_parent = Path(outputs_path).parent
    ledger = _safe_file(output_parent, output_obj.get("programme_ledger_path"))
    if ledger.name != "budget.sqlite3":
        raise ValueError("collector programme ledger identity invalid")
    verify_review_evidence_binding(ledger.parent, prerequisites_path)
    collected = inspect_outputs(ledger.parent, output_parent,
                                expected_manifest_sha=expected_manifest_sha)
    if collected["complete"] is not True or output_obj.get("complete") is not True:
        raise ValueError("collector evidence is incomplete")
    if collected != output_obj:
        raise ValueError("outputs index differs from durable collector evidence")
    records = output_obj.get("records")
    if not isinstance(records, list):
        raise ValueError("outputs JSON needs records list")
    filings = {filing["accession_number"]: filing for filing in manifest["filings"]}
    for row in records:
        selection = _json(_safe_file(output_parent, row["collector_evidence"]["selection"]["path"]))
        if selection["filing"] != filings.get(row["accession_number"]):
            raise ValueError("collector selection differs from approved filing manifest")
    checked = _check_output_records(manifest, records, Path(outputs_path).parent,
                                    readiness["config_sha256"], brief_frozen)
    earliest_output = min(_utc(item["row"]["created_at"]) for item in checked)
    exposure_record = (prereq["ai_assisted"]["exposure_review"] if ai_mode
                       else prereq["exposure_attestation"])
    exposure = _json(_safe_file(Path(prerequisites_path).parent, exposure_record["path"]))
    exposure_time = exposure["observed_at"] if ai_mode else exposure["signed_at"]
    if _utc(exposure_time) >= earliest_output:
        raise ValueError("exposure review must predate every output")
    configs: dict[str, dict[str, Any]] = {}
    for arm in ("candidate", "comparator"):
        config = _json(_safe_file(Path(prerequisites_path).parent, prereq[f"{arm}_config"]["path"]))
        if _utc(config["frozen_at"]) >= earliest_output:
            raise ValueError("configuration freeze must predate every output")
        configs[arm] = config

    reviewer_root, custodian_root = Path(reviewer_root), Path(custodian_root)
    if (reviewer_root.exists() or custodian_root.exists() or reviewer_root.is_symlink() or
            custodian_root.is_symlink() or reviewer_root.resolve().is_relative_to(custodian_root.resolve()) or
            custodian_root.resolve().is_relative_to(reviewer_root.resolve())):
        raise ValueError("destinations must be new and separate")
    if reviewer_root.parent.is_symlink() or custodian_root.parent.is_symlink():
        raise ValueError("destination parent symlink")
    reviewer_root.parent.mkdir(parents=True, exist_ok=True)
    custodian_root.parent.mkdir(parents=True, exist_ok=True)
    seed = secrets.token_hex(32)
    rng = random.Random(int(seed, 16))
    by_accession = {f["accession_number"]: f for f in manifest["filings"]}
    mapping: dict[str, Any] = {"schema_version": 2 if ai_mode else 1,
                               "review_protocol": "ai_assisted" if ai_mode else "human",
                               "exposure_status": readiness["exposure_status"],
                               "evidence_limitations": readiness["evidence_limitations"],
                               "seed": seed, "manifest_sha256": readiness["manifest_sha256"],
                               "collector_index": {"path": str(Path(outputs_path).resolve()),
                                                   "sha256": _sha256(Path(outputs_path))},
                               "programme_ledger": {"path": str(ledger), "sha256": _sha256(ledger)},
                               ("packet_sets" if ai_mode else "reviewers"): {}}
    created_reviewer = False
    created_custodian = False
    try:
        reviewer_root.mkdir(mode=0o700)
        created_reviewer = True
        custodian_root.mkdir(mode=0o700)
        created_custodian = True
        for reviewer_index in (1, 2):
            reviewer_name = (f"ai-packet-{reviewer_index}" if ai_mode else
                             f"reviewer-{reviewer_index}")
            reviewer_dir = reviewer_root / reviewer_name
            reviewer_dir.mkdir(mode=0o700)
            case_ids = {acc: secrets.token_hex(12) for acc in by_accession}
            packet_ids = {id(item): secrets.token_hex(12) for item in checked}
            order = checked.copy()
            rng.shuffle(order)
            source_dir = reviewer_dir / "sources"
            source_dir.mkdir()
            for accession, filing in by_accession.items():
                case_dir = source_dir / case_ids[accession]
                case_dir.mkdir()
                sources = []
                for source in filing["source_packets"]:
                    original = _safe_file(Path(archive_root), source["path"])
                    extension = original.suffix.lower() or ".txt"
                    relative = f"sources/{case_ids[accession]}/{source['role']}{extension}"
                    shutil.copyfile(original, reviewer_dir / relative)
                    sources.append({"role": source["role"], "path": relative,
                                    "official_url": source["provenance"]["final_url"]})
                (case_dir / "identity.json").write_text(json.dumps({
                    "accession_number": accession, "ticker": filing["ticker"],
                    "filing_type": filing["filing_type"], "sources": sources,
                }, indent=2), encoding="utf-8")
                (case_dir / "reference-brief.json").write_text(json.dumps({
                    "accession_number": accession,
                    "evidence_kind": "ai_source_reconciliation" if ai_mode else "human_reference_brief",
                    "exposure_status": readiness["exposure_status"],
                    "evidence_limitations": readiness["evidence_limitations"],
                    "material_issues": briefs[accession]["material_issues"],
                }, indent=2), encoding="utf-8")
            index = []
            private_rows = []
            packets_dir = reviewer_dir / "packets"
            packets_dir.mkdir()
            for item in order:
                row = item["row"]
                packet_id = packet_ids[id(item)]
                packet_dir = packets_dir / packet_id
                packet_dir.mkdir()
                reviewer_artifacts = {}
                for key, source_path in item["paths"].items():
                    suffix = source_path.suffix or ".txt"
                    projected = packet_dir / f"{key}{suffix}"
                    projected.write_bytes(_reviewer_artifact(
                        source_path, key, row, configs[row["arm"]],
                        by_accession[row["accession_number"]]["holdout_id"]))
                    reviewer_artifacts[key] = {"path": str(projected.relative_to(reviewer_dir)),
                                               "sha256": _sha256(projected)}
                index.append({"packet_id": packet_id, "source_case_id": case_ids[row["accession_number"]],
                              "accession_number": row["accession_number"],
                              "source_identity": f"sources/{case_ids[row['accession_number']]}/identity.json",
                              "packet_dir": f"packets/{packet_id}"})
                private_rows.append({"packet_id": packet_id, "accession_number": row["accession_number"],
                                     "arm": row["arm"], "draw": row["draw"],
                                     "config_sha256": row["config_sha256"],
                                     "collector_evidence": row["collector_evidence"],
                                     "reviewer_artifacts": reviewer_artifacts,
                                     "raw_artifacts": {key: {"path": str(path), "sha256": _sha256(path)}
                                                       for key, path in item["paths"].items()}})
            (reviewer_dir / "index.json").write_text(json.dumps({"packets": index}, indent=2), encoding="utf-8")
            mapping["packet_sets" if ai_mode else "reviewers"][reviewer_name] = private_rows
        map_path = custodian_root / "mapping.json"
        map_path.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
        map_path.chmod(0o600)
    except BaseException:
        if created_reviewer:
            shutil.rmtree(reviewer_root)
        if created_custodian:
            shutil.rmtree(custodian_root)
        raise
    return {"review_protocol": "ai_assisted" if ai_mode else "human",
            "exposure_status": readiness["exposure_status"],
            "evidence_limitations": readiness["evidence_limitations"],
            ("packet_sets" if ai_mode else "reviewers"): 2,
            "packets_per_set" if ai_mode else "packets_per_reviewer": 120,
            "source_cases_per_set" if ai_mode else "source_cases_per_reviewer": 30,
            "mapping_path": str(map_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("archive_root", type=Path)
    parser.add_argument("prerequisites", type=Path)
    parser.add_argument("--outputs", type=Path)
    parser.add_argument("--reviewer-root", type=Path)
    parser.add_argument("--custodian-root", type=Path)
    args = parser.parse_args(argv)
    if args.outputs or args.reviewer_root or args.custodian_root:
        if not (args.outputs and args.reviewer_root and args.custodian_root):
            parser.error("packet mode needs --outputs, --reviewer-root and --custodian-root")
        result = build_blinded_packets(args.manifest, args.archive_root, args.prerequisites,
                                       args.outputs, args.reviewer_root, args.custodian_root)
    else:
        result = inspect_readiness(args.manifest, args.archive_root, args.prerequisites)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result.get("ready_for_paid_execution", True) else 2


if __name__ == "__main__":
    raise SystemExit(main())
