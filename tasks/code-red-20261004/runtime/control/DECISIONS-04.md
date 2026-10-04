# Decision record 04 — R1 planner-controls package receipt, time ceiling and corrections to record 03 (chief, 2026-10-04)

Recorded 2026-10-04T21:53:14Z by the chief (`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`, runtime-reported
model `claude-fable-5-1`). Input: Astra's "package adjustment report" of 2026-10-04 (10,392 bytes, SHA-256
`0d8b2342f09cced288fa65356ffc19b3ebfae2edaf806c03a13d9da11d9266dd`) and the controls archive it
describes, both relayed by the founder; founder instruction: record the package preparation charge, the
remaining ceiling and the reviewer identity, and keep implementation held pending the source-owned
refinement. Nothing below releases inputs, dispatches the planner, admits capacity, releases a hold,
invites a user, changes a production flag, adds load or spends.

## Package receipt (chief verification by hash only)

Archive `H20-REGISTERED-PLANNER-CONTROLS-20261004.zip`, 7,656 bytes, SHA-256
`ceed72448c3f675a49f4697d94533378df96dd52d0c108285ef57b46e76d4671`; six members, integrity test clean.
Every member's size and SHA-256 matches Astra's inventory:

| Member | Bytes | SHA-256 |
|---|---:|---|
| `00-BOOTSTRAP-PROMPT.md` | 4,192 | `650e8678c340119e24c7fdc5db72b7f1a4ec721712b8e29e2b3e989a3fa9f094` |
| `01-INPUT-SELECTION.md` | 3,793 | `b1cf7fd68224d399bb089935661b7526f455adb9a6631f42fed8dc9c7a256f3e` |
| `02-RETURN-CONTRACT.schema.json` | 732 | `c1f8fe8a6c454f54806e93b42c0e1ee6d6bb69235f9a605a9b6dc1127a5b9ff4` |
| `03-TIME-AND-STOP-RULES.md` | 3,392 | `dc28cda9fa460489f1ccc454d3c9dc9c7f29213b48188f292dbe3bdfbd658bf4` |
| `04-RELEASE-RECEIPT.template.json` | 898 | `b06cf6a00c378b881122c1db968bf85455800a6b41d29335f70520fcf7c87bd0` |
| `MANIFEST.json` | 1,082 | `c9ee8a57f8efde71b102a986bc2d430b656ad5878f059a9575dabdcf15aa0284` |

The chief verified membership, sizes and hashes only and did not read the members' contents: the
package is addressed to the source-only planner, and the executive boundary stays as recorded. Astra
states the archive holds no source bytes, executive records, complete closures, ledger, SEC patch,
candidate/judge material or custodian mappings, and that one isolated control-document reviewer read
the five controls (registered below). Nothing in it is a source-input release or a dispatch.

## Time ceiling (CEO)

Allowance 180 minutes (D2). Charged so far: 10 (preparation, record 03) + 10 (this package work) = **20**.
Remaining ceiling: **160 minutes** for all further custody preparation plus planner execution; it does
not restart at delivery. The founder's cumulative preparation receipt includes this charge; the planner's
terminal `minutes_used` covers all work since record 03 and excludes the first 10 already recorded, so
nothing is omitted or double-charged. Local time accounting; not a ledger write.

## Registration (closure 142)

`control/source-context-exclusion-142.json` (SHA-256 `3b2d195b1f3047167dcfff599c04304774327bdd00c2f0580b741efe80e5bd60`, 170 known contexts) adds
`codex-thread:01a102be-45bf-72f3-8b9a-a5ff7bb8adfe:/root/r1_package_boundary_review_20261004` as an engineering/control reviewer
(ineligible for source planning or authorship, reconciliation, blind financial judging and candidate
generation), resolves the decisions-03 delta reviewer's identity, and pre-registers this record's
reviewer. The planner's identity and restrictions from closure 140 are unchanged.

## Hold (CEO)

Implementation stays **HELD pending the source-owned refinement**: `R1-STATUS.md` remains
`BLOCKED_SOURCE_OWNED_PACKING`; the planner is idle; the release receipt is `NOT_RELEASED`; no clean
inputs have been released; no planner dispatch has occurred. Custody recovery and original-byte
verification against retained hashes remain the founder's prerequisite. The R1 dependency handover
worker stays undispatched.

## Corrections to record 03 raised by Astra and accepted

1. **Telemetry sentence (D3/D6 correction, line 78):** "a rise means SEC answered 429" is too strong.
   `_is_rate_limit_error` (`sec_rate_limiter.py:184-196`) is true for HTTP 429 **or** for any exception
   whose message contains "rate limit", "too many requests", "429" or "throttl". Supported wording: a rise
   records a recognised rate-limit error on an `execute_with_backoff` path; it is not by itself proof of an
   observed SEC 429. The conservative stop rule stands.
2. **"Zero writes" scope (line 5):** Astra's handover persisted one local administrative report and an
   immediately undone clipping. Supported statement: zero ledger, repository, production, flag, invitation
   and held-PR writes; not zero filesystem writes.
3. **Custody counts:** the 17/21 and 7/48 cloud-only figures were historical. Astra's read-only check for
   this report shows **18 of 21** bootstrap files and **12 of 48** predecessor files cloud-only. Availability
   alone does not prove custody verification.
4. **Recovery advice is unverified:** `brctl` could not be exercised from Astra's sandbox ("Trying to
   invoke brctl from a sandboxed process"), so the `brctl download` suggestion and the re-eviction remark
   remain unverified advice, not an execution instruction; the founder verifies recovered originals
   against retained hashes and lengths whatever method is used.

## Records-privacy sanitisation

`control/LEDGER-ACCESS.md` line 5 carried the founder's local filesystem path since PR #1086 (flagged by
the PR #1090 delta review). Replaced by a neutral description; the path stays in the private handover
materials. Forward-only policy; no history rewrite.

## Owners and next actions

| Item | Owner | Next action | State |
|---|---|---|---|
| Custody recovery + verification | Founder (local) | Materialise cloud-only files, verify retained hashes/lengths, fill the release receipt, include all preparation minutes | open |
| Release of clean inputs + planner run | Founder → registered planner (via Astra's custody process) | Only after the receipt predicates are all true; stop at the 160-minute ceiling; return counts, hashes, status, minutes | blocked on custody |
| Implementation (R1 handover worker) | Chief | Held pending the source-owned refinement | held |
| Package receipt | Chief | Done (hash-verified) | done |
| Registration | Chief | Done (closure 142) | done |
| Patch | Founder | Apply or change numbers; marking any PR carrying it ready needs a chief reservation (~USD 0.01) | open |

## Spend

0 DeepSeek calls; USD 0.000000; 0 reservations; 0 ledger events this record.
