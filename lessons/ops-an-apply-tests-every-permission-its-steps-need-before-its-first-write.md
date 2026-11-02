# Test every permission an apply's steps need before its first write, and have each failure name its step and permission

Date: 2026-11-02 · Area: ops / protected applies (PB-03)

**Context.** Between 2026-10-25 and 2026-11-02, five feedback-media Ops dispatches failed (Ops 40216512380,
40219380103, 40238146711, 40245986374, 41399763125). None of their messages could be acted on.
- An approved provision printed only `logging operation failed (HTTP 403)`. It could not say whether the metric
  read or the metric create was refused.
- Inspect printed one message for an absent, deleted, disabled or differing custom role, then stopped before
  the buckets, job, schedule and alerts.
- `ops/feedback_media/manage.py` had no permission preflight, unlike the verifier beside it. Each missing
  grant therefore surfaced only when its step ran, after earlier writes, and every discovery cost a fresh
  founder approval. Without a preflight, a missing `iam.roles.create` would have failed after the heartbeat
  metric and two enabled alert policies already existed.

**Rule.** For an Ops apply that writes several cloud resources (a single-write apply, such as the upload
switch's enable or disable, fails at its one write with nothing partial):
1. **Label.** Label every provider call with its step and the IAM permission it needs.
2. **Preflight.** Test that permission set, read-only, before the first write: Resource Manager
   `testIamPermissions` for project grants, and the identity resource itself for `actAs`. If anything is
   missing, refuse with the missing names and change nothing.
3. **Closed failures.** Print a refused provider call as its label and a closed error class:
   `<step> [<permission>] failed (HTTP n; <status>; <reason>; denied <permission>)`. The permission is named
   only when one of the steps names it, otherwise "an unlisted permission". An operation that fails after
   Cloud Run accepted it prints `Cloud Run operation failed (<status>)` alone. Never print provider text.
4. **Inspect reads everything.** Read every component before failing, as an independent inventory
   (`lessons/ops-denied-reads-report-unverified.md`):
   - absent is incomplete;
   - a failed read is `UNVERIFIED (<the refused call's label and class>)`;
   - readable drift is refused, and refused always wins.
5. **Know the preflight's blind spots.**
   - It sees the identity's own grants at the project, and `actAs` on the identity.
   - A disabled API or an organization policy passes the preflight and still surfaces at the step, so the
     labels matter.
   - A grant held only on a single resource is invisible to the project test. The preflight then reports it
     missing and refuses a run the step would have allowed, so grant provisioning permissions at the project.

**Gate.** Media provisioning, in `backend/tests/unit/test_feedback_media_infrastructure.py`:
- `test_provisioning_preflight_names_exactly_the_permissions_its_steps_use` holds `PROVISION_PERMISSIONS` equal
  to the permissions its steps name, apart from `iam.serviceAccounts.actAs`, which is tested on the runtime
  identity. It runs from nothing and over existing resources, and it fails a call whose label names no
  permission, or the capability label used outside `testIamPermissions`.
- `test_provision_from_nothing_tests_its_capability_before_its_first_write` and
  `test_provision_refuses_before_any_write_when_its_identity_lacks_a_permission` pin the order.
- `test_a_refused_provider_call_names_its_step_and_closed_error_class_never_its_payload` and
  `test_a_failed_cloud_run_operation_names_only_its_closed_status` pin the output.
- `test_an_unreadable_component_is_unverified_and_never_masks_readable_drift` and
  `test_inspection_names_the_role_state_and_still_reports_every_other_component` pin the inventory.

In `backend/tests/unit/test_feedback_media_verification_ops.py`,
`test_the_verification_preflight_tests_every_permission_its_reads_before_writing_name` holds the verifier's
labelled media-prerequisite reads, its operation poll and its revision read to its `PROJECT_PERMISSIONS`.

Review-checked: the verifier's other calls, which are unlabelled today and print the API name with the closed
class, and its writes; and every other apply.

**Evidence.** The five Ops runs above; neilmac91/EarningsNerd#1957, which adds the preflight, labels and
inventory; `docs/DEPLOYMENT.md`, "Private feedback screenshots".
