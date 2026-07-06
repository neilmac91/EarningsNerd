import React from 'react'
import clsx from 'clsx'

export interface PulseComponent {
  key: string
  label: string
  description: string
  source: string
  value: number
  share: number
}

export interface Pulse {
  score: number
  tier: string
  has_signal: boolean
  components: PulseComponent[]
}

// Muted, dark-first palette — deliberately NOT red/green "casino" coloring. Higher attention reads
// as a calmer, fuller mint; quiet reads as neutral slate.
const TIER_STYLE: Record<string, { fill: string; text: string }> = {
  Elevated: { fill: 'bg-brand-strong dark:bg-brand-dark', text: 'text-brand-strong dark:text-brand-strong-dark' },
  Active: { fill: 'bg-brand-strong/70 dark:bg-brand-dark/70', text: 'text-brand-strong dark:text-brand-strong-dark' },
  'On the radar': { fill: 'bg-text-secondary-light dark:bg-text-secondary-dark', text: 'text-text-secondary-light dark:text-text-secondary-dark' },
  Quiet: { fill: 'bg-text-secondary-light dark:bg-text-secondary-dark', text: 'text-text-secondary-light dark:text-text-secondary-dark' },
}

// The pulse is a relative attention gauge, not a precise score — fill it against a soft ceiling.
const SOFT_MAX = 15

export function FilingPulse({ pulse, score }: { pulse?: Pulse | null; score?: number }) {
  const tier = pulse?.tier ?? 'Quiet'
  const value = pulse?.score ?? score ?? 0
  const style = TIER_STYLE[tier] ?? TIER_STYLE.Quiet
  const width = Math.max(4, Math.min(100, Math.round((value / SOFT_MAX) * 100)))
  const top = (pulse?.components ?? []).slice(0, 3)

  return (
    <div className="flex w-40 flex-col items-end">
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-text-secondary-light dark:text-text-secondary-dark">
          Pulse
        </span>
        <span className={clsx('text-xs font-semibold', style.text)}>{tier}</span>
      </div>
      <div
        className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-border-light dark:bg-white/10"
        role="img"
        aria-label={`Filing pulse: ${tier}`}
      >
        <div
          className={clsx('h-1.5 rounded-full transition-[width] duration-slow', style.fill)}
          style={{ width: `${width}%` }}
        />
      </div>
      {top.length > 0 && (
        <ul className="mt-2 w-full space-y-0.5 text-xs text-text-secondary-light dark:text-text-secondary-dark">
          {top.map((c) => (
            <li
              key={c.key}
              className="flex items-center justify-between gap-3"
              title={`${c.description} · source: ${c.source}`}
            >
              <span className="truncate">{c.label}</span>
              <span className="font-medium tabular-nums text-text-secondary-light dark:text-text-secondary-dark">{c.share}%</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
