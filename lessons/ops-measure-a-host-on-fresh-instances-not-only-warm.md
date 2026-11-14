# Measure a serverless host on a fresh instance and after an idle period, beside the warm median: a site with little traffic lives on the cold path

Date: 2026-11-14   Area: ops, hosting, performance

**Context**: Comparing Cloudflare Workers with Vercel for the frontend, the first three rounds of timing took a
warm-up request and then the median of 10 to 30 samples per page. By that measure staging came within 10 to 30 ms of
production, and the report said the move was close to neutral. The same pages requested once after forty idle
minutes, on the single Worker of #2052 and with the connection counted, took 0.8 to 1.4 s on staging against 0.25
to 0.8 s on production. A Worker's script is loaded whole when an
instance starts, the Next server was 15 MB of it, and the product has almost no traffic yet, so nearly every real
visit would have met a fresh instance. The warm median described a state the site is rarely in. Splitting the
Worker (#2053) was found only after the cold path was measured: the Worker's own report of its time (274 ms) beside
the visitor's (0.85 s after the connection) showed where the rest went. The figures for the two Workers, after 45
idle minutes, are in `docs/DEPLOYMENT.md`.

Two measurements also went wrong in ways worth knowing. A trial that deployed and then timed the next request was
measuring Cloudflare replacing instances, not a cold start. And two requests on separate connections reached
different instances, so a warm-up on one said nothing about the other; reusing one connection (one `curl` with
several URLs and `--rate`) fixed that.

**Rule**:
- For any host that starts instances on demand, report three figures per page type, not one: the warm median; the
  first request on a fresh instance; and the first request after the service has been idle for at least half an hour.
  Take them for a cached page and for a page rendered for the first time.
- Say which of the three the product's traffic makes typical. Below a few requests a minute per location, it is the
  cold one.
- When the visitor's time and the server's own reported time differ, the difference is the platform's (connection,
  instance start, script load): measure it before changing application code.
- Hold the instance constant when comparing: one reused connection, a settling delay after a deploy, and a response
  header that says how old the instance is.

**Evidence**: #2052 (warm medians only) and #2053 (cold and idle figures, the split); `docs/DEPLOYMENT.md`,
"Frontend on Cloudflare Workers (staging)", "What was measured". Not gated: these are measurements made by hand.
