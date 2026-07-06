# A mid-session env/secret update does not reach the running shell — fingerprint the value before debugging

**Area:** process · **Date:** 2026-06-30

The user updated `ANTHROPIC_API_KEY` in the environment, but my shell kept seeing the old value
(env is captured at session start; updates don't propagate to a live session). Confirmed via a
non-secret fingerprint (prefix + length + last-2 charcodes) that the value hadn't changed.
**Rule:** when an env/secret is "updated" mid-session, verify the running process actually sees the
new value (fingerprint it) before debugging downstream; a fresh key may need a session restart, or
use the pasted value directly (write to a sourced scratch file, never echo it; recommend rotation).
