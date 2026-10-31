import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * A failed answer reads one way whoever writes it (E37; ASK-07, D-034): the reader's own sentences in copilot-api.ts
 * are twins of the server's in copilot_service.py, word for word. The page shows the reader's (an uncoded stream
 * error's words are the reader's own, since such an event may carry a draft's text); the server's reach every other
 * reader of the stream. Each pair is read from both sources, so a reword on one side fails until the other follows.
 */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..')
const read = (rel: string) => readFileSync(path.join(ROOT, rel), 'utf8')

/** The literal a module-level constant holds: `NAME = "..."` (Python) or `const NAME = '...'` (TypeScript), one quoted
    literal with no prefix that ends its line (a comment aside), so an f-string, a join or a call fails rather than
    reads as some other text. */
function constantText(source: string, name: string): string {
  const match = new RegExp(`^(?:const )?${name}\\s*=\\s*(["'])((?:\\\\.|(?!\\1).)*)\\1\\s*(?:(?:#|//).*)?$`, 'm').exec(source)
  if (!match) throw new Error(`${name} is no longer a one-literal constant: read it another way`)
  return match[2].replace(/\\(["'\\])/g, '$1')
}

const TWINS: Array<[string, string]> = [
  ['_PUBLICATION_ERROR', 'PUBLICATION_ERROR'],
  ['_STREAM_FAILURE', 'STREAM_ERROR'],
]

describe("Ask this Filing's error bubble twins", () => {
  const server = read('backend/app/services/copilot_service.py')
  const reader = read('frontend/features/filings/api/copilot-api.ts')

  it.each(TWINS)('holds %s and %s to the same words', (serverName, readerName) => {
    expect(constantText(reader, readerName)).toBe(constantText(server, serverName))
  })

  it('reads a constant from either language, and refuses one it cannot read', () => {
    expect(constantText('X = "a b."  # a comment', 'X')).toBe('a b.')
    expect(constantText("const X = 'c d.'", 'X')).toBe('c d.')
    expect(constantText(`const X = "I couldn't."`, 'X')).toBe("I couldn't.")
    expect(constantText(`X = 'I couldn\\'t.'`, 'X')).toBe("I couldn't.")
    expect(constantText('X = "one"\nXY = "two"', 'XY')).toBe('two')
    expect(() => constantText('X = f"a {b}"', 'X')).toThrow(/one-literal/)
    expect(() => constantText('X = " ".join(parts)', 'X')).toThrow(/one-literal/)
    expect(constantText('const X = "e." // its twin', 'X')).toBe('e.')
  })
})
