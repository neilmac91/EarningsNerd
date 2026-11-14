/* =============================================================================
   Earnings calendar — calendar-day math (features/calendar/lib/dates.ts)
   -----------------------------------------------------------------------------
   `event_date` is an America/New_York CALENDAR DAY serialized as YYYY-MM-DD.
   Every helper here does plain calendar arithmetic on the string (via UTC
   epoch days, which is timezone-neutral for whole days) — the ONE place a real
   timezone is consulted is todayEasternIso(), which asks Intl what "today" is
   in New York. Never `new Date('YYYY-MM-DD')` + toLocaleDateString: that
   parses as UTC midnight and shifts the day for viewers west of UTC
   (lib/format.ts documents the same bug for display formatting — render
   labels with formatLocalDate).
============================================================================= */

function parts(iso: string): [number, number, number] {
  const [y, m, d] = iso.split('-').map(Number)
  return [y, m, d]
}

function toIso(y: number, m: number, d: number): string {
  return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

function fromUtc(dt: Date): string {
  return toIso(dt.getUTCFullYear(), dt.getUTCMonth() + 1, dt.getUTCDate())
}

export function addDaysIso(iso: string, n: number): string {
  const [y, m, d] = parts(iso)
  const dt = new Date(Date.UTC(y, m - 1, d))
  dt.setUTCDate(dt.getUTCDate() + n)
  return fromUtc(dt)
}

/** 0 = Sunday … 6 = Saturday. */
export function isoDayOfWeek(iso: string): number {
  const [y, m, d] = parts(iso)
  return new Date(Date.UTC(y, m - 1, d)).getUTCDay()
}

export function diffDays(fromIso: string, toIsoDate: string): number {
  const [y1, m1, d1] = parts(fromIso)
  const [y2, m2, d2] = parts(toIsoDate)
  return Math.round((Date.UTC(y2, m2 - 1, d2) - Date.UTC(y1, m1 - 1, d1)) / 86_400_000)
}

export function mondayOf(iso: string): string {
  const w = isoDayOfWeek(iso)
  return addDaysIso(iso, w === 0 ? -6 : 1 - w)
}

export function firstOfMonth(iso: string): string {
  const [y, m] = parts(iso)
  return toIso(y, m, 1)
}

export function addMonths(iso: string, n: number): string {
  const [y, m] = parts(iso)
  const total = m - 1 + n
  const y2 = y + Math.floor(total / 12)
  const m2 = ((total % 12) + 12) % 12 + 1
  return toIso(y2, m2, 1)
}

/** Today as a New York calendar day — the only timezone-aware call. */
export function todayEasternIso(): string {
  try {
    return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York' }).format(new Date())
  } catch {
    return fromUtc(new Date())
  }
}

// ---- NYSE full-closure holidays -------------------------------------------
// Computed, not hardcoded, so month navigation is honest in any year.
// Good Friday: two days before Western Easter (anonymous Gregorian computus).
function goodFriday(y: number): string {
  const a = y % 19
  const b = Math.floor(y / 100)
  const c = y % 100
  const d = Math.floor(b / 4)
  const e = b % 4
  const f = Math.floor((b + 8) / 25)
  const g = Math.floor((b - f + 1) / 3)
  const h = (19 * a + b - d - g + 15) % 30
  const i = Math.floor(c / 4)
  const k = c % 4
  const l = (32 + 2 * e + 2 * i - h - k) % 7
  const m = Math.floor((a + 11 * h + 22 * l) / 451)
  const month = Math.floor((h + l - 7 * m + 114) / 31)
  const day = ((h + l - 7 * m + 114) % 31) + 1
  return addDaysIso(toIso(y, month, day), -2)
}

function nthWeekday(y: number, m: number, weekday: number, n: number): string {
  let count = 0
  for (let d = 1; d <= 31; d++) {
    const dt = new Date(Date.UTC(y, m - 1, d))
    if (dt.getUTCMonth() !== m - 1) break
    if (dt.getUTCDay() === weekday) {
      count++
      if (count === n) return toIso(y, m, d)
    }
  }
  return toIso(y, m, 1)
}

function lastWeekday(y: number, m: number, weekday: number): string {
  let last = toIso(y, m, 1)
  for (let d = 1; d <= 31; d++) {
    const dt = new Date(Date.UTC(y, m - 1, d))
    if (dt.getUTCMonth() !== m - 1) break
    if (dt.getUTCDay() === weekday) last = toIso(y, m, d)
  }
  return last
}

function observed(iso: string): string {
  const w = isoDayOfWeek(iso)
  if (w === 6) return addDaysIso(iso, -1) // Saturday → Friday
  if (w === 0) return addDaysIso(iso, 1) // Sunday → Monday
  return iso
}

const holidayCache = new Map<number, Record<string, string>>()

function holidaysForYear(y: number): Record<string, string> {
  const cached = holidayCache.get(y)
  if (cached) return cached
  const map: Record<string, string> = {
    [observed(toIso(y, 1, 1))]: "New Year's Day",
    [nthWeekday(y, 1, 1, 3)]: 'Martin Luther King Jr. Day',
    [nthWeekday(y, 2, 1, 3)]: "Washington's Birthday",
    [lastWeekday(y, 5, 1)]: 'Memorial Day',
    [observed(toIso(y, 7, 4))]: 'Independence Day',
    [nthWeekday(y, 9, 1, 1)]: 'Labor Day',
    [nthWeekday(y, 11, 4, 4)]: 'Thanksgiving Day',
    [observed(toIso(y, 12, 25))]: 'Christmas Day',
  }
  // NYSE first closed for Juneteenth in 2022.
  if (y >= 2022) map[observed(toIso(y, 6, 19))] = 'Juneteenth'
  map[goodFriday(y)] = 'Good Friday'
  holidayCache.set(y, map)
  return map
}

/** Name of the U.S. market holiday on this ET calendar day, else null. */
export function marketHolidayName(iso: string): string | null {
  return holidaysForYear(parts(iso)[0])[iso] ?? null
}
