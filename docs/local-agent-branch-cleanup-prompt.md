# Local AI Agent: Branch Cleanup Execution Prompt

**Objective**: Execute the automated branch cleanup script to delete 19 stale/merged branches from the EarningsNerd repository.

---

## Context

The EarningsNerd repository has accumulated 19 stale branches that need cleanup:
- **6 merged feature branches** (code already in main)
- **10 merged codex branches** (PRs #1-11, all merged)
- **3 stale experimental branches** (2 are old test configs, 1 is RAG/Supabase work)

A cleanup script has been created at `scripts/cleanup-branches.sh` that automates this process.

---

## Prerequisites

✅ **ASSUMPTION**: The local repository is already synced with GitHub (user has confirmed this)

---

## Your Task

Execute the branch cleanup script and verify successful completion.

### Step 1: Verify Repository State

First, confirm you're in the correct repository and on the right branch:

```bash
# Verify you're in the EarningsNerd repo
pwd

# Check current branch
git branch --show-current

# Verify the cleanup script exists
ls -lh scripts/cleanup-branches.sh
```

**Expected output:**
- Current directory should end with `/EarningsNerd`
- Should see the cleanup script file

### Step 2: Review What Will Be Deleted

Before executing, show what branches exist:

```bash
# Count current remote branches
echo "Current remote branches:"
git branch -r | grep -v HEAD | wc -l

# List all remote branches
git branch -r | grep -v HEAD
```

**Expected output:** Should show ~20 branches (19 + main)

### Step 3: Execute the Cleanup Script

Run the automated cleanup script:

```bash
# Execute the cleanup script
cd /home/user/EarningsNerd
./scripts/cleanup-branches.sh
```

**What to expect:**
1. Script will ask for confirmation (respond with `y`)
2. Will attempt to create an archive tag for the RAG branch
3. Will delete 19 branches in stages:
   - 6 merged feature branches
   - 10 merged codex branches
   - 3 stale experimental branches
4. Will clean up local references
5. Will show a summary of deletions

**Note:** The script may fail on individual branch deletions due to permissions or if branches were already deleted. This is OK - continue to completion.

### Step 4: Handle Script Execution

**If the script runs successfully:**
- Proceed to Step 5 for verification

**If the script fails completely (permission errors):**
- Use the manual cleanup commands from `docs/branch-cleanup-guide.md`
- Execute the commands in this order:
  1. Archive the RAG branch (create tag)
  2. Delete merged feature branches
  3. Delete codex branches
  4. Delete stale branches
  5. Clean up local references

**Manual fallback commands:**

```bash
# 1. Archive RAG branch
git tag -a archive/2025-11-18-supabase-rag $(git rev-parse origin/2025-11-18-qpw4-40e1b) -m "Archive: Supabase RAG integration"
git push origin archive/2025-11-18-supabase-rag

# 2. Delete merged feature branches
git push origin --delete \
  chore-remove-trending-tickers-N9qeV \
  claude/backend-financial-pipeline-3xu2b \
  claude/fix-footer-links-vwOPV \
  claude/fix-waitlist-conflicts-a4jY2 \
  fix-yahoo-rate-limit-tn2HH \
  fix/ci-tests-and-local-changes

# 3. Delete codex branches
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

# 4. Delete stale branches
git push origin --delete \
  2025-11-09-yptw-D3nRL \
  2025-11-10-p6z3-1dfbe \
  2025-11-18-qpw4-40e1b

# 5. Clean up local references
git fetch --prune
git branch -vv | grep ': gone]' | awk '{print $1}' | xargs git branch -D
```

### Step 5: Verification

After cleanup (whether via script or manual), verify the results:

```bash
# Count remaining branches (should be 1-2)
echo "=== Remaining Remote Branches ==="
git branch -r | grep -v HEAD | wc -l

# List remaining branches
git branch -r | grep -v HEAD

# Verify archive tag was created
echo "=== Archive Tags ==="
git tag -l "archive/*"

# Show local branches
echo "=== Local Branches ==="
git branch
```

**Expected results:**
- Remote branches: Should show only `origin/main` (possibly 1-2 others like current working branch)
- Archive tags: Should show `archive/2025-11-18-supabase-rag`
- Local branches: Should show current branch and possibly `main`

### Step 6: Report Results

Provide a summary report in this format:

```
=== BRANCH CLEANUP SUMMARY ===

Execution Method: [Script / Manual]

Results:
- Branches deleted successfully: X
- Branches that failed to delete: Y
- Archive tag created: [Yes/No]

Before cleanup: 20 branches
After cleanup: Z branches

Remaining branches:
[List them]

Archive tags:
[List them]

Status: [SUCCESS / PARTIAL SUCCESS / FAILED]

Notes:
[Any issues encountered or observations]
```

---

## Success Criteria

✅ **Complete Success:**
- 19 branches deleted (only `origin/main` remains)
- Archive tag `archive/2025-11-18-supabase-rag` created
- No errors during execution

✅ **Partial Success:**
- Most branches deleted (15-19 out of 19)
- Archive tag created
- Some branches may have failed due to already being deleted or permissions

❌ **Failure:**
- Script won't run
- Permission errors prevent all deletions
- Archive tag not created

---

## Error Handling

### Common Errors and Solutions

**Error: "error: RPC failed; HTTP 403"**
- **Cause**: Permission restriction or authentication issue
- **Solution**: This is expected in sandboxed environments. Report this to the user - they may need to run cleanup from their authenticated local machine.

**Error: "tag 'archive/...' already exists"**
- **Cause**: Tag was already created in a previous attempt
- **Solution**: This is fine - skip tag creation and continue with deletions

**Error: "remote ref does not exist"**
- **Cause**: Branch was already deleted
- **Solution**: This is fine - continue with remaining branches

**Error: "refusing to delete the current branch"**
- **Cause**: Trying to delete the checked-out branch
- **Solution**: This shouldn't happen, but if it does, checkout main first: `git checkout main`

---

## Additional Commands (If Needed)

### To check branch merge status:
```bash
# See which branches are merged to main
git branch -r --merged origin/main | grep -v "origin/main"

# See which branches are NOT merged
git branch -r --no-merged origin/main | grep -v "origin/main"
```

### To see what code was in a deleted branch:
```bash
# View the archived RAG branch
git show archive/2025-11-18-supabase-rag

# Or check it out
git checkout -b temp-rag-review archive/2025-11-18-supabase-rag
```

### To force delete a stubborn local branch:
```bash
git branch -D <branch-name>
```

---

## Final Notes

- **Be patient**: Deleting 19 branches may take 30-60 seconds
- **Don't panic on individual failures**: Some branches might already be deleted
- **Archive is safe**: The RAG/Supabase work is preserved as a git tag
- **Reversible**: Everything can be recovered from git history or the archive tag

---

## Expected Timeline

- **Step 1-2 (Verification)**: 10 seconds
- **Step 3 (Execution)**: 30-60 seconds
- **Step 4 (Error handling if needed)**: 2-3 minutes
- **Step 5 (Verification)**: 10 seconds
- **Step 6 (Report)**: 10 seconds

**Total estimated time:** 2-4 minutes

---

## Begin Execution

Start with Step 1 and proceed sequentially through all steps. Report your progress and any issues as you go.

Good luck! 🚀
