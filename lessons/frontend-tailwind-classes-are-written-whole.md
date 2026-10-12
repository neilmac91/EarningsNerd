# Write every Tailwind class whole; never assemble one from an interpolated prefix

Date: 2026-10-12   Area: frontend

**Context**: Resolving the reflow-200 branch onto main's opt-in Button `wrap` (#1262), the
narrow-viewport wrap state was rebuilt as `` `${NARROW}h-auto ${NARROW}min-h-10 …` `` with
`NARROW = '[@media(max-width:24rem)]:'`. Lint, typecheck, the unit suite and the production build
all stayed green, and `button-wrap.spec.tsx` passed because it reads the class string, not the
stylesheet. Tailwind generates only the class names its extractor finds whole in the source, so none
of those variants reached the CSS, and every route with a labelled Button scrolled sideways again at
200% text. The e2e gate caught it (5 of 7 cases red); nothing cheaper did.

**Rule**: A Tailwind class, variant prefix included, is written out in full as one token in the
source, whether in JSX, a `cx()` call, a recipe constant or a variant map. Never build one from an
interpolated prefix or suffix (`${variant}h-auto`, `text-${tone}`), a concatenation, or a lookup that
produces part of a token: write the whole string per case and let the map choose between whole
strings. A class string that passes a unit test proves only that the string exists, not that its
CSS does; a change to a variant or a composed class is proven in a browser or by the done gate's
emitted-CSS check.

**Evidence**: `frontend/components/ui/Button.tsx` (`WRAP_WHEN_NARROW`, three literal strings) and
`frontend/tests/e2e/reflow-200.spec.ts` on the reflow-200 branch, 2026-10-12. Gate:
`frontend/tests/unit/tailwindClassesWrittenWhole.spec.ts` fails on any template literal under
`app`, `components`, `features` or `lib` whose interpolation is followed, with no separator, by a
hyphenated utility token; with `WRAP_WHEN_NARROW` put back as the template literal it names
`components/ui/Button.tsx` and the three tokens.
