"""Fixed temporary Cloud SQL lifecycle; credentials never enter plans or receipts.

Cloud calls use documented SQL Admin v1beta4 fields. A create/delete is issued
once, then reconciled through exact ownership and operation identity. Expiry is
an admission rule, not a resource TTL: interrupted runs require supervised cleanup.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone

from ops.summary_delivery import spec

BASE = f"sql/v1beta4/projects/{spec.PROJECT}"
LIFECYCLE_SECONDS = 600
POLL_SECONDS = 5
PRODUCTION_NAME = "earningsnerd-db"


def _refuse(reason: str) -> None:
    raise spec.Refused(reason) from None


def _target(manifest: dict) -> str:
    spec.validate_scope(manifest)
    name = manifest.get("sql_instance", {}).get("name")
    if manifest.get("schema") != 2 or name != spec.instance_name(manifest["run_id"]):
        _refuse("sql_instance_scope")
    return name


def _labels(manifest: dict) -> dict:
    return {"purpose": spec.PURPOSE, "run-id": manifest["run_id"], "plan-nonce": manifest["nonce"]}


def _call(cloud, path: str, deadline: float, **kwargs):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        _refuse("sql_lifecycle_deadline")
    try:
        result = cloud.call("sqladmin", path, timeout=min(30, remaining), **kwargs)
    except Exception:
        _refuse("sql_cloud_operation_unverified")
    if time.monotonic() >= deadline:
        _refuse("sql_lifecycle_deadline")
    return result


def _pause(deadline: float) -> None:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        _refuse("sql_lifecycle_deadline")
    time.sleep(min(POLL_SECONDS, remaining))


def _owned(row: dict, manifest: dict) -> None:
    if (not isinstance(row, dict) or row.get("name") != _target(manifest)
            or row.get("project") != spec.PROJECT or row.get("region") != spec.REGION
            or row.get("settings", {}).get("userLabels") != _labels(manifest)):
        _refuse("sql_instance_ownership")


def _disabled(value) -> bool:
    # Protobuf JSON can omit false booleans; reject strings and integer lookalikes.
    return value is None or value is False


def _cleanup_policy(row: dict) -> None:
    settings = row.get("settings", {})
    if (row.get("replicaNames") or row.get("masterInstanceName")
            or not _disabled(settings.get("retainBackupsOnDelete"))
            or not _disabled(settings.get("finalBackupConfig", {}).get("enabled"))
            or not _disabled(settings.get("backupConfiguration", {}).get("enabled"))
            or not _disabled(settings.get("backupConfiguration", {}).get("pointInTimeRecoveryEnabled"))
            or settings.get("backupConfiguration", {}).get("backupTier") not in {None, "BACKUP_TIER_UNSPECIFIED", "STANDARD"}
            or not _disabled(settings.get("deletionProtectionEnabled"))):
        _refuse("sql_delete_retention_or_dependency_drift")


def _configuration(row: dict, manifest: dict) -> None:
    _owned(row, manifest)
    settings = row.get("settings", {})
    ip = settings.get("ipConfiguration", {})
    backups = settings.get("backupConfiguration", {})
    final = settings.get("finalBackupConfig", {})
    if (row.get("databaseVersion") != "POSTGRES_15" or row.get("state") != "RUNNABLE"
            or row.get("connectionName") != spec.connection_name(manifest)
            or row.get("instanceType") != "CLOUD_SQL_INSTANCE" or row.get("backendType") != "SECOND_GEN"
            or row.get("replicaNames") or row.get("masterInstanceName")
            or settings.get("tier") != "db-custom-1-3840" or settings.get("edition") != "ENTERPRISE"
            or settings.get("availabilityType") != "ZONAL" or settings.get("dataDiskSizeGb") != "10"
            or settings.get("dataDiskType") != "PD_SSD" or settings.get("connectorEnforcement") != "REQUIRED"
            or settings.get("activationPolicy") != "ALWAYS" or settings.get("databaseFlags")
            or not _disabled(settings.get("storageAutoResize"))
            or not _disabled(settings.get("deletionProtectionEnabled"))
            or not _disabled(settings.get("retainBackupsOnDelete"))
            or not _disabled(backups.get("enabled")) or not _disabled(backups.get("pointInTimeRecoveryEnabled"))
            or backups.get("backupTier") not in {None, "BACKUP_TIER_UNSPECIFIED", "STANDARD"}
            or not _disabled(backups.get("binaryLogEnabled")) or not _disabled(backups.get("replicationLogArchivingEnabled"))
            or not _disabled(final.get("enabled")) or ip.get("ipv4Enabled") is not True
            or ip.get("authorizedNetworks") or ip.get("privateNetwork") or ip.get("pscConfig", {}).get("pscEnabled")
            or ip.get("sslMode") != "ENCRYPTED_ONLY" or not _disabled(ip.get("requireSsl"))
            or ip.get("serverCaMode") != "GOOGLE_MANAGED_INTERNAL_CA"):
        _refuse("sql_instance_configuration")


def metadata(cloud) -> dict:
    """Only the existing production engine identity is read; no secret is accessed."""
    row = _call(cloud, BASE + "/instances/" + PRODUCTION_NAME, time.monotonic() + 30)
    if (not isinstance(row, dict) or row.get("name") != PRODUCTION_NAME or row.get("project") != spec.PROJECT
            or row.get("region") != spec.REGION or row.get("databaseVersion") != "POSTGRES_15"):
        _refuse("production_postgres_major_unverified")
    return {"name": PRODUCTION_NAME, "project": spec.PROJECT, "region": spec.REGION, "database_version": "POSTGRES_15"}


def require_absent(cloud, manifest: dict) -> None:
    name = _target(manifest)
    deadline = time.monotonic() + 30
    if _call(cloud, BASE + "/instances/" + name, deadline, missing_ok=True) is not None:
        _refuse("sql_instance_already_exists")
    if _inventory(cloud, name, deadline, manifest).get("_count"):
        _refuse("sql_instance_history_exists")


def _request(manifest: dict, password: str) -> dict:
    name = _target(manifest)
    if not isinstance(password, str) or not re.fullmatch(r"[a-f0-9]{64}", password):
        _refuse("sql_admin_password_shape")
    return {"name": name, "project": spec.PROJECT, "region": spec.REGION, "databaseVersion": "POSTGRES_15",
            "rootPassword": password, "settings": {
                "tier": "db-custom-1-3840", "edition": "ENTERPRISE", "availabilityType": "ZONAL",
                "dataDiskSizeGb": "10", "dataDiskType": "PD_SSD", "activationPolicy": "ALWAYS",
                "databaseFlags": [],
                "connectorEnforcement": "REQUIRED", "storageAutoResize": False,
                "deletionProtectionEnabled": False, "retainBackupsOnDelete": False,
                "finalBackupConfig": {"enabled": False},
                "backupConfiguration": {"enabled": False, "pointInTimeRecoveryEnabled": False},
                "ipConfiguration": {"ipv4Enabled": True, "authorizedNetworks": [], "sslMode": "ENCRYPTED_ONLY",
                                    "serverCaMode": "GOOGLE_MANAGED_INTERNAL_CA"},
                "userLabels": _labels(manifest)}}


def _operation(operation: dict, name: str, kind: str, manifest: dict) -> str:
    if (not isinstance(operation, dict) or operation.get("targetProject") != spec.PROJECT
            or operation.get("targetId") != name or operation.get("operationType") != kind
            or not isinstance(operation.get("name"), str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", operation["name"])
            or operation.get("status") not in {"PENDING", "RUNNING", "DONE"}):
        _refuse("sql_operation_identity")
    try:
        inserted = datetime.fromisoformat(operation["insertTime"].replace("Z", "+00:00"))
        created = datetime.fromisoformat(manifest["created_at"])
        if (inserted.tzinfo is None or created.tzinfo is None or inserted < created
                or inserted > datetime.now(timezone.utc) + timedelta(seconds=60)):
            _refuse("sql_operation_time")
    except (KeyError, AttributeError, TypeError, ValueError):
        _refuse("sql_operation_time")
    return operation["name"]


def _wait(cloud, operation: dict, name: str, kind: str, deadline: float, manifest: dict, *, allow_failed: bool = False) -> dict:
    operation_id = _operation(operation, name, kind, manifest)
    while operation["status"] != "DONE":
        _pause(deadline)
        operation = _call(cloud, BASE + "/operations/" + operation_id, deadline)
        if _operation(operation, name, kind, manifest) != operation_id:
            _refuse("sql_operation_identity")
    if operation.get("error") and not allow_failed:
        _refuse("sql_operation_failed")
    return operation


def _inventory(cloud, name: str, deadline: float, manifest: dict) -> dict:
    response = _call(cloud, BASE + "/operations?instance=" + name + "&maxResults=20", deadline)
    if (not isinstance(response, dict) or response.get("nextPageToken")
            or not isinstance(response.get("items", []), list) or len(response.get("items", [])) > 20
            or any(not isinstance(item, dict) for item in response.get("items", []))):
        _refuse("sql_operation_inventory")
    result = {"_count": len(response.get("items", []))}
    for item in response.get("items", []):
        kind = item.get("operationType")
        _operation(item, name, kind, manifest)
        if kind in {"CREATE", "DELETE"}:
            if kind in result:
                _refuse("sql_operation_inventory")
            result[kind] = item
    return result


def _find_operation(cloud, name: str, kind: str, deadline: float, manifest: dict) -> dict | None:
    return _inventory(cloud, name, deadline, manifest).get(kind)


def _reconcile_create(cloud, manifest: dict, deadline: float) -> dict:
    name = _target(manifest)
    while True:
        row = _call(cloud, BASE + "/instances/" + name, deadline, missing_ok=True)
        if row is not None:
            _owned(row, manifest)
            operation = _find_operation(cloud, name, "CREATE", deadline, manifest)
            if operation is not None:
                return operation
        _pause(deadline)


def create(cloud, manifest: dict, admin_password: str) -> dict:
    body = _request(manifest, admin_password)
    name, deadline = body["name"], time.monotonic() + LIFECYCLE_SECONDS
    if _call(cloud, BASE + "/instances/" + name, deadline, missing_ok=True) is not None:
        _refuse("sql_instance_already_exists")
    if _inventory(cloud, name, deadline, manifest).get("_count"):
        _refuse("sql_instance_history_exists")
    try:
        operation = _call(cloud, BASE + "/instances", deadline, method="POST", body=body)
    except spec.Refused:
        # The response can be lost after acceptance. Never POST a second time.
        operation = _reconcile_create(cloud, manifest, deadline)
    finally:
        body.pop("rootPassword", None)
    _wait(cloud, operation, name, "CREATE", deadline, manifest)
    row = _call(cloud, BASE + "/instances/" + name, deadline)
    _configuration(row, manifest)
    return {"state": "RUNNABLE", "name": name, "database_version": "POSTGRES_15",
            "tier": "db-custom-1-3840", "disk_size_gb": 10, "operation_done": True,
            "configuration_verified": True, "backup_policy_checked": True, "production_credentials_accessed": False}


def delete(cloud, manifest: dict) -> dict:
    """Caller confirms workers are absent first; only this entire owned instance is removed."""
    name, deadline = _target(manifest), time.monotonic() + LIFECYCLE_SECONDS
    path = BASE + "/instances/" + name
    row = _call(cloud, path, deadline, missing_ok=True)
    # A 404 can precede eventual visibility of an accepted CREATE. Only a
    # completed DELETE or failed CREATE plus a fresh 404 proves absence.
    deleted = False
    while row is None or row.get("state") in {"PENDING_CREATE", "PENDING_DELETE"}:
        if row is not None:
            _owned(row, manifest)
            _cleanup_policy(row)
        inventory = _inventory(cloud, name, deadline, manifest)
        if inventory.get("DELETE") is not None:
            _wait(cloud, inventory["DELETE"], name, "DELETE", deadline, manifest)
            deleted = True
        elif inventory.get("CREATE") is not None:
            completed = _wait(cloud, inventory["CREATE"], name, "CREATE", deadline, manifest, allow_failed=True)
            if completed.get("error"):
                row = _call(cloud, path, deadline, missing_ok=True)
                if row is None:
                    return {"state": "absent", "name": name, "failed_create_done": True, "absence_verified": True}
                _owned(row, manifest)
                _cleanup_policy(row)
                if row.get("state") not in {"PENDING_CREATE", "PENDING_DELETE"}:
                    break
        row = _call(cloud, path, deadline, missing_ok=True)
        if deleted:
            if row is None:
                return {"state": "absent", "name": name, "operation_done": True, "absence_verified": True}
            _owned(row, manifest)
            _cleanup_policy(row)
            # After a completed delete, never dispatch a second delete. Await
            # disappearance and refuse any unowned replacement instead.
            while row is not None:
                _pause(deadline)
                row = _call(cloud, path, deadline, missing_ok=True)
                if row is not None:
                    _owned(row, manifest)
                    _cleanup_policy(row)
            return {"state": "absent", "name": name, "operation_done": True, "absence_verified": True}
        if row is None or row.get("state") in {"PENDING_CREATE", "PENDING_DELETE"}:
            _pause(deadline)
    _owned(row, manifest)
    _cleanup_policy(row)
    operation = None
    if row.get("state") != "PENDING_DELETE":
        try:
            operation = _call(cloud, path + "?enableFinalBackup=false", deadline, method="DELETE")
        except spec.Refused:
            pass  # Reconcile acceptance; never issue an unbounded mutation retry.
    while operation is None:
        operation = _find_operation(cloud, name, "DELETE", deadline, manifest)
        if operation is None:
            _pause(deadline)
    _wait(cloud, operation, name, "DELETE", deadline, manifest)
    while True:
        row = _call(cloud, path, deadline, missing_ok=True)
        if row is None:
            return {"state": "absent", "name": name, "operation_done": True,
                    "absence_verified": True, "backup_policy_checked": True}
        _owned(row, manifest)
        _cleanup_policy(row)
        _pause(deadline)
