# Client-only exports (buttonVariants, hooks) can't be called in a Server Component — run next build to catch it

**Area:** frontend-build · **Date:** 2026-07-04

During the DS realignment I swapped a hand-rolled CTA on app/waitlist/page.tsx (a Server
Component) to `buttonVariants({variant:'secondary'})`. `tsc`/`eslint` passed but `next build`
failed at prerender: "Attempted to call buttonVariants() from the server but buttonVariants is on
the client." `buttonVariants` is a pure function, but it lives in the `'use client'` Button.tsx, so
Next marks it a client-only export — importing it into a server component and *calling* it throws.

**Rules:** (a) `<Button>`, `buttonVariants`, `useCountUp`, and anything from a `'use client'`
module can only be used in components that are themselves `'use client'`; a page with
`export const metadata` (no `'use client'`) is a Server Component. (b) For a link-styled CTA in a
Server Component, either keep a token-clean hand-rolled `<a>` or extract a small client wrapper —
you cannot call `buttonVariants()` there, and `<Button>` renders a native `<button>` (not an
anchor) so it can't be a link. (c) `tsc` + `eslint` do NOT catch the server/client boundary —
always run `next build` before shipping a change that moves DS primitives across page files.
