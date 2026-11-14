# Branch Cleanup Guide

> **2026-11-11: do not archive a branch as a tag.** The tag this guide created,
> `archive/2025-11-18-supabase-rag`, published a commit whose `backend/env.example.txt` held a real
> OpenRouter key and a Supabase secret key (GitHub secret-scanning alerts 1 and 2), outside CI's
> branches-only secret scan. The tag has since been deleted from GitHub, the keys are to be revoked
> (`tasks/todo.md` F77), and the script itself was deleted (#2048). The tag steps below are struck; see
> `lessons/ops-a-tag-publishes-the-commit-it-names.md`.

## Overview

Your repository has accumulated 19 stale branches (plus main) from previous development work. This guide will help you clean them up safely.

## Quick Summary

- **Total branches to delete**: 19
- **Branches to keep**: 1 (main)
- ~~**Archive preserved**: RAG/Supabase work saved as git tag~~ (the tag published real keys; see the note above)

## What Gets Deleted

### ✅ Safe to Delete - Merged to Main (16 branches)

**Merged Feature Branches (6):**
- `chore-remove-trending-tickers-N9qeV` - PR merged
- `claude/backend-financial-pipeline-3xu2b` - PR #48 merged
- `claude/fix-footer-links-vwOPV` - PR #47 merged
- `claude/fix-waitlist-conflicts-a4jY2` - PR #52 merged
- `fix-yahoo-rate-limit-tn2HH` - PR merged
- `fix/ci-tests-and-local-changes` - PR #50 merged

**Merged Codex Branches (10):**
All were merged via PRs #1-11:
- `codex/add-backend-tests-for-summarize_filing`
- `codex/add-helper-to-render-markdown-in-summarysections`
- `codex/add-trending-tickers-section-to-homepage`
- `codex/enhance-structured-summary-generation`
- `codex/investigate-and-resolve-github-failures`
- `codex/perform-code-review-for-earningsnerd-repo`
- `codex/refactor-earningsnerd-for-investor-grade-summaries`
- `codex/replace-recent-filings-with-hot-filings-section`
- `codex/update-schema_template-requirements-in-openai-service`
- `codex/update-summarize_filing-for-section-coverage`

### ⚠️ Stale Experimental Branches (3)

**Dated Branches:**
- `2025-11-09-yptw-D3nRL` - Vitest config fixes (likely superseded)
- `2025-11-10-p6z3-1dfbe` - Node.js + XBRL improvements (likely superseded)
- `2025-11-18-qpw4-40e1b` - **RAG/Supabase integration** (was archived as a tag that published real keys; see the note above)

## Automated Cleanup

### Option 1: Run the Script (Removed)

`scripts/cleanup-branches.sh` has been deleted: under `set -e` it exited after its first
successful delete, and the branches it named are long gone. Use Option 2. The block below is
kept as history.

```bash
# Make sure you're in the repo root
cd /home/user/EarningsNerd

# Run the cleanup script
./scripts/cleanup-branches.sh
```

The script will:
1. ~~Create archive tag `archive/2025-11-18-supabase-rag`~~ (removed 2026-11-11)
2. ✅ Delete all 19 branches
3. ✅ Clean up local references
4. ✅ Show summary of results

### Option 2: Manual Cleanup

If the script fails, run these commands manually:

#### Step 1: (removed 2026-11-11)
The archive tag published a commit holding real keys; never push a tag of an unscanned branch.

#### Step 2: Delete Merged Branches
```bash
git push origin --delete \
  chore-remove-trending-tickers-N9qeV \
  claude/backend-financial-pipeline-3xu2b \
  claude/fix-footer-links-vwOPV \
  claude/fix-waitlist-conflicts-a4jY2 \
  fix-yahoo-rate-limit-tn2HH \
  fix/ci-tests-and-local-changes
```

#### Step 3: Delete Codex Branches
```bash
git push origin --delete \
  codex/add-backend-tests-for-summarize_filing \
  codex/add-helper-to-render-markdown-in-summarysections \
  codex/add-trending-tickers-section-to-homepage \
  codex/enhance-structured-summary-generation \
  codex/investigate-and-resolve-github-failures \
  codex/perform-code-review-for-earningsnerd-repo \
  codex/refactor-earningsnerd-for-investor-grade-summaries \
  codex/replace-recent-filings-with-hot-filings-section \
  codex/update-schema_template-requirements-in-openai-service \
  codex/update-summarize_filing-for-section-coverage
```

#### Step 4: Delete Stale Branches
```bash
git push origin --delete \
  2025-11-09-yptw-D3nRL \
  2025-11-10-p6z3-1dfbe \
  2025-11-18-qpw4-40e1b
```

#### Step 5: Clean Local References
```bash
git fetch --prune
git branch -vv | grep ': gone]' | awk '{print $1}' | xargs git branch -D
```

## Restoring Archived Work

The archive tag has been deleted from GitHub: it published real keys. Keep any
copy of the RAG/Supabase work offline (a `git bundle` on your own machine), never as a pushed ref.

## What the RAG Archive Contains

The archived RAG/Supabase branch includes:
- Complete Supabase backend integration
- Retrieval Augmented Generation (RAG) for AI summarization
- Watchlist & real-time alerts feature
- Database schema reorganization for filing chunks
- RAGService for processing filings and querying
- Environment configurations for Supabase

## Verification

After cleanup, verify:

```bash
# Should show only 'main' (or very few branches)
git branch -a

# Should show no archive tag
git tag -l "archive/*"

# Should show ~20 fewer branches
git branch -r | wc -l
```

## Expected Result

**Before:** 20 branches (19 + main)
**After:** 1 branch (main)

## Troubleshooting

### Script Fails with 403 Error
- You may need to run from a properly authenticated environment
- Use the manual commands instead

### Can't Delete a Specific Branch
- Check if it has open PRs: `gh pr list --head <branch-name>`
- May have branch protection rules
- Contact repo admin if needed

## Safety Notes

✅ All branches to be deleted are either:
- Merged to main (code is preserved)
- Stale experimental work

✅ Merged work is in main
