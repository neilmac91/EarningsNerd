# Decision record 05 — pre-release update: custody state, release-receipt gate, time ceiling 150 (chief, 2026-10-04)

Recorded 2026-10-04T23:14:48Z by the chief (`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`, runtime-reported
model `claude-fable-5-1`). Input: Astra's "pre-release update" (observation from 2026-10-04T22:58:48Z;
relayed by the founder; zero spend; one local administrative write). Status carried: **NOT_RELEASED /
verification incomplete / no planner dispatch**. Nothing below releases inputs, dispatches the planner,
admits capacity, releases a hold, invites a user, changes a production flag, adds load or spends.

## Record 04 confirmed; one wording correction accepted

Astra confirms record 04 at main `756c2fff` (7,212 bytes, SHA-256
`66e1f9096e12049c676e092eaa71f066c3a08a29591579b3adaca987a3f8e811`), the archive, the prior report,
closure 142 and the time accounting. Correction, verified by the chief in
`backend/app/services/sec_rate_limiter.py:184-196`: `_is_rate_limit_error` returns directly for an
`httpx.HTTPStatusError` (true only for status 429), so the message fallback ("rate limit", "too many
requests", "429", "throttl") applies **only to non-`HTTPStatusError` exceptions**; a non-429 HTTP error
whose message contains "429" stays false. Record 04's "or for any exception whose message contains …" is
corrected to "or a matching message on a non-`HTTPStatusError` exception". No stop rule or release
predicate changes.

## Custody state (Astra's bounded read-only check; no founder materialisation reported)

| Directory | Cloud-only | Local read | Hash and length verified | Hash only | No accessible retained reference | Mismatches | Short reads |
|---|---:|---:|---:|---:|---:|---:|---:|
| Bootstrap | 18/21 | 3 | 0 | 1 | 2 | 0 | 0 |
| Predecessor | 12/48 | 36 | 11 | 1 | 24 | 0 | 0 |
| Total | 30/69 | 39 | 11 | 2 | 26 | 0 | 0 |

"Hash only" does not satisfy the two-part check; the 26 are unverified, not corrupt; zero mismatches and
zero short reads apply only to the 39 files read; the 30 cloud-only files were not forced open. No file is
declared unrecoverable. **No fully verified, fully local complete release manifest exists yet.** Retained
evidence chain (labels and hashes only): latest `SOURCE-ONLY-ALLOWLIST-SUCCESSOR.json` (custody request 5;
cloud-only; 2,020 bytes; `4987539c856a84554d8cfc3b70b4122495a4cf4207cfdb923946c4e346011980`);
`H20-ENGINEERING-SAFE-HANDBACK-v2.json` (local, verified; 9,381 bytes; `b3ef723d…`; 15 artifact entries, not
the complete manifest); the H20 scope decision (local; 8,423 bytes; `b7f0510c…`; scope identity, not an
allowlist).

## Recovery guidance adopted (founder's local action)

Finder first: locate the bootstrap and predecessor folders in iCloud Drive, select the cloud-only items,
use **Download Now**, then **Keep Downloaded** where offered; restore the custody/control chain first, then
the inputs it selects; in list view enable the iCloud Status column and wait for transfers to finish (a
progress icon is not byte verification). Fallback: disable **Optimise Mac Storage** (System Settings → Apple
Account → iCloud → Drive) if local space allows; it is a global setting. Never turn off iCloud Drive or
move/delete originals. `brctl download` is **not** the first step (unverified; rejected as sandboxed for
Astra; a zero exit is not proof of complete recovery). Verification after recovery: verify the retained
controls first, resolve their original custody chain, stream each selected original's bytes into SHA-256
while counting bytes, require both values to match the independently retained record, confirm the file did
not change during the read; never create a replacement baseline from reconstructed or newly fetched
content. If a required original cannot be recovered, H20 stays held under the frozen input set; omission
or substitution would need a separate explicit scope decision. Record 04's advice ordering is superseded
by this section.

## Release-receipt gate (adopted as the standing gate; chief's acceptance criteria)

The receipt template stays `template_only=true`, `release_status=NOT_RELEASED`, six attestations false,
manifest hash / cumulative minutes / timestamp null (template SHA-256 `b06cf6a0…`). Ownership per Astra's
table: identity and fixed hashes prepopulated by Astra, checked by the founder, registration confirmed by
the chief; the five custody attestations (original recovery, all retained hashes and lengths, existing
custody source eligibility, private references supplied separately, private output destination supplied
separately) and `no_provider_or_paid_step_required` are the founder's/custodian's, never inferred from an
incomplete form; `clean_frozen_h20_input_manifest_sha256` comes from the existing custody process (not
the ZIP or scope hash); `further_preparation_minutes_used` is consolidated by the founder and recorded by
the chief; `founder_verified_at_utc` and `template_only=false` / `release_status=RELEASED` are set by the
founder only after every predicate holds.

**Before any release the chief receives:** the completed receipt's SHA-256; all attestation values; the
identity/hash-match status; the verification timestamp; the original input-manifest identity; the
verification totals with mismatches and partials; the cumulative preparation minutes. Never the inputs,
artifact maps or private references. The chief records the disposition and time; the chief fills no
custody attestation and writes nothing to the frozen local ledger.

## Planner runtime availability — UNVERIFIED (new prerequisite)

Astra has not contacted the registered planner since the package report, but a read-only registry query
returned no entry for it, so its resumability cannot be certified. Decision: **no input release until the
runtime identity is resolved.** If the original context is not resumable, Astra bootstraps a fresh
context and reports its actual identity; the chief registers it in the next closure before any release;
the old name is never silently reused and its closure-140 entry is annotated as superseded. The chief
accepts terminal output only from a registered context.

## Return route (administrative description, not a dispatch)

Planner → its parent Astra context (existing agent return channel) → founder (this chat) → chief. Only
the six-field terminal JSON moves: `attempted`, `complete`, `partial`, `output_sha256s`, `status`
(`REFINEMENT_RETURNED` | `TIMEBOX_EXHAUSTED`), `minutes_used`. Astra validates schema,
`attempted = complete + partial`, time accounting and hash syntax without opening outputs. Pre-start
administrative failures are reported separately and never cast as a terminal result.

## Time ceiling (CEO)

This turn: 10 minutes charged (8 Astra + 2 reused control reviewer). Cumulative: **30 of 180**;
remaining **150** for all further preparation plus execution. The terminal `minutes_used` already
includes 20 minutes of post-record-03 preparation (10 package + 10 this turn) and is not charged again
on receipt. Astra's estimate after complete recovery and a confirmed resumable context: 10–20 further
focused minutes for manifest-chain verification, opaque hashing, receipt completion and delivery checks;
download and sync waiting is not charged. Stop on a concrete discrepancy rather than retrying blind.

## Registration

No new Astra-side context this turn. `control/source-context-exclusion-143.json` (SHA-256 `9f2a7536b0dcf218ecf06c9170a2e7c32c076ce1cbde9631496036d1b1a01bd5`, 174
known contexts) pre-registers the review contexts for this record's PR.

## Owners and next actions

| Item | Owner | Next action | State |
|---|---|---|---|
| Custody recovery | Founder (local) | Finder Download Now / Keep Downloaded on the 30 cloud-only files; controls first | open |
| Custody verification | Founder + Astra (opaque checks) | Two-part hash-and-length match for every selected original and governing control; totals to the chief | open |
| Planner runtime | Astra → chief | Resolve resumability; report any fresh identity for registration before release | open |
| Release receipt | Founder (attestations) → chief (record) | Complete only after every predicate holds; send the receipt hash and metadata to the chief | NOT_RELEASED |
| Implementation | Chief | HELD pending the source-owned refinement | held |
| Patch | Founder | Apply or change numbers; marking any PR carrying it ready needs a chief reservation (~USD 0.01) | open |

## Spend

0 DeepSeek calls; USD 0.000000; 0 reservations; 0 ledger events this record.
