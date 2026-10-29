/** One open viewer admits at most two private image reads, matching the API's bounded I/O lane. */
export function createFeedbackMediaLoader(load: (id: string, signal: AbortSignal) => Promise<Blob>) {
  let active = 0
  const waiting: Array<() => void> = []
  return async (id: string, signal: AbortSignal): Promise<Blob> => {
    signal.throwIfAborted()
    await new Promise<void>((resolve, reject) => {
      const start = () => {
        signal.removeEventListener('abort', abort)
        active += 1
        resolve()
      }
      const abort = () => {
        const index = waiting.indexOf(start)
        if (index >= 0) waiting.splice(index, 1)
        reject(new DOMException('Screenshot read cancelled', 'AbortError'))
      }
      if (active < 2) start()
      else {
        waiting.push(start)
        signal.addEventListener('abort', abort, { once: true })
      }
    })
    try {
      signal.throwIfAborted()
      return await load(id, signal)
    } finally {
      active -= 1
      waiting.shift()?.()
    }
  }
}
