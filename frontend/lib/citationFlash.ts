/**
 * Re-trigger the `.citation-flash` attention pulse on an element — shared by the copilot
 * filing-viewer highlight (highlightInDom.ts) and the analysis narrative's Sources list
 * (NarrativePane.tsx), so the restart trick and the cleanup timing live in one place.
 *
 * The remove → forced reflow → re-add sequence restarts the CSS animation on repeat clicks;
 * the cleanup timer clears the class after the animation's own duration (`--duration-ambient`,
 * mirrored as MOTION.ambient) so the fade is never truncated. One pending timer per element:
 * a re-flash cancels the previous timer, so an earlier click can't strip the class midway
 * through a later click's animation.
 */
import { MOTION } from '@/lib/motion'

const FLASH_CLASS = 'citation-flash'

const pendingCleanup = new WeakMap<HTMLElement, number>()

export function flashElement(el: HTMLElement): void {
  const prior = pendingCleanup.get(el)
  if (prior !== undefined) window.clearTimeout(prior)
  el.classList.remove(FLASH_CLASS)
  void el.offsetWidth // force reflow so re-adding the class restarts the animation
  el.classList.add(FLASH_CLASS)
  pendingCleanup.set(
    el,
    window.setTimeout(() => {
      el.classList.remove(FLASH_CLASS)
      pendingCleanup.delete(el)
    }, MOTION.ambient)
  )
}
