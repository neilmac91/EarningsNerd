import { ReactNode } from 'react'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

type Sentiment = 'bullish' | 'bearish' | 'neutral'

interface SummaryBlockProps {
  type?: Sentiment
  title?: string
  children: ReactNode
}

export function SummaryBlock({ type = 'neutral', title, children }: SummaryBlockProps) {
  const styles = {
    bullish: {
      border: 'border-mint-500',
      bg: 'bg-white dark:bg-slate-800',
      icon: TrendingUp,
      iconColor: 'text-mint-500',
      titleColor: 'text-mint-800'
    },
    bearish: {
      border: 'border-slate-400',
      bg: 'bg-white dark:bg-slate-800',
      icon: TrendingDown,
      iconColor: 'text-slate-500',
      titleColor: 'text-slate-700'
    },
    neutral: {
      border: 'border-slate-300',
      bg: 'bg-slate-50 dark:bg-slate-800/50',
      icon: Minus,
      iconColor: 'text-slate-400',
      titleColor: 'text-slate-700'
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
      
      <div className="text-slate-700 dark:text-slate-300 leading-relaxed text-sm">
        {children}
      </div>
    </div>
  )
}
