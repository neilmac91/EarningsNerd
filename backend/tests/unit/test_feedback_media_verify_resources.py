"""The verifier's resource line names its verdict, each failing condition and its figures; never runtime text.

A live verify-apply (Ops 43124458892) passed its browser stage and live cleanup, then stopped at
`measurement (resource-acceptance)`, one closed code for several conditions. These tests hold the line that now
explains such a refusal: it agrees with verify_runtime.resource_acceptance, which decides, on every input tried; it
prints only bounded numbers and closed names; a failed browser run prints it before the cleanup, and its own read can
never replace the browser's failure; every receipt read prints it before the receipt check.
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
UNAVAILABLE = "Verifier resources: unavailable (no counts-only resource record)"


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
    """The cap, the record's keys and its two fixed strings are the ones verify_runtime.py writes."""
    source = (ROOT / "ops/feedback_media/verify_runtime.py").read_text()
    assert verify.MEMORY_CAP_BYTES == CAP
    assert "cap = 1073741824" in source and '"configured_memory_limit_bytes": 1073741824' in source
    assert f'"method": "{verify.RESOURCE_METHOD}"' in source
    for basis in verify.EVIDENCE_BASES:
        assert f'"{basis}"' in source
    assert set(verify.RESOURCE_NUMBERS) <= set(re.findall(r'"([a-z_]+)"', source))
    assert verify.WORKER_LIMITS == {"feedback_image_service": 1, "feedback_storage_worker_service": 2}


def test_a_passing_record_prints_its_figures_and_names_no_condition():
    assert verify.resources_line(record()) == (
        "Verifier resources: acceptance passed; conditions failed: none; samples 4000; processes at the last sample 1; "
        "unexplained child none; last sample 0.02 s old; cgroup limit 1073741824 bytes; kernel peak 734003200 bytes; "
        "sampled peak 639631360 bytes; process-tree peak 545259520 bytes; own high-water 314572800 bytes; "
        "worker high-water 94371840 bytes; bound 912680550 bytes")


@pytest.mark.parametrize("changes, names", [
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
    line = verify.resources_line(record(acceptance_passed=False, **changes))
    assert line.startswith(f"Verifier resources: acceptance refused; conditions failed: {names}; samples ")


def test_without_a_kernel_peak_the_line_says_so():
    line = verify.resources_line(record(cgroup_kernel_peak_bytes=None, cgroup_memory_limit_bytes=None))
    assert "; cgroup limit unread; kernel peak unexposed; sampled peak 639631360 bytes;" in line
    assert "conditions failed: none;" in line


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
    record(unexplained_children=1), record(acceptance_passed="yes"),
])
def test_any_other_shape_is_unavailable_and_prints_nothing_it_carries(shape):
    assert verify.resources_line(shape) == UNAVAILABLE


def test_a_failed_browser_run_prints_the_resource_line_before_its_cleanup(monkeypatch, capsys):
    events = []

    def browser(*_args):
        raise verify.media.OperationError(FAILURE)

    def control(cloud, origin, key, run_id, path, payload=None):
        events.append(("control", cloud, origin, key, run_id, path, payload))
        return {"resources": record(cgroup_kernel_peak_bytes=950 * MIB, acceptance_passed=False), "receipt": None}

    monkeypatch.setattr(verify, "browser", browser)
    monkeypatch.setattr(verify, "control", control)
    monkeypatch.setattr(verify, "execute_cleanup", lambda cloud: events.append(("cleanup", cloud)))
    with pytest.raises(verify.media.OperationError) as failure:
        verify.browse_then_clean("cloud", "https://verify.example", "key", "40210191699-1", "image", {})
    assert str(failure.value) == FAILURE
    assert events == [("control", "cloud", "https://verify.example", "key", "40210191699-1", "receipt", None),
                      ("cleanup", "cloud")]
    assert capsys.readouterr().out.startswith(
        "Verifier resources: acceptance refused; conditions failed: kernel-peak; samples 4000;")


@pytest.mark.parametrize("error", [verify.media.OperationError("Private verification control request failed; response withheld"),
                                   AttributeError("withheld detail"), RuntimeError("withheld detail")])
def test_a_failed_resource_read_says_so_and_never_replaces_the_browser_failure(monkeypatch, capsys, error):
    cleanups = []

    def browser(*_args):
        raise verify.media.OperationError(FAILURE)

    def control(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(verify, "browser", browser)
    monkeypatch.setattr(verify, "control", control)
    monkeypatch.setattr(verify, "execute_cleanup", cleanups.append)
    with pytest.raises(verify.media.OperationError) as failure:
        verify.browse_then_clean("cloud", "https://verify.example", "key", "40210191699-1", "image", {})
    assert str(failure.value) == FAILURE and cleanups == ["cloud"]
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


def test_every_receipt_read_prints_the_resource_line_before_the_receipt_check(monkeypatch, capsys):
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
    monkeypatch.setattr(verify, "read_receipt", lambda *_args: {"resources": record(), "receipt": None})
    with pytest.raises(verify.media.OperationError, match="A completed live verification receipt is required"):
        verify.require_receipt(Cloud(), {})
    assert capsys.readouterr().out == verify.resources_line(record()) + "\n"
