// A deployment whose ROBOTS_NOINDEX variable is "true" marks every response it renders noindex, so a preview or
// staging copy of the site is never indexed beside production. cloudflare-worker.mjs applies it to each response;
// it lives here, apart from the entry point, so tests/unit/cloudflareWorkerConfig.spec.ts can run it without a build.
export function markNoindex(response, env) {
  if (env.ROBOTS_NOINDEX !== 'true') return response
  // A copy, because a response the runtime hands back can carry immutable headers.
  const marked = new Response(response.body, response)
  marked.headers.set('X-Robots-Tag', 'noindex, nofollow')
  return marked
}
