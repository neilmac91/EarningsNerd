# Run vitest before pushing any change to rendered text, numbers, or copy

Date: 2026-07-04   Area: test

**Context**: The pricing "show monthly cost" change flipped the displayed anchor ($390/yr → $32.50/mo). tsc, eslint, and `next build` all passed, and the screenshots looked right — but vitest was skipped and the component test asserted the exact old strings, so CI's frontend-tests job failed after the PR was already open.

**Rule**: Any change that alters rendered text, numbers, or copy MUST run `npx vitest run` before push — those are exactly what component tests assert, and neither the typechecker nor the build catches a changed string. Build + screenshot verifies rendering; only the test suite verifies the contract. When a test legitimately needs updating (behavior changed on purpose), update it to the new expected value in the same PR — don't just delete the assertion.

**Evidence**: `PricingPage.test.tsx` asserted the exact old strings ("$390"/"$290"); displayed anchor changed $390/yr → $32.50/mo.
