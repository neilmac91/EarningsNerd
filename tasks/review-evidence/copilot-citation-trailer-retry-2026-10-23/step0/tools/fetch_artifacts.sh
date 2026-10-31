#!/usr/bin/env bash
# Download each copilot-eval artifact zip into its own directory, extract only the report files
# (never executing anything from it), record the zip listing, then delete the zip to save disk.
# Usage: fetch_artifacts.sh <run-artifacts.tsv> <artifacts_dir>
set -u
TSV="$1"
DIR="$2"
while IFS=$'\t' read -r run art name size expired sha created; do
  d="$DIR/$run"
  [ -f "$d/.done" ] && continue
  mkdir -p "$d"
  if [ "$expired" = "true" ]; then echo "expired" > "$d/.excluded"; touch "$d/.done"; continue; fi
  if ! gh api "repos/neilmac91/EarningsNerd/actions/artifacts/$art/zip" > "$d/a.zip" 2> "$d/dl.err"; then
    echo "download failed" > "$d/.excluded"; rm -f "$d/a.zip"; touch "$d/.done"; continue
  fi
  unzip -Z1 "$d/a.zip" > "$d/zip-listing.txt" 2>> "$d/dl.err"
  sha256sum "$d/a.zip" | cut -d' ' -f1 > "$d/zip.sha256"
  mkdir -p "$d/x"
  for member in copilot-eval.json copilot-eval.md preparation.json preparation.log runner.log; do
    if grep -qx "$member" "$d/zip-listing.txt"; then
      unzip -o -q "$d/a.zip" "$member" -d "$d/x" 2>> "$d/dl.err"
    fi
  done
  rm -f "$d/a.zip"
  echo "$run $art $(ls "$d/x" | tr '\n' ' ')"
  touch "$d/.done"
done < "$TSV"
echo FETCH_DONE
