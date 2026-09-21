# Operations readiness package — 2026-09-21

Preparation only. Nothing here has been applied to project `earnings-nerd`. The copied 2026-09-20 [observation receipt](observations-2026-09-20.json) records backup/PITR enabled, deletion protection false, two Copilot policies using channel `projects/earnings-nerd/notificationChannels/2698479126467110226`, and no uptime configuration. It does not prove that the channel delivers. The existing [E09 decision package](../../fleet-coordination-proposal-2026-09-19.md) remains the source for the job-ledger access boundary and the two separate fleet decisions.

## General alerts — apply only after the production hold is released

The four [policy JSON files](alerts/) are exact Cloud Monitoring `AlertPolicy` create bodies. The notification channel is a placeholder so it can be checked against the existing Copilot policy before use. The uptime policy also needs the assigned check ID. All four policy names are unique within this package. The job policy observes all Cloud Run jobs in this project and the **completed execution** metric; it does not infer useful work from exit 0. The log filters match `logging_service.py`'s `jsonPayload.message` or ordinary `textPayload` and the messages in `circuit_breaker.py` and `summary_pipeline.py`. A handler that catches an error and emits no matching terminal log will not fire this alert.

Before application, read back the current inventory and channel metadata without exposing its recipient in the receipt. Verify the channel is enabled, has an appropriate destination owner, and appears on the two existing Copilot policies. Confirm a recent `run.googleapis.com/job/completed_execution_count` time series has `metric.label.result="failed"` or confirm that enum through the Monitoring metrics explorer; Google's metric catalog documents the label but not its values. If no failed sample exists, mark that part unproven and verify against a future natural failure; do not force an execution. Verify no policy or uptime check already uses these display names. The uptime check probes `https://api.earningsnerd.io/health/detailed` every minute, requires HTTP 200 **and** JSON `$.status == healthy`, and times out at 10 seconds; this catches the endpoint's HTTP-200 `degraded` response as well as its HTTP-503 `unhealthy` response. It will not prove business-function health.

```bash
gcloud monitoring policies list --project=earnings-nerd --format=json
gcloud monitoring uptime list-configs --project=earnings-nerd --format=json
gcloud beta monitoring channels describe projects/earnings-nerd/notificationChannels/2698479126467110226 --project=earnings-nerd --format='json(name,displayName,type,enabled)'
```

The local `gcloud` installation used for this preparation lacks the beta channel command group, so the channel's enabled state and owner remain a readback hold. The existing policies prove only the reference. A console read of the channel is an equivalent read-only check; do not create a replacement channel on that basis.

The following is an idempotent apply recipe for an authorized operator. Run from this directory with `jq` and `gcloud`; retain the rendered files and created resource names in the change receipt. It verifies an existing display name and **stops on configuration drift**. Check the listed resource's definition before deciding that a re-run is complete. Do not run until channel ownership, production application and alert-delivery validation are authorized.

```bash
set -euo pipefail
channel='projects/earnings-nerd/notificationChannels/2698479126467110226'
check_name='EarningsNerd: detailed health healthy'
existing_check=$(gcloud monitoring uptime list-configs --project=earnings-nerd --format=json |
  jq -r --arg n "$check_name" '.[] | select(.displayName == $n) | .name')
if [ -z "$existing_check" ]; then
  gcloud monitoring uptime create "$check_name" --project=earnings-nerd \
    --resource-type=uptime-url --resource-labels=host=api.earningsnerd.io,project_id=earnings-nerd \
    --protocol=https --port=443 --validate-ssl=true --path=/health/detailed --request-method=get --status-codes=200 \
    --matcher-type=matches-json-path --json-path='$.status' \
    --json-path-matcher-type=exact-match --matcher-content=healthy --period=1 --timeout=10
  existing_check=$(gcloud monitoring uptime list-configs --project=earnings-nerd --format=json |
    jq -r --arg n "$check_name" '.[] | select(.displayName == $n) | .name')
fi
test "$(printf '%s\n' "$existing_check" | wc -l | tr -d ' ')" = 1
check_id=${existing_check##*/}
gcloud monitoring uptime describe "$existing_check" --project=earnings-nerd --format=json |
  jq -e '.monitoredResource.type == "uptime_url" and
         .monitoredResource.labels.host == "api.earningsnerd.io" and
         .monitoredResource.labels.project_id == "earnings-nerd" and
         .httpCheck.requestMethod == "GET" and .httpCheck.port == 443 and
         .httpCheck.validateSsl == true and
         (.httpCheck.acceptedResponseStatusCodes | length) == 1 and
         .httpCheck.acceptedResponseStatusCodes[0].statusValue == 200 and
         ((.httpCheck.acceptedResponseStatusCodes[0].statusClass // "STATUS_CLASS_UNSPECIFIED") == "STATUS_CLASS_UNSPECIFIED") and
         ((.httpCheck.headers // {}) == {}) and ((.httpCheck.body // "") == "") and
         .httpCheck.authInfo == null and .httpCheck.serviceAgentAuthentication == null and
         ((.httpCheck.contentType // "TYPE_UNSPECIFIED") == "TYPE_UNSPECIFIED") and
         ((.httpCheck.customContentType // "") == "") and
         .httpCheck.path == "/health/detailed" and .httpCheck.useSsl == true and
         .period == "60s" and .timeout == "10s" and
         (.contentMatchers | length) == 1 and
         .contentMatchers[0].matcher == "MATCHES_JSON_PATH" and
         .contentMatchers[0].content == "healthy" and
         .contentMatchers[0].jsonPathMatcher.jsonPath == "$.status" and
         .contentMatchers[0].jsonPathMatcher.jsonMatcher == "EXACT_MATCH"' >/dev/null

for file in alerts/*.json; do
  rendered=$(mktemp)
  if [ "$file" = alerts/uptime-failure.json ]; then
    jq --arg c "$channel" --arg id "$check_id" \
      '.notificationChannels=[$c] | .conditions[0].conditionThreshold.filter |= gsub("__CHECK_ID__"; $id)' \
      "$file" > "$rendered"
  else
    jq --arg c "$channel" '.notificationChannels=[$c]' "$file" > "$rendered"
  fi
  name=$(jq -r '.displayName' "$rendered")
  existing=$(gcloud monitoring policies list --project=earnings-nerd --format=json |
    jq -r --arg n "$name" '.[] | select(.displayName == $n) | .name')
  if [ -z "$existing" ]; then
    gcloud monitoring policies create --project=earnings-nerd --policy-from-file="$rendered"
  else
    test "$(printf '%s\n' "$existing" | wc -l | tr -d ' ')" = 1
    gcloud monitoring policies describe "$existing" --project=earnings-nerd --format=json |
      jq --slurpfile desired "$rendered" -e \
        '$desired[0] as $wanted | . as $actual |
         ($actual.enabled == $wanted.enabled) and
         ($actual.notificationChannels == $wanted.notificationChannels) and
         ($actual.combiner == $wanted.combiner) and
         ($actual.alertStrategy == $wanted.alertStrategy) and
         (($actual.conditions | map(del(.name))) == $wanted.conditions)' >/dev/null
  fi
  rm "$rendered"
done
```

Read back each named policy and the check. Record policy/check resource names, enabled state, full filters and channel reference. Wait up to five minutes for new uptime results, then inspect a natural healthy check result and natural job metric series. A controlled alert delivery test needs a separate authorized test incident; a policy creation response alone is insufficient. The existing channel must not be deleted by this package.

Rollback only resources **created by this application**, using the resource names retained in its receipt. Delete the four created policies first, then the created uptime check. An existing resource reused on re-run is not owned by this receipt. Check for any other policy referencing the check before deleting it.

```bash
gcloud monitoring policies delete 'projects/earnings-nerd/alertPolicies/CREATED_ID' --project=earnings-nerd
gcloud monitoring uptime delete 'projects/earnings-nerd/uptimeCheckConfigs/CREATED_ID' --project=earnings-nerd
```

The alert-policy JSON shape, `conditionMatchedLog` and required `notificationRateLimit` follow [Google's AlertPolicy API](https://docs.cloud.google.com/monitoring/api/ref_v3/rest/v3/projects.alertPolicies); the uptime metric/filter follow [Google's policy example](https://docs.cloud.google.com/monitoring/alerts/policies-in-json), and the content match follows the [uptime config API](https://docs.cloud.google.com/monitoring/api/ref_v3/rest/v3/projects.uptimeCheckConfigs). The Cloud Run [completed execution metric](https://docs.cloud.google.com/monitoring/api/metrics_gcp_p_z) is sampled every 60 seconds and may lag by 120 seconds. Core CLI flags were checked against installed `gcloud monitoring` help on 2026-09-21; the beta channel command remains unverified locally. Log filter syntax should be read back and matched against retained natural entries before claiming coverage. GitHub Actions failure notifications for scheduled workflows are a separate account/repository setting and are not applied here.

## Other deliverables

- [Isolated restore rehearsal](restore-rehearsal.md), with read-only [integrity SQL](restore-integrity.sql).
- [SEC outbound-attempt map](sec-outbound-attempts.md), including retries and SDK pagination gaps.
- [Capacity worksheet](capacity-worksheet.md), retaining the E09 evidence and missing inputs.

Held actions: applying production policies, creating or deleting a restore target, changing deletion protection, sending alerts, executing jobs, retrieving secrets, accessing the denied job ledger through the same IAM identity, and implementing either E09 fleet coordinator. Monthly lifecycle-managed export has not been verified or de-scoped; record an explicit decision after inventory rather than assume it exists.

Offline validation on 2026-09-21: all JSON parses and renders with a dry channel/check ID; all local links resolve; the log phrases and table names match source. The integrity SQL ran with `ON_ERROR_STOP=1` against an isolated PostgreSQL 15 database built from the current SQLAlchemy models and one synthetic company/filing/summary. It returned one joined row and zero orphan/missing-identity counts. The synthetic database was dropped. No Cloud Monitoring policy or restore operation was exercised.
