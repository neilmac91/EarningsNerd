# Test every fail-closed check with a genuine input it must accept; refusals alone pass while it refuses everything

Date: 2026-10-16   Area: test

**Context**: The Resend webhook's signature check (`verify_webhook_signature` in
`backend/app/routers/webhooks.py`) was written from a prose reading of the Svix scheme. It keyed the
HMAC with the secret's raw `whsec_…` text and compared a hex digest, while Svix keys it with the
base64-decoded text after the prefix and sends a base64 digest. So it refused every genuine delivery:
clicks, bounces and complaints. A check that fails closed fails quietly: the endpoint answers 401
and logs one error line per delivery, and nothing a user sees breaks. The alert-click measurement
(E11c) that reads those webhooks recorded nothing. No test called the check, and a refusal-only test would have passed
too. #1281's second review found the defect by reading the code, not by any test (todo E20).

**Rule**: A fail-closed check (a signature, a token, an allowlist match) needs at least one test
with a genuine input it must accept, taken from outside the implementation: for a provider
signature, the provider's own published example (secret, headers, body, signature), pinned with its
source URL. A signer the test builds from the same reading of the docs proves nothing until it
reproduces that example. Refusal cases come after the accept case, never instead of it.

**Evidence**: `backend/tests/unit/test_resend_webhook_signature.py` checks the example on
https://docs.svix.com/receiving/verifying-payloads/how-manual and ties the test's signer to it. Given
the module-level clock import the test patches, the pre-E20 implementation fails that test and
eleven more on assertions; dropped in unchanged, every test errors at setup on the missing import. Partly gated: that file pins this
webhook. The next verifier's accept case is review-checked.
