'use client'

/* =============================================================================
   StreamingSummaryDisplay — app/filing/[id]/StreamingSummaryDisplay.tsx
   -----------------------------------------------------------------------------
   The live generation experience for a filing summary: one calm progress Card
   (bar + honest step log + polished whimsy) and, once text streams in, a second
   Card carrying the AI summary. Composed from the DS primitives (Card, Badge,
   Notice, GuidanceCard, SkeletonText) with useCountUp for the percent and motion
   tokens for its timers — no hand-rolled cards, rings, or raw ms.

   The PROGRESS MATH is load-bearing and unchanged from the prior inline version
   (STAGE_ORDER / STAGE_PROGRESS_MAP / the asymptotic optimistic-progress loop);
   only the presentation was rebuilt. Math edits belong with the SSE pipeline
   (backend/app/services/summary_pipeline.py), not here.
============================================================================= */

import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Filing } from '@/features/filings/api/filings-api'
import AiDisclaimer from '@/components/AiDisclaimer'
import { Badge, Card, GuidanceCard, Notice, SkeletonText } from '@/components/ui'
import { Button } from '@/components/ui/Button'
import { SparkleIcon } from '@/lib/icons'
import { useCountUp } from '@/hooks/useCountUp'
import { MOTION } from '@/lib/motion'

// --- Constants ---

// Playful but polished: personality without the cringe. Rotates while we work.
const WHIMSY_MESSAGES = [
  'Turning caffeine into investment insights…',
  'Teaching the model to read between the lines…',
  "Scanning 400 pages of footnotes so you don't have to…",
  'Cross-referencing the numbers with the narrative…',
  'Translating corporate-speak into plain English…',
  'Reading the size-8 fine print…',
  "Reviewing the obscure 'Other' section…",
  'Decoding the tone of the outlook…',
  'Looking for hidden gems in the appendix…',
]

// Ordered list of the real pipeline stages the backend streams over SSE
// (see backend/app/services/summary_pipeline.py). Step status is derived from the
// live stage below — not from a timer — so the log reflects what is actually happening.
const STAGE_ORDER = ['initializing', 'queued', 'fetching', 'parsing', 'analyzing', 'summarizing', 'completed'] as const

// Honest progress steps mapped to real backend stages. The filing-type label is
// derived from the actual filing (no more hard-coded "10-Q"), and there is no
// "vectorizing"/"semantic analysis" step because the summary path does no embedding.
const buildLoadingSteps = (filingType: string) => [
  { stage: 'fetching', label: `Retrieving ${filingType || 'SEC'} filing from EDGAR` },
  { stage: 'parsing', label: 'Extracting financial statements, risk factors & MD&A' },
  { stage: 'analyzing', label: 'Cross-referencing standardized XBRL financials' },
  { stage: 'summarizing', label: 'Generating investment analysis' },
]

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

/** Quiet, backend-driven step log — brand check (done) / static dot (active) /
    dimmed (pending). No connector line, no ping, no bounce. */
function StepList({ filingType, stage, displayStageIdx }: { filingType: string; stage: string; displayStageIdx: number }) {
  const steps = buildLoadingSteps(filingType)
  return (
    <ul className="space-y-3">
      {steps.map((step) => {
        const stepIdx = STAGE_ORDER.indexOf(step.stage as (typeof STAGE_ORDER)[number])
        const status: StepStatus =
          stage === 'completed' || (displayStageIdx > -1 && displayStageIdx > stepIdx)
            ? 'complete'
            : displayStageIdx === stepIdx
              ? 'active'
              : 'pending'

        return (
          <li
            key={step.stage}
            className={`flex items-center gap-3 transition-opacity duration-base ${status === 'pending' ? 'opacity-40' : 'opacity-100'}`}
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
                <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              ) : status === 'active' ? (
                <span className="h-1.5 w-1.5 rounded-full bg-brand-strong dark:bg-brand-strong-dark" />
              ) : null}
            </span>
            <span className={`text-sm ${status === 'active' ? 'font-medium text-text-primary-light dark:text-text-primary-dark' : 'text-text-secondary-light dark:text-text-secondary-dark'}`}>
              {step.label}
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
}: {
  streamingText: string
  stage: string
  message: string
  filing: Filing
  error?: string | null
  onRetry?: () => void
  elapsedSeconds?: number
}) {
  const [isClient, setIsClient] = useState(false)
  const [whimsyMessage, setWhimsyMessage] = useState('')
  const [showWhimsy, setShowWhimsy] = useState(false)
  const [optimisticProgress, setOptimisticProgress] = useState(0)
  const [isStalled, setIsStalled] = useState(false)

  const isError = stage === 'error' || !!error

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- mount-time client detection to gate SSR-unsafe rendering (avoids hydration mismatch)
    setIsClient(true)
  }, [])

  // Whimsy rotation effect
  useEffect(() => {
    if (stage === 'completed' || isError) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- syncs whimsy-message visibility to the async streaming generation stage
      setShowWhimsy(false)
      return
    }

    setShowWhimsy(true)
    // Initial random message
    setWhimsyMessage(WHIMSY_MESSAGES[Math.floor(Math.random() * WHIMSY_MESSAGES.length)])

    // Rotation cadence = a motion-token multiple (DS §11: no raw ms). ambient*2 ≈ 3.6s read.
    const intervalId = setInterval(() => {
      setWhimsyMessage(WHIMSY_MESSAGES[Math.floor(Math.random() * WHIMSY_MESSAGES.length)])
    }, MOTION.ambient * 2)

    return () => clearInterval(intervalId)
  }, [stage, isError])

  // Stalled state detection
  useEffect(() => {
    // Normal generation runs ~30-60s; only flag a genuine stall well past that window
    // so we never signal "failure" during a healthy run.
    if (elapsedSeconds > 45 && stage !== 'completed' && stage !== 'summarizing' && !isError) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- derives a stall flag from async streaming elapsed time + generation stage
      setIsStalled(true)
    } else {
      setIsStalled(false)
    }
  }, [elapsedSeconds, stage, isError])

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
        <Card className="p-8">
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

  // Whimsy copy: rotating quip while healthy, a reassuring line when stalled. Only rendered
  // inside the progress card, which is itself hidden on error — so the GuidanceCard is the
  // single failure surface (one error surface, not two).
  const whimsyText = isStalled
    ? "Taking longer than usual — this looks like a complex filing. Still working on it."
    : showWhimsy && whimsyMessage
      ? whimsyMessage
      : 'Warming up the analysis…'
  const whimsyAttribution = isStalled ? 'Complex filing detected' : 'EarningsNerd analyst'

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Progress card — one calm focus. Hidden on error: the GuidanceCard below is the single
          error surface, so the bar/steps/whimsy never duplicate the failure state. */}
      {!isError && (
        <Card className="p-6 sm:p-8">
          {/* Header: title + live status + count-up percent */}
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3 min-w-0">
              <SparkleIcon className="mt-0.5 h-5 w-5 flex-none text-brand-strong dark:text-brand-strong-dark" aria-hidden="true" />
              <div className="min-w-0">
                <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">
                  Generating your analysis
                </h2>
                <p className="mt-0.5 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                  {filing.filing_type} • Processing…
                </p>
              </div>
            </div>
            <div className="flex flex-col items-end flex-none">
              <span className="tnum font-data text-2xl font-semibold leading-none text-text-primary-light dark:text-text-primary-dark">
                {pctLabel}
              </span>
              {isGenerating && (
                <span className="mt-1 text-xs text-text-tertiary-light dark:text-text-secondary-dark">
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

          {/* Polished whimsy — Notice nested in the Card (DS-sanctioned).
              aria-hidden: it's decorative flavor that rotates; the progressbar + step log
              carry the real, accessible status, so we don't spam SR with rotating quips. */}
          <div aria-hidden="true" className="mt-6">
            <Notice
              variant="info"
              icon={<SparkleIcon className="h-[18px] w-[18px]" aria-hidden="true" />}
              title={<span key={whimsyText} className="animate-fadeIn">{whimsyText}</span>}
              description={whimsyAttribution}
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

      {/* Error surface — the single failure message + retry */}
      {isError && (
        <GuidanceCard
          variant="error"
          title="Generation interrupted"
          description={error || message || 'Generation timed out. Please retry to continue.'}
          action={
            onRetry ? (
              // Secondary, per the GuidanceCard convention (error retry is never the page's primary action)
              <Button variant="secondary" onClick={onRetry}>
                Retry generation
              </Button>
            ) : undefined
          }
        />
      )}

      {/* Streamed summary — the payoff, canonical .markdown-body render */}
      {displayText && (
        <Card as="section" className="p-6 sm:p-8">
          <div className="mb-6 flex items-center gap-3 border-b border-border-light dark:border-border-dark pb-4">
            <SparkleIcon className="h-5 w-5 flex-none text-brand-strong dark:text-brand-strong-dark" aria-hidden="true" />
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
            May be incomplete or contain errors — the authoritative source is always the
            original SEC filing.
          </AiDisclaimer>
        </Card>
      )}
    </div>
  )
}
