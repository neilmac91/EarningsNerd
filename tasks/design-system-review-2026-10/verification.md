# Records verification

The records tier applies: changes are confined to this task directory and one Impeccable critique archive. No application files, design snapshots, founder task list, workflow or backend files change. No test is added for prose.

The local production build succeeded before the walk. It is a capture-harness check; no fresh lint/unit/e2e suite is claimed for this records-only diff. DESIGN.md and the sidecar are unchanged, so snapshot parity is not required.

The link/path/anchor, immutable-source line bounds, JSON parse, score/plan count, no-em-dash and JPEG budget checks are recorded below after the independent read-only pass.

The fresh-context ten-finding and three-plan refutation is in [refutation.md](refutation.md). It is separate from the final records review.

## Independent review

One fresh read-only records lens found zero blockers, zero should-fix items and one clarity nit. [The review](records-review.md) checked policy/scope, score and plan arithmetic, source samples, archive fingerprint and rendered exhibits. The F2 phrase now explicitly names the Multi-Period Analysis demo snapshot. The separate [refutation](refutation.md) reviewed the ten leading candidates and all plans; its material corrections are incorporated in REPORT.md.

## Validation

Run from the repository root:

```sh
python tasks/design-system-review-2026-10/data/validate_records.py
git diff --check
```

The checker validates Markdown links and anchors, immutable source paths and line bounds, JSON/gzip parsing, score totals, plan counts, the JPEG budget and committed plus pending scope. It does not certify the UI or repeat frontend tests. The report has 6 Distill items (3 S, 3 M), 9 Polish items (2 S, 7 M, including 3 deferred E9 page reworks), and 1 Clarify item (M), all routine.

The review source remains 1f12fc835fcbf525042473ab0e988b4827734f38. Delivery main advanced to fdf195d564a7bb880dfd990e347dab629f22eeb4 through PR 1337; a direct diff confirms no frontend or design-source change. The overlapping PR head hashes were unchanged between snapshots. The stored critique fingerprint matches frontend/components/ui/index.ts: sha256:1a68bbbec0ebad07084b263758a6fa2e94439cfd644f68fd6c29b97fa9221dba.

The plugin storage write succeeded and its trend helper returned the new entry, 28/40, one P0 and four P1 instrument issues. The complete report adds the wider census findings. No mutation proof applies to this records-only PR; future gate-changing plan items name their required proof.

## Publication follow-up

The independent [scan review](scan-review.md) confirms a false positive in the design inventory's radius identifier. Its identifier field was renamed without changing source values or counts. Gitleaks 8.24.3, verified against the CI-pinned SHA-256, reports no leaks in the current records directory. The exact unpublished [exception patch](data/proposed-secret-scan-exception.patch) covers only the already-published commit's finding. With that one pin supplied through a scratch ignore file, the unchanged full-history command produced:

```text
10:41AM INF 2129 commits scanned.
10:41AM INF scanned ~76932398 bytes (76.93 MB) in 5.33s
10:41AM INF no leaks found
```

The gate configuration is unchanged. Its history false positive remains a merge blocker until the gate owner accepts that exact exception. The draft-only review-gate failure is expected and no ready/merge action was taken. Codex completed the first published head without major issues; the final records-format follow-up is re-requested and its completion recorded in the PR body.

Final records-check tail:

```text
  "markdown_files": 13,
  "links_checked": 1527,
  "immutable_source_line_links": 745,
  "json_archives_parsed": 35,
  "jpeg_files": 339,
  "jpeg_bytes": 1596853,
  "errors": []
}
```

The storage helper emitted trailing whitespace after an empty YAML field; it was normalized before the complete-diff whitespace check. No frontend/application test result is implied by the records check.

## Validator review correction

The GitHub review of the inventory follow-up found that immutable source URLs were checked against worktree files. The validator now reads their bytes from the pinned Git tree, caches those reads, and excludes link text from the separate literal-path pass. Literal source citations also use the review baseline; new record paths use the checkout. A checkout must contain the referenced Git object to run this check.

A scratch repository probe changed and then deleted its worktree source while retaining the committed version, and checked an absent committed path. Result:

```text
Pinned-tree probe: PASS (changed worktree, deleted worktree file, absent pinned path)
```

The complete records validator passes again with the counts above. No application file or gate configuration changed.

The follow-up scope review found that a clean committed application change was invisible to git status. The validator now compares `--base` and `--head` (defaulting to the captured baseline and HEAD), unions those paths with pending changes, and disables rename detection so both the removed and added paths are checked. Pass explicit revisions when reviewing another checkout/range. The independent records reviewer inspected both validator fixes and found no material false-pass issue.

```text
Scope probe: PASS (records-only commit accepted; clean committed application change and source-to-record rename rejected)
```
