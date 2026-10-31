import { useEffect } from 'react'

/**
 * A checkout-return notice outlives a remount in the same commit, never a later visit (D-033).
 *
 * Each page drops its return flag from the address once read, so the notice lives only in component
 * state. Any parent that swaps its element type (a wrapper rendered only once something loads, say)
 * remounts the page below it in one commit, and the notice would be lost for good. While a page
 * showing the notice unmounts, it leaves a carry under its key; a mount in the same commit (React
 * runs the old subtree's effect cleanups, then the new one's effects, in one pass) takes it once.
 * The carry is gone by the next microtask, so a reload, a history entry or a later visit never sees
 * it. Module state, not sessionStorage: storage would outlive a reload and announce the return again.
 */
const carried = new Set<string>()

/** While `shown`, an unmount leaves the notice for a mount in the same commit. */
export function useCarryReturnNotice(key: string, shown: boolean): void {
  useEffect(() => {
    if (!shown) return
    return () => {
      carried.add(key)
      queueMicrotask(() => carried.delete(key))
    }
  }, [key, shown])
}

/** Whether a page that unmounted in this same commit was showing this notice; takes it once. */
export function takeCarriedReturnNotice(key: string): boolean {
  return carried.delete(key)
}
