"""The verifier's resource line names its verdict, each failing condition and its figures; never runtime text.

A live verify-apply (Ops 43124458892) passed its browser stage and live cleanup, then stopped at
`measurement (resource-acceptance)`, one closed code for several conditions. These tests hold the line that now
explains such a refusal: it agrees with verify_runtime.resource_acceptance, which decides, on every input tried; it
prints only bounded numbers and closed names, and says whose record it is; a failed browser run prints the answering
instance's line, its cleanup runs whatever that read does, and the read never replaces the browser's failure; a receipt
check prints the run's signed record once it verifies, or the answering instance's when there is no receipt.
"""
from __future__ import annotations

import importlib.util
import itertools
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ops/feedback_media"))
SPEC = importlib.util.spec_from_file_location("feedback_verify_resources_ops", ROOT / "ops/feedback_media/verify_manage.py")
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)
RUNTIME_SPEC = importlib.util.spec_from_file_location("feedback_verify_resources_runtime",
                                                      ROOT / "ops/feedback_media/verify_runtime.py")
runtime = importlib.util.module_from_spec(RUNTIME_SPEC)
RUNTIME_SPEC.loader.exec_module(runtime)

CAP = 1073741824
MIB = 1024 * 1024
BOUND = int(CAP * .85)  # 912680550; the acceptance compares against 912680550.4
FAILURE = "Live browser verification failed at measurement (resource-acceptance)"
BOOT = "1a2b3c4d-5e6f-4a1b-8c2d-0123456789ab"
INSTANCE = "the answering instance since its start, boot 1a2b3c4d"
SIGNED = "the run's signed receipt"


def record(**changes):
    """A resource record shaped as the verifier's receipt answer carries it."""
    base = {"sample_count": 4000, "rss_peak_bytes": 520 * MIB, "cgroup_sample_peak_bytes": 610 * MIB,
            "cgroup_kernel_peak_bytes": 700 * MIB, "cgroup_memory_limit_bytes": CAP, "configured_memory_limit_bytes": CAP,
            "self_high_water_rss_bytes": 300 * MIB, "worker_high_water_rss_bytes": 90 * MIB, "last_process_count": 1,
            "conservative_process_bound_bytes": 570 * MIB, "method": verify.RESOURCE_METHOD,
            "worker_limits": dict(verify.WORKER_LIMITS), "unexplained_children": False, "acceptance_passed": True,
            "sample_age_seconds": 0.02, "evidence_basis": verify.EVIDENCE_BASES[0]}
    return {**base, **changes}


def test_the_constants_match_the_runtime_that_writes_the_record():
    """The cap, the record's keys and its fixed strings are the ones verify_runtime.py writes."""
    source = (ROOT / "ops/feedback_media/verify_runtime.py").read_text()
    assert verify.MEMORY_CAP_BYTES == CAP
    assert re.search(r"\bcap = 1073741824\b", source) and re.search(r'"configured_memory_limit_bytes": 1073741824\b', source)
    assert f'"method": "{verify.RESOURCE_METHOD}"' in source
    for basis in verify.EVIDENCE_BASES:
        assert f'"{basis}"' in source
    assert set(verify.RESOURCE_NUMBERS) <= set(re.findall(r'"([a-z_]+)"', source))
    assert verify.WORKER_LIMITS == {"feedback_image_service": 1, "feedback_storage_worker_service": 2}


def test_a_passing_record_prints_its_figures_and_names_no_condition():
    assert verify.resources_line(record(), SIGNED) == (
        "Verifier resources (the run's signed receipt): acceptance passed; conditions failed: none; samples 4000; "
        "processes at the last sample 1; "
        "unexplained child none; last sample 0.02 s old; cgroup limit 1073741824 bytes; kernel peak 734003200 bytes; "
        "sampled peak 639631360 bytes; process-tree peak 545259520 bytes; own high-water 314572800 bytes; "
        "worker high-water 94371840 bytes; bound 912680550 bytes")


@pytest.mark.parametrize("changes, names", [
    ({"configured_memory_limit_bytes": 2 * CAP}, "configured-limit"),
    ({"sample_count": 4}, "samples"),
    ({"unexplained_children": True}, "unexplained-child"),
    ({"last_process_count": 2}, "process-count"),
    ({"sample_age_seconds": 1.5}, "sample-age"),
    ({"cgroup_memory_limit_bytes": CAP - 1}, "cgroup-limit"),
    ({"cgroup_kernel_peak_bytes": BOUND + 1}, "kernel-peak"),
    ({"cgroup_kernel_peak_bytes": 0}, "kernel-peak"),
    ({"cgroup_sample_peak_bytes": BOUND + 1}, "sampled-peak"),
    ({"cgroup_kernel_peak_bytes": BOUND + 1, "cgroup_sample_peak_bytes": BOUND + 1, "last_process_count": 3},
     "process-count, kernel-peak, sampled-peak"),
    ({"cgroup_kernel_peak_bytes": None, "self_high_water_rss_bytes": 0}, "high-water-unread"),
    ({"cgroup_kernel_peak_bytes": None, "cgroup_sample_peak_bytes": None}, "sampled-peak"),
    ({"cgroup_kernel_peak_bytes": None, "self_high_water_rss_bytes": 600 * MIB, "worker_high_water_rss_bytes": 200 * MIB},
     "process-bound"),
])
def test_a_refused_record_names_every_failing_condition(changes, names):
    line = verify.resources_line(record(acceptance_passed=False, **changes), INSTANCE)
    assert line.startswith(f"Verifier resources ({INSTANCE}): acceptance refused; conditions failed: {names}; samples ")


def test_the_printed_verdict_is_the_verifiers_own_even_when_no_condition_is_named():
    """A verdict skewed from the conditions named here (another runtime source) still prints as the verifier gave it."""
    assert verify.resources_line(record(acceptance_passed=False), SIGNED).startswith(
        f"Verifier resources ({SIGNED}): acceptance refused; conditions failed: none; ")


def receipt_with(resources):
    """A receipt of the counts-only shape counts_only_receipt admits (its values are verify_receipt's to check)."""
    observed = {
        "database": {**dict.fromkeys(("feedback", "submitted", "attachments", "fixture_users", "available", "deleted",
                                      "pending", "published_attachments", "confirmed_generation_deletions"), 0),
                     "normalized_metadata_valid": True},
        "notifications": {"accepted": 1, "rejected": 0, "attachment_counts": [3], "admin_link_valid": True,
                          "no_image_payload": True},
        "resources": resources,
        "cleanup": {"dry_run": False, "eligible": 3, "deleted": 3, "errors": 0, "overdue": 0, "pending_verification": 0}}
    payload = dict.fromkeys(("schema", "purpose", "run_id", "completed_at", "image_digest", "runtime_source_sha256",
                             "verification_suite_sha256", "frontend_tree", "browser_assertions"), "x")
    return {"payload": {**payload, "observed": observed}, "signature": "f" * 64}


@pytest.mark.parametrize("resources, admitted", [
    (record(), True),
    (record(error="withheld runtime text"), False),
    (record(sample_age_seconds=10**400), False),
    (record(method="another method"), False),
    (record(cgroup_kernel_peak_bytes=None, cgroup_memory_limit_bytes=None, evidence_basis=verify.EVIDENCE_BASES[2]), True),
    (record(evidence_basis="kernel peak unavailable; conservative process bound plus sampled cgroup"), False),
])
def test_the_receipt_allow_list_still_checks_its_resources_through_the_shared_helper(resources, admitted):
    """counts_only_receipt keeps runtime text out of a retained receipt; its resources check is valid_resources."""
    assert verify.counts_only_receipt(receipt_with(resources)) is admitted


def test_without_a_kernel_peak_the_line_says_so():
    line = verify.resources_line(record(cgroup_kernel_peak_bytes=None, cgroup_memory_limit_bytes=None), SIGNED)
    assert "; cgroup limit unread; kernel peak unexposed; sampled peak 639631360 bytes;" in line
    assert "conditions failed: none;" in line


def test_a_meminfo_sample_is_named_as_the_instance_memory_in_use():
    """Where no cgroup memory file reads (Cloud Run's second generation), the sample is MemTotal - MemAvailable."""
    meminfo = record(cgroup_kernel_peak_bytes=None, cgroup_memory_limit_bytes=None, evidence_basis=verify.EVIDENCE_BASES[2])
    assert verify.valid_resources(meminfo)
    assert ("; cgroup limit unread; kernel peak unexposed; "
            "sampled peak 639631360 bytes (instance memory in use, /proc/meminfo); process-tree peak ") in (
        verify.resources_line(meminfo, SIGNED))
    assert "conditions failed: none;" in verify.resources_line(meminfo, SIGNED)
    refused = verify.resources_line({**meminfo, "cgroup_sample_peak_bytes": BOUND + 1, "acceptance_passed": False}, SIGNED)
    assert "conditions failed: sampled-peak; " in refused and "(instance memory in use, /proc/meminfo)" in refused
    for basis in verify.EVIDENCE_BASES[:2]:  # the process-bound basis is the one the runtime writes beside no peak
        other = record(cgroup_kernel_peak_bytes=None, cgroup_memory_limit_bytes=None, evidence_basis=basis)
        assert "; sampled peak 639631360 bytes; process-tree peak " in verify.resources_line(other, SIGNED)


def test_the_named_conditions_agree_with_the_runtime_acceptance_on_every_combination():
    """resource_refusals is empty exactly when verify_runtime.resource_acceptance passes the same record."""
    tried = 0
    for (samples, unexplained, processes, age, limit, peak, sample, own, worker) in itertools.product(
            (4, 5), (False, True), (1, 2), (0, 1, 1.01), (None, CAP, CAP - 1), (None, 0, 1, BOUND, BOUND + 1),
            (None, 0, 1, BOUND, BOUND + 1), (0, 1, 300 * MIB), (0, 1, 90 * MIB, 300 * MIB)):
        memory = record(sample_count=samples, unexplained_children=unexplained, last_process_count=processes,
                        sample_age_seconds=age, cgroup_memory_limit_bytes=limit, cgroup_kernel_peak_bytes=peak,
                        cgroup_sample_peak_bytes=sample, self_high_water_rss_bytes=own, worker_high_water_rss_bytes=worker)
        assert (verify.resource_refusals(memory) == []) is runtime.resource_acceptance(memory), memory
        tried += 1
    assert tried == 2 * 2 * 2 * 3 * 3 * 5 * 5 * 3 * 4


@pytest.mark.parametrize("shape", [
    None, "text", [], {},
    record(error="withheld runtime text"),
    {name: value for name, value in record().items() if name != "sample_count"},
    record(sample_count="5"), record(sample_count=True), record(sample_count=-1), record(sample_count=2**63),
    record(last_process_count=1.0), record(cgroup_memory_limit_bytes="max"), record(configured_memory_limit_bytes=None),
    record(method="another method"), record(evidence_basis="another basis"),
    record(worker_limits={"feedback_image_service": 2, "feedback_storage_worker_service": 2}),
    record(sample_age_seconds=math.nan), record(sample_age_seconds=math.inf), record(sample_age_seconds=-0.5),
    record(sample_age_seconds=7201), record(sample_age_seconds=None), record(sample_age_seconds=True),
    record(sample_age_seconds=10**400), record(sample_age_seconds=-(10**400)),
    record(unexplained_children=1), record(acceptance_passed="yes"),
])
def test_any_other_shape_is_unavailable_and_prints_nothing_it_carries(shape):
    """Never an exception either: an integer beyond float range once overflowed the age check's isfinite."""
    assert verify.resources_line(shape, INSTANCE) == f"Verifier resources ({INSTANCE}): unavailable (no counts-only resource record)"


@pytest.mark.parametrize("answer, source", [
    ({"boot_id": BOOT}, INSTANCE),
    ({"boot_id": BOOT.upper()}, "the answering instance since its start"),
    ({"boot_id": "1a2b3c4d-5e6f-1a1b-8c2d-0123456789ab"}, "the answering instance since its start"),
    ({"boot_id": BOOT + "\nwithheld"}, "the answering instance since its start"),
    ({"boot_id": 7}, "the answering instance since its start"),
    ({}, "the answering instance since its start"),
])
def test_a_live_record_names_the_instance_that_answered_and_only_a_uuid4_boot(answer, source):
    assert verify.instance_source(answer) == source


def test_a_failed_browser_run_prints_the_resource_line_before_its_cleanup(monkeypatch, capsys):
    events = []

    def browser(*_args):
        raise verify.media.OperationError(FAILURE)

    def control(cloud, origin, key, run_id, path, payload=None):
        events.append(("control", cloud, origin, key, run_id, path, payload))
        return {"resources": record(cgroup_kernel_peak_bytes=950 * MIB, acceptance_passed=False), "receipt": None,
                "boot_id": BOOT}

    monkeypatch.setattr(verify, "browser", browser)
    monkeypatch.setattr(verify, "control", control)
    monkeypatch.setattr(verify, "execute_cleanup", lambda cloud: events.append(("cleanup", cloud)))
    with pytest.raises(verify.media.OperationError) as failure:
        verify.browse_then_clean("cloud", "https://verify.example", "key", "40210191699-1", "image", {})
    assert str(failure.value) == FAILURE
    assert events == [("control", "cloud", "https://verify.example", "key", "40210191699-1", "receipt", None),
                      ("cleanup", "cloud")]
    assert capsys.readouterr().out.startswith(
        f"Verifier resources ({INSTANCE}): acceptance refused; conditions failed: kernel-peak; samples 4000;")


@pytest.mark.parametrize("error", [verify.media.OperationError("Private verification control request failed; response withheld"),
                                   AttributeError("withheld detail"), RuntimeError("withheld detail"), None])
def test_a_failed_resource_read_says_so_and_never_replaces_the_browser_failure(monkeypatch, capsys, error):
    """A raising read, and an answer whose line cannot be formed (a list has no .get), both say unavailable."""
    cleanups = []

    def browser(*_args):
        raise verify.media.OperationError(FAILURE)

    def control(*args, **_kwargs):
        reads.append(args[-1])
        if error is None:
            return ["withheld detail"]
        raise error

    reads = []
    monkeypatch.setattr(verify, "browser", browser)
    monkeypatch.setattr(verify, "control", control)
    monkeypatch.setattr(verify, "execute_cleanup", cleanups.append)
    with pytest.raises(verify.media.OperationError) as failure:
        verify.browse_then_clean("cloud", "https://verify.example", "key", "40210191699-1", "image", {})
    # One read, never read_receipt's four-minute retry loop, before the bounded cleanup.
    assert str(failure.value) == FAILURE and cleanups == ["cloud"] and reads == ["receipt"]
    out = capsys.readouterr().out
    assert out == "Verifier resources: unavailable (receipt read failed)\n" and "withheld" not in out


def test_a_passing_or_interrupted_browser_run_makes_no_extra_read(monkeypatch, capsys):
    reads, cleanups = [], []
    monkeypatch.setattr(verify, "control", lambda *args, **_kwargs: reads.append(args))
    monkeypatch.setattr(verify, "execute_cleanup", cleanups.append)
    monkeypatch.setattr(verify, "browser", lambda *_args: None)
    verify.browse_then_clean("cloud", "https://verify.example", "key", "40210191699-1", "image", {})

    def interrupted(*_args):
        raise KeyboardInterrupt

    monkeypatch.setattr(verify, "browser", interrupted)
    with pytest.raises(KeyboardInterrupt):
        verify.browse_then_clean("cloud", "https://verify.example", "key", "40210191699-1", "image", {})
    assert reads == [] and cleanups == ["cloud", "cloud"] and capsys.readouterr().out == ""


def test_an_interrupted_resource_read_still_runs_the_in_run_cleanup(monkeypatch):
    cleanups = []

    def browser(*_args):
        raise verify.media.OperationError(FAILURE)

    def control(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(verify, "browser", browser)
    monkeypatch.setattr(verify, "control", control)
    monkeypatch.setattr(verify, "execute_cleanup", cleanups.append)
    with pytest.raises(KeyboardInterrupt):
        verify.browse_then_clean("cloud", "https://verify.example", "key", "40210191699-1", "image", {})
    assert cleanups == ["cloud"]


def test_a_receipt_check_without_a_receipt_prints_the_answering_instance_line(monkeypatch, capsys):
    service = {"template": {"containers": [{"env": [{"name": "FEEDBACK_VERIFY_RUN_ID", "value": "40210191699-1"}]}]}}

    class Cloud:
        def call(self, api, path, **_kwargs):
            assert (api, path) == ("run", "v2/" + verify.SERVICE)
            return service

    monkeypatch.setattr(verify, "current_image", lambda *_args: "image")
    monkeypatch.setattr(verify, "fingerprints", dict)
    monkeypatch.setattr(verify, "assert_private_service", lambda *_args: "https://verify.example")
    monkeypatch.setattr(verify, "secret", lambda *_args, **_kwargs: ("key", "1"))
    monkeypatch.setattr(verify, "runtime_spec", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(verify, "contains_spec", lambda *_args: True)
    monkeypatch.setattr(verify, "read_receipt", lambda *_args: {"resources": record(), "receipt": None, "boot_id": BOOT})
    with pytest.raises(verify.media.OperationError, match="A completed live verification receipt is required"):
        verify.require_receipt(Cloud(), {})
    assert capsys.readouterr().out == verify.resources_line(record(), INSTANCE) + "\n"


def test_a_receipt_check_with_a_verified_receipt_prints_the_run_record_not_the_instance(monkeypatch, capsys):
    """The run's own measured record, from its signed receipt, and only after the receipt verifies."""
    service = {"template": {"containers": [{"env": [{"name": "FEEDBACK_VERIFY_RUN_ID", "value": "40210191699-1"}]}]}}
    run_record = record(cgroup_kernel_peak_bytes=800 * MIB)
    receipt = {"payload": {"observed": {"resources": run_record}}, "signature": "f" * 64}
    verified = []

    class Cloud:
        def call(self, api, path, **_kwargs):
            return service

    monkeypatch.setattr(verify, "current_image", lambda *_args: "image")
    monkeypatch.setattr(verify, "fingerprints", dict)
    monkeypatch.setattr(verify, "assert_private_service", lambda *_args: "https://verify.example")
    monkeypatch.setattr(verify, "secret", lambda *_args, **_kwargs: ("key", "1"))
    monkeypatch.setattr(verify, "runtime_spec", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(verify, "contains_spec", lambda *_args: True)
    monkeypatch.setattr(verify, "read_receipt", lambda *_args: {"resources": record(sample_count=6), "receipt": receipt,
                                                                 "boot_id": BOOT})
    monkeypatch.setattr(verify, "verify_receipt", lambda *args: verified.append(args[0]))
    assert verify.require_receipt(Cloud(), {}) is receipt and verified == [receipt]
    assert capsys.readouterr().out.splitlines() == [
        verify.resources_line(run_record, SIGNED),
        "Live isolated feedback verification receipt: current image and sources verified"]


def test_a_receipt_that_fails_verification_prints_no_resource_line(monkeypatch, capsys):
    service = {"template": {"containers": [{"env": [{"name": "FEEDBACK_VERIFY_RUN_ID", "value": "40210191699-1"}]}]}}

    class Cloud:
        def call(self, api, path, **_kwargs):
            return service

    def refuse(*_args):
        raise verify.media.OperationError("Live verification receipt is invalid")

    monkeypatch.setattr(verify, "current_image", lambda *_args: "image")
    monkeypatch.setattr(verify, "fingerprints", dict)
    monkeypatch.setattr(verify, "assert_private_service", lambda *_args: "https://verify.example")
    monkeypatch.setattr(verify, "secret", lambda *_args, **_kwargs: ("key", "1"))
    monkeypatch.setattr(verify, "runtime_spec", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(verify, "contains_spec", lambda *_args: True)
    monkeypatch.setattr(verify, "read_receipt", lambda *_args: {"resources": record(), "receipt": {"payload": {}},
                                                                 "boot_id": BOOT})
    monkeypatch.setattr(verify, "verify_receipt", refuse)
    with pytest.raises(verify.media.OperationError, match="invalid"):
        verify.require_receipt(Cloud(), {})
    assert capsys.readouterr().out == ""
