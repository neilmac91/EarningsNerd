import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { flashElement } from '@/lib/citationFlash'
import { MOTION } from '@/lib/motion'

describe('flashElement', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('adds the flash class and removes it after the ambient token duration (never earlier)', () => {
    const el = document.createElement('li')
    flashElement(el)
    expect(el.classList.contains('citation-flash')).toBe(true)

    // Just before the CSS animation (--duration-ambient) finishes, the class must still be on —
    // stripping early truncates the fade (the 1500-vs-1800 bug this helper replaces).
    vi.advanceTimersByTime(MOTION.ambient - 1)
    expect(el.classList.contains('citation-flash')).toBe(true)

    vi.advanceTimersByTime(1)
    expect(el.classList.contains('citation-flash')).toBe(false)
  })

  it('cancels the previous cleanup on a rapid re-flash so the restarted animation runs full length', () => {
    const el = document.createElement('li')
    flashElement(el)
    vi.advanceTimersByTime(MOTION.ambient - 100)
    flashElement(el) // restart 100ms before the first cleanup would fire

    // The first click's stale timer must NOT strip the class from the second click's animation.
    vi.advanceTimersByTime(200)
    expect(el.classList.contains('citation-flash')).toBe(true)

    // The second flash still cleans up after its own full duration.
    vi.advanceTimersByTime(MOTION.ambient)
    expect(el.classList.contains('citation-flash')).toBe(false)
  })

  it('tracks cleanup per element — flashing one row never strips another', () => {
    const a = document.createElement('li')
    const b = document.createElement('li')
    flashElement(a)
    vi.advanceTimersByTime(MOTION.ambient / 2)
    flashElement(b)

    vi.advanceTimersByTime(MOTION.ambient / 2)
    expect(a.classList.contains('citation-flash')).toBe(false)
    expect(b.classList.contains('citation-flash')).toBe(true)
  })
})
