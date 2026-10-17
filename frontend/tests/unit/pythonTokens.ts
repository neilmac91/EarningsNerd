/**
 * Python source as tokens, for the specs that read backend Python: streamErrorCopy.spec.ts reads the error
 * strings the pipeline streams, authPagesCopy.spec.tsx reads where the backend reads an account's
 * email_verified, and wordmarkSingleSource.spec.ts reads the strings that compose the wordmark, so a comment,
 * a docstring or another string never counts as code.
 */
export type Token = { kind: 'str' | 'name' | 'op'; text: string; line: number }

const ESCAPES: Record<string, string> = { n: '\n', t: '\t', r: '\r', '\\': '\\', "'": "'", '"': '"', '\n': '' }
/** The `\N{…}` character names the reader decodes; any other name fails it rather than read it as text. */
const UNICODE_NAMES: Record<string, string> = {
  'EM DASH': '\u2014', 'EN DASH': '\u2013', 'HORIZONTAL ELLIPSIS': '\u2026', 'NO-BREAK SPACE': '\u00a0', 'MIDDLE DOT': '\u00b7',
  BULLET: '\u2022', 'LEFT SINGLE QUOTATION MARK': '\u2018', 'RIGHT SINGLE QUOTATION MARK': '\u2019',
  'LEFT DOUBLE QUOTATION MARK': '\u201c', 'RIGHT DOUBLE QUOTATION MARK': '\u201d', 'HYPHEN-MINUS': '-', 'MINUS SIGN': '\u2212',
  // The characters that render as nothing, by their names and Python's aliases for them.
  'SOFT HYPHEN': '\u00ad', SHY: '\u00ad', 'ZERO WIDTH SPACE': '\u200b', ZWSP: '\u200b', 'ZERO WIDTH NON-JOINER': '\u200c',
  ZWNJ: '\u200c', 'ZERO WIDTH JOINER': '\u200d', ZWJ: '\u200d', 'WORD JOINER': '\u2060', WJ: '\u2060',
  'ZERO WIDTH NO-BREAK SPACE': '\ufeff', 'BYTE ORDER MARK': '\ufeff', BOM: '\ufeff', ZWNBSP: '\ufeff',
}

/** Python source as tokens: string literals (prefix and quotes dropped; escapes decoded as Python decodes
    them, unless the literal is raw; an f-string's `{{` and `}}` read as single braces), names and
    single-character operators. Comments and whitespace are skipped. */
export function pythonTokens(src: string): Token[] {
  const out: Token[] = []
  let i = 0
  let line = 1
  while (i < src.length) {
    const c = src[i]
    if (c === '\n') line++
    if (c === '#') {
      while (i < src.length && src[i] !== '\n') i++
      continue
    }
    if (/\s/.test(c)) {
      i++
      continue
    }
    const prefix = /^[rRbBuUfF]{0,2}(?=["'])/.exec(src.slice(i, i + 3))
    if (prefix && (i === 0 || !/\w/.test(src[i - 1]))) {
      const start = line
      const raw = /r/i.test(prefix[0])
      const fString = /f/i.test(prefix[0])
      i += prefix[0].length
      const quote = src.startsWith('"""', i) ? '"""' : src.startsWith("'''", i) ? "'''" : src[i]
      i += quote.length
      let text = ''
      while (i < src.length && !src.startsWith(quote, i)) {
        if (src[i] === '\n') line++
        if (src[i] === '\\') {
          const next = src[i + 1]
          const hex = /^(?:x([0-9a-fA-F]{2})|u([0-9a-fA-F]{4})|U([0-9a-fA-F]{8}))/.exec(src.slice(i + 1, i + 10))
          if (raw) text += src.slice(i, i + 2)
          else if (next === 'N' && src[i + 2] === '{') {
            const close = src.indexOf('}', i + 3)
            const name = src.slice(i + 3, close).toUpperCase()
            if (close < 0 || !(name in UNICODE_NAMES)) throw new Error(`line ${line}: \\N{${name}} is a character name this reader does not know: add it to UNICODE_NAMES`)
            text += UNICODE_NAMES[name]
            i = close + 1
            continue
          } else if (hex) {
            text += String.fromCodePoint(parseInt(hex[1] ?? hex[2] ?? hex[3], 16))
            i += 1 + hex[0].length
            continue
          } else text += next in ESCAPES ? ESCAPES[next] : src.slice(i, i + 2)
          if (next === '\n') line++
          i += 2
        } else if (fString && (src.startsWith('{{', i) || src.startsWith('}}', i))) {
          text += src[i]
          i += 2
        } else text += src[i++]
      }
      i += quote.length
      out.push({ kind: 'str', text, line: start })
      continue
    }
    if (/[A-Za-z_]/.test(c)) {
      let j = i
      while (j < src.length && /\w/.test(src[j])) j++
      out.push({ kind: 'name', text: src.slice(i, j), line })
      i = j
      continue
    }
    out.push({ kind: 'op', text: c, line })
    i++
  }
  return out
}
