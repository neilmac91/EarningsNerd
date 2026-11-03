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
2. **Preflight.** Before the first write, and read-only:
   - test the reads every run makes: Resource Manager `testIamPermissions` for project grants, and the
     resource itself for a resource-scoped prerequisite (`actAs` on the identity; image read on the Artifact
     Registry repository of an image the apply deploys, which the caller needs apart from the Cloud Run service
     agent). If anything is missing, refuse with the missing names;
   - then read every existing resource a later step would refuse rather than repair (one owned by something
     else, or in a state the apply never converges, such as a deleted or `DISABLED` role or a schedule an
     update cannot resume), and refuse it. Only a read that finds a resource absent (404) plans its create: a
     denied read stops with its label, and a malformed answer is refused, so neither is planned as absent or
     as already approved;
   - then test only the writes the state it read needs: a create for what is absent, a set-policy for a
     missing grant, an update for what exists. A resource or grant made by hand in the approved shape then
     needs no create or set-policy permission. Each write decides with the same test the plan used, so a
     write the plan left out never happens untested.
   Each refusal changes nothing; the write steps keep their own ownership and etag checks, and a policy read
   without an etag is refused, because its write-back would not be conditional.
3. **Closed failures.** Print a refused provider call as its label and a closed error class:
   `<step> [<permission>] failed (HTTP n; <status>; <reason>; denied <permission>)`. The permission is named
   only when one of the steps names it, otherwise "an unlisted permission". An operation that fails after
   Cloud Run accepted it prints `<step> [<permission>]: Cloud Run operation failed (<status>)`, and a dropped
   connection prints `<step> [<permission>] unavailable or unreadable`. Never print provider text.
4. **Inspect reads everything.** Read every component before failing, as an independent inventory
   (`lessons/ops-denied-reads-report-unverified.md`), with one component per independently readable resource
   and its own sub-resources, so a failed read never stops another resource's checks:
   - absent is incomplete;
   - a failed read is `UNVERIFIED (<the refused call's label and class>)`;
   - readable drift is refused, and refused always wins.
5. **Know the preflight's blind spots.**
   - It sees the identity's own grants at the project, `actAs` on the identity and image read on the
     repository.
   - A disabled API or an organization policy passes the preflight and still surfaces at the step, so the
     labels matter.
   - A grant held only on a single resource is invisible to the project test. The preflight then reports it
     missing and refuses a run the step would have allowed, so grant provisioning permissions at the project.

**Gate.** Media provisioning, in `backend/tests/unit/test_feedback_media_infrastructure.py`:
- `test_provisioning_preflight_names_exactly_the_permissions_its_steps_use` holds `PROVISION_PERMISSIONS` equal
  to the permissions its steps name, apart from the two tested on their own resources: `iam.serviceAccounts.actAs`
  on the runtime identity and `artifactregistry.repositories.downloadArtifacts` on the image repository. It runs
  from nothing and over existing resources, with the real `Cloud.wait` polling each Cloud Run operation. It fails
  a call whose label names no permission, or one its HTTP method cannot need (a read must name only `get`,
  `list` or `getIamPolicy`; a write names what it changes), and the capability label used outside
  `testIamPermissions`. Absent resources answer 404 as Google does, and so do the policies and execution lists
  under them, with one policy per bucket, so a read that forgets `missing_ok` fails it.
- `test_provision_tests_exactly_the_writes_its_state_needs` holds the write set a run tests equal to the write
  permissions its write labels name, from nothing, over existing resources, after a founder bootstrap, with
  grants missing, with grants held through a later binding of the same role, and in mixed states (one bucket
  absent or without its grant, a conditional or other-role grant on the job, one alert policy absent).
  `test_provision_reads_are_exactly_the_reads_its_runs_make` holds the every-run set to read verbs and to the
  reads the runs make. `test_a_founder_bootstrap_provisions_without_role_bucket_or_bucket_grant_permissions`,
  `test_provision_refuses_a_malformed_or_denied_read_before_any_write_never_planning_it`,
  `test_a_malformed_policy_never_reads_as_private_or_granted` and
  `test_bind_writes_exactly_when_the_planners_bound_test_is_false` pin the planning's reads and writes: a
  denial at each planning read, and malformed policies and resources. `test_only_a_404_reads_as_absent` pins
  the transport rule they rest on, and `test_each_write_step_rechecks_what_it_writes_after_the_plan` pins the
  write-time ownership and etag checks against a state that changes after the plan.
- `test_provision_from_nothing_tests_its_capability_before_its_first_write`,
  `test_provision_refuses_before_any_write_when_its_identity_lacks_a_permission` and
  `test_provision_refuses_a_state_it_would_not_repair_before_any_write` pin the order, and
  `test_provision_still_converges_drift_in_resources_this_feature_owns` keeps the state check from over-refusing,
  a bucket without its runtime grant included.
- `test_a_refused_provider_call_names_its_step_and_closed_error_class_never_its_payload`,
  `test_a_failed_cloud_run_operation_names_only_its_step_and_closed_status` and
  `test_a_dropped_connection_is_an_unreadable_provider_call_not_a_traceback` pin the output, and
  `test_every_permission_a_step_label_names_can_be_named_in_a_refusal` keeps each label's permissions nameable.
- `test_an_unreadable_component_is_unverified_and_never_masks_readable_drift`,
  `test_a_failed_read_never_stops_another_resources_drift_check` and
  `test_inspection_names_the_role_state_and_still_reports_every_other_component` and
  `test_inspection_names_the_state_of_an_owned_schedule_provisioning_will_not_resume` pin the inventory.

In `backend/tests/unit/test_feedback_media_verification_ops.py`,
`test_the_verification_preflight_tests_every_permission_its_reads_before_writing_name` holds the verifier's
labelled media-prerequisite reads, its operation poll and its revision read to its `PROJECT_PERMISSIONS`, and
`test_a_founder_bootstrap_removes_every_owner_equivalent_and_identity_write_from_verify_apply`,
`test_without_a_bootstrap_verify_apply_still_names_every_grant_it_would_make`,
`test_a_bootstrap_in_another_shape_or_unreadable_is_refused_before_any_write`,
`test_ensure_identity_writes_the_identity_policy_exactly_when_bootstrap_planning_does`,
`test_verify_inspect_reports_what_verify_apply_would_lack_without_writing` and
`test_verify_apply_plans_exactly_the_writes_each_state_needs` (a first run, a re-run, partial bootstraps and
refusals, each against the writes read off its write paths) pin its bootstrap planning; its fixture answers 404
where Google does. `test_a_denied_verifier_planning_read_refuses_before_any_write_is_tested` pins a denial at each
of its planning reads, and `test_each_verifier_write_step_rechecks_what_it_writes_after_the_plan` its write-time
ownership and etag checks.

Review-checked: whether a label names the exact permission its call needs (the gate checks only that it fits
the call's method); the verifier's other calls, which are unlabelled today and print the API name with the
closed class, and its writes, so its bootstrap plan is held to its write paths by review and the focused cases,
not by a gate; and every other apply.

**Evidence.** The five Ops runs above; neilmac91/EarningsNerd#1957, which adds the preflight, labels and
inventory; `docs/DEPLOYMENT.md`, "Private feedback screenshots".
