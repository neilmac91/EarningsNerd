"""Exercise documented SQL Admin lifecycle requests against a stateful fake transport."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from ops.summary_delivery import instance, spec  # noqa: E402

IMAGE = "us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend@sha256:" + "a" * 64
PASSWORD = "c" * 64  # Synthetic fixture only.
PRIVATE = "PRIVATE_SQL_PROVIDER_ERROR_SENTINEL"


def manifest():
    return spec.plan(ROOT, IMAGE, "123456789", "123", "b" * 32)["manifest"]


def documented_request(m):
    # Independent literal fixture from SQL Admin discovery, not the implementation builder.
    return {"name": "earningsnerd-summary-verify-db-" + m["run_id"], "project": "earnings-nerd", "region": "us-west1",
            "databaseVersion": "POSTGRES_15", "rootPassword": PASSWORD, "settings": {
                "tier": "db-custom-1-3840", "edition": "ENTERPRISE", "availabilityType": "ZONAL",
                "dataDiskSizeGb": "10", "dataDiskType": "PD_SSD", "activationPolicy": "ALWAYS", "databaseFlags": [],
                "connectorEnforcement": "REQUIRED", "storageAutoResize": False,
                "deletionProtectionEnabled": False, "retainBackupsOnDelete": False,
                "finalBackupConfig": {"enabled": False},
                "backupConfiguration": {"enabled": False, "pointInTimeRecoveryEnabled": False},
                "ipConfiguration": {"ipv4Enabled": True, "authorizedNetworks": [], "sslMode": "ENCRYPTED_ONLY",
                                    "serverCaMode": "GOOGLE_MANAGED_INTERNAL_CA"},
                "userLabels": {"purpose": "summary-delivery-verification", "run-id": m["run_id"], "plan-nonce": m["nonce"]}}}


class Clock:
    now = 100.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        assert 0 < seconds <= 5
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    value = Clock()
    monkeypatch.setattr(instance.time, "monotonic", value.monotonic)
    monkeypatch.setattr(instance.time, "sleep", value.sleep)
    return value


class Cloud:
    def __init__(self, m, clock):
        self.manifest, self.clock = m, clock
        self.calls, self.operations = [], {}
        self.row = None
        self.fail = None
        self.stuck = False
        self.corrupt = None
        self.completed_error = False
        self.latency = 0
        self.row_visible_at = self.operations_visible_at = 0
        self.production = {"name": "earningsnerd-db", "project": spec.PROJECT, "region": spec.REGION,
                           "databaseVersion": "POSTGRES_15", "privateProviderField": PRIVATE,
                           "settings": {"tier": PRIVATE}}

    def prepare(self, *, state="RUNNABLE"):
        self.row = documented_request(self.manifest)
        self.row.pop("rootPassword")
        self.row.update(connectionName=spec.connection_name(self.manifest), instanceType="CLOUD_SQL_INSTANCE",
                        backendType="SECOND_GEN", state=state)
        if state == "PENDING_CREATE":
            self.operation("CREATE")
        elif state == "PENDING_DELETE":
            self.operation("DELETE")

    def operation(self, kind):
        operation = {"name": "operation-" + kind.lower() + "-123", "operationType": kind,
                     "targetProject": spec.PROJECT, "targetId": spec.instance_name(self.manifest["run_id"]),
                     "status": "PENDING", "insertTime": self.manifest["created_at"]}
        self.operations[operation["name"]] = operation
        return deepcopy(operation)

    def call(self, api, path, *, method="GET", body=None, missing_ok=False, timeout=None):
        assert api == "sqladmin" and 0 < timeout <= 30
        self.calls.append((api, path, method, deepcopy(body), timeout))
        if self.latency >= timeout:
            self.clock.now += timeout
            raise TimeoutError(PRIVATE)
        self.clock.now += self.latency
        if path == instance.BASE + "/instances/earningsnerd-db":
            assert method == "GET"
            return deepcopy(self.production)
        target = instance.BASE + "/instances/" + spec.instance_name(self.manifest["run_id"])
        if path == instance.BASE + "/instances" and method == "POST":
            assert self.row is None
            # Validate documented field placement, including the non-retained root password.
            assert body["rootPassword"] == PASSWORD and "rootPassword" not in body["settings"]
            assert body["settings"]["ipConfiguration"]["serverCaMode"] == "GOOGLE_MANAGED_INTERNAL_CA"
            assert body["settings"]["connectorEnforcement"] == "REQUIRED"
            self.prepare(state="PENDING_CREATE")
            if self.fail == "create_response_lost":
                raise RuntimeError(PRIVATE)
            result = next(iter(self.operations.values()))
            if self.corrupt:
                result = {**result, **self.corrupt}
            return deepcopy(result)
        if path == target + "?enableFinalBackup=false" and method == "DELETE":
            assert self.row is not None and self.row["state"] != "PENDING_CREATE"
            self.row["state"] = "PENDING_DELETE"
            result = self.operation("DELETE")
            if self.fail == "delete_response_lost":
                raise RuntimeError(PRIVATE)
            return result
        if path == target and method == "GET":
            if self.clock.now < self.row_visible_at:
                assert missing_ok
                return None
            if self.row is None:
                assert missing_ok
            return deepcopy(self.row)
        if path == instance.BASE + "/operations?instance=" + spec.instance_name(self.manifest["run_id"]) + "&maxResults=20":
            return {"items": deepcopy(list(self.operations.values())) if self.clock.now >= self.operations_visible_at else []}
        if path.startswith(instance.BASE + "/operations/"):
            operation = self.operations[path.rsplit("/", 1)[-1]]
            if not self.stuck:
                operation["status"] = "DONE"
                if self.completed_error:
                    operation["error"] = {"errors": [{"message": PRIVATE}]}
                if operation["operationType"] == "CREATE":
                    self.row["state"] = "FAILED" if self.completed_error else "RUNNABLE"
                elif not self.completed_error:
                    self.row = None
            return deepcopy(operation)
        raise AssertionError("Unexpected SQL Admin path")


def mutations(cloud):
    return [row for row in cloud.calls if row[2] in {"POST", "DELETE", "PUT", "PATCH"}]


def test_metadata_projects_only_production_engine_identity_without_credentials(clock, capsys):
    cloud = Cloud(manifest(), clock)
    result = instance.metadata(cloud)
    assert result == {"name": "earningsnerd-db", "project": spec.PROJECT, "region": spec.REGION,
                      "database_version": "POSTGRES_15"}
    assert len(cloud.calls) == 1 and not mutations(cloud)
    assert PRIVATE not in json.dumps(result) and capsys.readouterr().out == ""


@pytest.mark.parametrize("field,value", [("databaseVersion", "POSTGRES_16"), ("name", "another-db"),
                                       ("project", "another-project"), ("region", "us-east1")])
def test_unknown_production_engine_identity_refuses_without_writes(clock, field, value):
    cloud = Cloud(manifest(), clock)
    cloud.production[field] = value
    with pytest.raises(spec.Refused, match="production_postgres_major_unverified"):
        instance.metadata(cloud)
    assert not mutations(cloud)


@pytest.mark.parametrize("response_lost", [False, True])
def test_create_posts_once_then_verifies_operation_and_resource(clock, capsys, response_lost):
    m = manifest()
    cloud = Cloud(m, clock)
    if response_lost:
        cloud.fail = "create_response_lost"
    result = instance.create(cloud, m, PASSWORD)
    assert len(mutations(cloud)) == 1
    sent = mutations(cloud)[0][3]
    assert sent == documented_request(m)
    assert m["sql_instance"]["activation_policy"] == "ALWAYS" and m["sql_instance"]["database_flags"] == []
    assert sent["settings"]["tier"] == "db-custom-1-3840"
    assert sent["settings"]["dataDiskSizeGb"] == "10"
    assert sent["settings"]["userLabels"] == {"purpose": spec.PURPOSE, "run-id": "123", "plan-nonce": "b" * 32}
    assert result["state"] == "RUNNABLE" and result["operation_done"] and result["configuration_verified"]
    assert PASSWORD not in json.dumps(result) and PRIVATE not in json.dumps(result)
    assert all(row[0] == "sqladmin" for row in cloud.calls)
    assert capsys.readouterr().out == "" and capsys.readouterr().err == ""


def test_existing_owned_instance_is_not_adopted_by_new_create(clock):
    m = manifest()
    cloud = Cloud(m, clock)
    cloud.prepare()
    with pytest.raises(spec.Refused, match="sql_instance_already_exists"):
        instance.require_absent(cloud, m)
    with pytest.raises(spec.Refused, match="sql_instance_already_exists"):
        instance.create(cloud, m, PASSWORD)
    assert not mutations(cloud)


@pytest.mark.parametrize("field,value", [("targetProject", "elsewhere"), ("targetId", "earningsnerd-db"),
                                       ("operationType", "UPDATE"), ("name", "../operation"), ("status", PRIVATE)])
def test_create_never_trusts_an_operation_for_another_resource(clock, field, value):
    m = manifest()
    cloud = Cloud(m, clock)
    cloud.corrupt = {field: value}
    with pytest.raises(spec.Refused, match="sql_operation_identity") as error:
        instance.create(cloud, m, PASSWORD)
    assert PRIVATE not in str(error.value)
    assert len(mutations(cloud)) == 1


def test_provider_error_body_is_closed_and_not_a_success(clock, capsys):
    m = manifest()
    cloud = Cloud(m, clock)
    cloud.completed_error = True
    with pytest.raises(spec.Refused, match="sql_operation_failed") as error:
        instance.create(cloud, m, PASSWORD)
    assert PRIVATE not in str(error.value)
    assert capsys.readouterr().out == "" and capsys.readouterr().err == ""


@pytest.mark.parametrize("field,value", [("tier", "db-custom-64-245760"), ("storageAutoResize", True),
                                       ("dataDiskSizeGb", "100"), ("deletionProtectionEnabled", True),
                                       ("retainBackupsOnDelete", True), ("connectorEnforcement", "NOT_REQUIRED"),
                                       ("availabilityType", "REGIONAL"), ("edition", "ENTERPRISE_PLUS"),
                                       ("databaseFlags", [{"name": "max_connections", "value": "1000"}])])
def test_configuration_readback_rejects_cost_or_isolation_drift(clock, field, value):
    m = manifest()
    cloud = Cloud(m, clock)
    cloud.prepare()
    cloud.row["settings"][field] = value
    with pytest.raises(spec.Refused, match="sql_instance_configuration"):
        instance._configuration(cloud.row, m)


@pytest.mark.parametrize("block,field,value", [("ipConfiguration", "authorizedNetworks", [{"value": "0.0.0.0/0"}]),
    ("ipConfiguration", "serverCaMode", "CUSTOMER_MANAGED_CAS_CA"),
    ("ipConfiguration", "sslMode", "ALLOW_UNENCRYPTED_AND_ENCRYPTED"),
    ("backupConfiguration", "enabled", True), ("backupConfiguration", "pointInTimeRecoveryEnabled", True),
    ("backupConfiguration", "backupTier", "ENHANCED"), ("backupConfiguration", "backupTier", "ADVANCED"),
    ("finalBackupConfig", "enabled", True)])
def test_network_and_retention_configuration_is_fail_closed(clock, block, field, value):
    m = manifest()
    cloud = Cloud(m, clock)
    cloud.prepare()
    cloud.row["settings"][block][field] = value
    with pytest.raises(spec.Refused, match="sql_instance_configuration"):
        instance._configuration(cloud.row, m)


@pytest.mark.parametrize("state,response_lost", [("RUNNABLE", False), ("RUNNABLE", True),
                                                ("PENDING_CREATE", False), ("PENDING_DELETE", False)])
def test_delete_reconciles_pending_or_ambiguous_operation_without_sql_credentials(clock, state, response_lost):
    m = manifest()
    cloud = Cloud(m, clock)
    cloud.prepare(state=state)
    if response_lost:
        cloud.fail = "delete_response_lost"
    result = instance.delete(cloud, m)
    assert cloud.row is None and result["absence_verified"] and result["operation_done"]
    assert len(mutations(cloud)) == (0 if state == "PENDING_DELETE" else 1)
    assert all(row[0] == "sqladmin" for row in cloud.calls)
    assert PASSWORD not in json.dumps(result) and PRIVATE not in json.dumps(result)


def test_completed_delete_and_fresh_absence_prove_cleanup_without_new_mutation(clock):
    m = manifest()
    cloud = Cloud(m, clock)
    operation = cloud.operation("DELETE")
    cloud.operations[operation["name"]]["status"] = "DONE"
    result = instance.delete(cloud, m)
    assert result["absence_verified"] and result["operation_done"]
    assert not mutations(cloud)


@pytest.mark.parametrize("disappears", [True, False])
def test_done_delete_is_not_removal_until_instance_really_disappears(clock, disappears):
    m = manifest()
    cloud = Cloud(m, clock)
    cloud.prepare()
    target = instance.BASE + "/instances/" + spec.instance_name(m["run_id"])
    original, gone_at = cloud.call, clock.now + 15
    observed_after_done = []

    def lagged(api, path, **kwargs):
        before = deepcopy(cloud.row)
        if path == target and any(op["operationType"] == "DELETE" and op["status"] == "DONE"
                                  for op in cloud.operations.values()):
            observed_after_done.append(clock.now)
            if disappears and clock.now >= gone_at:
                cloud.row = None
        result = original(api, path, **kwargs)
        if "/operations/" in path and result.get("operationType") == "DELETE" and result["status"] == "DONE":
            cloud.row = before  # Provider acknowledgement precedes resource disappearance.
        return result

    cloud.call = lagged
    if disappears:
        assert instance.delete(cloud, m)["absence_verified"]
        assert clock.now >= gone_at and len(observed_after_done) >= 2 and cloud.row is None
    else:
        with pytest.raises(spec.Refused, match="sql_lifecycle_deadline"):
            instance.delete(cloud, m)
        assert cloud.row is not None
    assert len(mutations(cloud)) == 1


@pytest.mark.parametrize("kind", ["CREATE", "DELETE"])
def test_any_existing_lifecycle_history_blocks_same_plan_create_replay(clock, kind):
    m = manifest()
    cloud = Cloud(m, clock)
    operation = cloud.operation(kind)
    cloud.operations[operation["name"]]["status"] = "DONE"
    with pytest.raises(spec.Refused, match="sql_instance_history_exists"):
        instance.require_absent(cloud, m)
    with pytest.raises(spec.Refused, match="sql_instance_history_exists"):
        instance.create(cloud, m, PASSWORD)
    assert not mutations(cloud)


@pytest.mark.parametrize("stamp", [None, "invalid", "2000-01-01T00:00:00Z", "2099-01-01T00:00:00Z"])
def test_missing_stale_or_future_operation_cannot_prove_absence(clock, stamp):
    m = manifest()
    cloud = Cloud(m, clock)
    operation = cloud.operation("DELETE")
    cloud.operations[operation["name"]].update(status="DONE", insertTime=stamp)
    with pytest.raises(spec.Refused, match="sql_operation_time"):
        instance.delete(cloud, m)
    assert not mutations(cloud)


def test_operation_before_plan_is_refused_even_when_just_one_second_old(clock):
    m = manifest()
    cloud = Cloud(m, clock)
    operation = cloud.operation("CREATE")
    prior = (datetime.fromisoformat(m["created_at"]) - timedelta(seconds=1)).isoformat()
    cloud.operations[operation["name"]].update(status="DONE", insertTime=prior, error={"errors": [{}]})
    with pytest.raises(spec.Refused, match="sql_operation_time"):
        instance.delete(cloud, m)
    assert not mutations(cloud)


def test_absence_without_operation_evidence_remains_unverified_for_entire_budget(clock):
    m = manifest()
    cloud = Cloud(m, clock)
    start = clock.now
    with pytest.raises(spec.Refused, match="sql_lifecycle_deadline"):
        instance.delete(cloud, m)
    assert clock.now - start == 600 and not mutations(cloud)


def test_failed_create_done_and_fresh_absence_prove_no_instance(clock):
    m = manifest()
    cloud = Cloud(m, clock)
    operation = cloud.operation("CREATE")
    cloud.operations[operation["name"]].update(status="DONE", error={"errors": [{"message": PRIVATE}]})
    result = instance.delete(cloud, m)
    assert result["absence_verified"] and result["failed_create_done"]
    assert not mutations(cloud) and PRIVATE not in json.dumps(result)


@pytest.mark.parametrize("row_delay,operation_delay", [(10, 15), (15, 5), (5, 15)])
def test_delete_settles_delayed_instance_and_operation_visibility(clock, row_delay, operation_delay):
    m = manifest()
    cloud = Cloud(m, clock)
    cloud.prepare(state="PENDING_CREATE")
    cloud.row_visible_at = clock.now + row_delay
    cloud.operations_visible_at = clock.now + operation_delay
    result = instance.delete(cloud, m)
    assert result["absence_verified"] and cloud.row is None
    assert len(mutations(cloud)) == 1 and mutations(cloud)[0][2] == "DELETE"


def test_timed_out_ambiguous_create_can_materialize_during_cleanup(clock):
    m = manifest()
    cloud = Cloud(m, clock)
    cloud.fail = "create_response_lost"
    cloud.row_visible_at = clock.now + 610
    cloud.operations_visible_at = clock.now + 615
    with pytest.raises(spec.Refused, match="sql_lifecycle_deadline"):
        instance.create(cloud, m, PASSWORD)
    result = instance.delete(cloud, m)
    assert result["absence_verified"] and cloud.row is None
    assert [r[2] for r in mutations(cloud)] == ["POST", "DELETE"]


@pytest.mark.parametrize("label,value", [("purpose", "other"), ("run-id", "456"), ("plan-nonce", "d" * 32)])
def test_delete_does_not_adopt_named_resource_with_wrong_ownership(clock, label, value):
    m = manifest()
    cloud = Cloud(m, clock)
    cloud.prepare()
    cloud.row["settings"]["userLabels"][label] = value
    with pytest.raises(spec.Refused, match="sql_instance_ownership"):
        instance.delete(cloud, m)
    assert not mutations(cloud)


@pytest.mark.parametrize("tier", ["ENHANCED", "ADVANCED"])
@pytest.mark.parametrize("state", ["RUNNABLE", "PENDING_DELETE"])
def test_delete_refuses_external_backup_retention_instead_of_claiming_cleanup(clock, tier, state):
    m = manifest()
    cloud = Cloud(m, clock)
    cloud.prepare(state=state)
    cloud.row["settings"]["backupConfiguration"]["backupTier"] = tier
    with pytest.raises(spec.Refused, match="sql_delete_retention_or_dependency_drift"):
        instance.delete(cloud, m)
    assert not mutations(cloud)


def test_lost_create_response_cannot_adopt_other_nonce(clock):
    m = manifest()
    cloud = Cloud(m, clock)
    cloud.fail = "create_response_lost"
    original = cloud.prepare

    def replace(**kwargs):
        original(**kwargs)
        cloud.row["settings"]["userLabels"]["plan-nonce"] = "d" * 32

    cloud.prepare = replace
    with pytest.raises(spec.Refused, match="sql_instance_ownership"):
        instance.create(cloud, m, PASSWORD)
    assert len(mutations(cloud)) == 1


@pytest.mark.parametrize("operation", ["create", "delete"])
def test_lifecycle_polling_stops_at_one_shared_600_second_deadline(clock, operation):
    m = manifest()
    cloud = Cloud(m, clock)
    cloud.stuck = True
    if operation == "delete":
        cloud.prepare()
    start = clock.now
    with pytest.raises(spec.Refused, match="sql_lifecycle_deadline"):
        if operation == "create":
            instance.create(cloud, m, PASSWORD)
        else:
            instance.delete(cloud, m)
    assert clock.now - start == 600
    assert len(mutations(cloud)) == 1


def test_transport_timeout_is_clamped_to_lifecycle_remainder(clock):
    cloud = Cloud(manifest(), clock)
    cloud.latency = 60
    start = clock.now
    with pytest.raises(spec.Refused, match="sql_cloud_operation_unverified"):
        instance._call(cloud, instance.BASE + "/instances/earningsnerd-db", clock.now + 2)
    assert clock.now - start == 2 and cloud.calls[-1][-1] == 2


@pytest.mark.parametrize("operation", ["create", "delete", "require_absent"])
def test_tampered_instance_name_is_refused_before_cloud(operation, clock):
    m = manifest()
    cloud = Cloud(m, clock)
    m["sql_instance"]["name"] = "earningsnerd-db"
    with pytest.raises(spec.Refused):
        getattr(instance, operation)(cloud, m, PASSWORD) if operation == "create" else getattr(instance, operation)(cloud, m)
    assert not cloud.calls
