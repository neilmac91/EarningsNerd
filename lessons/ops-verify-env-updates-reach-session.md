# Fingerprint env values in the running shell before debugging a rotated secret

Date: 2026-06-30   Area: ops

**Context**: The user updated `ANTHROPIC_API_KEY` in the environment, but the shell kept seeing the old value — env is captured at session start and updates don't propagate to a live session. Confirmed via a non-secret fingerprint that the visible value hadn't changed.

**Rule**: When an env/secret is "updated" mid-session, verify the running process actually sees the new value (fingerprint it: prefix + length + last-2 charcodes — never echo it) before debugging downstream. A fresh key may need a session restart, or use the pasted value directly via a sourced scratch file; recommend rotation afterwards.

**Evidence**: `ANTHROPIC_API_KEY` mid-session update invisible to the running shell; confirmed via prefix + length + last-2 charcodes fingerprint.
