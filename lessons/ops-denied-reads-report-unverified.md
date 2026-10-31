# A denied optional read-back reports UNVERIFIED with a closed failure class; fail closed only on readable evidence

Date: 2026-10-10 · Area: ops / read-backs

**Context.** The read-back PR (neilmac91/EarningsNerd#1181, CODE RED records 20–22) taught the Ops
workflow's `describe-service` to read the private task worker's invoker IAM policy. Whether the Ops
identity may read a service's IAM policy was unknown until a run tried; a design that failed the step on
a denied read would have turned an IAM permission question into a red operation that proves nothing
about the worker, and a design that printed `PRIVATE` on a denied read would have claimed evidence it
did not have. The same shape recurs for every optional read-back that depends on a permission the
operator has not yet observed. A required read is different: the service, revision and job describes
carry the traffic, pins and sizing every later check needs, so an unreadable required resource
keeps the operation nonzero. A dependent service read stops
when later checks need its result; an independent job inventory continues through every fixed
resource and retains its readable evidence.

**Rule.** An optional read-back that cannot read (one whose absence leaves the operation's required
evidence intact, as the worker's invoker-policy read does) reports that it could not read, never a
verdict: print `<item>: UNVERIFIED (<class>)` where the class comes from a closed set derived from the
tool's stderr (`permission_denied`, `not_found`, `unavailable`, `timeout`, `unreadable_response`,
`error (… exit N)`, `error (… not executable)`), never the stderr text itself (it can name the acting
principal or a private URL); add one workflow warning with the class-specific remedy; let the step pass
with a qualified verdict line so the other checks still run and still fail closed on readable evidence;
and make the operator's checklist item complete only when a run prints the positive verdict
(`Worker invoker policy: PRIVATE`). Fail closed only on readable evidence: a public principal on any
binding, a disabled IAM check, a pin that reads other than `1`, traffic that reads tagged or split.
Never let UNVERIFIED mask a collected failure. A required read that cannot read never passes.
Dependent service reads stop with the closed
class before checks that need their result. Independent job reads report every fixed resource,
continue after unreadable descriptions and finish INCOMPLETE/nonzero, or FAIL/nonzero when
readable drift also exists. Never print PASS from a partial inventory. Both collectors own their
gcloud reads in Python (`ops/describe/service.py`, `ops/describe/jobs.py`); neither emits raw stderr.
A resource provisioned separately is not a reason to suppress other evidence or create that
resource merely to satisfy the diagnostic.

**Gate.** In `backend/tests/unit/test_prod_flag_visibility.py`,
`test_ops_renderer_reports_denied_invoker_policy_as_unverified` pins the denied classes, the single
warning, the qualified verdict and that a denied read never prints `PRIVATE`;
`test_ops_renderer_treats_malformed_policy_as_unverified` pins `unreadable_response`;
`test_ops_renderer_unverified_never_masks_a_fail` pins that UNVERIFIED never masks a collected failure;
and `test_ops_renderer_fails_closed_on_failed_describe` pins that a failed required read in the
describe-service code (the revision, pregenerate-job, worker and worker-revision describes) stops the
step with its class, and `test_ops_renderer_fails_closed_on_failed_service_describe` pins the same for
the API service's own describe, `error (gcloud not executable)` included;
`backend/tests/unit/test_ops_stderr_withheld.py` runs the describe-service, describe-jobs and logs-probe
steps against a fake gcloud and pins that no gcloud stderr reaches their log (its `INHERITED` map lists the
ops.yml calls that still let it through). `test_ops_describe_jobs.py` exercises failures at
multiple positions, closed classes, malformed descriptions, readable drift alongside an
unreadable resource, and complete absence; its collector continues through all nine reads and
never passes an incomplete inventory. A planted break-on-error mutation proves the later-evidence
guard fails; `docs/DEPLOYMENT.md` states the rule beside the checklist. The first live run (ops run 38053869837,
2026-10-10T12:57Z) read the policy and printed `PRIVATE`, so the UNVERIFIED path stayed unexercised in
production; the rule stands for the next read that a permission withholds.
