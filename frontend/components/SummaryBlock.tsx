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
      border: 'border-emerald-500',
      bg: 'bg-white',
      icon: TrendingUp,
      iconColor: 'text-emerald-500',
      titleColor: 'text-emerald-900'
    },
    bearish: {
      border: 'border-rose-500',
      bg: 'bg-white',
      icon: TrendingDown,
      iconColor: 'text-rose-500',
      titleColor: 'text-rose-900'
    },
    neutral: {
      border: 'border-slate-300',
      bg: 'bg-slate-50',
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
      
      <div className="text-slate-700 leading-relaxed text-sm">
        {children}
      </div>
    </div>
  )
}
