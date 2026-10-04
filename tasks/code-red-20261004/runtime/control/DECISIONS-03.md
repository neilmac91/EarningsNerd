# Decision record 03 — R1 bootstrap handover response and corrections to record 02 (chief, 2026-10-04)

Recorded 2026-10-04T20:07:50Z by the chief (`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`, runtime-reported
model `claude-fable-5-1`). Input: Astra's private administrative handover "R1 bootstrap and bounded local
findings" (preparation observed from 19:41:09 UTC as reported; relayed by the founder; zero spend, zero
writes, no source work started). Astra's evidence files live on the founder's machine and are cited by
size and SHA-256 only; nothing from them is reproduced here. Nothing below admits capacity, releases a
hold, invites a user, changes a production flag, adds load or spends.

## Prerequisite 1 — planner registered (CEO)

- Identity: `codex-thread:01a102be-45bf-72f3-8b9a-a5ff7bb8adfe:/root/h20_refinement_planner_20261004` (canonical agent identity `/root/h20_refinement_planner_20261004`), reported
  before any output and registered in `control/source-context-exclusion-140.json`
  (SHA-256 `37c6520da8d32d236f6acfe90484404e48c2526987d634b0d869116bf4906d31`, 151 known contexts) as a **known source-role context**: excluded from every
  executive role, reconciliation, blind financial judging and candidate generation; source-role
  eligibility comes only from the existing custody process; output crosses to executives only as
  counts, output SHA-256s, status and minutes used.
- State at registration (Astra): `BOOTSTRAP_ONLY_AWAITING_REGISTRATION_AND_CLEAN_INPUTS`; attempted 0,
  complete 0, partial 0; no output hashes; disposition `BLOCKED_BEFORE_REFINEMENT` accepted as the
  truthful pre-start state. `R1-STATUS.md` stays `BLOCKED_SOURCE_OWNED_PACKING`.

## Prerequisite 2 — scope confirmed and D2's unit corrected (CEO with CTO)

- **Confirmed scope:** H20-only packing/closure refinement using the existing frozen H20 input set,
  under the existing scope decision (Astra's evidence: `H20-DELIVERY-SCOPE-DECISION.json`, 8,423 bytes,
  SHA-256 `b7f0510ce88da28c8fd54f95718c6f6f3a9224fd4f0d92136a0fc2487a9291d0`; predecessor
  engineering-safe handback v2, 9,381 bytes, SHA-256
  `b3ef723d91c0ab2012ecdf399a9c4f5dda53be128594535450e447ef97ff4fd0`).
- **Correction to D2:** "the 27 remaining H20 items" named the wrong unit. 27 is the count of remaining
  programme dossiers (3/30 complete; 54 briefs + 27 reconciliations); the H20 scope record counts 523
  structural units and 838 projection tiles and defines no 27-item H20 worklist. The allowance is **not**
  expanded to the 27 dossiers; the worklist is whatever the custody process releases as clean approved
  inputs for the H20 packing/closure refinement. No fresh spending authority is implied.

## Prerequisite 3 — custody access (founder's local action)

- Astra reports 17 of the 21 files under `source-engineering/h20-planner-bootstrap/` cloud-only and
  4 local; `PLANNING-CONTROLS.json` (4,695 bytes) dataless, a 5-second bounded read timed out, no
  "Download Now" action offered; the predecessor planning directory has 7 of 48 files cloud-only.
- The chief cannot act on the founder's machine. Founder action: materialise the cloud-only files
  (on macOS, `brctl download <path>` per file or folder forces the iCloud download when Finder offers
  no action; disabling "Optimise Mac Storage" for that tree prevents re-eviction), then verify the
  retained hashes before any release. Controls are never reconstructed from executive summaries.

## Time accounting (CEO)

Allowance 180 minutes (D2). Charged: 10 minutes of preparation (Astra's bounded checks included).
Remaining: **170 minutes**, bounding all further preparation plus refinement. External waiting is not
charged. The chief records further charges only from the planner's return contract.

## Corrections to record 02 raised by Astra and verified by the chief

### D1 — reconciliation wording (ledger event 1)

- Verified in the successor document: entries stamped `2026-10-04T09:35:21.075303+00:00` (H20
  accounting) and `2026-10-04T12:49:19.634909+00:00` (release verification/observation) exist and were
  already in the packaged snapshot. The supported statement is "byte-identical to the packaged snapshot",
  not "no event after 09:35:21Z". Balances, holds and reservations are unaffected.
- Ledger write: event 1 (`designation_wording_correction`) appended under the hash-chain rule with
  `previous_sha256` `53e8486800e193277c5be5c14a786cfeff90d3b4fa212be1c044c7343fea9f78`; the successor
  document is now 21,295 bytes, SHA-256 `beef4ca0b2973db9f00503e0bbbf3ae2ad816def51c0f53820c41e51431be3fa`;
  page SHA-256 `6ee48c8ac775c6a42f9d4ecdb75c62121f294f34610808282a97b78ecc08e3d0`. Spend 0, reservations
  0. `LEDGER-ACCESS.md` carries the new hash.

### D3 / D6 — what `rate_limit_hits` measures

- Verified in `backend/app/services/sec_rate_limiter.py` at main `fdbbcb25`: `_wait_for_token`
  (`:72-98`) increments only `_total_requests`; `_rate_limit_hits` increments only inside
  `execute_with_backoff` when a request raises a recognised rate-limit error (`:143-153`); recognition is
  HTTP 429 or a message containing "rate limit", "too many requests", "429" or "throttl" (`:184-196`), so
  an SEC 403 is re-raised uncounted; `execute()` paths (compat document fetches, XBRL fallback,
  company SIC) and all edgartools traffic never touch the counter. Astra's reading stands.
- Consequence: local throttling never moves the counter, so **a flat `rate_limit_hits` is not evidence of
  safe aggregate traffic**; a rise means SEC answered 429 on a backoff path (EFTS, companyfacts) and
  remains a conservative stop signal. The D3 sentence "exceeding the aggregate shows as
  `rate_limit_hits` climbing" is withdrawn. **D6 condition 1 now reads:** any rise in
  `sec_rate_limiter.rate_limit_hits`, any SEC 403 or 429 seen in logs, or
  `circuit_breaker.sec_edgar.state` other than `closed`; a flat counter closes nothing.
- The founder's patch is revised accordingly (`docs/OPERATIONS.md` wording only): 20,062 bytes, SHA-256
  `21322a0546542156a5c9d21fc3de9cb9ad0e4b93b320d9a4da6d3987eb8c3969`, supersedes `e1c097f9…`; its
  targeted tests pass. Astra's other D3 statements are accepted as written: the two defaults are
  supported (the pinned `edgar/httpclient.py` hash matches), the sums are configured sustained bounds
  and not observations, the burst figures are conservative bounds, and no route around the denied commit
  is authorised.

## Owners and next actions

| Item | Owner | Next action | State |
|---|---|---|---|
| Planner registration | CEO | Done (closure 140) | done |
| Scope | CEO/CTO → Astra | H20-only, frozen input set; worklist from the custody process | confirmed |
| Custody recovery | Founder (local) | Materialise cloud-only files, verify retained hashes, release clean inputs | open |
| Refinement | Planner (via Astra, read-only on the ledger) | Run within 170 minutes; return counts, hashes, status, minutes | blocked on custody |
| D1 wording | CEO | Ledger event 1 written; records updated | done |
| D3/D6 telemetry | CTO/COO | Records corrected; patch revised | done |
| Patch | Founder | Apply or change numbers; chief reserves ~USD 0.01 before any PR carrying it is marked ready | open |

## Spend

0 DeepSeek calls; USD 0.000000; 0 reservations; 1 ledger event (wording correction, no balance change).
