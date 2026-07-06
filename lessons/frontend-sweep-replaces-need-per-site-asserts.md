# Assert every targeted replace in a sweep script and grep all token variants first

Date: 2026-07-02   Area: frontend

**Context**: During the PR-5 banned-utility sweep, two blind string replaces caused regressions only Gemini's review caught: a targeted transition replace missed an SVG ring whose classes live in a TEMPLATE LITERAL, so the blanket fallback silently killed the animation; and a bg-amber-400 replace also matched its /10 and hover:/20 variants, producing a solid fill, a dead hover, and a conflicting un-prefixed dark class on a banner I did not know existed.

**Rule**: (a) Every targeted replace in a sweep script must `assert old in s` — a silent no-op means the fallback rewrites the site wrong. (b) Before replacing any token, grep ALL its variants first (`/opacity` suffixes, `hover:`/`dark:` prefixes, template literals) and handle each explicitly. (c) After a sweep, grep the RESULT for impossible combinations (e.g. a solid fill next to a `/10` dark pair) — the bug shows up as nonsense class adjacency.

**Evidence**: `transition-all -> transition-[stroke-dashoffset]` missed ``className={`transition-all ... ${isError ...}`}``; `replace('bg-amber-400', 'bg-warning-light dark:bg-warning-dark')` also matched `bg-amber-400/10` and `hover:bg-amber-400/20`.
