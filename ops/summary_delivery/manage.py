"""Plan, execute and clean one bounded isolated Cloud Tasks delivery rehearsal.

All mutations require the protected Ops first-attempt job, the reviewed plan hash
and its nonce. No production service, queue, database object or feature setting is
changed. A completed run retains a counts-only receipt; cleanup is also attempted
on failure, and an incomplete cleanup is a failure requiring explicit follow-up.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import secrets
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ops.feedback_media.manage import Cloud as BaseCloud  # noqa: E402
from ops.summary_delivery import spec  # noqa: E402


class Cloud(BaseCloud):
    def __init__(self):
        super().__init__()
        self.calls = 0
        self.cleanup_calls = 0
        self.cleaning = False

    def begin_cleanup(self):
        self.cleaning = True

    def call(self, *args, **kwargs):
        if self.cleaning:
            self.cleanup_calls += 1
        else:
            self.calls += 1
        if self.calls > 400 and not self.cleaning or self.cleanup_calls > 500:
            raise spec.Refused("cloud_operation_budget")
        return super().call(*args, **kwargs)


def production_snapshot(cloud) -> tuple[str, tuple[str, ...]]:
    service = cloud.call("run", "v2/" + spec.PARENT + "/services/earningsnerd-backend")
    traffic = [row for row in service.get("trafficStatuses", []) if row.get("percent")]
    revision = service.get("latestReadyRevision", "").rsplit("/", 1)[-1]
    if (service.get("reconciling") or len(traffic) != 1 or traffic[0].get("percent") != 100
            or traffic[0].get("revision", "").rsplit("/", 1)[-1] != revision
            or not re.fullmatch(r"earningsnerd-backend-[0-9]{5}-[a-z0-9]+", revision)):
        raise spec.Refused("production_not_stable")
    row = cloud.call("us-west1-run", f"apis/serving.knative.dev/v1/namespaces/{spec.PROJECT}/revisions/{revision}")
    image = row.get("status", {}).get("imageDigest", "")
    if not spec.IMAGE.fullmatch(image):
        raise spec.Refused("production_image_unverified")
    references = []
    containers = row.get("spec", {}).get("containers", [])
    if len(containers) != 1:
        raise spec.Refused("production_secret_inventory")
    for item in containers[0].get("env", []):
        ref = item.get("valueFrom", {}).get("secretKeyRef")
        if ref:
            name = ref.get("name", "")
            prefix = f"projects/{spec.PROJECT}/secrets/"
            if name.startswith(prefix):
                name = name[len(prefix):]
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,255}", name):
                raise spec.Refused("production_secret_inventory")
            references.append(name)
    if not references:
        raise spec.Refused("production_secret_inventory")
    return image, tuple(sorted(set(references)))


def policy(cloud, api: str, path: str, *, post: bool = False) -> dict:
    suffix = ":getIamPolicy" if post else ":getIamPolicy?options.requestedPolicyVersion=3"
    result = cloud.call(api, path + suffix, method="POST" if post else "GET",
                        body={"options": {"requestedPolicyVersion": 3}} if post else None)
    if any(member in {"allUsers", "allAuthenticatedUsers"} for b in result.get("bindings", []) for member in b.get("members", [])):
        raise spec.Refused("public_policy")
    return result


def bind(cloud, api: str, path: str, role: str, member: str, *, post: bool = False) -> None:
    value = policy(cloud, api, path, post=post)
    binding = next((b for b in value.get("bindings", []) if b.get("role") == role and not b.get("condition")), None)
    if binding is None:
        value.setdefault("bindings", []).append({"role": role, "members": [member]})
    elif member in binding.get("members", []):
        return
    else:
        binding.setdefault("members", []).append(member)
    cloud.call(api, path + ":setIamPolicy", method="POST", body={"policy": value})


def wait_run(cloud, operation: dict) -> dict:
    deadline = time.monotonic() + 240
    while not operation.get("done"):
        name = operation.get("name", "")
        if not name.startswith(spec.PARENT + "/operations/") or time.monotonic() >= deadline:
            raise spec.Refused("resource_operation_unverified")
        time.sleep(2)
        operation = cloud.call("run", "v2/" + name)
    if operation.get("error"):
        raise spec.Refused("resource_operation_failed")
    return operation.get("response", {})


def resources(manifest: dict):
    yield from (("run", "v2/" + row["name"], "service") for row in manifest["services"])
    yield from (("cloudtasks", "v2/" + row["name"], "queue") for row in manifest["queues"])
    yield from (("iam", f"v1/projects/{spec.PROJECT}/serviceAccounts/{email}", "identity") for email in manifest["identities"])
    yield from (("secretmanager", f"v1/projects/{spec.PROJECT}/secrets/{name}", "secret") for name in manifest["secrets"])


def require_empty(cloud, manifest: dict) -> None:
    for api, path, _ in resources(manifest):
        if cloud.call(api, path, missing_ok=True) is not None:
            raise spec.Refused("verification_resources_already_exist")


def create_secret(cloud, name: str, value: str, run_id: str) -> str:
    if name not in spec.SECRETS.values():
        raise spec.Refused("secret_boundary")
    path = f"v1/projects/{spec.PROJECT}/secrets/{name}"
    cloud.call("secretmanager", f"v1/projects/{spec.PROJECT}/secrets?secretId={name}", method="POST",
               body={"replication": {"automatic": {}}, "labels": {"purpose": spec.PURPOSE, "run-id": run_id}})
    result = cloud.call("secretmanager", path + ":addVersion", method="POST",
                        body={"payload": {"data": base64.b64encode(value.encode()).decode()}})
    version = result.get("name", "").rsplit("/", 1)[-1]
    if not re.fullmatch(r"[1-9][0-9]*", version):
        raise spec.Refused("secret_version_unverified")
    bind(cloud, "secretmanager", path, "roles/secretmanager.secretAccessor", "serviceAccount:" + spec.RUNTIME_IDENTITY)
    return version


def create_identities(cloud, manifest: dict, deployer: str) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]@earnings-nerd\.iam\.gserviceaccount\.com", deployer):
        raise spec.Refused("deployer_identity")
    for email in manifest["identities"]:
        cloud.call("iam", f"v1/projects/{spec.PROJECT}/serviceAccounts", method="POST", body={
            "accountId": email.split("@", 1)[0],
            "serviceAccount": {"displayName": spec.PURPOSE, "description": spec.PURPOSE + ":" + manifest["run_id"]}})
    runtime_path = f"v1/projects/{spec.PROJECT}/serviceAccounts/{spec.RUNTIME_IDENTITY}"
    invoker_path = f"v1/projects/{spec.PROJECT}/serviceAccounts/{spec.INVOKER_IDENTITY}"
    bind(cloud, "iam", runtime_path, "roles/iam.serviceAccountUser", "serviceAccount:" + deployer, post=True)
    bind(cloud, "iam", invoker_path, "roles/iam.serviceAccountOpenIdTokenCreator", "serviceAccount:" + deployer, post=True)
    bind(cloud, "iam", invoker_path, "roles/iam.serviceAccountUser", "serviceAccount:" + spec.RUNTIME_IDENTITY, post=True)
    bind(cloud, "iam", invoker_path, "roles/iam.serviceAccountTokenCreator",
         f"serviceAccount:service-{manifest['project_number']}@gcp-sa-cloudtasks.iam.gserviceaccount.com", post=True)
    project = cloud.call("cloudresourcemanager", f"v1/projects/{spec.PROJECT}:getIamPolicy", method="POST",
                         body={"options": {"requestedPolicyVersion": 3}})
    member = "serviceAccount:" + spec.RUNTIME_IDENTITY
    previous = [b for b in project.get("bindings", []) if member in b.get("members", [])]
    if previous:
        raise spec.Refused("runtime_identity_has_existing_project_grants")
    project.setdefault("bindings", []).append({"role": "roles/cloudsql.client", "members": [member]})
    cloud.call("cloudresourcemanager", f"v1/projects/{spec.PROJECT}:setIamPolicy", method="POST", body={"policy": project})


def create_queues(cloud, manifest: dict) -> None:
    for row in manifest["queues"]:
        cloud.call("cloudtasks", "v2/" + spec.PARENT + "/queues", method="POST", body={
            "name": row["name"], "rateLimits": {"maxConcurrentDispatches": 1, "maxDispatchesPerSecond": 0.2},
            "retryConfig": {"maxAttempts": 3, "maxRetryDuration": "1s", "minBackoff": "30s",
                            "maxBackoff": "30s", "maxDoublings": 0}})
        cloud.call("cloudtasks", "v2/" + row["name"] + ":pause", method="POST", body={})
        current = cloud.call("cloudtasks", "v2/" + row["name"])
        if current.get("state") != "PAUSED":
            raise spec.Refused("queue_pause_unverified")
        bind(cloud, "cloudtasks", "v2/" + row["name"], "roles/cloudtasks.enqueuer",
             "serviceAccount:" + spec.RUNTIME_IDENTITY, post=True)


def create_services(cloud, manifest: dict, versions: dict) -> None:
    source = (ROOT / "ops/summary_delivery/runtime.py").read_text()
    for role in spec.ROLES:
        body = spec.service_spec(manifest, versions, role, source)
        name = body["name"].rsplit("/", 1)[-1]
        wait_run(cloud, cloud.call("run", "v2/" + spec.PARENT + "/services?serviceId=" + name, method="POST", body=body))
        bind(cloud, "run", "v2/" + body["name"], "roles/run.invoker", "serviceAccount:" + spec.INVOKER_IDENTITY)
        row = cloud.call("run", "v2/" + body["name"])
        # Distinct Cloud Run resource names are authoritative; alias URL differences are not.
        if (row.get("name") != body["name"] or row.get("invokerIamDisabled")
                or row.get("labels", {}).get("run-id") != manifest["run_id"]
                or spec.origin(role, manifest["project_number"]) not in {row.get("uri"), *row.get("urls", [])}):
            raise spec.Refused("private_service_unverified")
        bindings = policy(cloud, "run", "v2/" + body["name"]).get("bindings", [])
        if bindings != [{"role": "roles/run.invoker", "members": ["serviceAccount:" + spec.INVOKER_IDENTITY]}]:
            raise spec.Refused("private_invoker_unverified")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise spec.Refused("unexpected_redirect")


def verify_private_surface(cloud, manifest: dict) -> dict:
    """Prove effective ingress, including inherited IAM, using health requests only."""
    tokens = {}
    for role in spec.ROLES:
        result = cloud.call("iamcredentials", f"v1/projects/-/serviceAccounts/{spec.INVOKER_IDENTITY}:generateIdToken",
                            method="POST", body={"audience": spec.origin(role, manifest["project_number"]), "includeEmail": True})
        tokens[role] = result.get("token")
        if not isinstance(tokens[role], str) or not tokens[role]:
            raise spec.Refused("invoker_identity_unverified")
    opener = build_opener(NoRedirect())
    for index, role in enumerate(spec.ROLES):
        wrong_role = spec.ROLES[(index + 1) % len(spec.ROLES)]
        for token, accepted in ((None, False), (tokens[wrong_role], False), (tokens[role], True)):
            headers = {} if token is None else {"X-Serverless-Authorization": "Bearer " + token}
            request = Request(spec.origin(role, manifest["project_number"]) + "/health", headers=headers)
            try:
                with opener.open(request, timeout=30) as response:
                    raw = response.read(1025)
                    if not accepted or len(raw) > 1024 or json.loads(raw) != {"status": "healthy", "synthetic": True}:
                        raise spec.Refused("effective_private_ingress_unverified")
            except HTTPError as error:
                if accepted or error.code not in {401, 403}:
                    raise spec.Refused("effective_private_ingress_unverified") from None
            except (URLError, TimeoutError, ValueError):
                raise spec.Refused("effective_private_ingress_unverified") from None
    return {"anonymous_denied": True, "wrong_audience_denied": True, "correct_identity_accepted": True,
            "services_checked": 3, "health_requests": 9}


class Client:
    def __init__(self, cloud, manifest: dict, key: str):
        self.origin = spec.origin("api", manifest["project_number"])
        result = cloud.call("iamcredentials", f"v1/projects/-/serviceAccounts/{spec.INVOKER_IDENTITY}:generateIdToken",
                            method="POST", body={"audience": self.origin, "includeEmail": True})
        self.identity, self.key = result.get("token"), key
        if not isinstance(self.identity, str) or not self.identity:
            raise spec.Refused("invoker_identity_unverified")
        self.opener, self.calls = build_opener(NoRedirect()), 0

    def request(self, path: str, *, method: str = "GET", bearer: str | None = None, first_frame: bool = False):
        if not path.startswith(("/__summary_verify__/", "/api/summaries/filing/45003", "/api/summaries/filing/45004")):
            raise spec.Refused("request_boundary")
        self.calls += 1
        if self.calls > 120:
            raise spec.Refused("http_request_budget")
        headers = {"X-Serverless-Authorization": "Bearer " + self.identity,
                   "X-Summary-Verify": self.key, "Content-Type": "application/json"}
        if bearer:
            headers["Authorization"] = "Bearer " + bearer
        request = Request(self.origin + path, data=b"{}" if method == "POST" else None, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=30) as response:
                if first_frame:
                    for _ in range(30):
                        line = response.readline(4097)
                        if len(line) > 4096:
                            raise spec.Refused("response_bound")
                        if line.startswith(b"data: "):
                            return json.loads(line[6:])
                    raise spec.Refused("missing_sse_frame")
                raw = response.read(32769)
                if len(raw) > 32768:
                    raise spec.Refused("response_bound")
                return json.loads(raw)
        except (HTTPError, URLError, TimeoutError, ValueError):
            raise spec.Refused("verification_http_failed") from None


def assess(result: dict) -> dict:
    jobs = result.get("jobs", [])
    events = result.get("events", [])
    if (len(jobs) != 2 or {r["filing_id"] for r in jobs} != {45003, 45004}
            or any(r["status"] != "complete" or not r["summary_present"] or r["charge_state"] != "settled" for r in jobs)
            or result.get("summaries") != 2 or result.get("reservations") != 0 or result.get("logical_charges") != 2
            or next(r["attempts"] for r in jobs if r["filing_id"] == 45003) != 1
            or next(r["attempts"] for r in jobs if r["filing_id"] == 45004) != 2):
        raise spec.Refused("summary_outcome_failed")
    def when(kind: str, filing_id=None):
        rows = [r for r in events if r["kind"] == kind and (filing_id is None or r["filing_id"] == filing_id)]
        if len(rows) != 1:
            raise spec.Refused("event_outcome_failed")
        return datetime.fromisoformat(rows[0]["at"])
    mail_start, mail_enqueue = when("mail_started"), when("mail_enqueued")
    provider_start, provider_end = when("provider_started", 45003), when("provider_completed", 45003)
    if not (provider_start < mail_start < provider_end and 0 <= (mail_start - mail_enqueue).total_seconds() <= 60):
        raise spec.Refused("mail_isolation_failed")
    if (not any(r["kind"] == "worker_failed" for r in events) or not any(r["kind"] == "native_stall" for r in events)
            or sum(r["kind"] == "child_reaped" for r in events) < 4):
        raise spec.Refused("native_deadline_unverified")
    result["acceptance"] = {"persisted_results": True, "logical_usage_settled": True, "mail_during_summary": True,
                            "mail_start_seconds": (mail_start - mail_enqueue).total_seconds(),
                            "native_child_recovery": True, "actual_cloud_tasks": True,
                            "actual_private_oidc": True, "source_model_or_mail_quality": False}
    return result


def exercise(cloud, manifest: dict, key: str) -> dict:
    client = Client(cloud, manifest, key)
    credentials = client.request("/__summary_verify__/seed", method="POST")
    tokens = credentials.get("tokens", [])
    if len(tokens) != 2:
        raise spec.Refused("fixture_seed_unverified")
    for fid, token in zip((45003, 45004), tokens, strict=True):
        client.request(f"/api/summaries/filing/{fid}/generate-stream", method="POST", bearer=token, first_frame=True)
    for queue in manifest["queues"]:
        cloud.call("cloudtasks", "v2/" + queue["name"] + ":resume", method="POST", body={})
    deadline, next_recovery, mailed = time.monotonic() + 540, time.monotonic() + 60, False
    while time.monotonic() < deadline:
        result = client.request("/__summary_verify__/receipt")
        if not mailed and any(r["kind"] == "provider_started" and r["filing_id"] == 45003 for r in result["events"]):
            client.request("/__summary_verify__/mail", method="POST")
            mailed = True
        if len(result["jobs"]) == 2 and all(r["status"] == "complete" for r in result["jobs"]):
            break
        if time.monotonic() >= next_recovery:
            client.request("/__summary_verify__/recover", method="POST")
            next_recovery += 60
        time.sleep(6)
    else:
        raise spec.Refused("delivery_window_exhausted")
    for fid, token in zip((45003, 45004), tokens, strict=True):
        client.request(f"/api/summaries/filing/{fid}/generate-stream", method="POST", bearer=token, first_frame=True)
        for _ in range(3):
            stored = client.request(f"/api/summaries/filing/{fid}", bearer=token)
            if not stored.get("id") or not stored.get("business_overview"):
                raise spec.Refused("stored_result_unverified")
    result = assess(client.request("/__summary_verify__/receipt"))
    result["harness_http_calls"] = client.calls
    result["image"] = manifest["image"]
    result["runtime_sha256"] = manifest["runtime_sha256"]
    result["source_hashes"] = manifest["source_hashes"]
    return result


def pause_owned_queues(cloud, manifest: dict) -> None:
    spec.validate_scope(manifest)
    cloud.begin_cleanup()
    for queue in manifest["queues"]:
        current = cloud.call("cloudtasks", "v2/" + queue["name"], missing_ok=True)
        if current:
            if current.get("name") != queue["name"] or not queue["name"].endswith("-" + manifest["run_id"]):
                raise spec.Refused("cleanup_queue_ownership")
            cloud.call("cloudtasks", "v2/" + queue["name"] + ":pause", method="POST", body={})


def cleanup(cloud, manifest: dict, sql) -> dict:
    spec.validate_scope(manifest)
    cloud.begin_cleanup()
    failures = []
    identities = []
    owned = []
    # Verify all readable ownership markers before deletion. A resource with an
    # unexpected owner is never adopted merely because its fixed name matches.
    for api, path, kind in resources(manifest):
        try:
            current = cloud.call(api, path, missing_ok=True)
        except Exception:
            failures.append("inventory_" + kind)
            continue
        if current is None:
            continue
        if kind in {"service", "secret"}:
            labels = current.get("labels", {})
            if labels.get("purpose") != spec.PURPOSE or labels.get("run-id") != manifest["run_id"]:
                raise spec.Refused("cleanup_resource_ownership")
        elif kind == "identity" and current.get("description") != spec.PURPOSE + ":" + manifest["run_id"]:
            raise spec.Refused("cleanup_identity_ownership")
        if kind == "identity":
            identities.append((api, path))
            continue
        owned.append((api, path, kind))
    try:
        pause_owned_queues(cloud, manifest)
    except Exception:
        failures.append("queue_pause")
    for api, path, kind in owned:
        try:
            result = cloud.call(api, path, method="DELETE")
            if kind == "service":
                wait_run(cloud, result)
        except Exception:
            failures.append("delete_" + kind)
    # Keep the SQL database and identity while a worker's removal is unverified.
    workers_absent = True
    for service in manifest["services"]:
        try:
            workers_absent &= cloud.call("run", "v2/" + service["name"], missing_ok=True) is None
        except Exception:
            workers_absent = False
    if not workers_absent:
        return {"state": "UNVERIFIED", "requires_explicit_cleanup": True,
                "failed_stages": sorted(set(failures + ["worker_absence"]))}
    try:
        sql.cleanup()
    except Exception:
        return {"state": "UNVERIFIED", "requires_explicit_cleanup": True,
                "failed_stages": sorted(set(failures + ["database_cleanup"]))}
    # Remove only the grant this controller owns; preserve policy etag and all other members.
    project = cloud.call("cloudresourcemanager", f"v1/projects/{spec.PROJECT}:getIamPolicy", method="POST",
                         body={"options": {"requestedPolicyVersion": 3}})
    member = "serviceAccount:" + spec.RUNTIME_IDENTITY
    changed = False
    for binding in project.get("bindings", []):
        if binding.get("role") == "roles/cloudsql.client" and not binding.get("condition"):
            changed |= member in binding.get("members", [])
            binding["members"] = [m for m in binding.get("members", []) if m != member]
    project["bindings"] = [b for b in project.get("bindings", []) if b.get("members")]
    if changed:
        # The owned runtime identity must still exist while removing its grant;
        # deleting it first turns IAM members into tombstones with a different ID.
        if not any(spec.RUNTIME_IDENTITY in path for _, path in identities):
            raise spec.Refused("cleanup_project_grant_ownership")
        cloud.call("cloudresourcemanager", f"v1/projects/{spec.PROJECT}:setIamPolicy", method="POST", body={"policy": project})
    for api, path in identities:
        try:
            cloud.call(api, path, method="DELETE")
        except Exception:
            failures.append("delete_identity")
    for api, path, _ in resources(manifest):
        try:
            if cloud.call(api, path, missing_ok=True) is not None:
                failures.append("final_resource_absence")
        except Exception:
            failures.append("final_resource_absence")
    if failures:
        return {"state": "UNVERIFIED", "requires_explicit_cleanup": True, "failed_stages": sorted(set(failures))}
    return {"state": "removed", "owned_resources_only": True}


def apply(cloud, document: dict, expected_hash: str, nonce: str, env: dict) -> dict:
    from ops.summary_delivery.database import admin
    manifest = spec.approve(document, expected_hash, nonce, env)
    regenerated = spec.plan(ROOT, manifest["image"], manifest["project_number"], manifest["run_id"], manifest["nonce"],
                            now=datetime.fromisoformat(manifest["created_at"]),
                            production_secret_names=tuple(manifest["production_secret_names"]))
    image, names = production_snapshot(cloud)
    if regenerated != document or image != manifest["image"] or list(names) != manifest["production_secret_names"]:
        raise spec.Refused("reviewed_plan_changed")
    require_empty(cloud, manifest)
    with admin(cloud, ROOT) as sql:
        started, result, phase = False, None, "database_preflight"
        closed = {"state": "not_needed"}
        try:
            sql.preflight()
            key, password = secrets.token_urlsafe(48), secrets.token_hex(32)
            started = True
            phase = "isolated_database"
            url = sql.provision(password)
            phase = "identities"
            create_identities(cloud, manifest, env.get("SUMMARY_DELIVERY_DEPLOYER", ""))
            phase = "isolated_secrets"
            versions = {"SECRET_KEY": create_secret(cloud, spec.SECRETS["SECRET_KEY"], key, manifest["run_id"]),
                        "DATABASE_URL": create_secret(cloud, spec.SECRETS["DATABASE_URL"], url, manifest["run_id"])}
            phase = "queues"
            create_queues(cloud, manifest)
            phase = "private_services"
            create_services(cloud, manifest, versions)
            phase = "private_ingress_acceptance"
            surface = verify_private_surface(cloud, manifest)
            phase = "actual_delivery"
            result = exercise(cloud, manifest, key)
            result["private_ingress"] = surface
            result["state"] = "completed"
        except Exception:
            result = {"state": "UNVERIFIED", "failed_phase": phase,
                      "database_headroom": getattr(sql, "headroom_snapshot", None)}
        finally:
            if started:
                try:
                    closed = cleanup(cloud, manifest, sql)
                except Exception:
                    closed = {"state": "UNVERIFIED", "requires_explicit_cleanup": True}
        if result is None:
            result = {"state": "UNVERIFIED", "failed_phase": phase}
        if closed["state"] == "UNVERIFIED":
            result["state"] = "UNVERIFIED"
        result["cleanup"] = closed
        result["cloud_api_calls"] = cloud.calls
        result["cleanup_cloud_api_calls"] = cloud.cleanup_calls
        result["plan_sha256"] = expected_hash
        return result


def write_private(path: Path, value: dict) -> None:
    data = spec.canonical(value)
    if len(data) > 32768:
        raise spec.Refused("artifact_bound")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(data + b"\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("plan", "apply", "cleanup"))
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-plan-sha256", default="")
    parser.add_argument("--approval-nonce", default="")
    args = parser.parse_args(argv)
    try:
        if args.operation == "plan":
            cloud = Cloud()
            number = str(cloud.call("cloudresourcemanager", f"v1/projects/{spec.PROJECT}").get("projectNumber", ""))
            image, names = production_snapshot(cloud)
            result = spec.plan(ROOT, image, number, os.environ.get("GITHUB_RUN_ID", ""), secrets.token_hex(16),
                               production_secret_names=names)
        else:
            if args.plan is None or args.plan.stat().st_size > 32768:
                raise spec.Refused("bounded_plan_required")
            document = json.loads(args.plan.read_text())
            manifest = spec.approve(document, args.expected_plan_sha256, args.approval_nonce, dict(os.environ),
                                    cleanup=args.operation == "cleanup")
            cloud = Cloud()
            if args.operation == "apply":
                result = apply(cloud, document, args.expected_plan_sha256, args.approval_nonce, dict(os.environ))
            else:
                from ops.summary_delivery.database import admin
                # Stop new deliveries even when SQL credentials/proxy cannot be
                # resolved; exact fixed queue scope and approval still apply.
                pause_owned_queues(cloud, manifest)
                with admin(cloud, ROOT) as sql:
                    result = cleanup(cloud, manifest, sql)
        write_private(args.output, result)
        print(json.dumps({"state": result.get("state", "completed"), "operation": args.operation,
                          "artifact": args.output.name, "plan_sha256": result.get("sha256")}))
        return 1 if result.get("state") == "UNVERIFIED" else 0
    except Exception:
        # Provider bodies, credentials, auth headers and source text are never formatted.
        try:
            write_private(args.output, {"state": "UNVERIFIED", "operation": args.operation,
                                       "reason": "summary_delivery_operation_refused"})
        except Exception:
            pass
        print(json.dumps({"state": "UNVERIFIED", "reason": "summary_delivery_operation_refused"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
