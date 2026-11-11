#!/bin/bash
# Branch Cleanup Script for EarningsNerd
# This script removes 19 stale/merged branches

set -e  # Exit on error

echo "========================================="
echo "  EarningsNerd Branch Cleanup Script"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counter for tracking
DELETED_COUNT=0
FAILED_COUNT=0

echo "This script will:"
echo "  2. Delete 6 merged feature branches"
echo "  3. Delete 10 merged codex branches"
echo "  4. Delete 3 stale experimental branches"
echo "  Total: 19 branches to be removed"
echo ""

read -p "Do you want to proceed? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cleanup cancelled."
    exit 1
fi

# Step 1 (archiving the RAG/Supabase branch as a tag) was removed on 2026-11-11: the tag it pushed,
# archive/2025-11-18-supabase-rag, published a commit holding a real OpenRouter key and a Supabase
# secret key (secret-scanning alerts 1 and 2). Never archive a branch as a tag without scanning it;
# lessons/ops-a-tag-publishes-the-commit-it-names.md.

echo ""
echo "========================================="
echo "Step 2: Deleting Merged Feature Branches"
echo "========================================="

MERGED_BRANCHES=(
    "chore-remove-trending-tickers-N9qeV"
    "claude/backend-financial-pipeline-3xu2b"
    "claude/fix-footer-links-vwOPV"
    "claude/fix-waitlist-conflicts-a4jY2"
    "fix-yahoo-rate-limit-tn2HH"
    "fix/ci-tests-and-local-changes"
)

for branch in "${MERGED_BRANCHES[@]}"; do
    echo -n "Deleting $branch... "
    if git push origin --delete "$branch" 2>/dev/null; then
        echo -e "${GREEN}✓${NC}"
        ((DELETED_COUNT++))
    else
        echo -e "${RED}✗ Failed${NC}"
        ((FAILED_COUNT++))
    fi
done

echo ""
echo "========================================="
echo "Step 3: Deleting Merged Codex Branches"
echo "========================================="

CODEX_BRANCHES=(
    "codex/add-backend-tests-for-summarize_filing"
    "codex/add-helper-to-render-markdown-in-summarysections"
    "codex/add-trending-tickers-section-to-homepage"
    "codex/enhance-structured-summary-generation"
    "codex/investigate-and-resolve-github-failures"
    "codex/perform-code-review-for-earningsnerd-repo"
    "codex/refactor-earningsnerd-for-investor-grade-summaries"
    "codex/replace-recent-filings-with-hot-filings-section"
    "codex/update-schema_template-requirements-in-openai-service"
    "codex/update-summarize_filing-for-section-coverage"
)

for branch in "${CODEX_BRANCHES[@]}"; do
    echo -n "Deleting $branch... "
    if git push origin --delete "$branch" 2>/dev/null; then
        echo -e "${GREEN}✓${NC}"
        ((DELETED_COUNT++))
    else
        echo -e "${RED}✗ Failed${NC}"
        ((FAILED_COUNT++))
    fi
done

echo ""
echo "========================================="
echo "Step 4: Deleting Stale Experimental Branches"
echo "========================================="

STALE_BRANCHES=(
    "2025-11-09-yptw-D3nRL"
    "2025-11-10-p6z3-1dfbe"
    "2025-11-18-qpw4-40e1b"
)

for branch in "${STALE_BRANCHES[@]}"; do
    echo -n "Deleting $branch... "
    if git push origin --delete "$branch" 2>/dev/null; then
        echo -e "${GREEN}✓${NC}"
        ((DELETED_COUNT++))
    else
        echo -e "${RED}✗ Failed${NC}"
        ((FAILED_COUNT++))
    fi
done

echo ""
echo "========================================="
echo "Step 5: Cleaning Up Local References"
echo "========================================="

echo -n "Pruning deleted remote branches... "
if git fetch --prune 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠ Prune may have failed${NC}"
fi

echo -n "Removing local branches tracking deleted remotes... "
GONE_BRANCHES=$(git branch -vv | grep ': gone]' | awk '{print $1}' || true)
if [ -n "$GONE_BRANCHES" ]; then
    echo "$GONE_BRANCHES" | xargs git branch -D 2>/dev/null || true
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}None found${NC}"
fi

echo ""
echo "========================================="
echo "Cleanup Complete!"
echo "========================================="
echo ""
echo -e "${GREEN}Successfully deleted: $DELETED_COUNT branches${NC}"
if [ $FAILED_COUNT -gt 0 ]; then
    echo -e "${RED}Failed to delete: $FAILED_COUNT branches${NC}"
fi
echo ""
echo "Remaining branches:"
git branch -a | grep -v "HEAD"
echo ""
echo "Archive tags:"
git tag -l "archive/*"
echo ""
echo "✨ Your repository is now clean!"
