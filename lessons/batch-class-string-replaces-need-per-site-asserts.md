# Every targeted replace in a sweep must assert the old string is present; grep all token variants first

**Area:** refactor · **Date:** 2026-07-02

During the PR-5 banned-utility sweep, two blind string replaces caused regressions
that only Gemini's review caught: (1) a targeted `transition-all ->
transition-[stroke-dashoffset]` replace missed the SVG ring because its classes
live in a TEMPLATE LITERAL (``className={`transition-all ... ${isError ...}`}``),
so the blanket `transition-all -> transition` fallback silently killed the
animation; (2) `replace('bg-amber-400', 'bg-warning-light dark:bg-warning-dark')`
also matched `bg-amber-400/10` and `hover:bg-amber-400/20`, producing a solid
fill, a dead hover, and a conflicting un-prefixed dark class on a banner I did
not know existed.

**Rules:** (a) every targeted replace in a sweep script must `assert old in s` —
a silent no-op means the fallback rewrites the site wrong; (b) before replacing
any token, grep ALL its variants first (`/opacity` suffixes, `hover:`/`dark:`
prefixes, template literals) and handle each explicitly; (c) after a sweep, grep
the RESULT for impossible combinations (e.g. a solid fill next to a `/10` dark
pair) — the bug shows up as nonsense class adjacency.
