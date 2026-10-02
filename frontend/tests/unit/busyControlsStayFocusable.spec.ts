import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Rule-12 gate for lessons/frontend-busy-controls-stay-focusable.md: a control busy with a request
 * never takes native `disabled`. Chromium blurs a focused control the moment it turns disabled, so
 * keyboard focus falls to <body> and stays there. A busy state uses the DS Button's `loading`, or
 * `aria-disabled` (+ `aria-busy`) and an early return in the handler; a text field uses `readOnly`.
 *
 * The scan reads the TypeScript AST of every .tsx under app/, components/ and features/. It counts
 * each JSX `disabled={…}` whose expression names a busy flag (BUSY below), directly, through a member
 * (`mutation.isPending`) or through a same-file `const` it references (followed up to three levels,
 * so `const canSend = … && !sending` counts). Any JSX element counts, components included: a
 * `disabled` prop fed by a busy flag is the same bug one component away. Strings and comments never
 * count.
 *
 * What it cannot see, so per-site specs stay the real proof of focus:
 *  - a busy flag under a name outside BUSY;
 *  - a post-success flip (`!dirty` after a save, `saved`, `resent`, a cooldown) that disables the
 *    control the user just activated;
 *  - a value threaded through props under another name, or computed in another file.
 *
 * ALLOW pins every sanctioned site by the exact text of its `disabled` expression (whitespace collapsed), per file, with a
 * reason. A new site fails, a busy flag added to a pinned attribute fails (its text changes), and a
 * converted site fails until its pin is removed. The list is shrink-only (MAX_ALLOWLIST_SIZE).
 */
const BUSY = /pending|loading|submitting|saving|sending|streaming|running|busy|refetching|fetching|mutating|deleting|removing|inflight/i

const FOLLOW_UP =
  'Pre-existing follow-up (lesson rule (d)): a busy flag natively disables a control that can hold focus. ' +
  'Convert it to `loading` / aria-disabled + an early return, then lower this pin.'
const DESIGN_V3 =
  'The design-v3 stack (#1042–#1048) converts this to the DS Button `loading`; lower the pin when it lands.'

const ALLOW: Record<string, { sites: string[]; reason: string }> = {
  // Kept by design.
  'features/calendar/components/AlertBell.tsx': {
    sites: ['checking'],
    reason:
      '`checking` (identity not yet resolved) keeps native disabled: it holds only before identity first ' +
      'resolves, when the bell cannot have focus yet. Its own in-flight toggle is aria-disabled.',
  },
  'features/analysis/components/AnalysisPageClient.tsx': {
    sites: ['!range || running'],
    reason:
      "Run's native disabled while running is pinned by analysis-api.spec.ts (the SSE parsing contract). " +
      'Converting it needs a PR-body-documented contract change (CLAUDE.md rule 6).',
  },
  // Converted by the in-flight design-v3 stack.
  'app/forgot-password/page.tsx': { sites: ['loading'], reason: DESIGN_V3 },
  'app/login/page.tsx': { sites: ['loading || (TURNSTILE_ENABLED && !turnstileToken)'], reason: DESIGN_V3 },
  'app/register/page.tsx': { sites: ['loading || (TURNSTILE_ENABLED && !turnstileToken)'], reason: DESIGN_V3 },
  'app/reset-password/page.tsx': { sites: ['loading || !token'], reason: DESIGN_V3 },
  'features/admin/components/RevokeConfirmModal.tsx': {
    sites: ['isPending', 'isPending'],
    reason: `${DESIGN_V3} Cancel keeps its pin: it is disabled while Revoke, the control that holds focus, runs.`,
  },
  'features/auth/components/EmailVerificationModal.tsx': {
    sites: ['loading || resent'],
    reason: `${DESIGN_V3} Its post-success \`disabled={resent}\` still drops focus and is not visible to this scan.`,
  },
  // Pre-existing follow-ups.
  'app/admin/invites/page.tsx': { sites: ['sending', 'sending', 'sending', 'sending', '!canSend'], reason: FOLLOW_UP },
  'app/check-email/page.tsx': { sites: ['resendLoading || cooldown > 0 || !email'], reason: FOLLOW_UP },
  'app/company/[ticker]/page-client.tsx': { sites: ['watchlistMutation.isPending', 'filingsRefetching'], reason: FOLLOW_UP },
  'app/dashboard/settings/page.tsx': { sites: ['deleteMutation.isPending', 'deleteMutation.isPending'], reason: FOLLOW_UP },
  'features/admin/components/FeedbackRow.tsx': { sites: ['statusMutation.isPending'], reason: FOLLOW_UP },
  'features/auth/components/VerificationBanner.tsx': { sites: ['loading'], reason: FOLLOW_UP },
  'features/contact/components/ContactForm.tsx': { sites: ['isSubmitting', 'isSubmitting', 'isSubmitting', 'isSubmitting', 'isSubmitting || (TURNSTILE_ENABLED && !turnstileToken)'], reason: FOLLOW_UP },
  'features/dashboard/components/YourCompanies.tsx': { sites: ['removeMutation.isPending'], reason: FOLLOW_UP },
  'features/feedback/components/FeedbackWidget.tsx': { sites: ['submitting || message.trim().length < 5'], reason: FOLLOW_UP },
  'features/filings/components/copilot/AskCopilotRail.tsx': { sites: ['isStreaming || !canAsk'], reason: FOLLOW_UP },
  'features/settings/components/BillingPanel.tsx': { sites: ['portal.isPending'], reason: FOLLOW_UP },
  'features/settings/components/ChangePasswordForm.tsx': { sites: ['mutation.isPending || !next || !confirm || (hasPassword && !current)'], reason: FOLLOW_UP },
  'features/settings/components/ConnectedAccounts.tsx': { sites: ['isLast || pending', 'logoutAllMutation.isPending'], reason: FOLLOW_UP },
  'features/settings/components/NotificationPreferencesForm.tsx': { sites: ['mutation.isPending'], reason: FOLLOW_UP },
  'features/settings/components/ProfileForm.tsx': { sites: ['!dirty || mutation.isPending'], reason: FOLLOW_UP },
  'features/summaries/components/SummaryActionsBar.tsx': { sites: ['saveMutation.isPending'], reason: FOLLOW_UP },
  'features/watchlist/components/PopularTickerChips.tsx': { sites: ['addMutation.isPending'], reason: FOLLOW_UP },
  'features/watchlist/components/WatchlistAddSearch.tsx': { sites: ['addMutation.isPending'], reason: FOLLOW_UP },
}

/** A frozen ceiling: lower it when an entry is removed, never raise it. */
const MAX_ALLOWLIST_SIZE = 26

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const ROOTS = ['app', 'components', 'features']

function walk(dir: string, out: string[]): string[] {
  for (const name of readdirSync(dir)) {
    const p = path.join(dir, name)
    if (statSync(p).isDirectory()) walk(p, out)
    else if (p.endsWith('.tsx')) out.push(p)
  }
  return out
}

interface Site {
  line: number
  /** The `disabled` expression, whitespace collapsed: what ALLOW pins. */
  expr: string
}

/** One entry per `disabled={…}` site whose expression reaches a busy flag. */
function busyDisabledSites(source: string, fileName: string): Site[] {
  const sf = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const consts = new Map<string, ts.Expression>()
  const collect = (node: ts.Node): void => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
      consts.set(node.name.text, node.initializer)
    }
    ts.forEachChild(node, collect)
  }
  collect(sf)

  const reachesBusy = (expr: ts.Node, depth: number, seen: Set<string>): boolean => {
    let hit = false
    const visit = (n: ts.Node): void => {
      if (hit) return
      if (ts.isIdentifier(n)) {
        if (BUSY.test(n.text)) {
          hit = true
          return
        }
        const init = consts.get(n.text)
        if (init && depth < 3 && !seen.has(n.text)) {
          seen.add(n.text)
          if (reachesBusy(init, depth + 1, seen)) hit = true
        }
        return
      }
      if (ts.isStringLiteralLike(n)) return
      ts.forEachChild(n, visit)
    }
    visit(expr)
    return hit
  }

  const sites: Site[] = []
  const visit = (node: ts.Node): void => {
    if (
      ts.isJsxAttribute(node) &&
      node.name.getText(sf) === 'disabled' &&
      node.initializer &&
      ts.isJsxExpression(node.initializer) &&
      node.initializer.expression &&
      reachesBusy(node.initializer.expression, 0, new Set())
    ) {
      const { line } = sf.getLineAndCharacterOfPosition(node.getStart(sf))
      sites.push({ line: line + 1, expr: node.initializer.expression.getText(sf).replace(/\s+/g, ' ') })
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return sites
}

const found = new Map<string, Site[]>()
for (const abs of ROOTS.flatMap((root) => walk(path.join(frontendRoot, root), []))) {
  const rel = path.relative(frontendRoot, abs).split(path.sep).join('/')
  const sites = busyDisabledSites(readFileSync(abs, 'utf8'), rel)
  if (sites.length) found.set(rel, sites)
}

describe('busy controls stay focusable (rule-12 gate)', () => {
  it('the scanner sees busy flags directly, through members and through same-file consts, and nothing else', () => {
    const fixture = [
      'const refreshDisabled = isRefetching || !ready',
      'const viaTwo = refreshDisabled',
      'export function X() {',
      '  return (<>',
      '    <button disabled={mutation.isPending} />',
      '    <Button disabled={loading || !valid} />',
      '    <button disabled={viaTwo} />',
      '    <Button loading={saving} disabled={!valid} />',
      '    <button aria-disabled={pending} />',
      '    <button disabled={!email} />',
      "    <button disabled={'pending' === mode} />",
      '    {/* <button disabled={isPending} /> */}',
      '    <button disabled />',
      '  </>)',
      '}',
    ].join('\n')
    expect(busyDisabledSites(fixture, 'fixture.tsx').map((site) => site.expr)).toEqual([
      'mutation.isPending',
      'loading || !valid',
      'viaTwo',
    ])
  })

  it('no control takes native disabled from a busy flag outside the allowlist', () => {
    const offenders: string[] = []
    for (const [file, sites] of found) {
      const allowed = [...(ALLOW[file]?.sites ?? [])]
      for (const site of sites) {
        const i = allowed.indexOf(site.expr)
        if (i === -1) offenders.push(`${file}:${site.line}: disabled={${site.expr}}`)
        else allowed.splice(i, 1)
      }
    }
    expect(
      offenders,
      'A control busy with a request must stay focusable: use the DS Button `loading` prop, or aria-disabled ' +
        '(+ aria-busy) and an early return in the handler; readOnly for a text field. ' +
        'See lessons/frontend-busy-controls-stay-focusable.md.',
    ).toEqual([])
  })

  it('is shrink-only, and every entry has a reason', () => {
    expect(
      Object.keys(ALLOW).length,
      `ALLOW has ${Object.keys(ALLOW).length} entries but the ceiling is ${MAX_ALLOWLIST_SIZE}. Fix the control instead of adding an entry.`,
    ).toBeLessThanOrEqual(MAX_ALLOWLIST_SIZE)
    for (const [file, { reason }] of Object.entries(ALLOW)) {
      expect(reason.trim().length, `${file} needs a reason`).toBeGreaterThan(0)
    }
  })

  it.each(Object.keys(ALLOW))('%s still has every pinned site (remove the pins of converted ones)', (file) => {
    const actual = (found.get(file) ?? []).map((site) => site.expr).sort()
    expect(actual, `${file}: a pinned busy-disabled site was converted or edited; update its ALLOW pins.`).toEqual(
      [...ALLOW[file].sites].sort(),
    )
  })
})
