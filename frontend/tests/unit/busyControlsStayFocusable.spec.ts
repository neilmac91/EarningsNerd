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
 * (`mutation.isPending`), or through the binding visible from the site: a `const` (followed
 * transitively, so `const canSend = … && !sending` counts) or a renamed destructured prop
 * (`{ isPending: waiting }`). Names resolve in their lexical scope, so a parameter shadows an outer
 * const and two components may each declare their own `cannotSubmit`. Any JSX element counts,
 * components included: a `disabled` prop fed by a busy flag is the same bug one component away.
 * Strings and comments never count.
 *
 * What it cannot see, so per-site specs stay the real proof of focus:
 *  - a busy flag under a name outside BUSY;
 *  - a post-success flip (`!dirty` after a save, `saved`, `resent`, a cooldown) that disables the
 *    control the user just activated;
 *  - a value threaded through props under another name, or computed in another file.
 *
 * ALLOW pins every sanctioned site, per file and with a reason, by the exact text of its `disabled`
 * expression (whitespace collapsed). A new site fails, a busy flag added to a pinned expression fails
 * (its text changes), and a converted site fails until its pin is removed. Files and pinned sites are
 * both capped, shrink-only.
 */
const BUSY = /pending|loading|submitting|saving|sending|streaming|running|busy|refetching|fetching|mutating|deleting|removing|inflight/i

const FOLLOW_UP =
  'Pre-existing follow-up (lesson rule (d)): a busy flag natively disables a control that can hold focus. ' +
  'Convert it to `loading` / aria-disabled + an early return, then lower this pin.'

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
  'features/admin/components/RevokeConfirmModal.tsx': {
    sites: ['isPending'],
    reason:
      'Cancel is disabled while Revoke runs. Revoke (`loading`) is the control that holds focus, and Cancel ' +
      'cannot be activated during the request, so it never holds focus when it flips.',
  },
  // Pre-existing follow-ups.
  'app/admin/invites/page.tsx': { sites: ['sending', 'sending', 'sending', 'sending', '!canSend'], reason: FOLLOW_UP },
  'app/check-email/page.tsx': { sites: ['resendLoading || cooldown > 0 || !email'], reason: FOLLOW_UP },
  'app/company/[ticker]/page-client.tsx': { sites: ['watchlistMutation.isPending', 'filingsRefetching'], reason: FOLLOW_UP },
  'app/dashboard/settings/page.tsx': {
    sites: ['deleteMutation.isPending', 'deleteMutation.isPending'],
    reason:
      'The delete-confirm field and Cancel stay disabled while deleting: only Confirm (`loading`) starts the ' +
      'delete, with no form, so focus is on Confirm, never on them, when they flip.',
  },
  'features/admin/components/FeedbackRow.tsx': { sites: ['statusMutation.isPending'], reason: FOLLOW_UP },
  'features/auth/components/VerificationBanner.tsx': { sites: ['loading'], reason: FOLLOW_UP },
  'features/contact/components/ContactForm.tsx': { sites: ['isSubmitting', 'isSubmitting', 'isSubmitting', 'isSubmitting', 'isSubmitting || (TURNSTILE_ENABLED && !turnstileToken)'], reason: FOLLOW_UP },
  'features/dashboard/components/YourCompanies.tsx': { sites: ['removeMutation.isPending'], reason: FOLLOW_UP },
  'features/feedback/components/FeedbackWidget.tsx': { sites: ['submitting || message.trim().length < 5'], reason: FOLLOW_UP },
  'features/filings/components/copilot/AskCopilotRail.tsx': { sites: ['isStreaming || !canAsk'], reason: FOLLOW_UP },
  'features/summaries/components/SummaryActionsBar.tsx': { sites: ['saveMutation.isPending'], reason: FOLLOW_UP },
  'features/watchlist/components/PopularTickerChips.tsx': { sites: ['addMutation.isPending'], reason: FOLLOW_UP },
  'features/watchlist/components/WatchlistAddSearch.tsx': { sites: ['addMutation.isPending'], reason: FOLLOW_UP },
}

/** Frozen ceilings on files and on pinned sites: lower them as sites are converted, never raise them. */
const MAX_ALLOWLIST_SIZE = 16
const MAX_PINNED_SITES = 26

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

/** A name binding: where it is visible, and what it aliases (if anything). */
interface Binding {
  scope: ts.Node
  /** The initializer, or for `{ isPending: x }` the property it renames; none for a plain parameter. */
  alias?: ts.Node
}

/** The node whose extent bounds a binding's visibility: the enclosing block, or a parameter's function. */
function scopeOf(node: ts.Node): ts.Node {
  if (ts.isParameter(node)) return node.parent
  for (let p = node.parent; ; p = p.parent) {
    if (ts.isParameter(p)) return p.parent
    if (
      ts.isBlock(p) || ts.isSourceFile(p) || ts.isModuleBlock(p) || ts.isCaseClause(p) || ts.isDefaultClause(p) ||
      ts.isCatchClause(p) || ts.isForStatement(p) || ts.isForInStatement(p) || ts.isForOfStatement(p)
    ) {
      return p
    }
  }
}

/** One entry per `disabled={…}` site whose expression reaches a busy flag. */
function busyDisabledSites(source: string, fileName: string): Site[] {
  const sf = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  // Every binding of each name, so a reference resolves to the one visible from it: two components
  // in one file may each declare their own `cannotSubmit`, and a parameter shadows an outer const.
  const bindings = new Map<string, Binding[]>()
  const bind = (name: ts.Identifier, at: ts.Node, alias?: ts.Node): void => {
    bindings.set(name.text, [...(bindings.get(name.text) ?? []), { scope: scopeOf(at), alias }])
  }
  const collect = (node: ts.Node): void => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) bind(node.name, node, node.initializer)
    else if (ts.isParameter(node) && ts.isIdentifier(node.name)) bind(node.name, node)
    else if (ts.isBindingElement(node) && ts.isIdentifier(node.name)) bind(node.name, node, node.propertyName)
    ts.forEachChild(node, collect)
  }
  collect(sf)

  /** The innermost binding of `ref`'s name whose scope contains `ref`. */
  const visible = (ref: ts.Identifier): Binding | undefined => {
    let best: Binding | undefined
    for (const b of bindings.get(ref.text) ?? []) {
      if (b.scope.pos > ref.pos || ref.end > b.scope.end) continue
      if (!best || b.scope.end - b.scope.pos < best.scope.end - best.scope.pos) best = b
    }
    return best
  }

  // Aliases are followed transitively. `path` holds only the bindings on the current chain, so a cycle
  // stops there but an alias already met on another branch is still followed on this one. A binding
  // proven busy stays busy from anywhere, so that result is remembered; "not busy" may be a cycle
  // cut-off and is not.
  const busyBindings = new Set<Binding>()
  const reachesBusy = (expr: ts.Node, path: Set<Binding>): boolean => {
    let hit = false
    const visit = (n: ts.Node): void => {
      if (hit) return
      if (ts.isIdentifier(n)) {
        if (BUSY.test(n.text)) {
          hit = true
          return
        }
        // `form.cannotSubmit` names a property, not a local binding.
        if (ts.isPropertyAccessExpression(n.parent) && n.parent.name === n) return
        const binding = visible(n)
        if (!binding?.alias || path.has(binding)) return
        if (busyBindings.has(binding)) {
          hit = true
          return
        }
        path.add(binding)
        const busy = reachesBusy(binding.alias, path)
        path.delete(binding)
        if (busy) {
          busyBindings.add(binding)
          hit = true
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
      reachesBusy(node.initializer.expression, new Set())
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

  it('resolves each name to the binding visible from the site, not the last one declared in the file', () => {
    const fixture = [
      'const shadowed = isLoading',
      'function A() {',
      '  const cannotSubmit = isPending',
      '  return <button disabled={cannotSubmit} />', // A's own busy alias: counts
      '}',
      'function B() {',
      '  const cannotSubmit = !valid',
      '  return <button disabled={cannotSubmit} />', // B's validation alias: does not count
      '}',
      'function C({ isPending: waiting, ready }: Props) {',
      '  return <><button disabled={waiting} /><button disabled={ready} /></>', // renamed busy prop counts
      '}',
      'function D(shadowed: boolean) {',
      '  return <button disabled={shadowed} />', // the parameter, not the outer busy const
      '}',
      'function E() {',
      '  return <button disabled={shadowed} />', // the outer busy const
      '}',
      'function F() {',
      '  return <button disabled={form.cannotSubmit} />', // a property, not A's binding
      '}',
      // The same pair in the other order: the earlier, non-busy sibling must not count either.
      'function G() {',
      '  const canSend = true',
      '  return <button disabled={!canSend} />', // does not count
      '}',
      'function H() {',
      '  const canSend = !request.isPending',
      '  return <button disabled={!canSend} />', // counts
      '}',
    ].join('\n')
    expect(busyDisabledSites(fixture, 'fixture.tsx').map((site) => `${site.line}: ${site.expr}`)).toEqual([
      '4: cannotSubmit',
      '11: waiting',
      '17: shadowed',
      '28: !canSend',
    ])
  })

  it('follows every path to an alias, however long, and stops only on a cycle', () => {
    const fixture = [
      'function I() {',
      '  const a2 = mutation.isPending',
      '  const a1 = a2',
      '  const fieldBlocked = a1', // three hops to the busy flag
      '  const b1 = fieldBlocked',
      '  const buttonBlocked = b1', // reaches fieldBlocked first, on a longer path
      '  return <button disabled={buttonBlocked || fieldBlocked} />', // counts
      '}',
      'function J() {',
      '  const c5 = isSaving',
      '  const c4 = c5',
      '  const c3 = c4',
      '  const c2 = c3',
      '  const c1 = c2',
      '  return <button disabled={c1} />', // five hops: counts
      '}',
      'function K() {',
      '  let x = y',
      '  let y = x',
      '  return <button disabled={x} />', // a cycle with no busy flag: does not count, and terminates
      '}',
    ].join('\n')
    expect(busyDisabledSites(fixture, 'fixture.tsx').map((site) => `${site.line}: ${site.expr}`)).toEqual([
      '7: buttonBlocked || fieldBlocked',
      '15: c1',
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
    // Files alone are not enough: a new exception appended to a listed file keeps the file count.
    const pinned = Object.values(ALLOW).reduce((sum, { sites }) => sum + sites.length, 0)
    expect(
      pinned,
      `ALLOW pins ${pinned} sites but the ceiling is ${MAX_PINNED_SITES}. Fix the control instead of pinning it.`,
    ).toBeLessThanOrEqual(MAX_PINNED_SITES)
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
