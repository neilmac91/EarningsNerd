# Run next build before moving design-system client exports across page files

Date: 2026-07-04   Area: frontend

**Context**: During the DS realignment, swapped a hand-rolled CTA on the waitlist page (a Server Component) to `buttonVariants({variant:'secondary'})`. tsc/eslint passed but `next build` failed at prerender: buttonVariants is a pure function but lives in the `'use client'` Button.tsx, so Next marks it a client-only export — importing it into a server component and calling it throws.

**Rule**: (a) `<Button>`, `buttonVariants`, `useCountUp`, and anything from a `'use client'` module can only be used in components that are themselves `'use client'`; a page with `export const metadata` (no `'use client'`) is a Server Component. (b) For a link-styled CTA in a Server Component, either keep a token-clean hand-rolled `<a>` or extract a small client wrapper — you cannot call `buttonVariants()` there, and `<Button>` renders a native `<button>` (not an anchor). (c) `tsc` + `eslint` do NOT catch the server/client boundary — always run `next build` before shipping a change that moves DS primitives across page files.

**Evidence**: `app/waitlist/page.tsx` + `buttonVariants({variant:'secondary'})`; `next build` prerender error "Attempted to call buttonVariants() from the server but buttonVariants is on the client"; `'use client'` Button.tsx.
