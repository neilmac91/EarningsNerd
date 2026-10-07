#!/bin/bash
# Read-only check of the two private H20 planning folders on the founder's Mac: iCloud status, byte length and
# SHA-256 per file. Never prints file contents. Writes nothing inside the folders. Output: a text file on the Desktop.
# Usage: bash ~/Downloads/h20-custody-check.sh "/path/to/bootstrap-folder" "/path/to/predecessor-folder"
# STATUS per line: LOCAL = bytes already on disk; WAS_DATALESS = iCloud-evicted before this read (the read fetches
# it, like Finder's Download Now); STUB = a .name.icloud placeholder; UNREADABLE = could not be read after one try.
set -u
if [ $# -ne 2 ]; then
  echo "Usage: bash $0 \"/path/to/bootstrap-folder\" \"/path/to/predecessor-folder\""
  exit 2
fi
OUTDIR="$HOME/Desktop"
[ -d "$OUTDIR" ] || OUTDIR="$HOME"
OUT="$OUTDIR/h20-custody-check-$(date -u +%Y%m%dT%H%M%SZ).txt"
check() {
  local dir="$1" total=0 local_ok=0 dataless=0 stubs=0 unreadable=0 f base size flags status h
  echo "## $dir"
  if [ ! -d "$dir" ]; then
    echo "MISSING_DIR"
    return
  fi
  while IFS= read -r -d '' f; do
    total=$((total+1))
    base=$(basename "$f")
    case "$base" in
      .*.icloud) stubs=$((stubs+1)); echo "STUB  -  -  $f"; continue;;
    esac
    size=$(stat -f '%z' "$f" 2>/dev/null || echo '?')
    flags=$(stat -f '%f' "$f" 2>/dev/null || echo 0)
    status=LOCAL
    if [ $((flags & 1073741824)) -ne 0 ]; then
      status=WAS_DATALESS
      dataless=$((dataless+1))
    fi
    h=$(shasum -a 256 "$f" 2>/dev/null | cut -d' ' -f1)
    if [ -n "$h" ]; then
      [ "$status" = LOCAL ] && local_ok=$((local_ok+1))
      echo "$status  $size  $h  $f"
    else
      unreadable=$((unreadable+1))
      echo "UNREADABLE  $size  -  $f"
    fi
  done < <(find "$dir" -type f -print0 | sort -z)
  echo "TOTAL=$total LOCAL_BEFORE=$local_ok MATERIALISED_BY_THIS_READ=$dataless STUBS=$stubs UNREADABLE=$unreadable"
}
{
  echo "h20 custody check $(date -u +%Y-%m-%dT%H:%M:%SZ) macOS $(sw_vers -productVersion 2>/dev/null)"
  check "$1"
  check "$2"
} | tee "$OUT"
echo
echo "Saved: $OUT"
echo "Give that file to Astra for the manifest comparison. Send the chief only the two TOTAL= lines."
