/**
 * Serialize a JSON-LD object for a `<script type="application/ld+json" dangerouslySetInnerHTML>`.
 * `<` is escaped as the JSON-safe `<`, so a `</script>` sequence inside a value (a company
 * name or form type from SEC data) can never terminate the tag.
 */
export function jsonLdHtml(data: unknown): string {
  return JSON.stringify(data).replace(/</g, '\\u003c')
}
