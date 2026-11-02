"""Fixed isolated summary-delivery resource manifest; planning performs no network calls."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT = "earnings-nerd"
REGION = "us-west1"
PARENT = f"projects/{PROJECT}/locations/{REGION}"
PREFIX = "earningsnerd-summary-verify"
PURPOSE = "summary-delivery-verification"
DATABASE = "earningsnerd_summary_verify"
DATABASE_VERSION = "POSTGRES_15"
SQL_PERMISSIONS = ("cloudsql.instances.connect", "cloudsql.instances.create", "cloudsql.instances.delete",
                   "cloudsql.instances.get", "cloudsql.instances.list")
RUNTIME_IDENTITY = f"en-summary-verify@{PROJECT}.iam.gserviceaccount.com"
INVOKER_IDENTITY = f"en-summary-verify-invoker@{PROJECT}.iam.gserviceaccount.com"
SECRETS = {"DATABASE_URL": "EARNINGSNERD_SUMMARY_VERIFY_DATABASE_URL", "SECRET_KEY": "EARNINGSNERD_SUMMARY_VERIFY_SECRET_KEY"}
ROLES = ("api", "background", "summary")
SOURCE_FILES = (
    "app/services/durable_tasks.py", "app/services/task_process_service.py", "app/services/task_process.py",
    "app/services/background_task_runner.py", "app/services/summary_jobs.py", "app/services/summary_job_store.py",
    "app/routers/tasks.py", "app/routers/summaries.py", "app/config.py", "app/services/task_routing.py",
    "app/services/summary_recovery.py", "app/services/request_work.py",
)
IMAGE = re.compile(r"us-west1-docker\.pkg\.dev/earnings-nerd/earningsnerd/backend@sha256:[0-9a-f]{64}")


class Refused(RuntimeError):
    """Safe closed operational refusal."""


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def origin(role: str, project_number: str) -> str:
    if role not in ROLES or not re.fullmatch(r"[0-9]{6,20}", project_number):
        raise Refused("resource_identity")
    return f"https://{PREFIX}-{role}-{project_number}.{REGION}.run.app"


def instance_name(run_id: str) -> str:
    if not isinstance(run_id, str) or not re.fullmatch(r"[0-9]{1,20}", run_id):
        raise Refused("instance_identity")
    return f"{PREFIX}-db-{run_id}"


def sql_instance_contract(run_id: str, nonce: str) -> dict:
    if not isinstance(nonce, str) or not re.fullmatch(r"[a-f0-9]{32}", nonce):
        raise Refused("instance_identity")
    return {"name": instance_name(run_id), "database_version": DATABASE_VERSION, "region": REGION,
            "tier": "db-custom-1-3840", "edition": "ENTERPRISE", "availability": "ZONAL",
            "disk_size_gb": 10, "disk_type": "PD_SSD", "storage_auto_resize": False,
            "activation_policy": "ALWAYS", "database_flags": [],
            "connector_enforcement": "REQUIRED", "public_ipv4": True, "authorized_networks": [],
            "ssl_mode": "ENCRYPTED_ONLY", "server_ca_mode": "GOOGLE_MANAGED_INTERNAL_CA",
            "backup_enabled": False, "pitr_enabled": False, "final_backup_enabled": False,
            "retain_backups": False, "deletion_protection": False, "replicas": 0,
            "labels": {"purpose": PURPOSE, "run-id": run_id, "plan-nonce": nonce}}


def connection_name(manifest: dict) -> str:
    expected = sql_instance_contract(manifest["run_id"], manifest["nonce"])
    if manifest.get("sql_instance") != expected:
        raise Refused("fixed_instance_scope")
    return f"{PROJECT}:{REGION}:{expected['name']}"


def sql_permission_receipt(granted: list[str]) -> dict:
    if (not isinstance(granted, list) or any(not isinstance(item, str) for item in granted)
            or len(granted) != len(set(granted)) or not set(granted).issubset(SQL_PERMISSIONS)):
        raise Refused("sql_permissions_unverified")
    return {"required": list(SQL_PERMISSIONS), "granted": sorted(granted),
            "missing": sorted(set(SQL_PERMISSIONS) - set(granted))}


def plan(root: Path, image: str, project_number: str, run_id: str, nonce: str, *, now: datetime | None = None,
         production_secret_names: tuple[str, ...] = ("DATABASE_URL", "SECRET_KEY"),
         source_database_version: str = DATABASE_VERSION, sql_permissions: dict | None = None) -> dict:
    if (not IMAGE.fullmatch(image) or not re.fullmatch(r"[0-9]{1,20}", run_id)
            or not re.fullmatch(r"[a-f0-9]{32}", nonce)):
        raise Refused("plan_identity")
    if source_database_version != DATABASE_VERSION:
        raise Refused("database_version_unsupported")
    permissions = sql_permission_receipt(list(SQL_PERMISSIONS)) if sql_permissions is None else sql_permissions
    if permissions != sql_permission_receipt(permissions.get("granted")):
        raise Refused("sql_permissions_unverified")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise Refused("plan_clock")
    if (not 1 <= len(production_secret_names) <= 40
            or any(not re.fullmatch(r"[A-Za-z0-9_-]{1,255}", n) for n in production_secret_names)
            or set(production_secret_names) & set(SECRETS.values())):
        raise Refused("production_secret_inventory")
    runtime = root / "ops/summary_delivery/runtime.py"
    if not 0 < runtime.stat().st_size <= 32768:
        raise Refused("runtime_size")
    sources = {name: hashlib.sha256((root / "backend" / name).read_bytes()).hexdigest() for name in SOURCE_FILES}
    manifest = {
        "schema": 2, "purpose": PURPOSE, "run_id": run_id, "nonce": nonce,
        "created_at": current.isoformat(), "expires_at": (current + timedelta(hours=2)).isoformat(),
        "image": image, "project_number": project_number,
        "runtime_sha256": hashlib.sha256(runtime.read_bytes()).hexdigest(), "source_hashes": sources,
        "production_secret_names": sorted(set(production_secret_names)),
        "services": [{"name": f"{PARENT}/services/{PREFIX}-{role}", "role": role,
                      "origin": origin(role, project_number), "private": True, "cpu": "1",
                      "memory": "2Gi" if role == "summary" else "1Gi", "min_instances": 0,
                      "max_instances": 1, "concurrency": 1, "request_timeout_seconds": 600} for role in ROLES],
        "queues": [{"name": f"{PARENT}/queues/{PREFIX}-{role}-{run_id}", "concurrency": 1,
                    "dispatches_per_second": 0.2, "attempts": 3, "retry_duration_seconds": 1} for role in ("background", "summary")],
        "identities": [RUNTIME_IDENTITY, INVOKER_IDENTITY], "secrets": list(SECRETS.values()),
        "database": DATABASE, "database_role": DATABASE, "database_connection_limit": 12,
        "sql_instance": sql_instance_contract(run_id, nonce), "source_database_version": source_database_version,
        "resource_expiry_is_enforced": False,
        "sql_permissions": permissions,
        "bounds": {"generation_posts": 4, "result_gets": 6, "control_receipt_gets": 100,
                   "mail_jobs": 1, "summary_jobs": 2, "summary_generation_attempts": 8,
                   "recovery_calls": 8, "runtime_seconds": 600, "cloud_create_tasks": 32, "worker_deliveries": 12,
                   "task_child_deadline_seconds": 80, "provider_fixture_stall_seconds": 200,
                   "long_summary_fixture_seconds": 70, "provider_calls": 0, "sec_calls": 0, "mail_sends": 0},
        "claim_scope": "Synthetic transport, ownership and persistence only; no source/model/email quality or production SLO claim",
    }
    return {"manifest": manifest, "sha256": digest(manifest)}


def approve(document: dict, expected_hash: str, nonce: str, env: dict, *, now: datetime | None = None,
            cleanup: bool = False) -> dict:
    if set(document) != {"manifest", "sha256"} or digest(document["manifest"]) != document["sha256"]:
        raise Refused("plan_integrity")
    m = document["manifest"]
    current = now or datetime.now(timezone.utc)
    if (not hmac_equal(document["sha256"], expected_hash) or not hmac_equal(m.get("nonce", ""), nonce)
            or env.get("GITHUB_ACTIONS") != "true" or env.get("GITHUB_RUN_ATTEMPT") != "1"
            or not re.fullmatch(r"[0-9]{1,20}", env.get("GITHUB_RUN_ID", ""))
            or env.get("SUMMARY_DELIVERY_APPROVED") != "true"
            or current < datetime.fromisoformat(m["created_at"])
            or (not cleanup and current > datetime.fromisoformat(m["expires_at"]))):
        raise Refused("approval_boundary")
    validate_scope(m)
    return m


def validate_scope(manifest: dict) -> None:
    """Cleanup can outlive source/image changes, but never changes its fixed target set."""
    m = manifest
    if (m.get("schema") != 2 or m.get("purpose") != PURPOSE
            or not isinstance(m.get("run_id"), str) or not re.fullmatch(r"[0-9]{1,20}", m["run_id"])
            or not isinstance(m.get("project_number"), str)
            or not re.fullmatch(r"[0-9]{6,20}", m["project_number"])
            or m.get("identities") != [RUNTIME_IDENTITY, INVOKER_IDENTITY]
            or m.get("secrets") != list(SECRETS.values()) or m.get("database") != DATABASE
            or m.get("database_role") != DATABASE or m.get("database_connection_limit") != 12):
        raise Refused("fixed_resource_scope")
    if (m.get("source_database_version") != DATABASE_VERSION or m.get("resource_expiry_is_enforced") is not False
            or m.get("sql_instance") != sql_instance_contract(m["run_id"], m["nonce"])):
        raise Refused("fixed_instance_scope")
    permissions = m.get("sql_permissions")
    if (not isinstance(permissions, dict)
            or permissions != sql_permission_receipt(permissions.get("granted"))):
        raise Refused("sql_permissions_unverified")
    expected_services = [{"name": f"{PARENT}/services/{PREFIX}-{role}", "role": role,
                          "origin": origin(role, m["project_number"]), "private": True, "cpu": "1",
                          "memory": "2Gi" if role == "summary" else "1Gi", "min_instances": 0,
                          "max_instances": 1, "concurrency": 1, "request_timeout_seconds": 600} for role in ROLES]
    expected_queues = [{"name": f"{PARENT}/queues/{PREFIX}-{role}-{m['run_id']}", "concurrency": 1,
                       "dispatches_per_second": 0.2, "attempts": 3, "retry_duration_seconds": 1} for role in ("background", "summary")]
    if m.get("services") != expected_services or m.get("queues") != expected_queues:
        raise Refused("fixed_resource_scope")


def hmac_equal(left: str, right: str) -> bool:
    import hmac
    return isinstance(left, str) and isinstance(right, str) and hmac.compare_digest(left.encode(), right.encode())


def runtime_env(manifest: dict, versions: dict[str, str], role: str, source: str) -> list[dict]:
    if role not in ROLES or hashlib.sha256(source.encode()).hexdigest() != manifest["runtime_sha256"]:
        raise Refused("runtime_source")
    values = {"ENVIRONMENT": "production", "SKIP_REDIS_INIT": "true", "DB_POOL_SIZE": "1", "DB_MAX_OVERFLOW": "0",
              "DB_POOL_TIMEOUT": "5", "SUMMARY_VERIFY_ROLE": role, "SUMMARY_VERIFY_RUN_ID": manifest["run_id"],
              "SUMMARY_VERIFY_RUNTIME_SOURCE": source, "SUMMARY_VERIFY_RUNTIME_SHA256": manifest["runtime_sha256"],
              "SUMMARY_VERIFY_SOURCE_HASHES": json.dumps(manifest["source_hashes"], sort_keys=True),
              "SUMMARY_VERIFY_PRODUCTION_SECRET_NAMES": json.dumps(manifest["production_secret_names"]),
              "SUMMARY_VERIFY_INSTANCE": connection_name(manifest),
              "OPENAI_API_KEY": "offline-summary-delivery-fixture", "RESEND_API_KEY": "", "RESEND_WEBHOOK_SECRET": "",
              "POSTHOG_API_KEY": "", "SENTRY_DSN": "", "STRIPE_SECRET_KEY": "", "STRIPE_WEBHOOK_SECRET": "",
              "STRIPE_PUBLISHABLE_KEY": "", "GOOGLE_CLIENT_SECRET": "", "APPLE_PRIVATE_KEY": "", "AI_FALLBACK_API_KEY": "",
              "DURABLE_TASKS_ENABLED": "true", "SUMMARY_DURABLE_GENERATION_ENABLED": "true",
              "SUMMARY_NEW_JOBS_PAUSED": "false", "SUMMARY_PREWARM_MAX_PER_SCAN": "0", "SUMMARY_PREWARM_MAX_PER_DAY": "0",
              "SEC_DISTRIBUTED_LIMIT_ENABLED": "false", "SEC_RATE_LIMIT_PER_SECOND": "1", "EDGAR_RATE_LIMIT_PER_SEC": "1",
              "TASKS_PROJECT_ID": PROJECT, "TASKS_LOCATION": REGION, "TASKS_QUEUE": PREFIX + "-background-" + manifest["run_id"],
              "TASKS_WORKER_URL": origin("background", manifest["project_number"]), "TASKS_INVOKER_EMAIL": INVOKER_IDENTITY,
              "SUMMARY_TASKS_QUEUE": PREFIX + "-summary-" + manifest["run_id"], "SUMMARY_TASKS_WORKER_URL": origin("summary", manifest["project_number"]),
              "SUMMARY_TASKS_INVOKER_EMAIL": INVOKER_IDENTITY, "TASKS_WORKER_ROLE": "summary" if role == "summary" else "background",
              "TASKS_WORKER_PROCESS": "false" if role == "api" else "true", "TASKS_WORK_TIMEOUT_SECONDS": "80",
              "REGISTRATION_MODE": "invite_only", "ENABLE_HISTORY_BACKFILL_ON_VISIT": "false",
              "PWNED_PASSWORD_CHECK_ENABLED": "false", "FRONTEND_URL": "https://delivery.invalid"}
    result = [{"name": name, "value": value} for name, value in sorted(values.items())]
    if set(versions) != set(SECRETS) or not all(re.fullmatch(r"[1-9][0-9]*", v) for v in versions.values()):
        raise Refused("secret_versions")
    result.extend({"name": key, "valueSource": {"secretKeyRef": {"secret": secret, "version": versions[key]}}}
                  for key, secret in SECRETS.items())
    return result


BOOTSTRAP = ("import os,pathlib,runpy; p=pathlib.Path('/tmp/summary-delivery-runtime.py');"
             "p.write_text(os.environ.pop('SUMMARY_VERIFY_RUNTIME_SOURCE'));runpy.run_path(str(p),run_name='__main__')")


def service_spec(manifest: dict, versions: dict[str, str], role: str, source: str) -> dict:
    service = next(row for row in manifest["services"] if row["role"] == role)
    return {"name": service["name"], "labels": {"purpose": PURPOSE, "run-id": manifest["run_id"]},
            "ingress": "INGRESS_TRAFFIC_ALL", "invokerIamDisabled": False,
            "scaling": {"minInstanceCount": 0, "maxInstanceCount": 1}, "template": {
                "serviceAccount": RUNTIME_IDENTITY, "timeout": "600s", "maxInstanceRequestConcurrency": 1,
                "scaling": {"minInstanceCount": 0, "maxInstanceCount": 1},
                "volumes": [{"name": "sql", "cloudSqlInstance": {"instances": [connection_name(manifest)]}}],
                "containers": [{"image": manifest["image"], "command": ["python"], "args": ["-c", BOOTSTRAP],
                                "env": runtime_env(manifest, versions, role, source),
                                "volumeMounts": [{"name": "sql", "mountPath": "/cloudsql"}],
                                "resources": {"limits": {"cpu": "1", "memory": service["memory"]}, "cpuIdle": True}}]}}
