'use client'

import { Fragment, useEffect, useRef, useState, type KeyboardEvent } from 'react'
import Link from 'next/link'
import { Button, Notice, cx } from '@/components/ui'
import { RetryButton } from '@/hooks/useRetainedFailure'
import type {
  SectionChange,
  SectionChangesOk,
  WordOp,
  WordingLabel,
  WordingReviewState,
} from '@/features/summaries/api/summaries-api'
import { useWordingReview } from '@/features/summaries/hooks/useWordingReview'
import { periodKind } from '@/features/filings/lib/filingPeriod'
import { changesPhrase, plural } from '@/features/filings/lib/sectionChanges'
import UpgradeModal from '@/features/subscriptions/components/UpgradeModal'
import { analytics } from '@/lib/analytics'
import { formatLocalDate } from '@/lib/format'

/**
 * The Item 1A wording block of the change report (E27, PR B): the risk factors' text of this filing
 * against the prior same-form original, as the backend's paragraph-paired diff serves it. Inside the
 * "What changed" section, under its own subheading: a sentence of counts in the data face, then the
 * changes as one hairline list in reading order, each row a label word (Modified, Added, Removed,
 * Moved) over the paragraph. A modified paragraph is a redline: inserted words underlined in
 * primary ink, removed words struck through in muted ink, with the words "added" and "removed" for
 * assistive tech, because neither the brand tint (the mark means "located in the filing") nor a
 * financial tone (money direction) may say "edited". Whole added and removed paragraphs carry their
 * label instead, in primary and muted ink. A 10-Q that only refers back to the annual report's risk
 * factors is not compared (wordingHasContent, in lib/sectionChanges), and a prior that only referred
 * back is said so.
 *
 * Anonymous and Free readers get the counts and the first items the server sent, then one line
 * naming how many more there are and the upgrade prompt (UpgradeModal); while the anonymous seed
 * stands in for a signed-in reader's own read, that prompt is withheld (the reader may be Pro). Pro
 * readers get every item and, signed in, the review: each row carries two pressed-state toggles
 * (Reviewed, Follow up), the list takes j/k to move between changes and 1/2 to mark the focused one,
 * a line above counts the progress, and reaching the end of the queue freezes a receipt (the two
 * texts' fingerprints, the engine and extractor versions, the counts and the follow-ups) that can be
 * copied as text. A review read that failed shows a Notice with a Retry over the plain list; one the
 * server has nothing for says so over the plain list; one whose receipt the filing's re-read text no
 * longer describes says so and offers a new receipt. Events: `wording_changes_viewed` once the
 * viewer's own read settled (not while the anonymous seed stands in for a signed-in reader), the
 * paywall pair with entry_point "wording_changes", and for the review `wording_change_labeled`,
 * `wording_review_completed` (on the server's transition, once) and `wording_receipt_copied`.
 */

/** Who is reading, for the events and the teaser's sign-in link; absent on the landing page's sample. */
export interface WordingContext {
  filingId: number
  ticker: string | null
  filingType: string
  isAuthenticated: boolean
  /** The block on the page is the anonymous seed standing in while the viewer's own read runs. */
  provisional?: boolean
}

/** The paywall surface's name in the events (paywall_prompt_shown, paywall_cta_clicked). */
export const WORDING_ENTRY_POINT = 'wording_changes'
/** The feature as the upgrade prompt names it. */
export const WORDING_FEATURE = 'Risk factor wording review'

const INK = 'text-text-primary-light dark:text-text-primary-dark'
const MUTED = 'text-text-secondary-light dark:text-text-secondary-dark'
const TERTIARY = 'text-text-tertiary-light dark:text-text-secondary-dark'
const HAIRLINE = 'border-border-light dark:border-white/10'
const INS = 'underline decoration-2 underline-offset-2 font-medium text-text-primary-light dark:text-text-primary-dark'
const DEL = 'line-through decoration-1 text-text-tertiary-light dark:text-text-secondary-dark'
const RING = 'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark'

const KIND_LABEL: Record<SectionChange['kind'], string> = { modified: 'Modified', added: 'Added', removed: 'Removed', moved: 'Moved' }
const PERIOD_NOUN = { annual: 'year', quarter: 'quarter', period: 'period', event: 'period' } as const
const LABEL_TEXT: Record<WordingLabel, string> = { reviewed: 'Reviewed', follow_up: 'Follow up' }

/** "the 10-K for the year ended Sep 28, 2024" */
function againstPhrase(block: SectionChangesOk): string {
  const prior = block.prior_filing
  if (!prior) return 'the prior filing'
  const ended = prior.period_end_date ? formatLocalDate(prior.period_end_date, 'MMM d, yyyy') : null
  return ended ? `the ${prior.filing_type} for the ${PERIOD_NOUN[periodKind(prior.filing_type)]} ended ${ended}` : `the prior ${prior.filing_type}`
}

/** A modified paragraph as a redline. Segments carry no edge spaces, so one space joins them, kept
 *  outside the underline and the strike. */
export function Redline({ ops }: { ops: WordOp[] }) {
  return (
    <>
      {ops.map(([kind, text], i) => {
        const space = i < ops.length - 1 ? ' ' : ''
        return (
          <Fragment key={i}>
            {kind === 'equal' ? (
              text
            ) : kind === 'insert' ? (
              <ins className={INS}>
                <span className="sr-only">added: </span>
                {text}
              </ins>
            ) : (
              <del className={DEL}>
                <span className="sr-only">removed: </span>
                {text}
              </del>
            )}
            {space}
          </Fragment>
        )
      })}
    </>
  )
}

/** The review as the rows read it: the labels set so far and how to change one. */
interface RowReview {
  labels: Record<string, WordingLabel>
  /** Set the label, or clear it when it is already set (a pressed toggle). */
  toggle: (itemId: string, label: WordingLabel) => void
  /** The review read has not settled yet: the toggles show, pressed nowhere, and take no press. */
  ready: boolean
}

function LabelToggle({
  pressed,
  disabled,
  onClick,
  children,
  ariaLabel,
}: {
  pressed: boolean
  disabled: boolean
  onClick: () => void
  children: string
  ariaLabel: string
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={onClick}
      className={cx(
        'inline-flex h-8 items-center rounded-lg border px-2.5 text-xs transition-colors duration-fast disabled:cursor-progress disabled:opacity-60',
        RING,
        pressed
          ? 'border-brand-border bg-brand-weak font-semibold text-brand-strong dark:border-brand-border-dark dark:bg-brand-weak-dark dark:text-brand-strong-dark'
          : cx('border-border-light font-medium hover:bg-brand-weak hover:text-brand-strong dark:border-white/15 dark:hover:bg-brand-weak-dark dark:hover:text-brand-strong-dark', MUTED),
      )}
    >
      {children}
    </button>
  )
}

function ChangeRow({ item, position, total, review }: { item: SectionChange; position: number; total: number; review?: RowReview }) {
  const label = item.kind === 'modified' && item.moved ? 'Modified and moved' : KIND_LABEL[item.kind]
  const current = review?.labels[item.id]
  return (
    <li
      className={cx('border-b py-4 [overflow-wrap:anywhere]', HAIRLINE, review && cx('rounded', RING))}
      // The row takes focus from the j/k keys (never from Tab: its toggles are the Tab stops), so the
      // 1 and 2 keys know which change they mark.
      tabIndex={review ? -1 : undefined}
      data-change-id={review ? item.id : undefined}
    >
      {review ? (
        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
          <p className={cx('font-data text-xs', TERTIARY)}>{label}</p>
          {/* eslint-disable-next-line earningsnerd/no-hand-rolled-toggle-group -- a second press clears the label, so "pressed nowhere" is a valid state here, which the SegmentedControl cannot hold (E62). */}
          <div role="group" aria-label={`Mark change ${position} of ${total}`} className="flex items-center gap-1.5">
            {(['reviewed', 'follow_up'] as const).map((value) => (
              <LabelToggle
                key={value}
                pressed={current === value}
                disabled={!review.ready}
                onClick={() => review.toggle(item.id, value)}
                ariaLabel={`${LABEL_TEXT[value]}: change ${position} of ${total}`}
              >
                {LABEL_TEXT[value]}
              </LabelToggle>
            ))}
          </div>
        </div>
      ) : (
        <p className={cx('font-data text-xs', TERTIARY)}>{label}</p>
      )}
      <p className={cx('mt-1.5 text-sm leading-relaxed', item.kind === 'added' ? INK : MUTED)}>
        {item.kind === 'modified' ? (
          <Redline ops={item.ops} />
        ) : item.kind === 'added' ? (
          <ins className="no-underline">{item.after}</ins>
        ) : item.kind === 'removed' ? (
          <del className="no-underline">{item.before}</del>
        ) : (
          item.after
        )}
      </p>
    </li>
  )
}

/** The changes as one hairline list. With a review, the list also takes the keys: j/k (or the
 *  arrows) move between changes, 1 marks the focused change reviewed and 2 flags it for follow-up,
 *  each a toggle like its button. */
function ChangeList({ items, review }: { items: SectionChange[]; review?: RowReview }) {
  const listRef = useRef<HTMLOListElement>(null)
  const onKeyDown = (event: KeyboardEvent<HTMLOListElement>) => {
    if (!review || event.altKey || event.ctrlKey || event.metaKey) return
    const rows = Array.from(listRef.current?.querySelectorAll<HTMLLIElement>('li[data-change-id]') ?? [])
    const current = (event.target as HTMLElement).closest<HTMLLIElement>('li[data-change-id]')
    const index = current ? rows.indexOf(current) : -1
    if (event.key === 'j' || event.key === 'ArrowDown') {
      rows[Math.min(index + 1, rows.length - 1)]?.focus()
    } else if (event.key === 'k' || event.key === 'ArrowUp') {
      rows[Math.max(index - 1, 0)]?.focus()
    } else if ((event.key === '1' || event.key === '2') && current && review.ready) {
      // A held key repeats; one press is one toggle.
      if (!event.repeat) review.toggle(current.dataset.changeId as string, event.key === '1' ? 'reviewed' : 'follow_up')
    } else {
      return
    }
    event.preventDefault()
  }
  return (
    <ol
      ref={listRef}
      role="list"
      className={cx('mt-3 border-t', HAIRLINE)}
      onKeyDown={review ? onKeyDown : undefined}
      aria-keyshortcuts={review ? 'j k 1 2' : undefined}
    >
      {items.map((item, i) => (
        <ChangeRow key={item.id} item={item} position={i + 1} total={items.length} review={review} />
      ))}
    </ol>
  )
}

const short = (sha: string | null) => (sha ? `${sha.slice(0, 12)}…` : 'unavailable')
const describeFiling = (ref: { filing_type: string; accession_number: string; period_end_date: string | null; filing_date: string | null }) =>
  `${ref.filing_type} ${ref.accession_number}` +
  (ref.period_end_date ? ` (period ended ${ref.period_end_date.slice(0, 10)}` : '') +
  (ref.filing_date ? `${ref.period_end_date ? ', ' : ' ('}filed ${ref.filing_date.slice(0, 10)})` : ref.period_end_date ? ')' : '')

/** The receipt as plain text, for the clipboard: every fingerprint in full. */
export function receiptText(state: WordingReviewState): string {
  const receipt = state.receipt
  if (!receipt) return ''
  const marked = `${receipt.labels.reviewed} reviewed, ${receipt.labels.follow_up} to follow up`
  return [
    'EarningsNerd review receipt',
    `Section: ${receipt.section_label}`,
    `Filing: ${describeFiling(receipt.filing)}`,
    `Compared against: ${describeFiling(receipt.prior_filing)}`,
    `Text SHA-256: current ${receipt.texts.current.sha256 ?? 'unavailable'}; prior ${receipt.texts.prior.sha256 ?? 'unavailable'}`,
    `Extractor v${receipt.texts.current.extractor_version ?? '?'} / v${receipt.texts.prior.extractor_version ?? '?'}; diff engine v${receipt.engine_version}; app ${receipt.app_version}`,
    `Paragraphs: ${changesPhrase(receipt.counts)}; ${receipt.counts.unchanged} unchanged`,
    `Marked: ${marked}`,
    `Follow-up change ids: ${receipt.follow_up_ids.length ? receipt.follow_up_ids.join(', ') : 'none'}`,
    `Completed: ${receipt.completed_at}`,
  ].join('\n')
}

function Receipt({ state, context }: { state: WordingReviewState; context: WordingContext }) {
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle')
  const receipt = state.receipt
  if (!receipt) return null
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(receiptText(state))
      setCopyState('copied')
      analytics.wordingReceiptCopied({ filingId: context.filingId, ticker: context.ticker, filingType: context.filingType })
    } catch {
      setCopyState('failed')
    }
  }
  const row = (term: string, detail: string) => (
    <div className="flex flex-wrap gap-x-3">
      <dt className={cx('w-28 shrink-0', TERTIARY)}>{term}</dt>
      <dd className="min-w-0 flex-1">{detail}</dd>
    </div>
  )
  return (
    <div className={cx('mt-4 rounded border bg-panel-light p-4 dark:bg-panel-dark', HAIRLINE)} data-testid="wording-receipt">
      <p className={cx('text-sm font-semibold', INK)}>Review receipt</p>
      <dl className={cx('mt-2 space-y-1 font-data text-xs tnum', MUTED)}>
        {row('Completed', formatLocalDate(receipt.completed_at, 'MMM d, yyyy'))}
        {row('Filing', describeFiling(receipt.filing))}
        {row('Against', describeFiling(receipt.prior_filing))}
        {row('Fingerprints', `${short(receipt.texts.current.sha256)} / ${short(receipt.texts.prior.sha256)}`)}
        {row('Versions', `extractor v${receipt.texts.current.extractor_version ?? '?'} / v${receipt.texts.prior.extractor_version ?? '?'}, engine v${receipt.engine_version}, app ${receipt.app_version}`)}
        {row('Marked', `${receipt.labels.reviewed} reviewed, ${receipt.labels.follow_up} to follow up`)}
      </dl>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Button size="sm" variant="secondary" onClick={copy}>
          Copy receipt
        </Button>
        <p role="status" className={cx('text-xs', MUTED)}>
          {copyState === 'copied' ? 'Receipt copied.' : copyState === 'failed' ? 'Could not copy. Select the lines above instead.' : ''}
        </p>
      </div>
    </div>
  )
}

/** The Pro reader's review of the listed changes: the progress line, the list with its toggles and
 *  keys, and the receipt once the queue is complete. Owns the review read. A read that failed, or
 *  that found nothing to review, leaves the list plain (no toggles) under a line that says so; the
 *  failure also gets a Notice with the Retry, which hands focus to the progress line when it goes. */
function ReviewedChanges({ block, context }: { block: SectionChangesOk; context: WordingContext }) {
  const identity = { filingId: context.filingId, ticker: context.ticker, filingType: context.filingType }
  const kinds = Object.fromEntries(block.items.map((item) => [item.id, item.kind]))
  const progressRef = useRef<HTMLParagraphElement>(null)
  const { state, failure, unavailable, setLabel } = useWordingReview(context.filingId, {
    enabled: true,
    onLabeled: (itemId, label) => analytics.wordingChangeLabeled({ ...identity, label, kind: kinds[itemId] ?? 'unknown' }),
    onCompleted: (completed) =>
      analytics.wordingReviewCompleted({ ...identity, itemsTotal: completed.items_total, followUps: completed.counts.follow_up }),
  })
  const labels = state?.labels ?? {}
  const review: RowReview | undefined =
    failure.failed || unavailable
      ? undefined
      : {
          labels,
          ready: state !== undefined,
          toggle: (itemId, label) => setLabel(itemId, labels[itemId] === label ? null : label),
        }
  const total = block.items.length
  const marked = Object.keys(labels).length
  const followUps = state?.counts.follow_up ?? 0
  const complete = Boolean(state?.completed_at)
  // Every change marked, no receipt: the filing text was re-read since the receipt was frozen (a
  // re-extraction that changed bytes, not wording), so the server reports the review reopened.
  const reread = state !== undefined && marked === total && !complete
  const tail = followUps ? `, ${followUps} to follow up.` : '.'
  const progress = failure.failed
    ? 'Your review didn’t load.'
    : unavailable
      ? 'This review isn’t available for this comparison yet.'
      : state === undefined
        ? 'Loading your review…'
        : complete
          ? `All ${plural(total, 'change')} marked${tail} Receipt below.`
          : reread
            ? `All ${plural(total, 'change')} marked${tail} No current receipt.`
            : `${marked} of ${plural(total, 'change')} marked${tail}`
  // Marking any change again, unchanged, has the server freeze a receipt for the text now in front
  // of the reader.
  const reissue = () => {
    const [first] = Object.keys(labels)
    if (first) setLabel(first, labels[first])
  }
  return (
    <>
      <div className="mt-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p ref={progressRef} tabIndex={-1} className={cx('text-sm tnum outline-none', MUTED)} data-testid="wording-progress">
          {progress}
        </p>
        {review && <p className={cx('text-xs', TERTIARY)}>Keys: j and k move between changes, 1 marks reviewed, 2 flags follow-up.</p>}
      </div>
      {failure.failed && (
        <div className="mt-3">
          <Notice
            variant="error"
            title="Couldn’t load your review"
            description="The changes are listed below; try again to mark them."
            action={
              <RetryButton size="sm" failures={[failure]} focusTarget={progressRef} />
            }
          />
        </div>
      )}
      <ChangeList items={block.items} review={review} />
      {state && complete && <Receipt state={state} context={context} />}
      {reread && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-3" data-testid="wording-reread">
          <p className={cx('text-sm', MUTED)}>
            The filing text was re-read since your receipt, so it no longer describes the text above. Marking any change
            again issues a new one.
          </p>
          <Button size="sm" variant="secondary" onClick={reissue}>
            Issue a new receipt
          </Button>
        </div>
      )}
    </>
  )
}

export function WordingChanges({
  block,
  Heading,
  context,
  className,
}: {
  block: SectionChangesOk
  /** One level below the enclosing "What changed" heading. */
  Heading: 'h3' | 'h4' | 'h5'
  context?: WordingContext
  className?: string
}) {
  const [upgradeOpen, setUpgradeOpen] = useState(false)
  const teaser = block.access === 'teaser' && block.truncated
  const hidden = teaser ? block.items_total - block.items.length : 0
  const priorPointer = block.prior.reference_only
  const showItems = block.has_changes && !priorPointer
  const hasRedline = showItems && block.items.some((item) => item.kind === 'modified')
  const against = againstPhrase(block)
  // The full list in front of a signed-in reader is the review queue; the anonymous seed is never
  // the full list, so this is the reader's own read.
  const reviewable = showItems && block.access === 'full' && context !== undefined && context.isAuthenticated
  // The anonymous seed standing in for a signed-in reader: their own read may be the full list, so the
  // seed's prompt is not shown to them (a Pro reader never sees "Upgrade to Pro" flash).
  const promptWithheld = (context?.provisional ?? false) && (context?.isAuthenticated ?? false)

  // Once per filing and form the viewer is served: the seed may stand in as the teaser for a
  // signed-in reader whose own read is still running, and that moment is not a view of the teaser;
  // the block stays mounted across a client-side navigation to another filing, and that is a view.
  const filingId = context?.filingId
  const ticker = context?.ticker ?? null
  const filingType = context?.filingType
  const provisional = context?.provisional ?? false
  const seen = useRef<string | null>(null)
  useEffect(() => {
    if (filingId === undefined || filingType === undefined || provisional) return
    const served = `${filingId}:${block.access}`
    if (seen.current === served) return
    seen.current = served
    const identity = { filingId, ticker, filingType }
    analytics.wordingChangesViewed({ ...identity, access: block.access, status: block.status, itemsTotal: block.items_total, hasChanges: block.has_changes })
    if (teaser && showItems) analytics.paywallPromptShown({ ...identity, entryPoint: WORDING_ENTRY_POINT })
  }, [filingId, ticker, filingType, provisional, block.access, block.status, block.items_total, block.has_changes, teaser, showItems])

  const onUpgrade = () => {
    if (context) {
      analytics.paywallCtaClicked({ filingId: context.filingId, ticker: context.ticker, filingType: context.filingType, entryPoint: WORDING_ENTRY_POINT })
    }
    setUpgradeOpen(true)
  }

  return (
    <div className={className} data-wording-access={block.access}>
      <Heading className={cx('flex flex-wrap items-baseline gap-x-2 text-sm font-semibold', INK)}>
        Risk factor wording
        <span className={cx('font-data text-xs font-medium', MUTED)}>Item 1A</span>
      </Heading>

      {priorPointer ? (
        <p className={cx('mt-1.5 text-sm tnum', MUTED)}>
          The prior {block.prior_filing?.filing_type ?? 'filing'} only referred back to the annual report’s risk factors, so this
          section has nothing of its own to compare against: {plural(block.paragraphs.later, 'paragraph')} read as new.
        </p>
      ) : block.has_changes ? (
        <p className={cx('mt-1.5 text-sm tnum', MUTED)}>
          Against {against}: {changesPhrase(block.counts)}; {block.counts.unchanged} unchanged. {block.words.inserted} words added,{' '}
          {block.words.deleted} removed.
        </p>
      ) : (
        <p className={cx('mt-1.5 text-sm tnum', MUTED)}>
          No wording changes against {against} ({plural(block.paragraphs.later, 'paragraph')} compared).
        </p>
      )}

      {showItems && (
        <>
          {reviewable && context ? <ReviewedChanges block={block} context={context} /> : <ChangeList items={block.items} />}
          {hasRedline && (
            <p className={cx('mt-2 text-xs', MUTED)}>
              In a modified paragraph, underlined words were added and struck-through words removed since {against}.
            </p>
          )}
        </>
      )}

      {teaser && showItems && !promptWithheld && (
        <div className={cx('mt-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-3')}>
          <p className={cx('text-sm tnum', MUTED)}>
            {plural(hidden, 'more change')} in this section. Pro shows every change.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Button size="sm" onClick={onUpgrade}>
              Upgrade to Pro
            </Button>
            {context && !context.isAuthenticated && (
              <Link
                href="/login"
                className={cx(
                  'text-sm font-semibold text-brand-strong underline-offset-4 hover:underline dark:text-brand-strong-dark',
                  'rounded focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
                )}
              >
                Already Pro? Log in
              </Link>
            )}
          </div>
          <UpgradeModal open={upgradeOpen} onClose={() => setUpgradeOpen(false)} feature={WORDING_FEATURE} />
        </div>
      )}
    </div>
  )
}
