# Takeover verification — 26 September 2026

This is a retrospective, read-only reconstruction of agent deliveries since September 23,
followed by a documentation-only continuation update. It does not invent missing historical
observations. See the [completion plan](../../continuation-plan-2026-09-26.md).

The later [agent-checkpoint reconciliation](agent-checkpoint-reconciliation.md) resolves active
ownership, preserves Agent B's independent fixture pack and consolidates additional findings.
It also records the agents' dated corrections and historical-health attestations without treating
them as independently observed raw responses.

## September 27 implementation and evidence index

The sections below this index retain the initial September 26 retrospective audit. Subsequent implementation and paid ordinary CI measurements are recorded separately here; its earlier “no new measurement” statements describe only that initial audit.

- [#963 verified release](pr963-release.json): custody and source-unit corrections.
- [#964 verified release](pr964-release.json): exact prompts, durable pre-dispatch history and crash recovery.
- [#965 verified release](pr965-release.json): release database sessions before SEC network waits.
- [#966 verified frontend release](pr966-release.json) and [hosted default-build evidence](pr966-hosted-build.md): visible warnings and bounded product claims; its main backend deploy job explicitly skipped because no backend files changed.
- [#967 verified release](pr967-release.json) and [actual hosted audit](pr967-hosted-final.md): retained adverse source evidence.
- [#968 verified release](pr968-release.json) and [actual hosted audit](pr968-hosted-final.md): cached numeric warning persistence.
- [#969 initial local gate](pr969-local-verification.json), [independent final code review](pr969-independent-review.md) and [actual hosted audit](pr969-hosted-final.md): final corrected head passed 3,731 local tests, 70/70 summaries and 18/18 Copilot draws. [Release verification](pr969-release.json) is complete at revision `00393-6m9`; initial receipts do not claim to cover later heads.
- [#970 final hosted audit and review hold](pr970-hosted-final.md): actual ordinary regression output is retained separately from the unresolved whole-attempt omission finding. Draft and unmerged; no release or E7 admission.
- [Overnight spend audit](overnight-spend-audit.md) and [run-level data](overnight-spend-audit.json): deduplicated application telemetry, known-cost lower bound and explicit unknown costs; formal E7/E8/Fable ledgers remain separate.
- [H30 individual freeze](h30-freeze-receipt.json) and [custody audit](h30-custody-audit.json): financial source evidence plus one separate unresolved runtime-only history row; no programme admission.
- [Notable engineering disposition](notable-disposition-review.md): retain implementation and defer activation pending the missing readout; do not infer quality from seed counters or utility from a dark feature.
- [Live Analysis observations](live-analysis-acceptance.md), [post-release cached-warning check](post-release-cache-check.json) and [bounded large-source capacity](large-source-capacity.json).

This repository retains compact receipts, inventories and hashes. Large raw bundles remain in the operator workspace under `outputs/takeover-2026-09-26/`, at the per-receipt subdirectory named in each record; they are not silently repository-local. Release JSON filenames in `files` also refer to that external workspace root. Public compact copies normalize host-specific workspace/checkout paths to logical locations; original receipts and frozen artifacts remain byte-for-byte retained in the workspace. Their source/artifact hashes are unchanged. Evidence inventory hashes describe the original external bundles, not a recomputed claim that the compact copies contain them.

## Verified release chain

Each backend job below reported `apply_migrations: applied=0 skipped=39`, the named revision
serving 100%, and a healthy workflow `/health/detailed` response. Dates/times are UTC.

| PR | Main commit | Main CI | Revision suffix | Deploy completed |
| --- | --- | --- | --- | --- |
| #953 | `86cb2445` | [35930211192](https://github.com/neilmac91/EarningsNerd/actions/runs/35930211192) | `00381-rsq` | September 23 22:53:48 |
| #940 | `9ec55f70` | [35931893080](https://github.com/neilmac91/EarningsNerd/actions/runs/35931893080) | `00382-pgr` | September 23 23:14:24 |
| #956 | `964c85bb` | [36043810197](https://github.com/neilmac91/EarningsNerd/actions/runs/36043810197) | `00383-76b` | September 24 18:56:45 |
| #957 | `0dfc291c` | [36073634317](https://github.com/neilmac91/EarningsNerd/actions/runs/36073634317) | `00384-4r7` | September 24 23:45:10 |
| #958 | `80443291` | [36192422885](https://github.com/neilmac91/EarningsNerd/actions/runs/36192422885) | `00385-7bp` | September 25 21:43:38 |
| #959 | `16cdc1a2` | [36192848102](https://github.com/neilmac91/EarningsNerd/actions/runs/36192848102) | `00386-9bw` | September 25 21:48:32 |

#955 and #960 were documentation-only; their main CI deploy jobs explicitly skipped deployment.
Only #940 has the complete historical independent-health receipt retained by #955. Independent
health observations made at the time of the other five releases remain unverified. Their workflow
health checks are observed. The distinction matters: the current endpoint does not identify a
revision and cannot prove earlier observations occurred.

#959 merged at September 25 21:40:49, before #958's migrations at 21:42:06, healthy result at
21:43:34 and deploy completion at 21:43:38. It therefore breached the existing before-next-merge
verification rule. GitHub deployment concurrency still serialized the actual jobs; #959's deploy
began at 21:45:06. Both releases subsequently passed. This is a release-process finding, not a
claim of an outage or a reason to rerun successful releases.

## Actual measurement, rather than check names

- **#953:** exact head `6807810441b43376e2207561c1e225cfcc001870`, manual baseline
  [35929016827](https://github.com/neilmac91/EarningsNerd/actions/runs/35929016827):
  expected/attempted/scored 70/70/70, errors 0, regression PASS (one warning).
  Artifact `10780477957`, workflow-reported SHA-256
  `c321e60a2d183a02c144d7219513f2fe505ce689287fec5cb4bc432f87d2ab9a`.
  [Copilot 35927037805](https://github.com/neilmac91/EarningsNerd/actions/runs/35927037805)
  accepted 18/18, errors 0, with actual OpenAI SDK 3.16.2 provider calls. Artifact `10779182968`,
  digest `47ef24db06d2442fcdc79f1e4e78866e457374eb827c089ffe7fc7383f926ee3`.
  Ordinary scope-skipped PR baseline checks alone would not establish this compatibility.
- **#940:** final head `0a2dce2cf6fd1e39c4249b899f722877b90f7d84`,
  [baseline 35930815020](https://github.com/neilmac91/EarningsNerd/actions/runs/35930815020)
  scored 70/70, errors 0, regression PASS (one warning);
  [Copilot 35930814882](https://github.com/neilmac91/EarningsNerd/actions/runs/35930814882)
  accepted 18/18, errors 0. Its body still contains older measurement and unmerged-state text;
  the final runs and #955 release receipt supersede those statements.
- **#961:** exact head `c8c90ace48b0d199f200f5cccf3919f01cf18058`,
  [baseline 36272463033](https://github.com/neilmac91/EarningsNerd/actions/runs/36272463033)
  scored 70/70, errors 0, regression PASS;
  [Copilot 36272462976](https://github.com/neilmac91/EarningsNerd/actions/runs/36272462976)
  accepted 18/18, errors 0. Hosted backend and PostgreSQL gates are green on the final head.
  The committed local full-gate log describes earlier `fe03cd0`; it must not be represented as
  local execution on `c8c90ac`. These measurements do not close the custody findings below.

This audit read run metadata, job logs and artifact metadata. It did not redownload large
measurement archives; artifact-internal claims beyond those logs were not independently rechecked.
No new measurement, model call or workflow dispatch was made.

## #961 custody and release follow-up

#961 merged at September 26 21:29:29, main
`b53455bb3b13817d44cf089f3280ced143998583`. Main CI is
[36273109900](https://github.com/neilmac91/EarningsNerd/actions/runs/36273109900).
At the bounded 21:34 read, deployment had not completed. The later observation below closes
that pending snapshot.

**Completed release observation:** the main run and deploy job `108491479519` completed
successfully at 21:38:01. The [retained job extract](pr961-deploy-extract.txt) shows migrations
`applied=0 skipped=39`, revision `earningsnerd-backend-00387-55c` serving 100%, and workflow
health at 21:37:57 (database 6.93 ms). Codex's independent
[21:38:55 response](health-after-961.json) is healthy (database 6.62 ms, Redis disabled,
SEC circuit closed). This closes #961's deployment verification; it does not close its offline
custody defects or E7 acceptance. No deployment was initiated or rerun by this audit.

Independent [custody review and replay](e7-custody-review.md) confirm three gaps. Two also appear
in the final-head Codex review submitted at 21:21:52:
[missing attempt history](https://github.com/neilmac91/EarningsNerd/pull/961#discussion_r4112833584)
and [unused-kind template alias](https://github.com/neilmac91/EarningsNerd/pull/961#discussion_r4112833587).
Both predate the merge and apply to its unchanged head. The body reports a founder override and
an exhausted Codex allowance. We do not adjudicate the private founder instruction; the actual
completed review and outstanding findings must nevertheless remain visible.

## Current health and cloud limitations

The [21:26:29 UTC health response](health-before-961.json) is healthy: database 8.59 ms,
Redis intentionally disabled, SEC circuit closed. It predates the #961 deployment and does not
identify a serving revision. It is a dated observation, not ongoing monitoring.

The September 26 read-only Cloud SQL settings request failed with
`Reauthentication failed. cannot prompt during non-interactive execution.` No cloud mutation
occurred. Fresh backup, PITR recovery-window, export and restore evidence therefore remain
unverified; prior dated backup/PITR observations stand.

## Remaining repository observations

At the post-#961 snapshot, #942 and draft #952 were the only open PRs. #950 is closed, superseded
by #953. Issue #710 remains open; `refresh-index-membership.yml` runs at 08:00 UTC on the first
of each month and has no newer run than September 6's successful no-change result. The next
natural October 1 publication opportunity has not occurred.

GitHub lists open high-severity development `extract-zip` alerts #270/#283, both without a patched
version. No alert, dependency or repository setting was changed.
