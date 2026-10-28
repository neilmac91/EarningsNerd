/* =============================================================================
   GuidanceCard — components/ui/GuidanceCard.tsx
   -----------------------------------------------------------------------------
   The system states a financial app needs, as one guidance surface:
     - empty:  brand-tint icon + a concrete next step (role="status").
     - error:  error-tint icon + honest copy + retry (role="alert").
   For loading, use Skeleton/SkeletonText in place of the content instead —
   a spinner card hides layout; bones preserve it.

   NAMING (v2.1): shipped in v2 as ui/StateCard — renamed because the app
   already owns components/StateCard.tsx (notice card, 10 importers) and both
   sit one letter from StatCard (the KPI tile). The app's StateCard keeps its
   name; this surface is the empty/error guidance card only.
============================================================================= */

import { useId, type HTMLAttributes, type ReactNode, type Ref } from 'react'
import { MagnifyingGlassIcon, WarningCircleIcon } from '@/lib/icons'
import { cx } from './cx'

export type GuidanceCardVariant = 'empty' | 'error'

export interface GuidanceCardProps {
  variant?: GuidanceCardVariant
  /** Defaults: magnifier (empty) / alert circle (error). */
  icon?: ReactNode
  title: string
  /**
   * The title's element, chosen for its place in the page outline (DESIGN_SYSTEM §5): 'h3' (default)
   * for a card inside an h2 section; 'h2' where the card stands in for a page's content directly under
   * the page h1 (the filing page's signup gate and failure cards, an empty watchlist); 'h1' where the
   * card is the whole page (the route error boundaries). Size is unchanged.
   */
  headingLevel?: 'h1' | 'h2' | 'h3'
  /**
   * Makes the title a focus target (tabIndex={-1}, no outline), for a card that takes focus when it appears. The
   * description then describes the title (aria-describedby), so a screen reader that cuts the card's live
   * announcement short for the focus change still reads why, not only the title.
   */
  headingRef?: Ref<HTMLHeadingElement>
  description?: ReactNode
  /** Usually a <Button> — primary for empty, secondary for error retry. */
  action?: ReactNode
  className?: string
}

const ICON_WRAP: Record<GuidanceCardVariant, string> = {
  empty: cx(
    'border-brand-border bg-brand-weak text-brand-strong',
    'dark:border-brand-border-dark dark:bg-brand-weak-dark dark:text-brand-strong-dark',
  ),
  error: cx(
    'border-error-light/25 bg-error-light/10 text-error-light',
    'dark:border-error-dark/25 dark:bg-error-dark/10 dark:text-error-dark',
  ),
}

/** The card's icon well: a round well in its variant's tint (the brand's for guidance, the error's for a failure),
    the glyph in the tint's ink. The card draws it at 44px; the alert bell's blocked panel draws its glyph in it at
    32px, so the well is one recipe wherever it shows (E196 (4)). */
export function GuidanceIconWell({
  variant,
  className,
  ...rest
}: { variant: GuidanceCardVariant } & HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cx('flex flex-none items-center justify-center rounded-full border', ICON_WRAP[variant], className)}
      {...rest}
    />
  )
}

/** The variant's glyph, Phosphor's from lib/icons at regular weight (DESIGN.md › Icons), as Notice's are: the
    magnifier for an empty state, the warning circle for an error, 20px in the tile's ink (ICON_WRAP). */
function DefaultIcon({ variant }: { variant: GuidanceCardVariant }) {
  const Glyph = variant === 'error' ? WarningCircleIcon : MagnifyingGlassIcon
  return <Glyph className="h-5 w-5" aria-hidden="true" />
}

export function GuidanceCard({
  variant = 'empty',
  icon,
  title,
  headingLevel: Heading = 'h3',
  headingRef,
  description,
  action,
  className,
}: GuidanceCardProps) {
  const descriptionId = useId()
  const describes = headingRef && description ? descriptionId : undefined
  return (
    <div
      role={variant === 'error' ? 'alert' : 'status'}
      className={cx(
        'flex flex-col items-center rounded-xl border border-border-light bg-panel-light px-cap-6 py-cap-10 text-center shadow-e2',
        'dark:border-white/10 dark:bg-panel-dark dark:shadow-none',
        className,
      )}
    >
      <GuidanceIconWell variant={variant} className="h-11 w-11">
        {icon ?? <DefaultIcon variant={variant} />}
      </GuidanceIconWell>
      <Heading
        ref={headingRef}
        tabIndex={headingRef ? -1 : undefined}
        aria-describedby={describes}
        className={cx('mt-4 text-base font-semibold', headingRef ? 'outline-none' : undefined)}
      >
        {title}
      </Heading>
      {description ? (
        <p id={describes} className="mt-1.5 max-w-[38ch] break-words text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
          {description}
        </p>
      ) : null}
      {/* Two actions wrap to two centred rows when they do not fit side by side (a Retry keeps the room of
          "Trying again…", wider than its label), so a card never pushes a control past its edge or the screen's
          (tests/e2e/reflow-200.spec.ts holds the dashboard's account card and the error boundaries). */}
      {action ? <div className="mt-5 flex flex-wrap items-center justify-center gap-2">{action}</div> : null}
    </div>
  )
}
