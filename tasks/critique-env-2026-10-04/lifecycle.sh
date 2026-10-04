# Shared process-ownership helpers for the critique environment's lifecycle scripts. Source this file; do not run it.
#
# Supported environment: Linux only. The helpers read /proc/<pid>/stat, /proc/<pid>/cmdline and /proc/<pid>/cwd and the
# start scripts create a session/process group with setsid. Elsewhere lc_require_linux exits 2 with a clear message and
# nothing is changed (records are left in place; stop any servers manually).
#
# A server started by start_mock.sh / start_next.sh is described by a RECORD file (<name>.proc), one key=value per line:
#   pid=<n>            the server process (the process group leader the start script created)
#   pgid=<n> sid=<n>   its process group and session ids; both equal pid because the start script used setsid
#   starttime=<n>      /proc/<pid>/stat field 22 (clock ticks since boot): a PID reused by another process has a different value
#   boot_id=<uuid>     /proc/sys/kernel/random/boot_id at start: a starttime is only comparable within one boot
#   cwd=<path>         physical working directory of the process (readlink /proc/<pid>/cwd; the scripts derive their own
#                      directories with pwd -P so a checkout reached through a symlink still matches)
#   cmd=<text>         full command line once stable after start-up (Next sets its process title to "next-server (v…)")
#   started_at=<iso>   UTC time the record was written (informational)
# A live process is OWNED only when EVERY identity field still matches (pid alive, same boot, same starttime, pgid == sid == pid,
# cwd equals both the recorded and the expected directory, cmd equals the recorded command and contains the expected token).
# Anything else is refused: a mismatching process is never signalled, even when its command line looks right, and a refused
# record is renamed to <name>.proc.rejected rather than silently discarded.

lc_require_linux() {
  if [ "$(uname -s 2>/dev/null)" != "Linux" ] || [ ! -r /proc/self/stat ] || ! command -v setsid >/dev/null 2>&1; then
    echo "$(basename "$0"): the critique lifecycle scripts support Linux only (they need /proc and setsid); nothing was changed." >&2
    echo "Stop any critique servers manually and remove the *.proc records yourself." >&2
    exit 2
  fi
}

lc_boot_id() { cat /proc/sys/kernel/random/boot_id 2>/dev/null || echo unknown; }

# lc_stat <pid>: sets LC_STATE LC_PGID LC_SID LC_START from /proc/<pid>/stat; returns 1 when the process is gone or unreadable.
# A zombie (state Z) or dead (X) process still has a /proc entry; callers treat it as not running.
lc_stat() {
  local pid="$1" stat rest arr
  stat="$(cat "/proc/$pid/stat" 2>/dev/null)" || return 1
  rest="${stat##*) }"                      # skip "pid (comm) "; comm may contain spaces or parentheses
  read -r -a arr <<< "$rest"
  LC_STATE="${arr[0]}"; LC_PGID="${arr[2]}"; LC_SID="${arr[3]}"; LC_START="${arr[19]}"
  [[ "$LC_PGID" =~ ^[0-9]+$ && "$LC_SID" =~ ^[0-9]+$ && "$LC_START" =~ ^[0-9]+$ ]]
}
lc_cmdline() { tr '\0' ' ' < "/proc/$1/cmdline" 2>/dev/null | sed 's/ *$//'; }
lc_cwd() { readlink "/proc/$1/cwd" 2>/dev/null; }

# lc_write_record <record> <pid> <expected cmd token> <expected cwd>
# Called once the server answers: waits (up to ~10 s) for the child's command line to contain the expected token AND to stay
# unchanged for a second (npx and Next rewrite argv/process title while starting), then snapshots its identity. Returns 1
# (and writes nothing) when the identity cannot be established: the caller then has a process it started but cannot vouch for.
lc_write_record() {
  local rec="$1" pid="$2" token="$3" want_cwd="$4" cmd prev="" cwd i stable=0
  [[ "$pid" =~ ^[1-9][0-9]{0,8}$ ]] || { echo "lifecycle: refusing to record non-numeric pid '$pid'" >&2; return 1; }
  for i in $(seq 1 40); do
    [ -d "/proc/$pid" ] || { echo "lifecycle: pid $pid exited before its identity could be recorded (expected '$token')" >&2; return 1; }
    cmd="$(lc_cmdline "$pid")"
    case "$cmd" in *"$token"*) if [ "$cmd" = "$prev" ]; then stable=$((stable + 1)); else stable=0; fi ;; *) stable=0 ;; esac
    [ "$stable" -ge 4 ] && break   # four identical samples 0.25 s apart
    prev="$cmd"; sleep 0.25
  done
  case "$cmd" in *"$token"*) ;; *) echo "lifecycle: pid $pid never ran '$token' (cmdline: ${cmd:-unreadable})" >&2; return 1 ;; esac
  [ "$stable" -ge 4 ] || { echo "lifecycle: pid $pid command line kept changing (last: '$cmd'); not recorded" >&2; return 1; }
  lc_stat "$pid" || { echo "lifecycle: cannot read /proc/$pid/stat" >&2; return 1; }
  case "$LC_STATE" in Z|X) echo "lifecycle: pid $pid is already dead (state $LC_STATE)" >&2; return 1 ;; esac
  if [ "$LC_PGID" != "$pid" ] || [ "$LC_SID" != "$pid" ]; then
    echo "lifecycle: pid $pid is not the leader of its own session/process group (pgid=$LC_PGID sid=$LC_SID); setsid did not take effect" >&2; return 1
  fi
  cwd="$(lc_cwd "$pid")"
  if [ "$cwd" != "$want_cwd" ]; then echo "lifecycle: pid $pid runs in '$cwd', expected '$want_cwd'" >&2; return 1; fi
  {
    echo "pid=$pid"; echo "pgid=$LC_PGID"; echo "sid=$LC_SID"; echo "starttime=$LC_START"; echo "boot_id=$(lc_boot_id)"
    echo "cwd=$cwd"; echo "cmd=$cmd"; echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } > "$rec.tmp" && mv "$rec.tmp" "$rec"
}

# lc_read_record <record>: strict syntax validation; sets LC_R_PID LC_R_PGID LC_R_SID LC_R_START LC_R_BOOT LC_R_CWD LC_R_CMD.
# Returns 1 with LC_REASON set when the file is not a well-formed record.
lc_read_record() {
  local rec="$1" line key val n=0
  LC_R_PID=; LC_R_PGID=; LC_R_SID=; LC_R_START=; LC_R_BOOT=; LC_R_CWD=; LC_R_CMD=; LC_REASON=
  while IFS= read -r line || [ -n "$line" ]; do
    n=$((n + 1))
    [[ "$line" =~ ^(pid|pgid|sid|starttime|boot_id|cwd|cmd|started_at)=(.*)$ ]] || { LC_REASON="line $n is not key=value: '$line'"; return 1; }
    key="${BASH_REMATCH[1]}"; val="${BASH_REMATCH[2]}"
    case "$key" in
      pid|pgid|sid) [[ "$val" =~ ^[1-9][0-9]{0,8}$ ]] || { LC_REASON="$key '$val' is not a positive integer"; return 1; } ;;
      starttime)    [[ "$val" =~ ^[0-9]{1,20}$ ]] || { LC_REASON="starttime '$val' is not an integer"; return 1; } ;;
      boot_id)      [[ "$val" =~ ^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|unknown)$ ]] || { LC_REASON="boot_id '$val' malformed"; return 1; } ;;
      cwd)          [[ "$val" =~ ^/ ]] || { LC_REASON="cwd '$val' is not absolute"; return 1; } ;;
      cmd)          [ -n "$val" ] || { LC_REASON="cmd is empty"; return 1; } ;;
    esac
    case "$key" in pid) LC_R_PID="$val" ;; pgid) LC_R_PGID="$val" ;; sid) LC_R_SID="$val" ;; starttime) LC_R_START="$val" ;;
                   boot_id) LC_R_BOOT="$val" ;; cwd) LC_R_CWD="$val" ;; cmd) LC_R_CMD="$val" ;; esac
  done < "$rec"
  for key in PID PGID SID START BOOT CWD CMD; do
    eval "[ -n \"\$LC_R_$key\" ]" || { LC_REASON="missing field for $key"; return 1; }
  done
  if [ "$LC_R_PGID" != "$LC_R_PID" ] || [ "$LC_R_SID" != "$LC_R_PID" ]; then LC_REASON="record is not a session/group leader (pid=$LC_R_PID pgid=$LC_R_PGID sid=$LC_R_SID)"; return 1; fi
  return 0
}

# lc_verify <record> <expected cmd token> <expected cwd>
# Exit codes: 0 owned (LC_PID, LC_PGID set) | 3 no record | 4 malformed record | 5 recorded process not running | 6 live process does not match.
# LC_REASON explains 4/5/6. Never signals anything.
lc_verify() {
  local rec="$1" token="$2" want_cwd="$3" cmd cwd boot
  LC_PID=; LC_PGID=; LC_REASON=
  [ -f "$rec" ] || { LC_REASON="no record"; return 3; }
  lc_read_record "$rec" || return 4
  [ -d "/proc/$LC_R_PID" ] || { LC_REASON="pid $LC_R_PID is not running"; return 5; }
  boot="$(lc_boot_id)"
  [ "$boot" = "$LC_R_BOOT" ] || { LC_REASON="boot_id differs (record $LC_R_BOOT, now $boot): the recorded process cannot have survived"; return 5; }
  lc_stat "$LC_R_PID" || { LC_REASON="pid $LC_R_PID vanished while checking"; return 5; }
  case "$LC_STATE" in Z|X) LC_REASON="pid $LC_R_PID is a zombie/dead process (state $LC_STATE), not a running server"; return 5 ;; esac
  [ "$LC_START" = "$LC_R_START" ] || { LC_REASON="pid $LC_R_PID start time differs (record $LC_R_START, live $LC_START): the pid was reused"; return 6; }
  [ "$LC_PGID" = "$LC_R_PID" ] && [ "$LC_SID" = "$LC_R_PID" ] || { LC_REASON="pid $LC_R_PID is not its own group/session leader (pgid=$LC_PGID sid=$LC_SID)"; return 6; }
  cwd="$(lc_cwd "$LC_R_PID")"
  [ "$cwd" = "$LC_R_CWD" ] || { LC_REASON="pid $LC_R_PID working directory differs (record $LC_R_CWD, live $cwd)"; return 6; }
  [ "$cwd" = "$want_cwd" ] || { LC_REASON="pid $LC_R_PID runs in $cwd, this environment's server runs in $want_cwd"; return 6; }
  cmd="$(lc_cmdline "$LC_R_PID")"
  [ "$cmd" = "$LC_R_CMD" ] || { LC_REASON="pid $LC_R_PID command line differs (record '$LC_R_CMD', live '$cmd')"; return 6; }
  case "$cmd" in *"$token"*) ;; *) LC_REASON="pid $LC_R_PID command line '$cmd' lacks '$token'"; return 6 ;; esac
  LC_PID="$LC_R_PID"; LC_PGID="$LC_PGID"
  return 0
}

# lc_reject_record <record> <label> <reason>: keep the evidence, never delete it silently.
lc_reject_record() {
  local rec="$1" label="$2" reason="$3"
  mv -f "$rec" "$rec.rejected"
  echo "$label: record $(basename "$rec") REJECTED ($reason); the process was left alone and the record was moved to $(basename "$rec").rejected" >&2
}
