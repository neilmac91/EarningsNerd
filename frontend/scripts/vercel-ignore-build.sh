#!/usr/bin/env bash
# Vercel's Ignored Build Step for this project (vercel.json `ignoreCommand`), run by Vercel in the
# Root Directory, frontend/, before it installs or builds anything. Exit 0 cancels the deployment's
# build; any other exit builds it.
#
# It skips a build only on proof: nothing the build reads differs between this commit and the commit
# of this branch's last successful deployment (VERCEL_GIT_PREVIOUS_SHA). Every other case builds:
# a branch's first deployment, which has no such commit; a redeploy of the commit already deployed,
# which is how a changed dashboard variable reaches a build; a commit Vercel's shallow clone does
# not hold; and any failure to read. The one line it prints says what it read and why it decided.
#
# What the build reads: everything under frontend/, and nothing else. It is named from the repository's
# top, so the working directory does not change the answer. backend/tests/unit/test_frontend_build_filter.py
# runs this script on real histories, and fails when a shipped frontend file reads a file outside
# frontend/: such a file is copied in and held to its source by a spec instead, as
# frontend/lib/publicEmailAddresses.json is.
BUILD_INPUTS=(
  ':(top)frontend'
)

build() { printf 'ignore-build: build: %s\n' "$1"; exit 1; }

previous=${VERCEL_GIT_PREVIOUS_SHA:-}
[[ "$previous" =~ ^[0-9a-f]{40}$ ]] ||
  build "no earlier successful deployment of this branch to compare with (VERCEL_GIT_PREVIOUS_SHA is '${previous}')"
head=$(git rev-parse --verify 'HEAD^{commit}' 2>/dev/null) ||
  build 'git could not read HEAD'
[ "$previous" != "$head" ] ||
  build "this is a redeploy of ${head}, the commit already deployed"
changed=$(git diff --name-only --no-renames "$previous" "$head" -- "${BUILD_INPUTS[@]}" 2>/dev/null) ||
  build "git could not compare ${previous} with ${head}; the earlier commit may be outside this shallow clone"
[ -z "$changed" ] ||
  build "$(printf '%s\n' "$changed" | wc -l | tr -d ' ') build input(s) changed since ${previous}, the first being $(printf '%s\n' "$changed" | head -n 1)"

printf 'ignore-build: skip: nothing the build reads changed between %s and %s\n' "$previous" "$head"
exit 0
