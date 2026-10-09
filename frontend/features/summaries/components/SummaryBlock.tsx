import { ReactNode } from 'react'
import { MinusIcon, QuotesIcon, TrendDownIcon, TrendUpIcon } from '@/lib/icons'

// 'excerpt' is not a sentiment: a verbatim filing passage (the risk cards) states no trend, so it
// takes the neutral quotation glyph instead of the bearish arrow while keeping the card on the
// panel fill (CLAUDE.md rule 11: cards = panel), which 'neutral' would swap for the page ground.
type Variant = 'bullish' | 'bearish' | 'neutral' | 'excerpt'

interface SummaryBlockProps {
  type?: Variant
  title?: string
  children: ReactNode
}

export function SummaryBlock({ type = 'neutral', title, children }: SummaryBlockProps) {
  const styles = {
    bullish: {
      border: 'border-brand-border dark:border-brand-dark',
      bg: 'bg-panel-light dark:bg-panel-dark',
      icon: TrendUpIcon,
      iconColor: 'text-brand-strong dark:text-brand-strong-dark',
      titleColor: 'text-brand-strong dark:text-brand-strong-dark'
    },
    bearish: {
      border: 'border-border-light dark:border-border-dark',
      bg: 'bg-panel-light dark:bg-panel-dark',
      icon: TrendDownIcon,
      iconColor: 'text-text-tertiary-light dark:text-text-secondary-dark',
      titleColor: 'text-text-secondary-light dark:text-text-secondary-dark'
    },
    neutral: {
      border: 'border-border-light dark:border-border-dark',
      bg: 'bg-background-light dark:bg-background-dark',
      icon: MinusIcon,
      iconColor: 'text-text-tertiary-light dark:text-text-secondary-dark',
      titleColor: 'text-text-secondary-light dark:text-text-secondary-dark'
    },
    excerpt: {
      border: 'border-border-light dark:border-border-dark',
      bg: 'bg-panel-light dark:bg-panel-dark',
      icon: QuotesIcon,
      iconColor: 'text-text-tertiary-light dark:text-text-secondary-dark',
      titleColor: 'text-text-secondary-light dark:text-text-secondary-dark'
    }
  }

  const style = styles[type]
  const Icon = style.icon

  return (
    <div data-summary-block={type} className={`
      relative overflow-hidden rounded-r-lg border-l-4 shadow-e1 dark:shadow-none transition hover:shadow-e2
      ${style.border} ${style.bg}
      p-5 mb-4
    `}>
      <div className="flex items-start gap-3">
        {title && (
          // The glyph sits on the title's first line (20px icon, 2px down a 24px line), so a
          // headline that wraps keeps it beside its opening words; shrink-0 keeps it whole. A title
          // quoted from a filing can hold one long token (a URL): it wraps inside the card.
          <div className="mb-2 flex min-w-0 items-start gap-2">
            <Icon aria-hidden="true" className={`mt-0.5 h-5 w-5 shrink-0 ${style.iconColor}`} />
            <h4 className={`min-w-0 font-semibold [overflow-wrap:anywhere] ${style.titleColor}`}>{title}</h4>
          </div>
        )}
      </div>

      <div className="text-text-secondary-light dark:text-text-secondary-dark leading-relaxed text-sm">
        {children}
      </div>
    </div>
  )
}
