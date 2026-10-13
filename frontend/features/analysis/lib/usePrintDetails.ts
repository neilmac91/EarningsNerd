'use client'

import { useEffect, useId } from 'react'

/** Print every evidence disclosure, then restore the reader's open/closed choices. */
export function usePrintDetails() {
  const id = useId()
  useEffect(() => {
    let previous: Array<{ details: HTMLDetailsElement; open: boolean }> | null = null
    const beforePrint = () => {
      if (previous) return
      const root = document.querySelector(`[data-analysis-print-scope="${id}"]`)
      previous = [...(root?.querySelectorAll('details') ?? [])].map((details) => ({ details, open: details.open }))
      previous.forEach(({ details }) => { details.open = true })
    }
    const afterPrint = () => {
      previous?.forEach(({ details, open }) => { details.open = open })
      previous = null
    }
    window.addEventListener('beforeprint', beforePrint)
    window.addEventListener('afterprint', afterPrint)
    return () => {
      window.removeEventListener('beforeprint', beforePrint)
      window.removeEventListener('afterprint', afterPrint)
      afterPrint()
    }
  }, [id])
  return id
}
