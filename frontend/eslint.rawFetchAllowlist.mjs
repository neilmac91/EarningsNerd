// Single source of truth for the raw-`fetch(` allow-list (CLAUDE.md "Where things live": ALL HTTP
// goes through the shared axios client, lib/api/client.ts — cookies, silent refresh, error
// normalisation, base URL). Two consumers, so the list can drift in neither direction:
//   - eslint.config.mjs: only these files may call `fetch(` / `*.fetch(` (every other file fails lint);
//   - tests/unit/rawFetchAllowlist.spec.ts: each file here must STILL contain exactly `fetchCalls`
//     raw call sites (a new call inside a sanctioned file fails until the pin is updated and
//     justified in the PR; a file that stops using fetch fails until it is removed), and the list
//     itself is shrink-only.
// The two sanctioned reasons, and the only ones: SSE stream readers (axios rides XHR and cannot
// read a response body incrementally) and Next server/ISR fetches (Next extends `fetch` with
// `next: { revalidate }` + per-render dedupe; axios has neither). Anything else is a lint error,
// not a new entry.
export const RAW_FETCH_ALLOWLIST = [
  {
    file: 'app/sitemap.ts',
    fetchCalls: 1,
    reason:
      'Next metadata route: server fetch of the backend sitemap with `next: { revalidate }` (ISR); ' +
      'importing the axios client here would also drag its interceptors into the metadata bundle.',
  },
  {
    file: 'lib/serverApi.ts',
    fetchCalls: 2,
    reason:
      'Server Component / generateMetadata fetches (`fetchJson` + `fetchJsonResult`) that need ' +
      '`next: { revalidate }` and Next\'s per-render request dedupe.',
  },
  {
    file: 'features/summaries/api/summaries-api.ts',
    fetchCalls: 1,
    reason:
      'SSE reader: the summary generation stream is a POST whose body is consumed incrementally; ' +
      'axios (XHR) cannot stream a response body.',
  },
  {
    file: 'features/filings/api/copilot-api.ts',
    fetchCalls: 1,
    reason: 'SSE reader for the "Ask this Filing" Copilot answer stream (same XHR constraint).',
  },
  {
    file: 'features/analysis/api/analysis-api.ts',
    fetchCalls: 1,
    reason: 'SSE reader for the Multi-Period Analysis narrative stream (same XHR constraint).',
  },
]

export const RAW_FETCH_ALLOWLIST_FILES = RAW_FETCH_ALLOWLIST.map((entry) => entry.file)
