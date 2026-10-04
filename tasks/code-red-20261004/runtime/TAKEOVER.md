# CODE RED chief takeover record — Fable chief session

Recorded: 2026-10-04T14:31:37Z. This file records the actual receiving chief identity, observed runtime, verified
package identity, current repository/owner snapshot, live-ledger access status and retained
exclusions required by `control/CHIEF-TRANSFER-POLICY.md` in the founder's handover package. It is a
management record, not a dossier, quality acceptance, capacity admission or cohort readout.

## Actual chief identity and observed runtime

| Item | Observed value |
|---|---|
| Session | `https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8` (Claude Code cloud session, origin desktop app, environment `env_01Y7xCSn9NoXo9DGHWupQfYU`, container CLI 2.1.289) |
| Configured model | `claude-fable-5-1` (session_context.model); last served model reported by the runtime: `claude-fable-5-1` |
| Effort / mode flags | effort `xhigh`; runtime flag `ultracode: true` (observed in session flag settings, not inferred from the product label); permission mode `auto` |
| Tool access actually available | Bash/filesystem on a fresh clone of `neilmac91/EarningsNerd`; isolated subagents (`Agent`) and multi-agent `Workflow` orchestration; GitHub MCP tools authenticated as the founder's GitHub account `neilmac91` (any GitHub write from this session is attributed to that account); Vercel, PostHog, Gmail and Cloudflare MCP connectors are present but were not used; `gcloud`/`gh` CLIs are installed, authentication not probed and not needed for this session's work |
| Not available | The founder's local Codex workspace (`/Users/neilmacaogain/...`), its `outputs/next-stage-20261003/` live records, the H20 source-planner context and every clean source-role input; the Codex code-review service (credits exhausted, per founder) |

A requested model or mode is not runtime evidence; the values above are what the runtime reported
when queried at takeover. Served models of delegated subagents are recorded as requested routing in
`control/APPOINTMENTS.json`; the chief cannot independently observe each delegate's served model.

## Package verification

| Artifact | SHA-256 | Result |
|---|---|---|
| `earningsnerd-code-red-fable-chief-20261004.zip` | `e5316f506477144051b77f64dde240124e5f4a8571017c79d83dc76ba7e7661c` | received from founder upload |
| `CHIEF-LAUNCH-PROMPT.txt` (packaged) vs founder-pasted launch prompt | `11fb3f24057b64be25f85a2f3c4572a3c19a3a8c0ef880a8e825b74fab0a98aa` | byte-identical |
| Top-level `MANIFEST.json` | 27 listed files | 27 verified, 0 mismatches, 0 unlisted files |
| CTO zip `2209215e…` nested manifest | 36 files | verified |
| CPO zip `14e66f54…` nested manifest | 33 files | verified |
| COO zip `38210de1…` nested manifest | 31 files | verified |
| CFO zip `83c8214f…` nested manifest | 29 files | verified |
| `repository-current/AGENTS.md`, `CLAUDE.md` | `55a17858…`, `c66bddb4…` | identical to the clone at main `100fb7d6` |
| `.github/workflows/review-gate.yml` reference copy | `4f2fa6c2…` | identical to the clone at main |

## Current main, release and PR-owner snapshot (observed 2026-10-04T14:21:00Z, recorded 2026-10-04T14:31:37Z)

- `origin/main` = `100fb7d6bdaf62590af19964d39c2ed732062210` (PR1084 merge), identical to the package snapshot. Local clone HEAD = main; designated work branch `claude/vigilant-goodall-633yx3` exists locally only until pushed.
- Latest runs on main all completed: CI 37202227789 success, Review gate (issue_comment) skipped, Ops 37202971777/37203033138 success, Production smoke 37202612862 success. No workflow in progress. The package's release verification (revision `earningsnerd-backend-00443-n58`) is reused, not re-run.
- Open PRs (owners unchanged, no duplicate writer created): see `control/REPOSITORY-SNAPSHOT.json`. One change since the package snapshot: PR1085's owner session pushed head `583e828d` at 14:02:54Z (CI 37207819234 success; review-gate skipped because the PR is a draft). PR1081 `53cc2762`, PR1074 `437e245c`, PR1070 `e6b0de98`, PR1035 `23c948e9`, PR1009 `be11df3a` unchanged and held as recorded.

## Live spending ledger access

The authoritative live ledger named by the package is
`outputs/next-stage-20261003/spend-and-reservation.json` under the founder's local Codex task root. It
is **not reachable from this cloud session**. The packaged snapshot
`control/spend-and-reservation.SNAPSHOT.json` has SHA-256
`99c7259ff3e5f0f2c40b60e6b557bbc711222be0e261b9277f3105e9bca8fc7b`, which equals
`PACKAGE-INDEX.json.ledger_sha256` and the CFO packet's reference copy. Consequences, per the transfer
policy (details in `control/LEDGER-ACCESS.md`):

- No successor ledger is designated: the latest original cannot be reconciled from here.
- Paid dispatch and paid-CI triggers are **HELD** in this session. No paid action is currently
  unblocked, so this hold blocks nothing today. Zero new DeepSeek calls / USD 0.000000 by this chief.
- Recorded cumulative usage reused from the snapshot: 2,356 calls / USD 4.331765 estimate; future
  USD 15 authority: USD 0.547516 recorded use, USD 1.881713 retained holds (incl. the cancelled-run
  unknown, not zero), USD 12.570771 conditional unreserved. These are dated telemetry estimates.

## Ownership accepted and retained holds

From 2026-10-04T14:31:37Z this session is CEO/chief execution integrator, sole ledger/reservation writer (write
authority held until live access exists), paid-dispatch coordinator and serial backend-release
coordinator for the master plan, per the transfer policy; Astra is the retired predecessor. Existing
component owners are preserved: PR1085/PR1081 Claude owners; PR1074/1070/1035/1009 held. Retained
holds: candidate freeze HOLD; full E7 (90+30) not admitted; E8 separate; invitation/consent, production
flags, pricing (PR1009), new load/jobs, new subscriptions, Copilot iterations, broad generation. The
source-engineering timebox is not reset by this transfer. Codex-credit review exception: the founder's
standing authorization applies through the repository's `Review override:` mechanism only, with an
independent current-head review recorded; nothing else is waived.

Exclusion closure: 135 retained entries (`control/LATEST-EXCLUSION.json`,
`a91f4e6e…`) carried forward append-only as `control/source-context-exclusion-136.json`, adding this
chief session. Delegate identities are appended as later successors. All executive, engineering and
coordinator contexts, including this one, remain excluded from source A/B authorship, reconciliation
and blind financial judging.
