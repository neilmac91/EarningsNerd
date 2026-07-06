# git add is atomic across pathspecs — one bad path stages nothing; require an empty git status before push

**Area:** git · **Date:** 2026-07-03

A multi-path `git add a b c` stages NOTHING if any single pathspec is invalid — the
summary-layout commit shipped docs without its actual CSS because a bad root-relative
path poisoned the whole add (caught by the stop hook, not by me). Rule: after every
commit intended to complete a change, run `git status --short` and require EMPTY
before pushing or opening/updating a PR; never chain `git add bad-path || true`-style
recovery — fix the path.
