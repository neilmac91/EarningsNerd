#!/usr/bin/env bash
# setup_citation_alerts.sh — one-time, idempotent setup of Google Cloud alerting for
# EarningsNerd copilot citation-quality warnings. The citation resolver logs two
# WARNING lines: "misplaced fact marker" (fact chip stripped for sitting on the
# wrong figure/metric) and "uncited figure" (answer shipped figures uncited).
#
# Creates: 2 log-based metrics, 1 email notification channel, 2 alert policies.
# Safe to re-run — existing resources are detected and reused/skipped.
#
# Usage:    bash setup_citation_alerts.sh alerts@example.com
# Requires: authenticated gcloud with alpha + beta components installed
#           (gcloud components install alpha beta)
#           The deployed backend must include the JSON formatter's "severity" field
#           (logging_service.py) — shipped in the same PR as this script — or the
#           severity>=WARNING clause below will never match JSON logs.

set -euo pipefail

EMAIL="${1:-}"
if [[ -z "$EMAIL" ]]; then
  echo "Usage: $0 <alert-email-address>" >&2
  echo "Env overrides: PROJECT_ID (earnings-nerd), SERVICE (earningsnerd-backend), REGION (us-west1)" >&2
  exit 1
fi

PROJECT_ID="${PROJECT_ID:-earnings-nerd}"
SERVICE="${SERVICE:-earningsnerd-backend}"
REGION="${REGION:-us-west1}" # informational — metrics/policies are project-level
CHANNEL_DISPLAY_NAME="EarningsNerd Alerts"
RUNBOOK="backend/evals/RUNBOOK.md, section 'Copilot citation-fidelity audit'"
SUMMARY=()
METRIC_CREATED=0

echo "Project: ${PROJECT_ID} | Service: ${SERVICE} (${REGION}) | Email: ${EMAIL}"

# --- 1. Log-based metrics (describe first; skip if they already exist) -------
# Production emits structured JSON logs, but the message can land in either
# jsonPayload.message or textPayload — the filter must cover both.
create_metric() { # $1=metric name  $2=match phrase  $3=description
  if gcloud logging metrics describe "$1" --project="$PROJECT_ID" >/dev/null 2>&1; then
    SUMMARY+=("metric   $1: already exists (reused)")
    return
  fi
  gcloud logging metrics create "$1" \
    --project="$PROJECT_ID" \
    --description="$3" \
    --log-filter="resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${SERVICE}\" AND severity>=WARNING AND (jsonPayload.message:\"$2\" OR textPayload:\"$2\")"
  SUMMARY+=("metric   $1: created")
  METRIC_CREATED=1
}

create_metric copilot_misplaced_fact_markers "misplaced fact marker" \
  "Copilot citation resolver stripped a fact chip attached to the wrong figure/metric"
create_metric copilot_uncited_figures "uncited figure" \
  "Copilot answer shipped financial figures with no citation"

# New log-based metrics take a moment to become visible to Cloud Monitoring;
# creating a policy against them immediately can fail with "metric not found".
if [[ "$METRIC_CREATED" == 1 ]]; then
  echo "Waiting 20s for new log-based metric(s) to propagate to Cloud Monitoring..."
  sleep 20
fi

# --- 2. Email notification channel (reuse by display name) -------------------
CHANNEL=$(gcloud beta monitoring channels list --project="$PROJECT_ID" \
  --filter="displayName=\"${CHANNEL_DISPLAY_NAME}\"" --format="value(name)" --limit=1)
if [[ -n "$CHANNEL" ]]; then
  SUMMARY+=("channel  ${CHANNEL_DISPLAY_NAME}: already exists (reused: ${CHANNEL})")
else
  CHANNEL=$(gcloud beta monitoring channels create --project="$PROJECT_ID" \
    --display-name="$CHANNEL_DISPLAY_NAME" --type=email \
    --channel-labels="email_address=${EMAIL}" --format="value(name)")
  SUMMARY+=("channel  ${CHANNEL_DISPLAY_NAME}: created (${CHANNEL} -> ${EMAIL})")
fi

# --- 3. Alert policies (skip if a policy with the same displayName exists) ---
create_policy() { # $1=displayName  $2=metric name  $3=threshold  $4=docs content
  local existing tmp
  existing=$(gcloud alpha monitoring policies list --project="$PROJECT_ID" \
    --filter="displayName=\"$1\"" --format="value(name)" --limit=1)
  if [[ -n "$existing" ]]; then
    SUMMARY+=("policy   $1: already exists (skipped)")
    return
  fi
  tmp=$(mktemp)
  cat >"$tmp" <<EOF
{
  "displayName": "$1",
  "documentation": { "content": "$4", "mimeType": "text/markdown" },
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": ["${CHANNEL}"],
  "conditions": [{
    "displayName": "$2 count > $3 per hour",
    "conditionThreshold": {
      "filter": "resource.type = \\"cloud_run_revision\\" AND metric.type = \\"logging.googleapis.com/user/$2\\"",
      "comparison": "COMPARISON_GT",
      "thresholdValue": $3,
      "duration": "0s",
      "aggregations": [{ "alignmentPeriod": "3600s", "perSeriesAligner": "ALIGN_SUM" }],
      "trigger": { "count": 1 }
    }
  }]
}
EOF
  gcloud alpha monitoring policies create --project="$PROJECT_ID" --policy-from-file="$tmp"
  rm -f "$tmp"
  SUMMARY+=("policy   $1: created")
}

create_policy "Copilot: misplaced fact markers" copilot_misplaced_fact_markers 0 \
  "The copilot citation resolver stripped one or more fact chips because they sat on the wrong figure/metric. Answers still shipped, but with fewer verifiable citations. Any occurrence warrants a look. Investigate per ${RUNBOOK}."
create_policy "Copilot: uncited figures elevated" copilot_uncited_figures 5 \
  "Copilot answers shipped financial figures with no citation at an elevated rate (> 5/hour). Occasional occurrences are expected; sustained elevation suggests a prompt or model regression. Investigate per ${RUNBOOK}."

# --- 4. Summary ---------------------------------------------------------------
echo
echo "Done. Resources:"
printf '  %s\n' "${SUMMARY[@]}"
echo
echo "Verify with:"
echo "  gcloud alpha monitoring policies list --project=${PROJECT_ID} --format=\"table(displayName,enabled)\""
