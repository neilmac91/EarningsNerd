# Contract tests (SSE stream, auth flow, Stripe webhooks) must not be edited in the same PR as the code they guard

**Area:** testing · **Date:** 2026-07-06

The SSE stream contract (T1), the auth-flow suite, and the Stripe webhook tests are anchors: they pin behavior a refactor must preserve. Editing them in the same PR as the code they guard defeats their purpose — you can silently move the goalposts.

**Rule:** in a refactor PR, a contract test may be edited ONLY to drop references to a symbol deleted in that same PR. Any other change to a contract test = STOP and surface it as an explicit, signed-off contract change with its updated anchor (that is how S1's flag-off pins were removed — deliberately, with sign-off).
