# Earnings calendar — feature pack (`features/calendar/` + `app/calendar/`)

Implements **tasks/earnings-calendar-strategy.md §3.7** (PR #524 branch): a
week/month calendar of U.S. earnings dates, estimated or reported, with
per-company earnings-day alerts.
Live design spec with every state exercisable: **`Earnings Calendar.dc.html`**
(project root — Tweaks simulate plan and data states).

## What ships

| File | Role |
|---|---|
| `api/calendar-api.ts` | Typed client: `GET /api/calendar?from&to`, alert enable/disable, `EarningsAlertError` with the machine-readable `earnings_alert_limit` code |
| `api/calendar-fixtures.ts` | ⚠ Isolated mock (dynamic-import only, `NEXT_PUBLIC_CALENDAR_FIXTURES='true'`); exercises both cap 403s |
| `lib/dates.ts` | ET-honest calendar-day math + computed NYSE holidays (no `new Date(iso)` shift bug) |
| `lib/lanes.ts` | Top-5 ranking, BMO/AMC/during·unspecified lanes, "usually after close" wording |
| `hooks/useCalendar.ts` | Viewer (session/plan/alert count), optimistic alert toggle with rollback, and today from the reader's browser (`useTodayEasternIso`; the range query and its retained failure live in the page, beside its `RetryButton`) |
| `components/` | `EarningsCalendarPage` (route body), `WeekView` (desktop sheet + mobile day list), `MonthView`, `DayDetailDialog` (native `<dialog>`), `EventRow`/`StatusChip`/`EpsFigure`, `AlertBell` + `BellPopover`, `laneHeader` |
| `app/calendar/page.tsx` | Route, 404-gated on `NEXT_PUBLIC_ENABLE_CALENDAR` (same pattern as `ENABLE_ANALYSIS`) |

## Week-grid direction (decision record)

Weighed three layouts:
1. **Five weekday columns in one calendar sheet, lanes stacked per day** ← built.
   Keeps the "week at a glance" shape traders expect, lane order (BMO → AMC →
   unspecified) is consistent across columns, collapses naturally into the
   mobile day-by-day list, and one lifted card avoids five competing shadows.
2. Full-width horizontal day rows — roomier rows but loses the week shape and
   makes cross-day scanning ("what reports Thursday AMC?") a scroll exercise.
3. Fixed BMO/AMC band matrix (2 rows × 5 days) — strongest lane alignment but
   rigid: sparse weeks waste a whole band, and dmh/null needs an awkward third band.

## Behavior contract (the parts worth reviewing)

- **Dates are US-Eastern calendar days end to end.** Ranges and anchors are
  plain ISO strings; "today" is asked once via `Intl(America/New_York)`, in
  the reader's browser (`useTodayEasternIso`); labels render via
  `lib/format.formatLocalDate` (which already documents the
  UTC-shift bug this avoids). Holidays are computed, so any navigated
  month/week renders honestly (e.g. Fri Jul 3 2026 = Independence Day observed).
- **The week is the browser's.** `/calendar` is prerendered and revalidated
  hourly, so the server renders the page's frame and the sheet's skeleton,
  with a bone where the range heading goes, and names no week: a week it read
  would be last week's once the New York week turns over, and React would
  throw away markup that disagreed with the browser's (error 418, E136). The
  heading and the week's data follow from the browser's today, read in the
  render right after hydration. `tests/e2e/fixtures/calendarWeek.ts` fails a
  pinned load that logs a hydration error, or whose heading is not the pinned
  week.
- **Top 5 per day** by `anticipation_score` desc; `+N more` opens the day
  dialog (desktop/month) or expands in place (mobile). Day cells never overflow.
- **Only what fits whole, at any text size.** Each view picks its layout by its
  own width in em (container queries), so 200% text gets the narrow layout
  rather than a clipped one: the week shows the five-column sheet from 42.5em
  and the day list below it; a list or dialog row narrower than 16em drops its
  decorative logo and stacks (the bell beside the ticker alone, the status chip,
  name, note and EPS full width under it, so no chip runs under the bell); a
  month day lists tickers with their session glyph and follow bell from 42em,
  the tickers alone from 21em, and below that the count of companies
  reporting, under one-letter weekday heads, with a caption that says so; there
  a holiday drops its "Closed" and its date takes the weekend's muted ink.
  Today's marker is sized in rem, so it holds its digits at any text size.
  Names wrap, never truncate, and the range label wraps between whole dates.
  `tests/unit/calendarReflow.spec.tsx` and `calendarEventRow.spec.tsx`.
- **Status ladder:** a status, so every rung is a member of Badge's status
  set (E141): `Est.` (`tentative`: a dashed hairline with no fill in either
  theme, tentative by design) → `Confirmed` (`info-status`: a firm, upcoming
  date, the rung a reader scans for; not `success`, whose light ink is the
  beat's `gain.text` hex) → `Reported` (`neutral-status`: the event is over,
  and its EPS actual, with a calm ▲/▼ in the gain/loss *text* tokens, carries
  the news). It reads dashed, blue, quiet. A chip's ground is its variant's,
  never a class on top, and each rung's label clears 4.5:1 on the rows at rest
  and hovered in both themes (`badgeVariants.spec.tsx`). Estimated rows with a
  habitual slot say "usually before open / after close" (§3.3: right about 3
  times in 4), on a line of their own after the lane's glyph, in every row kind
  (the week sheet, the day list, the day dialog), since the page's footer
  explains "usually".
- **Alerts:** bell on every row (the subscription is per *company*, so it
  shows on reported rows too — it arms the next quarter).
  - Signed-out → sign-in popover; its second action follows the registration
    mode (`ACCESS_COPY`): "Request an invite" while invite-only, the free
    account when registration is public.
  - **Free**: visible "N of 3" chip; the 4th enable short-circuits to the
    upsell popover (deliberate conversion surface). A server 403 with
    `code='earnings_alert_limit'` lands on the same surface.
  - **Pro**: nothing in the UI counts, hints, or disables — the enable request
    is always sent, and a 403 renders the API's message verbatim in a terse
    error popover ("Alert not enabled" + Dismiss, no upsell). No client-side
    special-casing, per spec.
  - Toggles are optimistic with rollback; `aria-pressed` carries state.
- **States:** shimmer skeleton (role="status" wrapper, aria-hidden bones),
  `GuidanceCard` error with `RetryButton`, `GuidanceCard` empty range, per-day
  "No reports" / "Market closed" over the holiday's name (desktop column),
  "Market closed · {holiday}" (mobile list).
- **A11y:** semantic day `<section>`s + `<ul>` rows; rows are real links to
  `/company/[ticker]`; bell is a sibling button (never a link-in-link); native
  `<dialog>` for the day detail (focus trap + Esc for free, focus restored);
  the bell's popover is a non-modal `role="group"` on `z-overlay` (no dialog
  role: nothing is inert and Tab is not trapped — its transparent catcher only
  turns an outside press into a close; the async error is also a `role="alert"`) with
  Esc, outside-click, Tab-out, bell-moving scroll and resize dismissal and focus return,
  rendered inside the day `<dialog>` while one is open, and placed from its measured
  height inside the visible viewport (below the bell, above it, or capped on the
  roomier side and scrolling inside; when neither side offers 6rem of the reader's
  text, over the bell at the visible height), a capped panel scrolling its focused
  action into view, never the page;
  `aria-live` on the range heading; every numeral/ticker is `font-data tabular-nums`.
- **Motion:** token-timed only — `animate-content-in` on the skeleton→content
  flip, shimmer at `duration-ambient`, `motion-safe:` guards. No decorative motion.

## Replacing the two existing components (no duplication)

- `features/dashboard/components/EarningsCalendar.tsx` — retire in place: render
  `getCalendar(mondayOf(today), +14d)` filtered to the user's watchlist, or
  simply link the dashboard card to `/calendar`. Its `getUpcomingCalendar`
  (FMP-backed) call goes away with the FMP calendar path (strategy §3.2).
- `features/calendar/components/ReportingThisWeek.tsx` — switch its data source to
  `getCalendar(weekRange)` → `rankEvents(...).slice(0, 8)` (score-ranked DB
  reads replacing the hardcoded 60-ticker intersect, §4 P4). Its
  render-nothing-when-empty behavior stays.

## Assumptions (flagging, not asking — each is one small backend/API decision)

1. `GET /api/calendar` responds `{ events: CalendarEvent[] }` (matches the
   §3.3 column set exposed in the brief).
2. Alert subscriptions readable via `GET /api/watchlist/earnings-alerts` →
   `{ tickers: string[] }` (derived from `Watchlist.earnings_alert`; adjust
   `getEarningsAlertTickers` if it ships as a field on `GET /api/watchlist/`).
3. Cap 403 body: `{ detail: string, code?: 'earnings_alert_limit' }`. The
   shared axios interceptor collapses errors to `ApiError(status, detail)`,
   so the toggle uses per-request `validateStatus` to read the body itself —
   no shared-client refactor.
4. `lib/icons.ts` needs three one-line export additions used here:
   `CaretRightIcon`, and (already exported) `SunIcon`/`MoonIcon`/`ClockIcon`
   cover the lanes — only `CaretRightIcon` is genuinely new.
5. URL state (`/calendar?view=month&anchor=2026-08-01`) is a follow-up; state
   is component-local in this drop.

## Definition-of-done status (DESIGN_SYSTEM.md §12)

- Grep gates run against `features/calendar/` + `app/calendar/`: **0** legacy
  brand/type hits; raw-ms grep matches only prose ("401s"/"403s" in comments)
  and fixture latencies (mock I/O, not motion — motion is token-only).
- Both themes verified interactively on the design spec
  (`Earnings Calendar.dc.html`), which mirrors these components 1:1.
- `typecheck` / `lint --max-warnings 0` / `build` / `test` must run in the
  repo (not executable from this workspace) — expected clean except the
  `CaretRightIcon` export noted above; add it with this pack.
