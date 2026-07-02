'use client'

/* =============================================================================
   DataTable — components/ui/DataTable.tsx
   -----------------------------------------------------------------------------
   Financial table wiring:
     - numeric columns render in the data face + tabular-nums (no jitter),
     - per-cell tone maps to the gain/loss/flat DATA colors — never the brand,
     - row hover BRIGHTENS,
     - built-in system states: loading (shimmer skeleton rows that preserve
       column layout), empty, error — pass your own nodes or use the defaults,
     - optional sortable headers: real <button>s with aria-sort + the brand
       focus ring (pass `sortable` on the column and `sort`/`onSort` on the table),
     - density: 'comfortable' (default, py-2.5) | 'compact' — 4px-grid row
       padding + 12px text (the micro-annotation floor; never smaller), with
       skeleton rows matched to each rhythm so loading doesn't jump,
     - stickyHeader: thead sticks within the scroll container on an opaque
       panel surface with a token hairline underneath (no shadow). Uses
       border-separate so the hairline sticks with the header; the row
       hairlines live on the cells, which renders identically.
============================================================================= */

import { type ReactNode, useEffect, useRef, useState } from 'react'
import { cx } from './cx'
import { Skeleton } from './Skeleton'

export type CellTone = 'gain' | 'loss' | 'flat'

export type Density = 'comfortable' | 'compact'

/* Row rhythm per density. Compact stays on the 4px grid (py-1 = 4px) and
   drops cell text to 12px — the floor. Skeleton bar + padding sum to the same
   row height as a real row (12 + 6·2 = 24px = 4 + 16 + 4) so loading ⇄ loaded
   doesn't shift the layout. */
const DENSITY: Record<Density, { text: string; headerY: string; cellY: string; skelY: string; skelBar: string }> = {
  comfortable: { text: 'text-sm', headerY: 'py-2', cellY: 'py-2.5', skelY: 'py-3.5', skelBar: 'h-3.5' },
  compact: { text: 'text-xs', headerY: 'py-1', cellY: 'py-1', skelY: 'py-1.5', skelBar: 'h-3' },
}

const TONE: Record<CellTone, string> = {
  // -text variants: the 600-level green/red are graphic-only (3:1) — text needs the 700s on cream
  gain: 'font-semibold text-gain-text dark:text-gain-dark',
  loss: 'font-semibold text-loss-text dark:text-loss-dark',
  flat: 'text-flat-light dark:text-flat-dark',
}

export interface Column<T> {
  key: string
  header: ReactNode
  align?: 'left' | 'right'
  /** Money / % / tickers — data face + tabular-nums. */
  numeric?: boolean
  render?: (row: T) => ReactNode
  /** Map a row to gain/loss/flat coloring for this cell. */
  tone?: (row: T) => CellTone | undefined
  /** Header becomes a sort button (needs `onSort` on the table). */
  sortable?: boolean
}

export interface SortState {
  key: string
  dir: 'asc' | 'desc'
}

export interface DataTableProps<T> {
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T, index: number) => string
  loading?: boolean
  skeletonRows?: number
  /** Current sort — sorted header shows ▲/▼ and sets aria-sort. */
  sort?: SortState
  onSort?: (key: string) => void
  empty?: ReactNode
  error?: ReactNode
  /** Row rhythm — 'compact' for dense financial screens. Default 'comfortable'. */
  density?: Density
  /** Header sticks to the top of the nearest scroll container (give the wrapper a height via `className`). */
  stickyHeader?: boolean
  /** Accessible summary, rendered sr-only. */
  caption?: string
  className?: string
}

const ROW_BORDER = 'border-t border-border-light dark:border-border-dark'

const STICKY_TH =
  // Opaque token surface + token hairline — collapsed borders don't stick, so the
  // table switches to border-separate and the th carries its own bottom border.
  'sticky top-0 z-10 bg-panel-light dark:bg-panel-dark border-b border-border-light dark:border-border-dark'

export function DataTable<T extends Record<string, unknown>>({
  columns,
  rows,
  rowKey,
  loading = false,
  skeletonRows = 4,
  sort,
  onSort,
  empty,
  error,
  density = 'comfortable',
  stickyHeader = false,
  caption,
  className,
}: DataTableProps<T>) {
  const colSpan = columns.length
  const showRows = !loading && !error && rows.length > 0
  const d = DENSITY[density]

  // Skeleton→content handoff: when `loading` flips false, whatever replaces the
  // skeleton rows (data, empty, error) crossfades in — animate-content-in =
  // duration-base / ease-standard; instant under reduced motion. Tables that
  // never load don't animate on first paint.
  const wasLoading = useRef(loading)
  const [entered, setEntered] = useState(false)
  useEffect(() => {
    if (wasLoading.current && !loading) setEntered(true)
    if (loading) setEntered(false)
    wasLoading.current = loading
  }, [loading])

  // Row hairlines sit on the cells (renders identically to tr borders) so they
  // survive border-separate. With a sticky header the th's border-b already
  // draws the first hairline — the first body row skips its border-t.
  const rowBorder = (i: number) => (stickyHeader && i === 0 ? undefined : ROW_BORDER)

  return (
    <div className={cx(stickyHeader ? 'overflow-auto' : 'overflow-x-auto', className)}>
      <table
        className={cx('w-full', d.text, stickyHeader ? 'border-separate border-spacing-0' : 'border-collapse')}
        aria-busy={loading || undefined}
      >
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <thead>
          {/* 12px uppercase metric-label header — eyebrow tracking 0.08em (--track-eyebrow), matching .markdown-body th */}
          <tr className="text-left text-xs uppercase tracking-[0.08em] text-text-tertiary-light dark:text-text-secondary-dark">
            {columns.map((c) => {
              const sorted = sort && sort.key === c.key ? sort.dir : undefined
              return (
                <th
                  key={c.key}
                  scope="col"
                  aria-sort={sorted === 'asc' ? 'ascending' : sorted === 'desc' ? 'descending' : undefined}
                  className={cx('px-3 font-semibold', d.headerY, c.align === 'right' && 'text-right', stickyHeader && STICKY_TH)}
                >
                  {c.sortable && onSort ? (
                    <button
                      type="button"
                      onClick={() => onSort(c.key)}
                      className={cx(
                        'inline-flex items-center gap-1 rounded uppercase tracking-[0.08em]',
                        'hover:text-text-primary-light dark:hover:text-text-primary-dark',
                        'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
                        c.align === 'right' && 'flex-row-reverse',
                      )}
                    >
                      {c.header}
                      <span
                        aria-hidden="true"
                        className={cx(
                          'text-[9px] leading-none',
                          sorted ? 'text-brand-strong dark:text-brand-strong-dark' : 'opacity-40',
                        )}
                      >
                        {sorted === 'asc' ? '▲' : '▼'}
                      </span>
                    </button>
                  ) : (
                    c.header
                  )}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody className={entered ? 'animate-content-in motion-reduce:animate-none' : undefined}>
          {loading
            ? Array.from({ length: skeletonRows }).map((_, r) => (
                <tr key={r}>
                  {columns.map((c) => (
                    <td key={c.key} className={cx('px-3', d.skelY, rowBorder(r))}>
                      <Skeleton className={cx(d.skelBar, c.align === 'right' ? 'ml-auto w-14' : 'w-24')} />
                    </td>
                  ))}
                </tr>
              ))
            : null}

          {!loading && error ? (
            <tr>
              <td colSpan={colSpan} className={cx('px-3 py-6', rowBorder(0))}>
                {error}
              </td>
            </tr>
          ) : null}

          {!loading && !error && rows.length === 0 ? (
            <tr>
              <td colSpan={colSpan} className={cx('px-3 py-6', rowBorder(0))}>
                {empty ?? (
                  <p className="text-center text-sm text-text-tertiary-light dark:text-text-secondary-dark">
                    No results.
                  </p>
                )}
              </td>
            </tr>
          ) : null}

          {showRows
            ? rows.map((row, i) => (
                <tr
                  key={rowKey(row, i)}
                  className="transition-colors hover:bg-white dark:hover:bg-white/[0.03]"
                >
                  {columns.map((c) => {
                    const tone = c.tone?.(row)
                    return (
                      <td
                        key={c.key}
                        className={cx(
                          'px-3',
                          d.cellY,
                          rowBorder(i),
                          c.align === 'right' && 'text-right',
                          c.numeric && 'font-data tabular-nums',
                          tone && TONE[tone],
                        )}
                      >
                        {c.render ? c.render(row) : (row[c.key] as ReactNode)}
                      </td>
                    )
                  })}
                </tr>
              ))
            : null}
        </tbody>
      </table>
    </div>
  )
}
