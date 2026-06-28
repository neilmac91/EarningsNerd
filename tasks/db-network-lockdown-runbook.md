# Cloud SQL Network Lockdown Runbook — EarningsNerd

Goal: remove direct internet exposure of the Cloud SQL instances. Staged approach —
**Phase 1** (zero-downtime lockdown) now, **Phase 2** (private-IP migration) later in a
maintenance window.

Project: `earnings-nerd`. Run everything in **Google Cloud Shell**
(https://console.cloud.google.com → `>_`).

## Why Phase 1 is safe (read this first)

Cloud Run reaches the DB through the **Cloud SQL connector** — the `?host=/cloudsql/<conn>`
socket plus the `--add-cloudsql-instances` flag (see `gcp-deploy-runbook.md`). That connector
talks to the Cloud SQL **Admin API**, not to the database's IP. "Authorized networks" only
govern *direct* IP connections. So clearing authorized networks and enforcing TLS blocks the
public internet **without touching the Cloud Run → DB path**. No downtime.

Removing the public IP *entirely* requires a private IP, which requires a VPC with Private
Service Access and Cloud Run wired to that VPC — that's Phase 2.

Instances:
- `earningsnerd-db` (us-west1, PG15, `34.123.146.138`) — **live prod**, used by Cloud Run.
- `earningsnerd` (us-central1, PG18, `34.168.13.63`) — unused/leftover → lock down, back up, delete.

---

## Phase 1 — Lock down both instances now (zero-downtime)

```bash
gcloud config set project earnings-nerd
```

### 1a. Inspect current state (read-only)
```bash
for INST in earningsnerd-db earningsnerd; do
  echo "=== $INST ==="
  gcloud sql instances describe "$INST" --format='yaml(
    settings.ipConfiguration.ipv4Enabled,
    settings.ipConfiguration.sslMode,
    settings.ipConfiguration.authorizedNetworks,
    settings.ipConfiguration.privateNetwork,
    ipAddresses)'
done
```
Note any authorized-network CIDRs you see — that's who can currently reach the DB over the internet.

### 1b. Lock down production (`earningsnerd-db`)
```bash
# Remove ALL authorized networks -> no direct internet connections accepted.
gcloud sql instances patch earningsnerd-db --clear-authorized-networks

# Require TLS. ENCRYPTED_ONLY rejects unencrypted connections but does NOT require a
# client cert -> the Cloud SQL connector (which always uses TLS) keeps working.
gcloud sql instances patch earningsnerd-db --ssl-mode=ENCRYPTED_ONLY
```
✅ Verify:
```bash
gcloud sql instances describe earningsnerd-db --format='value(
  settings.ipConfiguration.authorizedNetworks,
  settings.ipConfiguration.sslMode)'
# Expect: empty authorizedNetworks, sslMode = ENCRYPTED_ONLY
```

### 1c. Confirm the app is unaffected
```bash
curl -s https://api.earningsnerd.io/health/detailed ; echo
# Expect: database healthy:true  (redis degraded is EXPECTED — Redis is off in prod)
```
If `database` is healthy, Phase 1 on prod is done and the public internet can no longer
open a direct connection.

> Need to run psql yourself later? `gcloud sql connect earningsnerd-db --user=appuser`
> temporarily whitelists your Cloud Shell IP for a few minutes — works fine with
> ENCRYPTED_ONLY. You do not need to re-add a permanent authorized network.

### 1d. Lock down the leftover (`earningsnerd`) before deleting it
```bash
gcloud sql instances patch earningsnerd --clear-authorized-networks
gcloud sql instances patch earningsnerd --ssl-mode=ENCRYPTED_ONLY
```

---

## Phase 2 — Decommission the leftover instance (`earningsnerd`)

Back up to a GCS bucket first — on-demand Cloud SQL backups are deleted *with* the instance,
so an exported dump is the durable record.

```bash
# 1. See what's on it (sanity check it's really unused)
gcloud sql databases list --instance=earningsnerd

# 2. Bucket to hold the final dump
gsutil mb -l us-central1 gs://earnings-nerd-sql-archive   # skip if it already exists

# 3. Grant the instance's service account write access to the bucket
SA_LEFTOVER=$(gcloud sql instances describe earningsnerd --format='value(serviceAccountEmailAddress)')
gsutil iam ch "serviceAccount:${SA_LEFTOVER}:roles/storage.objectAdmin" gs://earnings-nerd-sql-archive

# 4. Export each DB (repeat --database per DB name from step 1)
gcloud sql export sql earningsnerd \
  gs://earnings-nerd-sql-archive/earningsnerd-final.sql.gz \
  --database=<DB_NAME>
```
✅ Verify the dump exists: `gsutil ls -l gs://earnings-nerd-sql-archive/`

Then delete (disable deletion protection if it's on):
```bash
gcloud sql instances patch earningsnerd --no-deletion-protection
gcloud sql instances delete earningsnerd
```

---

## Phase 3 — Private-IP migration for prod (`earningsnerd-db`) — scheduled window

Add a private IP, route Cloud Run into the VPC, verify, then remove the public IP last.
Do this in a low-traffic window; keep public IP until private is proven.

```bash
# 0. Pick the VPC + subnet (default shown; substitute yours if different).
#    SUBNET is the subnet NAME in this VPC/region — it equals NETWORK only for the
#    auto-mode "default" VPC. Custom VPCs have distinct subnet names, so set it explicitly.
NETWORK=default
SUBNET=default
gcloud services enable servicenetworking.googleapis.com compute.googleapis.com

# 1. Private Service Access: reserve a range + peer it to Google services (one-time per VPC)
gcloud compute addresses create google-managed-services-${NETWORK} \
  --global --purpose=VPC_PEERING --prefix-length=16 --network=${NETWORK}
gcloud services vpc-peerings connect \
  --service=servicenetworking.googleapis.com \
  --ranges=google-managed-services-${NETWORK} --network=${NETWORK}

# 2. Add a private IP to the instance (KEEP public for now)
gcloud sql instances patch earningsnerd-db \
  --network=projects/earnings-nerd/global/networks/${NETWORK} \
  --enable-google-private-path
#    ^ takes a few min + a brief restart; verify a private 10.x address now appears:
gcloud sql instances describe earningsnerd-db --format='value(ipAddresses)'

# 3. Wire Cloud Run into the VPC (Direct VPC egress)
gcloud run services update earningsnerd-backend --region=us-west1 \
  --network=${NETWORK} --subnet=${SUBNET} --vpc-egress=private-ranges-only
#    Verify the app still healthy via public IP path:
curl -s https://api.earningsnerd.io/health/detailed ; echo

# 4. Remove the public IP LAST — this forces the connector onto the private path
gcloud sql instances patch earningsnerd-db --no-assign-ip

# 5. Force a new Cloud Run revision so serving instances re-resolve the DB IP.
#    The built-in connector caches the instance's IP config at container start, so
#    instances from the step-3 revision would keep dialing the now-removed public IP
#    until they're replaced. A label change triggers a rolling restart with no config drift.
gcloud run services update earningsnerd-backend --region=us-west1 \
  --update-labels=db-ip-transition=private-only
#    Immediately verify; if DB goes unhealthy, see Rollback below.
curl -s https://api.earningsnerd.io/health/detailed ; echo
```
✅ Success: `database healthy:true` with no public IP on the instance
(`ipAddresses` shows only a PRIVATE address).

### Rollback (Phase 3)
```bash
gcloud sql instances patch earningsnerd-db --assign-ip   # re-add public IP
# Restart Cloud Run too, so instances re-resolve and pick the public path back up.
gcloud run services update earningsnerd-backend --region=us-west1 \
  --update-labels=db-ip-transition=rollback-public
```

---

## Troubleshooting
- **`database` unhealthy right after a patch:** Cloud SQL patches can trigger a short restart;
  re-check `/health/detailed` after ~1 min before assuming breakage.
- **Phase 3 step 4 breaks the DB:** roll back with `--assign-ip`, confirm Cloud Run VPC egress
  (step 3) actually applied (`gcloud run services describe earningsnerd-backend
  --region=us-west1 --format='value(spec.template.metadata.annotations)'`), then retry.
- **Export fails with permission denied:** the *instance* service account (not yours) needs
  `roles/storage.objectAdmin` on the bucket — re-run Phase 2 step 3.
