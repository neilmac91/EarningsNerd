# Don't test error paths through a vi.fn-mocked module — vitest 4 re-reports the handled error and fails the test

Date: 2026-07-06   Area: test

**Context**: The F4 fix pointed `fetchFilingContent` at the shared axios client, and its spec
was rewritten to mock `@/lib/api/client` with the repo's usual `vi.fn()` factory pattern
(peers-api.spec.ts, fundamentals-api.spec.ts). The two happy-path tests passed; the
error-propagation test failed with the RAW error ("Request failed with status 404") attributed
to the test — even though the caller handled it. Every variant through `vi.fn()` failed the same
way: `mockRejectedValue`, a lazy `mockImplementation(() => Promise.reject(...))`, a synchronous
`throw`, and even catching the error with try/catch inside the test. Under vitest 4 (4.1.9 here),
the mock's call-result tracking re-reports the error as a test failure regardless of in-test
handling. Replacing `vi.fn()` with a plain reassignable impl holder
(`let getImpl = ...; vi.mock(..., () => ({ default: { get: (...a) => getImpl(...a) } }))`)
made the identical assertions pass.

**Rule**: When a test needs a mocked module member to THROW or REJECT, don't route the call
through `vi.fn()` — use a plain function via a mutable holder inside the `vi.mock` factory.
Keep `vi.fn()` for happy-path call/arg tracking (the existing spec convention). If a test fails
with the raw mocked error pointing at the mock's own construction site, suspect this tracking
behavior before suspecting the code under test.

**Evidence**: `frontend/tests/unit/filing-content-api.spec.ts` (header comment + the plain-holder
pattern); PR #568 CI run 28801074636 (the vi.fn variants failing); vitest 4.1.9,
`frontend/package.json`.
