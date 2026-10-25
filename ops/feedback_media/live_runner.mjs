/** Invoked only by founder-approved Ops after build, isolated-service readback and private manifest creation. */
import fs from 'node:fs'
import path from 'node:path'
import http from 'node:http'
import { fileURLToPath } from 'node:url'
import { isDeepStrictEqual } from 'node:util'
import { createHash } from 'node:crypto'
import { execFileSync, spawn } from 'node:child_process'
import { setTimeout as pause } from 'node:timers/promises'
import { readManifest, startProxy, controlRequest, check, VerificationError, FRONTEND_PORT } from './live_proxy.mjs'
import { runBrowser, ASSERTIONS } from './live_browser.mjs'

const ROOT = fileURLToPath(new URL('../../', import.meta.url))
export const SUITE_FILES = ['ops/feedback_media/live_proxy.mjs', 'ops/feedback_media/live_browser.mjs', 'ops/feedback_media/live_runner.mjs']

export function suiteDigest(root = ROOT) {
  const hash = createHash('sha256')
  for (const name of SUITE_FILES) hash.update(name).update('\0').update(fs.readFileSync(path.join(root, name))).update('\0')
  return hash.digest('hex')
}

export function approvedInvocation(config, env = process.env) {
  check(env.GITHUB_ACTIONS === 'true' && env.GITHUB_WORKFLOW === 'Ops'
    && env.GITHUB_EVENT_NAME === 'workflow_dispatch' && env.GITHUB_REF === 'refs/heads/main'
    && env.GITHUB_RUN_ATTEMPT === '1' && config.run_id === `${env.GITHUB_RUN_ID}-1`, 'approved-ops-invocation')
  // This is not an approval substitute: Ops checks the founder's protected-environment approval before producing the manifest.
}

function fields(value, names) {
  check(value && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).sort().join('|') === names.split(' ').sort().join('|'), 'receipt-fields')
}
function count(value) { check(Number.isSafeInteger(value) && value >= 0, 'receipt-count') }

export function receiptEnvelope(value, config) {
  const payload = value?.payload
  fields(payload, 'schema purpose run_id completed_at image_digest runtime_source_sha256 verification_suite_sha256 frontend_tree browser_assertions observed')
  check(value && Object.keys(value).sort().join('|') === 'payload|signature'
    && /^[a-f0-9]{64}$/.test(value.signature), 'receipt-envelope')
  check(payload?.schema === 1 && payload.purpose === 'feedback-media-verification'
    && payload.run_id === config.run_id && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(payload.completed_at), 'receipt-identity')
  for (const key of ['image_digest', 'runtime_source_sha256', 'verification_suite_sha256', 'frontend_tree']) {
    check(payload[key] === config[key], 'receipt-binding')
  }
  check(payload.browser_assertions && Object.keys(payload.browser_assertions).sort().join('|') === [...ASSERTIONS].sort().join('|')
    && ASSERTIONS.every(key => payload.browser_assertions[key] === true), 'receipt-browser-assertions')
  const observed = payload.observed
  fields(observed, 'database notifications resources cleanup')
  fields(observed.database, 'feedback submitted attachments fixture_users published_attachments confirmed_generation_deletions normalized_metadata_valid available deleted pending')
  for (const [key, value] of Object.entries(observed.database)) if (key !== 'normalized_metadata_valid') count(value)
  fields(observed.notifications, 'accepted rejected attachment_counts admin_link_valid no_image_payload')
  count(observed.notifications.accepted); count(observed.notifications.rejected)
  check(Array.isArray(observed.notifications.attachment_counts) && observed.notifications.attachment_counts.length <= 100, 'receipt-notifications')
  observed.notifications.attachment_counts.forEach(count)
  fields(observed.cleanup, 'dry_run eligible deleted errors overdue pending_verification')
  check(observed.cleanup.dry_run === false, 'receipt-cleanup')
  for (const [key, value] of Object.entries(observed.cleanup)) if (key !== 'dry_run') count(value)
  const memory = observed.resources
  fields(memory, 'sample_count rss_peak_bytes cgroup_sample_peak_bytes cgroup_kernel_peak_bytes cgroup_memory_limit_bytes configured_memory_limit_bytes self_high_water_rss_bytes reaped_child_high_water_rss_bytes worker_limits unexplained_children last_process_count method sample_age_seconds acceptance_passed conservative_process_bound_bytes evidence_basis')
  for (const name of ['sample_count', 'rss_peak_bytes', 'configured_memory_limit_bytes', 'self_high_water_rss_bytes', 'reaped_child_high_water_rss_bytes', 'last_process_count', 'conservative_process_bound_bytes']) count(memory[name])
  for (const name of ['cgroup_sample_peak_bytes', 'cgroup_kernel_peak_bytes', 'cgroup_memory_limit_bytes']) if (memory[name] !== null) count(memory[name])
  fields(memory.worker_limits, 'feedback_image_service feedback_storage_worker_service')
  check(memory.worker_limits.feedback_image_service === 1 && memory.worker_limits.feedback_storage_worker_service === 2
    && memory.unexplained_children === false && memory.last_process_count === 1 && memory.acceptance_passed === true
    && memory.conservative_process_bound_bytes === memory.self_high_water_rss_bytes + 3 * memory.reaped_child_high_water_rss_bytes
    && memory.evidence_basis === (memory.cgroup_kernel_peak_bytes === null
      ? 'kernel peak unavailable; conservative process-bound evidence' : 'kernel cgroup high-water peak')
    && memory.sample_count >= 5 && memory.configured_memory_limit_bytes === 1073741824
    && Number.isFinite(memory.sample_age_seconds) && memory.sample_age_seconds >= 0 && memory.sample_age_seconds <= 1
    && memory.method === 'kernel peak when exposed; otherwise conservative process bound plus sampled cgroup; representative workload only', 'receipt-resources')
  check(observed?.database?.feedback >= 1 && observed.database.submitted === observed.database.feedback
    && observed.database.attachments >= 3 && observed.database.pending === 0 && observed.database.fixture_users === 0
    && observed.database.deleted === observed.database.attachments
    && observed.database.confirmed_generation_deletions === observed.database.attachments
    && observed.database.normalized_metadata_valid === true
    && observed.notifications?.accepted === observed.database.feedback && observed.notifications.rejected === 0
    && observed.notifications.admin_link_valid === true && observed.notifications.no_image_payload === true
    && observed.notifications.attachment_counts.reduce((sum, value) => sum + value, 0) === observed.database.published_attachments
    && observed.cleanup?.errors === 0 && observed.cleanup.pending_verification === 0, 'receipt-observations')
  // The secret remains in Ops/runtime. This process validates bindings, never claims to verify the HMAC signature.
  return value
}

export function safeFailure(stage, error) {
  return { status: 'failed', stage, reason: error instanceof VerificationError ? error.message : 'verification-unavailable' }
}

async function ready() {
  const until = Date.now() + 30_000
  while (Date.now() < until) {
    const status = await new Promise(resolve => {
      const request = http.get({ hostname: '127.0.0.1', port: FRONTEND_PORT, path: '/terms', timeout: 2000 }, response => {
        response.resume(); resolve(response.statusCode)
      })
      request.on('timeout', () => request.destroy())
      request.on('error', () => resolve(0))
    })
    if (status === 200) return
    await pause(250)
  }
  throw new VerificationError('frontend-startup')
}

async function stopChild(child) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return
  const stopped = new Promise(resolve => child.once('exit', resolve))
  try { process.kill(-child.pid, 'SIGTERM') } catch { return }
  const force = setTimeout(() => { try { process.kill(-child.pid, 'SIGKILL') } catch { /* already gone */ } }, 3000)
  await stopped
  clearTimeout(force)
}

export async function run(manifestPath, requestedFrontend) {
  let stage = 'manifest'
  let config
  let child
  let proxy
  let cleanupDone = false
  let remoteAuthorized = false
  const controller = new AbortController()
  const deadline = setTimeout(() => controller.abort(), 12 * 60_000)
  const interrupt = () => controller.abort()
  process.once('SIGTERM', interrupt)
  process.once('SIGINT', interrupt)
  try {
    config = readManifest(manifestPath)
    approvedInvocation(config)
    check(suiteDigest() === config.verification_suite_sha256, 'suite-binding')
    const frontend = fs.realpathSync(path.join(ROOT, 'frontend'))
    check(!requestedFrontend || fs.realpathSync(requestedFrontend) === frontend, 'frontend-path')
    const tree = execFileSync('git', ['rev-parse', 'HEAD:frontend'], { cwd: ROOT, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim()
    check(tree === config.frontend_tree, 'frontend-tree-binding')
    fs.mkdirSync(config.output_dir, { recursive: true, mode: 0o700 })
    const output = fs.lstatSync(config.output_dir)
    check(output.isDirectory() && !output.isSymbolicLink() && (output.mode & 0o777) === 0o700
      && output.uid === process.getuid(), 'output-directory')
    stage = 'fixtures'
    remoteAuthorized = true
    const fixtures = await controlRequest(config, 'fixtures', {})
    const initial = await controlRequest(config, 'receipt')
    check(initial.run_id === config.run_id && typeof initial.boot_id === 'string', 'runtime-identity')
    stage = 'frontend'
    child = spawn(process.execPath, [path.join(frontend, 'node_modules/next/dist/bin/next'), 'start', '--hostname', '127.0.0.1', '--port', String(FRONTEND_PORT)], {
      cwd: frontend, detached: true, stdio: 'ignore', env: {
        PATH: process.env.PATH || '', HOME: process.env.HOME || '', TMPDIR: process.env.TMPDIR || '/tmp',
        NODE_ENV: 'production', WAITLIST_MODE: 'false', NEXT_PUBLIC_API_BASE_URL: 'https://localhost:8443',
      },
    })
    child.once('error', () => controller.abort())
    await ready()
    proxy = await startProxy(config)
    stage = 'browser'
    const { assertions } = await runBrowser(config, fixtures, proxy, frontend, controller.signal)
    check(!controller.signal.aborted, 'verification-deadline')
    stage = 'cleanup'
    const cleaned = await controlRequest(config, 'cleanup', {})
    check(cleaned.run_id === config.run_id && cleaned.boot_id === initial.boot_id
      && cleaned.database.pending === 0 && cleaned.database.fixture_users === 0
      && cleaned.database.deleted === cleaned.database.attachments && cleaned.cleanup.errors === 0, 'live-cleanup')
    cleanupDone = true
    assertions.cleanup = true
    stage = 'measurement'
    let receipt
    for (let attempt = 0; attempt < 20; attempt++) {
      receipt = await controlRequest(config, 'receipt')
      check(receipt.run_id === config.run_id && receipt.boot_id === initial.boot_id, 'runtime-restarted')
      if (receipt.resources?.acceptance_passed === true) break
      await pause(250)
    }
    check(receipt.resources?.acceptance_passed === true && receipt.resources.sample_count >= 5
      && receipt.resources.configured_memory_limit_bytes === 1073741824, 'resource-acceptance')
    assertions.memory_boundary = true
    stage = 'completion'
    const signed = receiptEnvelope(await controlRequest(config, 'complete', { assertions }), config)
    const reread = await controlRequest(config, 'receipt')
    check(isDeepStrictEqual(reread.receipt, signed), 'receipt-persistence')
    fs.writeFileSync(path.join(config.output_dir, 'receipt.json'), JSON.stringify(signed) + '\n', { mode: 0o600, flag: 'wx' })
    return { status: 'passed', checks: ASSERTIONS.length, feedback: signed.payload.observed.database.feedback,
      deleted_attachments: signed.payload.observed.database.deleted }
  } catch (error) {
    return safeFailure(stage, error)
  } finally {
    clearTimeout(deadline)
    process.removeListener('SIGTERM', interrupt)
    process.removeListener('SIGINT', interrupt)
    if (remoteAuthorized && config && !cleanupDone) { try { await controlRequest(config, 'cleanup', {}) } catch { /* Ops also runs its independent cleanup on failure. */ } }
    await proxy?.close()
    await stopChild(child)
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2)
  if (!(args.length === 2 || args.length === 4) || args[0] !== '--manifest' || (args.length === 4 && args[2] !== '--frontend')) {
    process.stderr.write('{"status":"failed","stage":"arguments","reason":"usage"}\n')
    process.exitCode = 1
  } else {
    const result = await run(args[1], args[3]).catch(error => safeFailure('shutdown', error))
    process.stdout.write(JSON.stringify(result) + '\n')
    process.exitCode = result.status === 'passed' ? 0 : 1
  }
}
