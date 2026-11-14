# Prove error reporting by receiving the error at an address you control, on the same build and layout that will serve; a client that exists, a flush that returns and an event seen once are not delivery

Date: 2026-11-14   Area: ops, observability, hosting

**Context**: The go/no-go for moving the frontend to Cloudflare Workers had "Sentry captures a server error" as a
criterion. #2051 marked it met: a scratch route threw on the Worker, and the founder saw the issue in Sentry
(`JAVASCRIPT-NEXTJS-2S`). The Next server's own Sentry client was not sending anything. Its `node:https` transport
never completes a send in the Workers runtime, and its `ContextLines` integration, which reads each stack frame's
source file from disk, never returns there, so no error event finishes processing. The event the founder saw came
from the middleware's edge build of the SDK, which lived in the same Worker instance and reported for both. When the
app was split into two Workers (#2053), the server Worker had only its own client: of three thrown errors it
delivered none. `Sentry.getClient()` returned a client with its DSN set throughout, and one earlier call to
`Sentry.flush` had returned true, on the layout where the other copy was doing the work.

What found it was a receiver: a ten-line Worker that logged each request it got, with the build's DSN pointed at it.
One Worker delivered three error events for three throws; two Workers delivered none; dropping `ContextLines` alone
delivered two of two. Without the receiver each of those was a guess about what Sentry's dashboard would show hours
later.

**Rule**:
- Call error reporting met only when an error thrown by the code path in question arrives at a receiver you can read
  (a logging endpoint with the DSN pointed at it, or the provider's own event search), on the build and the process
  layout that will serve. Count the events against the errors you threw.
- Do it again when the layout changes: a second process, Worker, runtime or region. A client that worked in a shared
  instance has proved nothing about a process of its own.
- Do not accept as delivery: a client object that exists, a DSN that is set, a flush that returns true, or one event
  seen in the dashboard without knowing which client sent it.
- Name which SDK build runs where (Node, edge, browser) before reading a result: two builds in one instance can hide
  one of them failing.

**Evidence**: #2053 (the receiver counts, the bisect of the default integrations, `frontend/lib/sentryOnWorkers.ts`,
`frontend/tests/unit/sentryOnWorkers.spec.ts`); #2051's go/no-go table, which records the criterion as met;
`docs/DEPLOYMENT.md`, "Frontend on Cloudflare Workers (staging)". Partly gated: CI's `worker-build` job fails when
the instrumentation hook does not load, and `sentryOnWorkers.spec.ts` holds `instrumentation.ts` to the Workers
options; neither sends an event, so delivery stays a check made by hand at each layout change.
