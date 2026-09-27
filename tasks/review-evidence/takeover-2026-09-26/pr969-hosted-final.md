# PR 969 hosted evidence

This compact repository copy summarizes the external operator-workspace bundle `outputs/takeover-2026-09-26/pr969-hosted-final/`, which keeps hosted evaluation evidence separated by Git head and synthetic merge. Run-specific and review subdirectories mentioned below are relative to that external bundle; they are not included beside this compact copy. It does not grant source admission or merge clearance.

## Superseded prior head `6c0e7fcb6e8111aad79575b668e30880c53aa4e9`

The workflow tested synthetic merge `5d645ac718c6b110f40fd738cbf27898a6a7b003`, whose tree `164a1dc881cd07090a155414f97579084edc7b88` matched the prior head tree.

- CI `36287000069`: 70/70 outputs scored, no judge. Telemetry recorded 71 calls: 70 successes and one unknown-usage/unknown-cost error followed by a successful INTC output. Known estimated cost was `$0.178558`; one call's cost is unknown. The hard gate passed with the soft `mean_untraceable_dollar_figures = 2.3143` advisory.
- Copilot `36287008284`: 18/18 passed, 35 successful calls, no retry/error/judge calls, estimated cost `$0.007617`. Four rows had advisory uncited-figure coverage.
- Exact-head review found the UTF-8 BOM classification defect. This head is historical evidence only.

## Superseded intermediate head `7ff7762132286f22678c814ab42fa3440e56d545`

The reports bind synthetic merge `6709deefe6f55d7cff5b4b3014f2e8e443db1340` (tree `c120d3e5c39fe2e19f1f1382fda61f0f77bdc16d`), combining the head with frontend-only base `eea26d2f6845dbea2cd19feb007afe00efa7bfd5`.

- CI `36287848125`: 70/70 outputs scored, 70 successful calls, no retry/error/judge calls, estimated cost `$0.178062`. The hard gate passed with the soft `mean_untraceable_dollar_figures = 2.1429` advisory.
- Copilot `36287848187`: 18/18 passed, 35 successful calls, no retry/error/judge calls, estimated cost `$0.007574`. Three rows had advisory uncited-figure coverage. All six source artifact sets exactly matched the prior-head source manifest and hashes.
- Exact-head review found XML reference, processing-instruction, and capacity/source-view boundary defects. This head is historical evidence and cost accounting only.

Detailed receipts and inventories are in each run-specific directory. The review snapshots are under `final-head-review/` even though that head was subsequently superseded.

## Corrected successor

Corrected head `c3a10d017d1b220783ceca8dcc7e3a6177fbf069` integrates `eea26d2f6845dbea2cd19feb007afe00efa7bfd5` and corrects the three hosted findings plus XML attribute normalization and explicit fail-closed subset guards. Its synthetic merge `f46600b6c37d41ed51f500bbb5edb34206b574d9` has tree `8a56ab1128008542e75132351708641b7fa3f723`, exactly matching the head tree.

- CI `36289097435`: 70/70 outputs scored, 71 successful provider calls (`70` summary-primary and `1` section-recovery), no retry/error/judge calls, estimated cost `$0.176262`. The hard regression gate passed with the soft `mean_untraceable_dollar_figures = 2.5` advisory.
- Copilot `36289097425`: 18/18 passed, 36 successful provider calls, no retry/error/judge calls, estimated cost `$0.007865`. Five rows had advisory uncited-figure coverage. All six source artifact sets exactly matched the prior hosted source manifest and hashes.
- Exact-head Codex review completed against `c3a10d017d`, reported no major issues, and authored no new inline findings on the corrected head.

The hosted checks support release review of this implementation. They do not themselves admit filing sources. Detailed receipts, raw reports, logs, and inventories are retained in the corrected run-specific directories and `corrected-head-review/`.
