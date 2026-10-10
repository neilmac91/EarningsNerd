# A denied read-back reports UNVERIFIED with a closed failure class; fail closed only on readable evidence

Date: 2026-10-10 · Area: ops / read-backs

**Context.** The read-back PR (neilmac91/EarningsNerd#1181, CODE RED records 20–22) taught the Ops
workflow's `describe-service` to read the private task worker's invoker IAM policy. Whether the Ops
identity may read a service's IAM policy was unknown until a run tried; a design that failed the step on
a denied read would have turned an IAM permission question into a red operation that proves nothing
about the worker, and a design that printed `PRIVATE` on a denied read would have claimed evidence it
did not have. The same shape recurs for every read-back that depends on a permission the operator has
not yet observed: traffic, pins and policy are facts only when the read succeeds.

**Rule.** A read-back that cannot read reports that it could not read, never a verdict: print
`<item>: UNVERIFIED (<class>)` where the class comes from a closed set derived from the tool's stderr
(`permission_denied`, `not_found`, `unavailable`, `timeout`, `unreadable_response`, `error (… exit N)`),
never the stderr text itself (it can name the acting principal or a private URL); add one workflow
warning with the class-specific remedy; let the step pass with a qualified verdict line so the other
checks still run and still fail closed on readable evidence; and make the operator's checklist item
complete only when a run prints the positive verdict (`Worker invoker policy: PRIVATE`). Fail closed
only on readable evidence: a public principal on any binding, a disabled IAM check, a pin that reads
other than `1`, traffic that reads tagged or split. Never let UNVERIFIED mask a collected failure.

**Gate.** In `backend/tests/unit/test_prod_flag_visibility.py`,
`test_ops_renderer_reports_denied_invoker_policy_as_unverified` pins the denied classes, the single
warning, the qualified verdict and that a denied read never prints `PRIVATE`;
`test_ops_renderer_treats_malformed_policy_as_unverified` pins `unreadable_response`; and
`test_ops_renderer_unverified_never_masks_a_fail` pins that UNVERIFIED never masks a collected failure; `docs/DEPLOYMENT.md` states the rule beside the checklist. The
first live run (ops run 38053869837, 2026-10-10T12:57Z) read the policy and printed `PRIVATE`, so the
UNVERIFIED path stayed unexercised in production; the rule stands for the next read that a permission
withholds.
