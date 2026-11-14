# ADR 0009 — Serve insider activity from a stored, budget-aware Form 4 scan, to beta users

- **Status:** Accepted
- **Deciders:** the founder (2026-11-14: "go ahead with the insider activity design and build"), EarningsNerd
  maintainers
- **Supersedes:** the founder's 2026-10-09 answer "A: guard, then pin" for the insider endpoint
  (`tasks/code-red-20261004/runtime/control/DECISIONS-17.md`), which left the endpoint switched off until the
  rework that record called option B. This is that rework. The pin of every process to 1 + 1 SEC requests a
  second stands.

## Context

`GET /api/companies/{ticker}/insiders` shows a company's recent open-market insider trades from SEC Form 4s. It
has been off in production since October (`ENABLE_INSIDER_ACTIVITY=false`, pinned by the deploy), and the founder
wants it working for beta users. As built it cannot be switched on:

- **A cold load does not fit the budget.** `insider_service` asks edgartools for up to 60 Form 4s, and
  edgartools' parse looks up every reporting owner's own submissions, so one load is about 121 SEC requests.
  Each process is pinned to one edgartools request a second: 63 s at the floor, 98 to 127 s measured
  (DECISIONS-17, finding 1), against the service's 60 s fetch timeout (the route's own ceiling is 75 s) and a
  30 s browser timeout.
- **A load that times out is lost.** The result is cached only when the whole loop returns, in process memory.
  The thread keeps running after the timeout, holding the instance's edgartools budget and one of four worker
  threads, and the timeout counts toward the circuit breaker that summary generation shares.
- **Nothing stops on SEC's refusal.** On this path edgartools hides a 403 or 5xx (`filing.xml()` returns None),
  so a blocked scan carries on (DECISIONS-17, finding 2).
- **It is public.** The route has no sign-in, so every visitor and crawler of a company page would start a load,
  and the panel retries a failed one twice.
- **The panel says nothing** while it waits or when it fails.

What was read from the code and from offline probes on 2026-11-14 (no request left the machine):

- edgartools 5.62.1 cannot build its Form 4 object from XML without the owner lookup
  (`ReportingOwners.from_reporting_owner_tags` calls `Entity(cik).data`), but the same object can be assembled
  from its own parts without it, and `ownership_extractor.extract_form4_transactions` then returns the same rows.
  A parse takes about 3 ms.
- Listing a company's Form 4s costs one submissions request, and each row carries the accession, the filing
  date and the primary document's name.
- `sec_edgar_service.get_filing_document` fetches one document through the app's limiter and its own circuit
  breaker entry, and its errors say what happened: a 404, a 429 with `Retry-After`, a 5xx and a timeout each
  have a type, and a 403 or any other refusal is an `EdgarError` whose code is `EDGAR_HTTP_REFUSED` and whose
  context holds the status. A wait for the app's own limiter that runs out is `EDGAR_WAIT_TIMEOUT`, which says
  nothing about SEC. The breaker counts network errors (a 5xx among them), timeouts and 429s; it does not count
  a 403.
- Durable tasks were on in production when DECISIONS-17 was written (2026-10-08) and `docs/DEPLOYMENT.md` says
  they still are; the switch is a repository variable (`GCP_DURABLE_TASKS_ENABLED`) the code cannot read, and
  step 2 of the build reads the deploy's own line for it before relying on the worker. With it on, the API
  enqueues to Cloud Tasks, and a private worker service (`earningsnerd-task-worker`, one instance, one task at a
  time) runs each task in a child process. The worker is its own process with its own SEC budget, already
  counted in the 10-a-second total (`tests/unit/test_sec_process_budgets.py`).
- `User.is_beta` is set when an invitation is redeemed and is already returned by `/api/auth/me`.

## Decision

Insider activity is read from the database. A background scan fills it, a few documents at a time, on the task
worker. The endpoint answers at once with what is stored and says how far the scan has got, and only a signed-in
beta user can ask.

1. **Storage, per accession, in Postgres.** Three tables, each created by the models and by an idempotent
   migration (rule 3; the deploy applies migrations before new code serves):
   - `earningsnerd_insider_filings`: one row per Form 4 accession in an issuer's listing, with its filing date
     and its state: `listed` when a scan has seen it and not fetched it yet, then an outcome (`ok`,
     `not_issuer`, `no_xml`, `not_found`, `failed`), the parser's version and when it was attempted. A filing
     is immutable, so one with an outcome is never fetched again. SEC lists a Form 4 under its issuer and under
     each reporting owner, and an owner can be a company with a scan of its own, so the row is unique per
     issuer and accession, and only the issuer the document names stores its trades (`not_issuer` otherwise).
   - `earningsnerd_insider_transactions`: the open-market trades parsed from a stored filing.
   - `earningsnerd_insider_scans`: one row per issuer, with the scan's state, a lease, when the filings were last
     listed, and when a paused scan may resume.
   Neither references `filings` or a user: this is public SEC data, kept outside the retention purge.

2. **A scan step is bounded and resumable.** One step lists the issuer's Form 4s when the last listing is older
   than an hour (one edgartools submissions request, amendments excluded as today, the 60 most recent as today),
   then fetches and parses at most 8 filings that are not stored yet, newest first, committing each. A step that
   leaves filings unstored enqueues the next. Two steps never run for one issuer: a step claims the scan row
   with a conditional update and a lease, and writes only while it holds the lease.

3. **Each Form 4 is fetched as a document and parsed offline.** The step fetches the filing's XML with
   `get_filing_document` (one attempt, a 10 s limit), and falls back once to the submission's text file when
   the XML answers 404. Both addresses are built in `app/utils/sec_urls.py`, which gains a builder for a
   document inside a filing's folder and one for the submission's text file beside it (rule 10: no address is
   assembled anywhere else). It parses with edgartools' own parts,
   without the owner lookup, behind a check of the installed version and a test that parses Form 4 documents
   with the network closed. The parse also reads the issuer the document names: a filing in a company's
   listing that reports another issuer's shares (the company filed it as an owner) stores no trades. `insider_service` stops calling `obj()`, and its entry leaves the allow-list.

4. **The scan stops itself on pushback.** A refusal (403 or any other unexpected status), a 429, a 5xx, a
   timeout of the request, or an open breaker ends the step at once, told apart by the error's type, code and
   status. The scan row records the reason and a time before which it will not run again: the `Retry-After`
   when SEC gave one, else a backoff that doubles from five minutes. The breaker would not have stopped a 403.
   A wait for the process's own limiter that runs out is not pushback: the step ends and the next one carries
   on, with no pause. An issuer SEC does not know fails the scan, which then waits as a paused one does. An
   installed edgartools the parser was not written for fails it before any request, with no wait, so the
   deploy that fixes it carries straight on.

5. **Steps run on the task worker, as a new task kind.** The scan spends the worker's SEC budget, not an API
   instance's, so it cannot delay a summary's fetches or open the breaker a summary depends on. Cloud Tasks
   keeps a task's name for a day after it ran, and a second task of that name is dropped without an error, so
   every key carries something that moves: a step enqueued by the step before it is named by the issuer and the
   scan's step count, and one enqueued by a visit by the issuer and a short time bucket, so a second visitor in
   the same minute adds nothing and a visit an hour later is not swallowed. A paused scan's next step is
   scheduled for the time its pause ends. With durable tasks off (development), the step runs after the response
   in process.

6. **The endpoint requires a beta user and never waits for SEC.** A new dependency, `require_beta`, answers 401
   to a signed-out caller and 403 to a signed-in one who is not a beta user. It is not an entitlement: plans
   are Free and Pro, and beta membership is neither. The response is always a 200 holding the stored trades for
   the window asked for and a `scan` object: its status (`complete`, `scanning`, `paused` or `failed`), how many
   listed filings are stored, the oldest filing date covered, when it was last refreshed, and when to ask again.
   The request reads the issuer from the `companies` table and enqueues a step when the scan is due. The
   per-address limit becomes a per-user one, and the route's 75 s timeout entry goes, since nothing waits. `ENABLE_INSIDER_ACTIVITY` remains, as the switch that turns the
   endpoint off for everyone.

7. **The panel mounts for beta users and shows what it knows.** It asks only when `/api/auth/me` says the user
   is a beta user. While the scan runs it shows the stored trades with a line saying how far back they reach,
   and asks again at the interval the response gives, for at most three minutes. It shows a skeleton while it
   loads, an error with a retry when a request fails, and does not retry on its own. Its cached answers are
   cleared at sign-out.

8. **The scan reports itself.** Each step logs and counts the filings it listed, fetched, stored and failed, the
   refusals by status, and its duration, where the admin metrics and the job records can read them.

## Consequences

- A company's first visitor sees trades arrive over about a minute, newest first, where today's design would
  have shown nothing and failed. Every later visitor, on either instance and after any restart, is answered from
  the database.
- A full first scan of an active issuer is about 61 requests where it was about 121, in eight steps of about
  ten seconds each, on a process summaries do not use.
- The worker runs one task at a time, so a scan step delays the account mail and other tasks queued behind it by
  up to its own ten seconds. Steps are separate tasks so that other work takes its turn between them. The
  queue's drain arithmetic (`tests/unit/test_filings_routes.py`) is redone with the step in it.
- The offline parse reads edgartools internals that are not its public interface. The version check and the
  parse test fail on an upgrade that moves them, before it ships.
- The parse test's documents are written to SEC's ownership schema, not recorded from SEC: SEC refuses a client
  that does not declare who it is, and the build ran without the production identity. The production trial
  compares the first stored filings with the same filings on sec.gov before the panel is shown to anyone.
- A company that files Form 4s as an owner of another issuer's shares no longer has those trades shown as its
  own insider activity, which the live fetch did.
- That SEC serves a Form 4's XML at the primary document's name without its stylesheet directory is SEC's
  convention, not something read from code. The text-file fallback covers a miss, and the production trial reads
  the first real fetches before the panel is shown to anyone.
- A 10b5-1 plan is still marked per filing, as today: a filing that ticks the box marks all its trades.
  Marking each trade from its own footnote is left for later.
- Form 4/A, Form 3 and Form 5 stay out, as today.
- Turning it on is still a flag: `ENABLE_INSIDER_ACTIVITY=true` in the deploy, which the budget and flag tests
  pin and which the founder has approved. Turning it off is the same flag.

## How it is built and proven

In order, each a reviewed pull request, each backend one deployed and healthy before the next merges:

1. The tables, the offline parse, the fetch and the scan step, with nothing calling them. Tests: Form 4
   documents parsed with the network closed (several owners, a derivative-only filing, a plan sale, garbage); a
   step's request count and its ceiling; a step interrupted at each point resumes without refetching; a 403,
   429, 5xx and timeout each stop the step and set the pause, and a limiter wait that runs out does not; two
   claims of one scan, on Postgres; migration and model parity.
2. The task kind, the endpoint's new contract, `require_beta` and the per-user limit, still switched off in
   production. Tests: signed-out, non-beta and beta callers; the response while a scan is due, running, paused
   and complete; one enqueue for many requests in a minute, and a new one an hour after a scan completed; no
   SEC call from the request.
3. The panel's states and its beta gate. Tests: loading, partial, complete, empty, failed, and a non-beta user
   who gets no request at all.
4. The switch, its pinned tests and the operations doc, then the production trial: five named issuers from a
   beta account, reading the scan's counters, the breaker and summary latency; then a day of beta use.
