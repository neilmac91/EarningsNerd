'use client'

import { CheckCircle2, ExternalLink } from 'lucide-react'
import type { CopilotCitation } from '@/features/filings/api/copilot-api'
import { isHttpUrl } from './CopilotMessage'

interface CitationChipProps {
  citation: CopilotCitation
}

/**
 * An interactive inline citation marker (`[n]`) injected into a completed Copilot answer.
 *
 * Behaviour ("SEC-jump"): when the citation carries an http(s) `fragment_url` the chip is an
 * anchor that opens the exact passage in the SEC filing in a new tab (the URL embeds a
 * `#:~:text=` text fragment). Without a usable URL it degrades to a non-navigating button so
 * the popover (excerpt + verified/cited status) is still reachable by hover and keyboard focus.
 */
export default function CitationChip({ citation }: CitationChipProps) {
  const { n, excerpt, section_ref, verified, fragment_url } = citation
  const header = section_ref || `Excerpt ${n}`
  const ariaLabel = `Citation ${n}: ${header}`

  // Hover + focus-within both reveal the popover; the chip itself is focusable so keyboard
  // users (Tab) can read the source without a pointer.
  const chipClass =
    'inline-flex min-h-[18px] min-w-[18px] items-center justify-center rounded bg-mint-500/15 px-1 text-[11px] font-semibold leading-none text-mint-300 align-baseline transition-colors hover:bg-mint-500/25 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-mint-400'

  const marker = `[${n}]`

  const popover = (
    <span
      role="tooltip"
      className="pointer-events-none invisible absolute bottom-full left-1/2 z-50 mb-1.5 w-64 -translate-x-1/2 rounded-lg border border-white/10 bg-slate-900 p-3 text-left opacity-0 shadow-xl transition-opacity duration-100 group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100"
    >
      <span className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400 break-words">
        {header}
      </span>
      <span className="mt-1.5 block max-h-40 overflow-y-auto border-l-2 border-mint-500/50 pl-2 text-xs italic text-slate-200 break-words">
        {excerpt}
      </span>
      {verified ? (
        <span className="mt-2 flex items-center gap-1 text-[11px] font-medium text-mint-300">
          <CheckCircle2 className="h-3 w-3 shrink-0" />
          Verified in filing
        </span>
      ) : (
        <span className="mt-2 flex items-center gap-1 text-[11px] font-medium text-slate-400">
          <ExternalLink className="h-3 w-3 shrink-0" />
          Cited
        </span>
      )}
    </span>
  )

  // `group` + `relative` on the wrapper so the absolutely-positioned popover anchors to the chip
  // and reacts to hover/focus anywhere inside the group.
  const wrapperClass = 'group relative inline-block align-baseline'

  if (isHttpUrl(fragment_url)) {
    return (
      <span className={wrapperClass}>
        <a
          href={fragment_url}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={ariaLabel}
          className={chipClass}
        >
          {marker}
        </a>
        {popover}
      </span>
    )
  }

  return (
    <span className={wrapperClass}>
      <button type="button" aria-label={ariaLabel} className={chipClass}>
        {marker}
      </button>
      {popover}
    </span>
  )
}
