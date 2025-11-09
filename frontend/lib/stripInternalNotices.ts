export const stripInternalNotices = (markdown: string): string => {
  if (!markdown) {
    return ''
  }

  const disclaimerPatterns = [
    /^(\*|_)?auto-generated from structured data/i,
    /^(\*|_)?writer output failed validation/i,
    /^(\*|_)?summary generated from structured data/i,
  ]

  const lines = markdown.split('\n')
  let startIndex = 0

  while (startIndex < lines.length) {
    const trimmed = lines[startIndex].trim()
    if (!trimmed) {
      startIndex += 1
      continue
    }

    const matchesDisclaimer = disclaimerPatterns.some((pattern) => pattern.test(trimmed))
    if (matchesDisclaimer) {
      startIndex += 1
      continue
    }

    break
  }

  return lines.slice(startIndex).join('\n')
}

export default stripInternalNotices
