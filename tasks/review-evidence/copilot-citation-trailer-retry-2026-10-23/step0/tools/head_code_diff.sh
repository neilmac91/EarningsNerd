#!/usr/bin/env bash
# For each run head, list the blob SHAs of the Copilot-path files (GitHub contents API, read only) and
# compare them with H (d4d9c510, local worktree HEAD) and with H's main base B (b3d3cb11).
# Output TSV: head_sha, files differing from H, files differing from B ("-" when none).
# Usage: head_code_diff.sh <heads.txt> <h_worktree> <out.tsv> <listing_dir>
set -u
HEADS="$1"; WT="$2"; OUT="$3"; LDIR="$4"
mkdir -p "$LDIR"
FILES="backend/app/services/copilot_service.py backend/app/services/citation_markers.py backend/app/services/provenance_service.py backend/app/services/copilot_tools.py"
DIRS="backend/app/services/copilot backend/app/services/ai"
ref_listing() {  # <ref-kind> <ref> -> "path blobsha" lines
  if [ "$1" = local ]; then
    for f in $FILES; do git -C "$WT" ls-tree "$2" -- "$f" | awk '{print $4" "$3}'; done
    for d in $DIRS; do git -C "$WT" ls-tree "$2" -- "$d/" | awk '$2=="blob"{print $4" "$3}'; done
  else
    for f in $FILES; do gh api "repos/neilmac91/EarningsNerd/contents/$f?ref=$2" --jq '.path+" "+.sha' 2>/dev/null || echo "$f MISSING"; done
    for d in $DIRS; do gh api "repos/neilmac91/EarningsNerd/contents/$d?ref=$2" --jq '.[] | select(.type=="file") | .path+" "+.sha' 2>/dev/null || echo "$d MISSING"; done
  fi
}
ref_listing local HEAD | grep -E '\.py ' | sort > "$LDIR/H.txt"
ref_listing local b3d3cb11 | grep -E '\.py ' | sort > "$LDIR/B.txt"
: > "$OUT"
while read -r sha; do
  [ -s "$LDIR/$sha.txt" ] || ref_listing remote "$sha" | grep -E '\.py |MISSING' | sort > "$LDIR/$sha.txt"
  dh=$(comm -3 "$LDIR/H.txt" "$LDIR/$sha.txt" | awk '{print $1}' | sed 's#backend/app/services/##' | sort -u | paste -sd, -)
  db=$(comm -3 "$LDIR/B.txt" "$LDIR/$sha.txt" | awk '{print $1}' | sed 's#backend/app/services/##' | sort -u | paste -sd, -)
  printf '%s\t%s\t%s\n' "$sha" "${dh:--}" "${db:--}" >> "$OUT"
done < "$HEADS"
echo HEADDIFF_DONE
