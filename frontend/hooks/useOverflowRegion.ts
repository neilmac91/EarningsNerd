'use client'

import { useLayoutEffect, useState, type RefObject } from 'react'

interface OverflowRegionOptions {
  label?: string
  describedBy?: string
  /** Disable while the scroll box is not rendered, or when region semantics are opt-in. */
  enabled?: boolean
}

/** Own overflow measurement and the extra keyboard stop, not a surface's scrolling behavior.
 *  Observe the box and its content: either can resize without a window resize. */
export function useOverflowRegion<T extends HTMLElement>(
  ref: RefObject<T>,
  { label, describedBy, enabled = true }: OverflowRegionOptions = {},
) {
  const [overflowing, setOverflowing] = useState(false)

  useLayoutEffect(() => {
    const box = ref.current
    if (!box || !enabled) {
      setOverflowing(false)
      return
    }
    // CSSOM widths are integers; a one-pixel rounding edge is not useful scrolling.
    const measure = () => setOverflowing(box.scrollWidth > box.clientWidth + 1)
    const observer = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(measure)
    let content = box.firstElementChild
    observer?.observe(box)
    if (content) observer?.observe(content)
    const children = new MutationObserver(() => {
      const next = box.firstElementChild
      if (next !== content) {
        if (content) observer?.unobserve(content)
        if (next) observer?.observe(next)
        content = next
      }
      measure()
    })
    children.observe(box, { childList: true })
    measure()
    window.addEventListener('resize', measure)
    return () => {
      observer?.disconnect()
      children.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [ref, enabled])

  const active = enabled && overflowing
  return {
    overflowing: active,
    regionProps: {
      role: active ? 'region' as const : undefined,
      tabIndex: active ? 0 : undefined,
      'aria-label': active ? label : undefined,
      'aria-describedby': active ? describedBy : undefined,
    },
  }
}
