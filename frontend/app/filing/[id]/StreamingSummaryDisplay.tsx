'use client'

/* =============================================================================
   StreamingSummaryDisplay — app/filing/[id]/StreamingSummaryDisplay.tsx
   -----------------------------------------------------------------------------
   The live generation experience for a filing summary: one calm progress Card
   (bar + honest step log + one line of the voice in the header's live-status
   line) and, once text streams in, a second Card carrying the AI summary.
   Composed from the DS primitives (Card, Badge, GuidanceCard, SkeletonText) with
   useCountUp for the percent and motion tokens for its timers — no hand-rolled
   cards, rings, or raw ms.

   The PROGRESS MATH is load-bearing and unchanged from the prior inline version
   (STAGE_ORDER / STAGE_PROGRESS_MAP / the asymptotic optimistic-progress loop);
   only the presentation was rebuilt. Math edits belong with the SSE pipeline
   (backend/app/services/summary_pipeline.py), not here.
============================================================================= */

import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Filing } from '@/features/filings/api/filings-api'
import AiDisclaimer from '@/components/AiDisclaimer'
import { Badge, Card, GuidanceCard, SkeletonText, buttonVariants } from '@/components/ui'
import { CheckIcon } from '@/lib/icons'
import { isNonRetryableStreamError, isPaywallStreamError } from '@/features/summaries/api/summaries-api'
import { streamErrorCopy } from '@/features/summaries/lib/streamErrorCopy'
import { ENABLE_PRO_TRIAL } from '@/lib/featureFlags'
import { PRO_FAIR_USE_LINE, TRIAL_DAYS } from '@/lib/planLimits'
import { useCountUp } from '@/hooks/useCountUp'
import { useFocusOnArrival } from '@/hooks/useFocusHandoff'
import { RetryButton } from '@/hooks/useRetainedFailure'
import { MOTION } from '@/lib/motion'
import { pricingHref } from '@/features/subscriptions/lib/pricingRoute'

// --- Constants ---

// The one sanctioned playful surface (docs/voice-and-style.md › the humour floor): dry, true to what
// the pipeline does, never a joke about money. One line per backend stage, chosen per filing, so the
// line changes only when the work does: a run in progress is activity, never a status notice
// (DESIGN_SYSTEM.md §4 › Inline notice, §9). The pools follow the pipeline
// (backend/app/services/summary_stages): fetching downloads, parsing reads the sections, and the
// figure work runs under summarizing (analyzing is two yields between two progress writes,
// enrichment.py:187-195, so it lasts milliseconds), so those two stages share a pool. A line says what the step
// beside it does not: "Checking the figures against the filing's data…" left the summarizing pool once the
// writing step said the same (E230).
const STATUS_LINES = {
  fetching: ['Opening the filing…'],
  parsing: [
    'Reading the size-8 fine print…',
    'Reading the footnotes so you can go straight to the ones that matter…',
    'Reviewing the line called Other…',
  ],
  summarizing: [
    'Finding where the filing says that…',
    'Translating management’s phrasing into plain English…',
  ],
} as const
type StatusPool = keyof typeof STATUS_LINES
const STATUS_POOL: Record<string, StatusPool> = {
  initializing: 'fetching',
  queued: 'fetching',
  fetching: 'fetching',
  parsing: 'parsing',
  analyzing: 'summarizing',
  summarizing: 'summarizing',
}
const STALLED_LINE = 'Taking longer than usual. Still working on it.'

/** The header's live-status line: the stalled sentence, else this filing's line for the stage's pool
    (unknown and terminal stages take the fetching pool). Deterministic per filing and pool, so it never
    flips between two lines of one pool across re-renders, and analyzing and summarizing show the same line. */
const statusLine = (stage: string, filingId: number, isStalled: boolean): string => {
  if (isStalled) return STALLED_LINE
  const pool = STATUS_POOL[stage] ?? 'fetching'
  const lines = STATUS_LINES[pool]
  const offset = Object.keys(STATUS_LINES).indexOf(pool)
  return lines[(Math.abs(Math.trunc(filingId)) + offset) % lines.length] ?? lines[0]
}

// Ordered list of the real pipeline stages the backend streams over SSE
// (see backend/app/services/summary_pipeline.py). Step status is derived from the
// live stage below — not from a timer — so the log reflects what is actually happening.
const STAGE_ORDER = ['initializing', 'queued', 'fetching', 'parsing', 'analyzing', 'summarizing', 'completed'] as const

// Honest progress steps mapped to real backend stages, each step the stages it covers, in order. The filing-type
// label is derived from the actual filing (no more hard-coded "10-Q"), and there is no "vectorizing"/"semantic
// analysis" step because the summary path does no embedding. The figures are checked while the summary is written:
// the backend's `analyzing` stage passes in milliseconds, two yields between two progress writes, and the XBRL
// cross-reference and the grounding check before the summary is stored both run under `summarizing`. So one step
// covers both stages and says both, where a step of its own ticked done before any figure was checked (E196 (6)). The
// check says "figures", never "its figures": the code checks only some, so the label claims no more than the step it
// replaced did (docs/voice-and-style.md › Claims). "Against the filing" is true of both checks: the figure trace reads
// the filing's text, and the projection beside it the filing's own XBRL.
const buildLoadingSteps = (filingType: string) => [
  { stages: ['fetching'], label: `Fetching the ${filingType || 'filing'} from SEC.gov`, code: filingType || undefined },
  { stages: ['parsing'], label: 'Reading the statements, risk factors and MD&A' },
  { stages: ['analyzing', 'summarizing'], label: 'Writing the summary and checking figures against the filing' },
]

// Screen-reader announcement for the live region. Derived from the stage (never the percent), so the
// polite region updates once per stage transition instead of chattering on every optimistic-progress
// tick; the stalled sentence joins it once a run stalls (the region is atomic, so a stage change while
// stalled reads both again).
const stageAnnouncement = (stage: string, filingType: string): string => {
  if (stage === 'completed') return 'Summary ready.'
  const step = buildLoadingSteps(filingType).find((s) => s.stages.includes(stage))
  if (step) return `${step.label}.`
  if (stage === 'initializing' || stage === 'queued') return 'Starting summary generation.'
  return 'Generating the summary.'
}

const STAGE_PROGRESS_MAP: Record<string, number> = {
  'queued': 5,
  'fetching': 10,
  'parsing': 25,
  'analyzing': 45,
  'summarizing': 75,
  'completed': 100,
  'error': 0,
  'initializing': 0
}

// --- Step log ---

type StepStatus = 'complete' | 'active' | 'pending'

/** A step's label with its form code kept whole, one whitespace-nowrap run, as the live-status line keeps it: at 390px
    under 200% text the fetching step broke "10-K" at its hyphen (E230). The live region reads the plain label. */
function StepLabel({ label, code }: { label: string; code?: string }) {
  const at = code ? label.indexOf(code) : -1
  if (!code || at < 0) return <>{label}</>
  return (
    <>
      {label.slice(0, at)}
      <span className="whitespace-nowrap">{code}</span>
      {label.slice(at + code.length)}
    </>
  )
}

/** Quiet, backend-driven step log — brand check (done) / static dot (active) / empty hairline
    circle (pending). Every label stays at full opacity: a pending one is tertiary ink (4.9:1 and up),
    never faded text. No connector line, no ping, no bounce. */
function StepList({ filingType, stage, displayStageIdx }: { filingType: string; stage: string; displayStageIdx: number }) {
  const steps = buildLoadingSteps(filingType)
  return (
    <ul className="space-y-3">
      {steps.map((step) => {
        // A step is active through each stage it covers and done once the run is past its last.
        const firstIdx = STAGE_ORDER.indexOf(step.stages[0] as (typeof STAGE_ORDER)[number])
        const lastIdx = STAGE_ORDER.indexOf(step.stages[step.stages.length - 1] as (typeof STAGE_ORDER)[number])
        const status: StepStatus =
          stage === 'completed' || (displayStageIdx > -1 && displayStageIdx > lastIdx)
            ? 'complete'
            : displayStageIdx >= firstIdx && displayStageIdx <= lastIdx
              ? 'active'
              : 'pending'

        return (
          // The marker aligns to the label's first line: its circle and the label's line are both 1.25rem, so a label
          // that wraps (the writing step's, at phone widths) keeps its dot beside its first line, not between lines.
          <li
            key={step.stages[0]}
            className="flex items-start gap-3"
          >
            <span
              className={`flex h-5 w-5 flex-none items-center justify-center rounded-full border transition-colors duration-base ${
                status === 'complete'
                  ? 'border-brand-strong bg-brand-strong text-white dark:border-brand-dark dark:bg-brand-dark dark:text-background-dark'
                  : status === 'active'
                    ? 'border-brand-border bg-panel-light dark:border-brand-border-dark dark:bg-panel-dark'
                    : 'border-border-light bg-background-light dark:border-border-dark dark:bg-background-dark'
              }`}
            >
              {status === 'complete' ? (
                // Bold: at 12px regular's stroke is 0.75px, under a device pixel (DESIGN.md › Icons).
                <CheckIcon weight="bold" className="h-3 w-3" aria-hidden="true" />
              ) : status === 'active' ? (
                <span className="h-1.5 w-1.5 rounded-full bg-brand-strong dark:bg-brand-strong-dark" />
              ) : null}
            </span>
            <span
              className={`text-sm ${
                status === 'active'
                  ? 'font-medium text-text-primary-light dark:text-text-primary-dark'
                  : status === 'complete'
                    ? 'text-text-secondary-light dark:text-text-secondary-dark'
                    : 'text-text-tertiary-light dark:text-text-tertiary-dark'
              }`}
            >
              <StepLabel label={step.label} code={step.code} />
            </span>
          </li>
        )
      })}
    </ul>
  )
}

// --- Main component ---

export default function StreamingSummaryDisplay({
  streamingText,
  stage,
  message,
  filing,
  error,
  onRetry,
  elapsedSeconds = 0,
  trialEligible = false,
  afterFailure,
}: {
  streamingText: string
  stage: string
  message: string
  filing: Filing
  error?: string | null
  onRetry?: () => void
  elapsedSeconds?: number
  /** Whether THIS user would get the Pro trial at checkout (first-time subscriber, resolved
   * subscription status, not beta). Gates the paywall card's trial promise — a churned ex-Pro
   * user is charged immediately, so promising them "you won't be charged" is a false billing
   * claim (staff review, PR #619). Defaults false: under-promising is the safe direction. */
  trialEligible?: boolean
  /** Shown under the failure surface once the run has ended without a summary (an error, or the
   * monthly limit): the filing page passes its change report, which needs no summary. */
  afterFailure?: ReactNode
}) {
  const [isClient, setIsClient] = useState(false)
  const [optimisticProgress, setOptimisticProgress] = useState(0)
  // Focus targets: the progress card's heading takes focus from a Retry that leaves (RetryButton's
  // hand-off), the failure card's heading takes focus nobody holds when it appears.
  const progressHeadingRef = useRef<HTMLHeadingElement>(null)
  const failureHeadingRef = useRef<HTMLHeadingElement>(null)
  // Where the card's Retry hands focus when it leaves while holding it, resolved after the commit: the progress
  // card's heading when its press starts the run, or this card's own heading when the card stays without its
  // Retry (a signed-out press starts no run, and its sign-in sentence is one no retry can help).
  const retryFocusTarget = useMemo(() => ({
    get current() { return progressHeadingRef.current ?? failureHeadingRef.current },
  }), [])

  const isError = stage === 'error' || !!error
  // Stalled: derived in render, not stored, so the stage and the stall land in one commit and the live region
  // below changes once per transition. Normal generation runs ~30-60s; only flag a genuine stall well past that
  // window, and never while the summary is being written, so we never signal "failure" during a healthy run.
  const isStalled = elapsedSeconds > 45 && stage !== 'completed' && stage !== 'summarizing' && !isError
  // A failed generation (or the monthly limit) ends the run the user is waiting on, often from page load
  // with focus on <body>: its card's heading takes focus then, so the next Tab is the card's action, not
  // the site header. Gated on isClient: the first client render is the skeleton, with no card to focus.
  useFocusOnArrival(failureHeadingRef, isClient && isError)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- mount-time client detection to gate SSR-unsafe rendering (avoids hydration mismatch)
    setIsClient(true)
  }, [])

  // Optimistic progress effect - uses real elapsed time from backend but asymptotic approach
  useEffect(() => {
    if (stage === 'completed') {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- syncs optimistic progress bar to the async streaming generation stage
      setOptimisticProgress(100)
      return
    }
    if (isError) return

    // Get base progress for current stage
    const baseProgress = STAGE_PROGRESS_MAP[stage] || 0

    // Calculate next stage target using map for cleaner code
    const NEXT_TARGET_MAP: Record<string, number> = {
      'initializing': 10,
      'queued': 10,
      'fetching': 25,
      'parsing': 45,
      'analyzing': 75,
      'summarizing': 98, // Allow getting very close to 100%
    }
    const nextTarget = NEXT_TARGET_MAP[stage] || 95

    // Use elapsed time from backend for smoother progress within stage
    const stageRange = nextTarget - baseProgress
    const timeBonus = Math.min(stageRange * 0.6, elapsedSeconds * 1.5) // Faster initial ramp

    // Set target to approach
    const targetProgress = Math.min(nextTarget, baseProgress + timeBonus)

    setOptimisticProgress(prev => Math.max(prev, targetProgress))

    // Fallback: asymptotically approach nextTarget if the backend goes quiet.
    // Tick cadence = MOTION.base (200ms) — the sanctioned motion token, not a raw ms.
    const interval = setInterval(() => {
      setOptimisticProgress(current => {
        const dist = nextTarget - current
        if (dist < 0.1) return current // Stop if very close
        return current + (dist * 0.05)
      })
    }, MOTION.base)

    return () => clearInterval(interval)
  }, [stage, isError, elapsedSeconds])

  // Count-up the percent from the ROUNDED integer (no sub-percent re-tweening) and
  // render it in the data face so its width never jitters. SSR/reduced-motion safe.
  const roundedProgress = Math.round(optimisticProgress)
  const pctLabel = useCountUp(roundedProgress, { format: (v) => `${Math.round(v)}%` })

  if (!isClient) {
    // SSR / pre-hydration: a quiet skeleton card (gates Math.random / Date below).
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        <Card className="p-cap-8">
          {/* SkeletonText carries its own role="status" — the wrapper stays role-less. */}
          <div className="space-y-6">
            <SkeletonText lines={2} />
            <SkeletonText lines={4} mono />
          </div>
        </Card>
      </div>
    )
  }

  const displayText = streamingText || ''
  const isGenerating = !isError && (stage === 'summarizing' || displayText.length > 0 || optimisticProgress < 100)

  // Honest, backend-driven progress log: steps reflect the real streamed stage.
  const currentStageIdx = STAGE_ORDER.indexOf(stage as (typeof STAGE_ORDER)[number])
  // On the error path `stage` becomes 'error' (not in STAGE_ORDER → index -1). Fall back to the
  // furthest stage the persisted progress implies so the step log keeps its completed steps instead
  // of collapsing to all-pending — staying consistent with the progress bar, which also retains its
  // last value on error.
  const displayStageIdx = currentStageIdx > -1
    ? currentStageIdx
    : STAGE_ORDER.reduce((acc, s, i) => ((STAGE_PROGRESS_MAP[s] ?? 0) <= optimisticProgress ? i : acc), -1)

  // The live-status line: the stage's line of the voice while healthy, the stalled sentence when stalled.
  // Only rendered inside the progress card, which is itself hidden on error — so the GuidanceCard is the
  // single failure surface (one error surface, not two).
  const line = statusLine(stage, filing.id, isStalled)
  // The trial sentence is true only while the trial ships (ENABLE_PRO_TRIAL, flipped with the backend's
  // PRO_TRIAL_DAYS) and this user would get it (trialEligible, from the page).
  const showTrial = ENABLE_PRO_TRIAL && trialEligible
  // The reason the run stopped, in the product's words: the raw message still decides the card (the
  // paywall matcher reads it), the reader sees its mapped sentence.
  const failureReason = streamErrorCopy(error || message) || 'It timed out before the summary finished. Try again to pick it up.'

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Progress card — one calm focus. Hidden on error: the GuidanceCard below is the single
          error surface, so the bar/steps/status line never duplicate the failure state. */}
      {!isError && (
        <Card className="p-cap-6 sm:p-cap-8">
          {/* Live region: one polite announcement per stage transition, plus the stalled sentence while
              the run stalls (the progressbar's value changes every tick and is deliberately NOT live). */}
          <p role="status" aria-live="polite" className="sr-only">
            {stageAnnouncement(stage, filing.filing_type)}
            {isStalled ? ` ${STALLED_LINE}` : ''}
          </p>

          {/* Header: title + live status + count-up percent. The row wraps: where the heading and the
              percent do not fit side by side (200% text on a phone) the percent moves beneath, still at
              the right (ml-auto), instead of printing over the heading. */}
          <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
            {/* No glyph beside the heading (DESIGN.md › Icons): the heading says what is running in words. */}
            <div className="min-w-0">
              <h2
                ref={progressHeadingRef}
                tabIndex={-1}
                className="text-lg font-semibold text-text-primary-light outline-none dark:text-text-primary-dark"
              >
                Generating the summary
              </h2>
              {/* The live-status line: the form code (wrapping whole, never at its hyphen), then one line of
                  the voice for the stage the backend is in, or the stalled sentence. Plain secondary ink, no
                  tint, no glyph: a run in progress is activity, never a status notice (DESIGN_SYSTEM.md §4
                  Inline notice, §9). The span is keyed so a stage change crossfades the line in (the
                  self-guarded animate-fadeIn; an inline span takes its opacity leg only). */}
              <p className="mt-0.5 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                <span className="whitespace-nowrap">{filing.filing_type}</span> ·{' '}
                <span key={line} className="animate-fadeIn break-words">{line}</span>
              </p>
            </div>
            <div className="ml-auto flex flex-none flex-col items-end">
              <span className="tnum font-data text-2xl font-semibold leading-none text-text-primary-light dark:text-text-primary-dark">
                {pctLabel}
              </span>
              {isGenerating && (
                <span className="mt-1 text-xs text-text-tertiary-light dark:text-text-tertiary-dark">
                  Usually 30–60s
                </span>
              )}
            </div>
          </div>

          {/* Horizontal progress bar (replaces the ring/orb/glow) */}
          <div
            className="mt-5 h-1.5 w-full overflow-hidden rounded-full bg-border-light dark:bg-white/10"
            role="progressbar"
            aria-valuenow={roundedProgress}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Summary generation progress"
          >
            <div
              className="h-full rounded-full bg-brand-strong dark:bg-brand-dark transition-[width] duration-slow ease-standard motion-reduce:transition-none"
              style={{ width: `${roundedProgress}%` }}
            />
          </div>

          {/* Honest step log */}
          <div className="mt-6">
            <StepList filingType={filing.filing_type} stage={stage} displayStageIdx={displayStageIdx} />
          </div>

          {/* Streaming placeholder — mono rhythm, folded into this card until text arrives */}
          {!displayText && <SkeletonText lines={4} mono className="mt-6" />}
        </Card>
      )}

      {/* Error surface. The monthly-limit paywall is a CONVERSION moment, not a failure — it gets
          the brand-tinted upgrade card (retry can't help; the quota resets monthly). The trial
          pitch renders ONLY for trial-eligible users — a churned ex-Pro hitting this card gets a
          plain upgrade CTA, because checkout would charge them immediately (staff review, #619).
          Everything else keeps the honest error, and a retry where one can help. */}
      {isError && isPaywallStreamError(error || message || '') ? (
        <GuidanceCard
          title="You've hit this month's free limit"
          headingLevel="h2"
          headingRef={failureHeadingRef}
          description={
            <>
              {showTrial
                ? `Your free summaries reset next month. Or go unlimited now with a ${TRIAL_DAYS}-day free trial of Pro: cancel anytime during the trial and you won’t be charged.`
                : 'Your free summaries reset next month. Or go unlimited now with Pro.'}
              {/* What "unlimited" holds, stated once app-wide (lib/planLimits.ts PRO_FAIR_USE_LINE, E58). */}
              <span className="mt-2 block">{PRO_FAIR_USE_LINE}</span>
            </>
          }
          action={
            <Link href={showTrial ? pricingHref('monthly') : '/pricing'} className={buttonVariants()}>
              {showTrial ? `Start ${TRIAL_DAYS}-day free trial` : 'Upgrade to Pro'}
            </Link>
          }
        />
      ) : isError ? (
        <GuidanceCard
          variant="error"
          title="Generation interrupted"
          headingLevel="h2"
          headingRef={failureHeadingRef}
          description={failureReason}
          action={
            // Only for a failure a retry can help. The raw message decides, read by the matcher that also stops
            // the stream's automatic retry: Pro's fair-use pause, a sign-in or a permission error keeps its
            // sentence and offers no Retry, since a press would only repeat the blocked request.
            onRetry && !isNonRetryableStreamError(error || message || '') ? (
              // RetryButton (secondary by default: an error retry is never the page's primary action).
              // It restarts the SSE stream, not a query, so its failure is the stream's own state, not
              // useRetainedFailure's hold: a press clears the error in the render that starts the stream,
              // so this card never shows a run in flight (busy stays false) and leaves with the press when
              // the run starts; focus then goes to the progress card's heading, in the branch that replaced
              // this one. A signed-out press starts no run: the card stays with the sign-in sentence, which
              // no retry can help, so the Retry leaves and focus goes to this card's heading.
              <RetryButton
                failures={[{ failed: true, error: error || message, busy: false, retry: onRetry }]}
                focusTarget={retryFocusTarget}
              />
            ) : undefined
          }
        />
      ) : null}
      {isError && afterFailure}

      {/* Streamed summary — the payoff, canonical .markdown-body render */}
      {displayText && (
        <Card as="section" className="p-cap-6 sm:p-cap-8">
          <div className="mb-6 flex items-center gap-3 border-b border-border-light dark:border-border-dark pb-4">
            <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">AI-generated summary</h2>
            {isGenerating && <Badge variant="brand">Live</Badge>}
          </div>
          <div className="markdown-body text-text-secondary-light dark:text-text-secondary-dark">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayText}</ReactMarkdown>
            {isGenerating && (
              // The one surviving pulse — signals the text is still streaming in.
              <span className="ml-1 inline-block h-5 w-0.5 align-middle bg-brand-strong dark:bg-brand-strong-dark animate-pulse motion-reduce:animate-none" aria-hidden="true" />
            )}
          </div>
          {/* Web/PDF parity (audit): the exported PDF of this summary carries a disclaimer —
              the on-page card previously relied on the global footer alone. Unconditional:
              isGenerating stays true for as long as this card shows streamed text, and the
              line is just as true mid-stream. */}
          <AiDisclaimer className="mt-4">
            May be incomplete or contain errors. The authoritative source is always the
            original SEC filing.
          </AiDisclaimer>
        </Card>
      )}
    </div>
  )
}
