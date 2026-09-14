# Give every local Python run on this Mac a fresh bytecode-cache prefix before trusting its timing

Date: 2026-09-14   Area: test

**Context**: While diagnosing the provider stall, local probes from the founder's Mac
appeared to reproduce it: an async request "hung" for 426 s past a 23 s asyncio deadline,
three parallel sync requests all took exactly 32.6 s, and an import-only script took over
two minutes. None of it was network. The deadline could not fire because a lazy import
inside the transport blocked the event loop, and the identical 32.6 s was contention on the
venv's bytecode cache. The same probes with `PYTHONPYCACHEPREFIX` pointed at a fresh
directory completed in under 1.1 s, matching curl.

**Rule** (local-environment guidance, not a tree invariant): on this machine, set
`PYTHONPYCACHEPREFIX` to a fresh directory for every local Python check, the way the
September 14 handover already prescribes for gates. Treat a local timing, hang or deadline
as evidence about a remote service only after the same run was repeated under a fresh
prefix, and prefer a runner-side workflow (`deepseek-transport-diagnostic.yml`) for any
timing that matters.

**Enforcement**: none at tree level; the cache lives outside the repository and a fresh
checkout is unaffected. The runner-side workflow is the committed alternative.

**Evidence**: `tasks/review-evidence/resumption-2026-09-14/inference-stall.md` (local timings paragraph).
