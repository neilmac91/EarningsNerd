/**
 * The full-text search query's bound, in code points as the router counts them: `full_text_search`
 * (backend/app/routers/search.py) declares `q: str = Query(..., max_length=400)`, and Python's `len`
 * counts code points, so an emoji is one character on the server. A native `maxLength` counts UTF-16
 * units and would cut an emoji-heavy query at half the bound, refusing input the server accepts, so
 * the field clamps its value by code points instead. `tests/unit/searchQueryLimitParity.spec.tsx`
 * reads the router's number and holds `SEARCH_QUERY_MAX` and the field to it.
 */
export const SEARCH_QUERY_MAX = 400

/** `value` cut to at most `max` code points (an emoji counts once, as on the server). */
export function clampCodePoints(value: string, max: number): string {
  const points = Array.from(value)
  return points.length <= max ? value : points.slice(0, max).join('')
}
