"""Ops describe-service: read back the API service and its serving revision, the pregenerate job and the
private task worker (traffic, env, sizing, ingress, entrypoint verdict and invoker policy).

Run by ops.yml's describe-service step as `python3 ops/describe/service.py` (REGION and SERVICE come from
the workflow env); stdlib only. Every gcloud read, the API service describe included, goes through
gcloud_json(), which captures stderr and reduces a failure to a closed class. Env values print only through
the allow-list, the SEC pins only as a bounded digit string; URLs, command and argument values never print
(lessons/ops-capacity-projection-withholds-command-values.md). Gates: backend/tests/unit/
test_capacity_projection_privacy.py, test_prod_flag_visibility.py and test_ops_stderr_withheld.py.
"""
import json
import os
import re
import subprocess
WORKER = "earningsnerd-task-worker"
GCLOUD_TIMEOUT = 100
PUBLIC_PRINCIPALS = ("allUsers", "allAuthenticatedUsers")
failures = []
def fail(message):
    # Readable evidence of drift is announced now and raised once at the end, so one dispatch lists
    # every defect and the later blocks still print. Reads that gate later reads stay immediate exits.
    failures.append(message)
    print(f"::error::Unresolved production configuration: {message}")
def stop(message):
    # An immediate exit still names every defect collected before it.
    raise SystemExit("Unresolved production configuration: " + "; ".join(failures + [message]))
def percent(target):
    value = target.get("percent", 0)
    return value if type(value) is int else 0
def resolve_traffic(who, label, status):
    # A tagged revision stays routable at its own URL whatever its traffic share, so a
    # leftover tag keeps a retired image serving beside the release.
    tagged = [target.get("revisionName") for target in status.get("traffic", []) if target.get("tag")]
    if tagged:
        stop(f"tagged traffic targets {tagged} on the {who}; remove stale revision tags.")
    # Only revisionName/percent are echoed: a traffic target can carry a private service URL.
    traffic = [{"revisionName": target.get("revisionName"), "percent": percent(target)}
               for target in status.get("traffic", []) if percent(target) > 0]
    print(f"{label}:", json.dumps(traffic, sort_keys=True))
    latest = status.get("latestReadyRevisionName")
    created = status.get("latestCreatedRevisionName")
    if not latest:
        cause = "no latest ready revision"
    elif created != latest:
        cause = f"latest created revision {created} is not ready (latest ready {latest})"
    elif len(traffic) != 1 or traffic[0]["percent"] != 100 or traffic[0]["revisionName"] != latest:
        cause = f"traffic is not a single 100% target on {latest}"
    else:
        return latest
    stop(f"require 100% traffic on the latest ready revision of the {who}; {cause}.")
def gcloud_json(argv):
    # The one seam for every gcloud read this readback makes. stderr is captured and reduced to a closed class, never
    # echoed: gcloud's error text can name the acting principal or a private URL.
    try:
        return json.loads(subprocess.check_output(
            ["gcloud", "run", *argv, "--region=" + os.environ["REGION"], "--format=json"],
            text=True, stderr=subprocess.PIPE, timeout=GCLOUD_TIMEOUT)), None
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except subprocess.CalledProcessError as exc:
        text = exc.stderr or ""
        if "PERMISSION_DENIED" in text:
            return None, "permission_denied"
        if "NOT_FOUND" in text:
            return None, "not_found"
        if "UNAVAILABLE" in text or "DEADLINE_EXCEEDED" in text:
            return None, "unavailable"
        return None, f"error (gcloud exit {exc.returncode})"
    except OSError:
        return None, "error (gcloud not executable)"
    except ValueError:
        return None, "unreadable_response"
def describe(kind, name):
    data, failure = gcloud_json([kind, "describe", name])
    if failure:
        stop(f"cannot describe {kind} {name} ({failure}).")
    return data
# The API service is read through the same seam (it was a shell read that let gcloud print its own error text).
svc = describe("services", os.environ["SERVICE"])
latest = resolve_traffic("Service", "Serving traffic", svc["status"])
revision = describe("revisions", latest)
pregenerate = describe("jobs", "earningsnerd-pregenerate")
# Only these non-sensitive flag/config values are echoed; everything else is name-only.
allow = {
    "USE_STATEMENT_FINANCIALS", "ENABLE_FPI_FILINGS",
    "STREAM_SECTION_REVEAL", "AI_DEFAULT_MODEL", "OPENAI_BASE_URL", "ENVIRONMENT",
    "TRUSTED_PROXY_HOPS", "COOKIE_DOMAIN",
    "NOTABLE_FILINGS_ENABLED", "AI_EVIDENCE_SNAP", "AI_FIGURE_TRACE_GATE",
    "AI_FORWARD_QUOTE_GATE", "AI_ATTRIBUTION_GATE", "AI_ATTRIBUTION_VERIFY",
    "USE_STRUCTURED_OUTPUT", "CALENDAR_INDEX_FILTER_ENABLED",
    "REGISTRATION_MODE", "AI_FALLBACK_MODEL", "AI_FALLBACK_BASE_URL",
    "SENTRY_RELEASE", "DB_POOL_SIZE", "DB_MAX_OVERFLOW",
    # CODE RED D3: the per-process SEC pins, durable delivery and the insider switch.
    "SEC_RATE_LIMIT_PER_SECOND", "EDGAR_RATE_LIMIT_PER_SEC", "DURABLE_TASKS_ENABLED",
    "ENABLE_INSIDER_ACTIVITY",
    # The worker/API role split the deploy pins (true on the worker, false on the service).
    "TASKS_WORKER_PROCESS",
}
# Defaults from app/config.py; never include credentials in this allow-list.
flag_defaults = {
    "USE_STATEMENT_FINANCIALS": True,
    "ENABLE_FPI_FILINGS": False,
    "STREAM_SECTION_REVEAL": False,
    "NOTABLE_FILINGS_ENABLED": False,
    "AI_EVIDENCE_SNAP": False,
    "AI_FIGURE_TRACE_GATE": False,
    "AI_FORWARD_QUOTE_GATE": False,
    "AI_ATTRIBUTION_GATE": False,
    "AI_ATTRIBUTION_VERIFY": False,
    "USE_STRUCTURED_OUTPUT": False,
    "CALENDAR_INDEX_FILTER_ENABLED": False,
    "REGISTRATION_MODE": "public",
    "AI_FALLBACK_MODEL": "",
    "AI_FALLBACK_BASE_URL": "",
    "SEC_RATE_LIMIT_PER_SECOND": 10,
    "DURABLE_TASKS_ENABLED": False,
    "ENABLE_INSIDER_ACTIVITY": False,
    "TASKS_WORKER_PROCESS": False,
}
# ci.yml's "Update configured private task worker" step sets this entrypoint (gate:
# test_prod_flag_visibility.py). Only match/mismatch is printed, never the observed values.
expected_worker_command = ["uvicorn"]
expected_worker_args = ["task_worker_main:app", "--host", "0.0.0.0", "--port", "8080",
                        "--proxy-headers", "--forwarded-allow-ips=*"]
SEC_PINS = ("SEC_RATE_LIMIT_PER_SECOND", "EDGAR_RATE_LIMIT_PER_SEC")
def bounded_pin(value):
    # A pin value is echoed only as a short digit string; anything else is withheld (it could be a secret
    # placed in the wrong variable), in the env block as well as in the verdict.
    return repr(value) if isinstance(value, str) and re.fullmatch(r"[0-9]{1,6}", value) else "<value withheld: not a plain numeric string>"
def show(label, containers):
    if len(containers) != 1:
        stop(f"{label} needs one application container.")
    print(label)
    print("image:", containers[0]["image"])
    print("Absent values below use checkout Settings defaults; verify these against the reported image before pinning.")
    seen = set()
    for e in containers[0].get("env", []):
        name = e.get("name", "?")
        seen.add(name)
        if "valueFrom" in e or "valueSource" in e:
            print(f"{name} = <secret-ref>")
        elif name in SEC_PINS:
            print(f"{name} = {bounded_pin(e.get('value'))}")
        elif name in allow:
            print(f"{name} = {e.get('value')!r}")
        else:
            print(f"{name} = <set; value withheld>")
    for flag, default in flag_defaults.items():
        if flag not in seen:
            message = "Settings default applies (True)" if default is True else f"Settings default applies ({default!r})"
            print(f"{flag} = <NOT SET -> {message}>")
    # Not a Settings field: edgartools reads it at import, so its default is the library's.
    if "EDGAR_RATE_LIMIT_PER_SEC" not in seen:
        print("EDGAR_RATE_LIMIT_PER_SEC = <NOT SET -> edgartools default 9>")
def plain_value(containers, name):
    for entry in containers[0].get("env", []):
        if entry.get("name") == name and "valueFrom" not in entry and "valueSource" not in entry:
            return entry.get("value")
    return None
def pin_state(entry):
    # A pin counts only as the plain string "1"; an echoed value is bounded to a short digit string.
    if entry is None:
        return False, "<missing>"
    if "valueFrom" in entry or "valueSource" in entry:
        return False, "<secret-ref>"
    value = entry.get("value")
    return value == "1", bounded_pin(value)
def require_sec_pins(label, containers):
    # CODE RED D3: both SEC buckets are pinned to exactly 1 as plain values on every process.
    env = {entry.get("name"): entry for entry in containers[0].get("env", [])}
    if len(env) != len(containers[0].get("env", [])):
        fail(f"{label} has a duplicate or nameless env entry")
    for pin in ("SEC_RATE_LIMIT_PER_SECOND", "EDGAR_RATE_LIMIT_PER_SEC"):
        ok, shown = pin_state(env.get(pin))
        if not ok:
            fail(f"{label} must pin {pin}=1 as a plain value, got {shown}")
def bounded_integer(value, maximum):
    return value if type(value) is int and 1 <= value <= maximum else None
def bounded_text(value, pattern):
    return value if isinstance(value, str) and re.fullmatch(pattern, value) else "unset_or_unresolved"
def annotation_text(value, pattern, absent):
    # An absent annotation has a documented meaning; a value outside the closed grammar is withheld.
    return absent if value is None else bounded_text(value, pattern)
def sizing(service_label, revision_label, service, revision, expected_allocation):
    service_notes = service.get("metadata", {}).get("annotations", {})
    revision_notes = revision.get("metadata", {}).get("annotations", {})
    limits = revision["spec"]["containers"][0].get("resources", {}).get("limits", {})
    print(f"{service_label} minScale:", annotation_text(service_notes.get("run.googleapis.com/minScale"), r"[0-9]{1,4}",
                                                        "absent (service-level minimum off, 0 per Cloud Run docs)"))
    print(f"{service_label} maxScale:", bounded_text(service_notes.get("run.googleapis.com/maxScale"), r"[0-9]{1,4}"))
    print(f"{revision_label} minScale:", bounded_text(revision_notes.get("autoscaling.knative.dev/minScale"), r"[0-9]{1,4}"))
    print(f"{revision_label} maxScale:", bounded_text(revision_notes.get("autoscaling.knative.dev/maxScale"), r"[0-9]{1,4}"))
    print(f"{revision_label} cpu:", bounded_text(limits.get("cpu"), r"[0-9]+(\.[0-9]+)?m?"))
    print(f"{revision_label} memory:", bounded_text(limits.get("memory"), r"[0-9]+(\.[0-9]+)?(Mi|Gi|M|G)"))
    # Cloud Run documents an absent cpu-throttling annotation as request-based (throttled) CPU.
    throttling = revision_notes.get("run.googleapis.com/cpu-throttling")
    observed = {"false": "always-allocated", "true": "request-based", None: "request-based"}.get(throttling)
    detail = {"false": "cpu-throttling=false", "true": "cpu-throttling=true", None: "cpu-throttling annotation absent"}.get(throttling)
    if observed is None:
        print(f"{revision_label} CPU allocation: unset_or_unresolved -> UNRESOLVED (expected {expected_allocation})")
    else:
        verdict = "MATCH" if observed == expected_allocation else "MISMATCH"
        print(f"{revision_label} CPU allocation: {observed} ({detail}) -> {verdict} (expected {expected_allocation})")
    print(f"{revision_label} startup CPU boost:", bounded_text(revision_notes.get("run.googleapis.com/startup-cpu-boost"), r"true|false"))
    print(f"{revision_label} containerConcurrency:", bounded_integer(revision["spec"].get("containerConcurrency"), 1000))
    print(f"{revision_label} timeoutSeconds:", bounded_integer(revision["spec"].get("timeoutSeconds"), 3600))
show("Serving revision: " + latest, revision["spec"]["containers"])
require_sec_pins("Serving revision " + latest, revision["spec"]["containers"])
show("Job: earningsnerd-pregenerate", pregenerate["spec"]["template"]["spec"]["template"]["spec"]["containers"])
# ci.yml pins request-based CPU together with DURABLE_TASKS_ENABLED=true and always-allocated otherwise.
service_allocation = "request-based" if plain_value(revision["spec"]["containers"], "DURABLE_TASKS_ENABLED") == "true" else "always-allocated"
sizing("Service", "Revision", svc, revision, service_allocation)
# Capacity inputs only: never print arbitrary command arguments or worker env text.
# An absent override is not evidence of the image's effective command or worker count.
# Printed before the worker read so a worker defect never costs the service's evidence.
container = revision["spec"]["containers"][0]
command = container.get("command") or []
args = container.get("args") or []
command_evidence = {"state": "image_default_unresolved"}
if command or args:
    command_evidence = {"state": "override_present_values_withheld"}
env_by_name = {entry.get("name"): entry for entry in container.get("env", [])}
worker_env = {}
for name in ("WEB_CONCURRENCY", "UVICORN_WORKERS"):
    entry = env_by_name.get(name)
    if entry is None:
        worker_env[name] = {"state": "not_set"}
    elif "valueFrom" in entry or "valueSource" in entry:
        worker_env[name] = {"state": "secret_ref_unresolved"}
    elif re.fullmatch(r"[1-9][0-9]{0,2}", str(entry.get("value", ""))):
        worker_env[name] = {"state": "literal", "value": int(entry["value"])}
    else:
        worker_env[name] = {"state": "present_unresolved_value_withheld"}
annotations = revision.get("metadata", {}).get("annotations", {})
egress = annotations.get("run.googleapis.com/vpc-access-egress")
ingress = svc.get("metadata", {}).get("annotations", {}).get("run.googleapis.com/ingress")
capacity_config = {
    "revision": latest,
    "container_command": command_evidence,
    "worker_environment": worker_env,
    "gunicorn_args_present_value_withheld": "GUNICORN_CMD_ARGS" in env_by_name,
    "container_concurrency": bounded_integer(revision["spec"].get("containerConcurrency"), 1000),
    "request_timeout_seconds": bounded_integer(revision["spec"].get("timeoutSeconds"), 3600),
    "vpc_egress": egress if egress in ("all-traffic", "private-ranges-only") else "unset_or_unresolved",
    "vpc_connector_annotation_present": "run.googleapis.com/vpc-access-connector" in annotations,
    "direct_vpc_annotation_present": "run.googleapis.com/network-interfaces" in annotations,
    "ingress": ingress if ingress in ("all", "internal", "internal-and-cloud-load-balancing") else "unset_or_unresolved",
    "effective_worker_count": None,
    "egress_ip_identity": None,
    "limit": "Configured inputs only; image defaults, running process count, egress IP and instantaneous rollout overlap are not measured.",
}
print("Capacity configuration:", json.dumps(capacity_config, sort_keys=True))
# Private task worker: same allow-list and pin rule; its URL (status.url, TASKS_WORKER_URL) is never echoed.
worker = describe("services", WORKER)
worker_latest = resolve_traffic("Worker", "Worker serving traffic", worker.get("status", {}))
worker_revision = describe("revisions", worker_latest)
show("Worker revision: " + worker_latest, worker_revision["spec"]["containers"])
require_sec_pins("Worker revision " + worker_latest, worker_revision["spec"]["containers"])
sizing("Worker service", "Worker revision", worker, worker_revision, "request-based")
worker_notes = worker.get("metadata", {}).get("annotations", {})
print("Worker ingress:", annotation_text(worker_notes.get("run.googleapis.com/ingress"), r"all|internal|internal-and-cloud-load-balancing",
                                         "absent (annotation not set; gcloud deploy default is all)"))
worker_container = worker_revision["spec"]["containers"][0]
observed_entrypoint = (worker_container.get("command") or [], worker_container.get("args") or [])
print("Worker command/args:", "matches the committed worker entrypoint (values withheld)"
      if observed_entrypoint == (expected_worker_command, expected_worker_args)
      else "DOES NOT MATCH the committed worker entrypoint (values withheld; compare ci.yml's --command/--args)")
# Public exposure has two legs: the invoker IAM check switch (in the describe JSON) and the policy.
if str(worker_notes.get("run.googleapis.com/invoker-iam-disabled", "")).strip().lower() == "true":
    print("Worker invoker IAM check: DISABLED")
    fail("the task worker's invoker IAM check is disabled (public without any binding)")
else:
    print("Worker invoker IAM check: enforced")
def invoker_policy(name):
    # run.services.get excludes run.services.getIamPolicy: a denied read is UNVERIFIED with its failure
    # class, never PRIVATE and never a crash. Only an exactly understood policy shape is classified,
    # and a public principal on ANY role is public (several predefined roles carry run.routes.invoke).
    policy, failure = gcloud_json(["services", "get-iam-policy", name])
    if failure:
        return "UNVERIFIED", failure
    bindings = policy.get("bindings", []) if isinstance(policy, dict) else None
    if not isinstance(bindings, list) or not all(
            isinstance(b, dict) and isinstance(b.get("role"), str) and isinstance(b.get("members", []), list)
            and all(isinstance(m, str) for m in b.get("members", [])) for b in bindings):
        return "UNVERIFIED", "unreadable_response"
    public = sorted({(b["role"], m) for b in bindings for m in b.get("members", []) if m in PUBLIC_PRINCIPALS})
    if public:
        return "PUBLIC", ", ".join(f"{member} on {role}" for role, member in public)
    invoker_members = sum(len(b.get("members", [])) for b in bindings if b["role"] == "roles/run.invoker")
    detail = f"{invoker_members} roles/run.invoker member(s); {len(bindings)} binding(s)"
    if invoker_members == 0:
        detail += "; no invoker binding: Cloud Tasks cannot invoke the worker (founder IAM item)"
    return "PRIVATE", detail
policy_state, policy_detail = invoker_policy(WORKER)
print(f"Worker invoker policy: {policy_state} ({policy_detail})")
if policy_state == "PUBLIC":
    fail(f"the task worker admits a public principal: {policy_detail}")
elif policy_state == "UNVERIFIED":
    remedy = {
        "permission_denied": "grant the Ops identity run.services.getIamPolicy (roles/run.viewer; a founder-approved IAM change) and re-dispatch",
        "not_found": "the worker name or region did not resolve for the policy read; check the worker exists in this region",
    }.get(policy_detail, "transient or failed read; re-dispatch describe-service before concluding")
    print(f"::warning::Worker invoker policy UNVERIFIED ({policy_detail}): not evidence of private access; {remedy}. "
          "The durable-tasks checklist item stays open until a run prints PRIVATE.")
if failures:
    print(f"describe-service: FAIL ({len(failures)} invariant failure(s))")
    raise SystemExit("Unresolved production configuration: " + "; ".join(failures))
print("describe-service: PASS" + (f"; UNVERIFIED: worker invoker policy ({policy_detail})" if policy_state == "UNVERIFIED" else ""))
