# Read-only capacity configuration inputs

The existing `describe-service` output omitted worker inputs, request concurrency and egress configuration. The added projection retains command-override presence and numeric worker environment values, plus the serving revision's concurrency/timeout, ingress and VPC annotation presence/egress mode. Missing or unfamiliar values remain unresolved. Concurrency accepts only integers 1–1000 and timeout only integers 1–3600; booleans, text, mappings, zero and out-of-range values become null. All raw commands and arguments, unrelated environment values and secret references are withheld. No secret reference is resolved.

The operation still requires one latest-ready serving revision at 100% traffic. Its output distinguishes configured inputs from runtime facts: effective worker count and egress IP remain null. An absent command override does not prove the image command; annotation presence does not prove NAT routing. CPU/memory and actual running processes are outside this projection.

[Uvicorn settings](https://www.uvicorn.org/settings/) document the `WEB_CONCURRENCY` fallback for workers. [Cloud Run maximum instances](https://docs.cloud.google.com/run/docs/configuring/max-instances) and [autoscaling behavior](https://docs.cloud.google.com/run/docs/about-instance-autoscaling) document temporary excess instances and revision overlap. Configuration alone does not establish a hard connection ceiling or safe cohort size.

The exact embedded Python was executed offline against normal, absent, secret-reference and unrecognized-command fixtures. Ten cases, including malformed numeric fields and integer bounds, withheld the arbitrary private sentinel; unresolved effective workers and IP stayed null. YAML parsed; the required workflow reader gates passed 138 tests, and the frontend Node lockstep gate passed three. Hashes and scope are in `local-proof.json`. Those initial checks performed no cloud dispatch or paid call. Independent review subsequently required the focused enduring gate described below.

Review must confirm that command values never enter the output and that missing values are not converted into defaults. A subsequent existing Ops dispatch can supply current configured inputs; it cannot retrospectively measure rollout overlap, live worker count or representative load.

## Independent review correction

The initial token allowlist admitted standalone numeric arguments outside recognized option positions. Two fresh refutation passes confirmed that `command: ["python", "123"]` was emitted, and that none of the existing workflow reader gates exercised this projection. Raw command arrays are now always withheld; only override presence is reported. This deliberately keeps effective workers unresolved.

`backend/tests/unit/test_capacity_projection_privacy.py` executes the exact embedded projection over 20 normal/adverse combinations, including numeric command arguments, valid worker commands, arbitrary text, secret references, malformed bounded numbers and missing overrides. It is the one enduring confidentiality gate. A committed-state fault/restored proof and the full backend gate are recorded after this correction. Because the new test is under `backend/`, merging this PR deploys the backend and requires serial deployment verification.
