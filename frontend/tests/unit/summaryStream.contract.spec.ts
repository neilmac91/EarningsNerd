/**
 * T10 — frontend SSE-parser parity with the producer (backend T1).
 *
 * Feeds the SAME recorded frame sequence the backend stream test emits
 * (backend/tests/fixtures/summary_stream_frames.json — ONE shared artifact, so "parity" is a fact,
 * not two opinions) through the real `generateSummaryStream` parser and asserts every producer
 * event type drives the right callback: progress → onProgress, chunk → onChunk, terminal complete →
 * onComplete, and nothing trips onError. If the producer's frame shapes drift, this test breaks
 * (not production).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { generateSummaryStream } from '@/features/summaries/api/summaries-api'

const FIXTURE = resolve(
  dirname(fileURLToPath(import.meta.url)),
  '../../../backend/tests/fixtures/summary_stream_frames.json',
)

describe('generateSummaryStream — parity with the recorded backend frames (T1/T10)', () => {
  const originalFetch = global.fetch

  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.restoreAllMocks()
    global.fetch = originalFetch
  })

  it('drives progress/chunk/complete from the shared fixture with no error', async () => {
    const frames: Array<Record<string, unknown>> = JSON.parse(readFileSync(FIXTURE, 'utf-8'))
    const encoder = new TextEncoder()
    const chunks = frames.map((f) => encoder.encode(`data: ${JSON.stringify(f)}\n\n`))

    let readIndex = 0
    const reader = {
      read: vi.fn(async () =>
        readIndex < chunks.length
          ? { value: chunks[readIndex++], done: false }
          : { value: undefined, done: true },
      ),
    }
    global.fetch = vi.fn(async () => ({
      ok: true,
      body: { getReader: () => reader },
    })) as unknown as typeof fetch

    const progressSpy = vi.fn()
    const chunkSpy = vi.fn()
    const completeSpy = vi.fn()
    const errorSpy = vi.fn()

    await generateSummaryStream(101, chunkSpy, progressSpy, completeSpy, errorSpy)
    vi.runAllTimers()

    const progressFrames = frames.filter((f) => f.type === 'progress')
    const chunkFrame = frames.find((f) => f.type === 'chunk')!
    const completeFrame = frames.find((f) => f.type === 'complete')!

    expect(errorSpy).not.toHaveBeenCalled()
    expect(progressSpy).toHaveBeenCalledTimes(progressFrames.length)
    expect(chunkSpy).toHaveBeenCalledWith(chunkFrame.content)
    expect(completeSpy).toHaveBeenCalledWith(completeFrame.summary_id)
  })
})
