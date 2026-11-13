# Validate the redirect destination you return, as the URL parser reads it

Date: 2026-11-13   Area: frontend

**Context**: Login honoured `?redirect=` when the value began with one slash and not with `//` or
`/\`. The URL parser drops tabs and line breaks and reads a backslash as a slash, so a slash, a tab
and a second slash before a host passed the prefix test and navigated to another site after a
completed login. The first fix parsed the value against this origin, compared origins and returned
the parsed path. Its review found that this opened a new form: the parser also removes dot
segments, so a value that opens with a dot segment and then two slashes before a host parses on
this origin with a path that opens with those two slashes, and the router reads that path as
another site. Each check validated one string and handed the router another.

**Rule**: Decide a redirect with the parser the navigation uses, never with prefix tests, and
validate the string you hand to the router, not the string you were given: after normalising,
parse the result again and return it only if it still resolves to this origin. Keep one function
for every reader and writer of the destination (the query value, the stash's write and its read).
Test each family the parser rewrites: tab, line feed, carriage return, backslash, dot segments and
their percent-encoded forms.

**Evidence**: `frontend/lib/postAuthRedirect.ts::safeInternalPath`;
`frontend/tests/unit/LoginRedirect.spec.tsx` (the cases fail on both earlier versions). The
second-round review fuzzed about 1.7 million inputs and found none that left the origin.
