# Read-only capacity configuration inputs

The existing `describe-service` output omitted worker inputs, request concurrency and egress configuration. The added projection retains recognized command tokens and numeric worker environment values, plus the serving revision's concurrency/timeout, ingress and VPC annotation presence/egress mode. Missing or unfamiliar values remain unresolved. Arbitrary arguments, unrelated environment values and secret references are not exposed. No secret reference is resolved.

The operation still requires one latest-ready serving revision at 100% traffic. Its output distinguishes configured inputs from runtime facts: effective worker count and egress IP remain null. An absent command override does not prove the image command; annotation presence does not prove NAT routing. CPU/memory and actual running processes are outside this projection.

[Uvicorn settings](https://www.uvicorn.org/settings/) document the `WEB_CONCURRENCY` fallback for workers. [Cloud Run maximum instances](https://docs.cloud.google.com/run/docs/configuring/max-instances) and [autoscaling behavior](https://docs.cloud.google.com/run/docs/about-instance-autoscaling) document temporary excess instances and revision overlap. Configuration alone does not establish a hard connection ceiling or safe cohort size.

The exact embedded Python was executed offline against normal, absent, secret-reference and unrecognized-command fixtures. All four withheld the arbitrary private sentinel; unresolved effective workers and IP stayed null. YAML parsed; the required workflow reader gates passed 138 tests, and the frontend Node lockstep gate passed three. Hashes and scope are in `local-proof.json`. No application code or tests changed, and this verification performed no cloud dispatch or paid call.

Review must confirm that the command allowlist cannot expose arbitrary text and that missing values are not converted into defaults. A subsequent existing Ops dispatch can supply current configured inputs; it cannot retrospectively measure rollout overlap, live worker count or representative load.
