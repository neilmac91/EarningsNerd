import { ReactNode } from 'react'
import { MinusIcon, TrendDownIcon, TrendUpIcon } from '@/lib/icons'

type Sentiment = 'bullish' | 'bearish' | 'neutral'

interface SummaryBlockProps {
  type?: Sentiment
  title?: string
  children: ReactNode
}

export function SummaryBlock({ type = 'neutral', title, children }: SummaryBlockProps) {
  const styles = {
    bullish: {
      border: 'border-brand-light dark:border-brand-dark',
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
    }
  }

  const style = styles[type]
  const Icon = style.icon

  return (
    <div className={`
      relative overflow-hidden rounded-r-lg border-l-4 shadow-sm transition-all hover:shadow-md
      ${style.border} ${style.bg}
      p-5 mb-4
    `}>
      <div className="flex items-start gap-3">
        {title && (
          <div className="mb-2 flex items-center gap-2">
            <Icon className={`h-5 w-5 ${style.iconColor}`} />
            <h4 className={`font-semibold ${style.titleColor}`}>{title}</h4>
          </div>
        )}
      </div>
      
      <div className="text-text-secondary-light dark:text-text-secondary-dark leading-relaxed text-sm">
        {children}
      </div>
    </div>
  )
}
