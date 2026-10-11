/* Prototype renderer. Reads the engine output (data/*.js) and renders the PROPOSED treatment, or a
   reproduction of today's markup for side-by-side measurement. Plain DOM, no framework: the
   implementation brief maps each block to the React component that owns it. */
(function () {
  'use strict'

  const $ = (sel, root) => (root || document).querySelector(sel)
  const el = (tag, attrs, ...children) => {
    const node = document.createElement(tag)
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue
      if (k === 'class') node.className = v
      else if (k === 'html') node.innerHTML = v
      else if (k.startsWith('on')) node.addEventListener(k.slice(2), v)
      else node.setAttribute(k, v === true ? '' : v)
    }
    for (const c of children.flat()) if (c != null && c !== false) node.append(c.nodeType ? c : document.createTextNode(String(c)))
    return node
  }

  // ---------- formatting (mirrors lib/format.ts + MetricsTable.formatSeriesValue) ----------
  const currencyFmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1, minimumFractionDigits: 1 })
  const fmtMoney = (v, unit) => {
    const code = (unit || 'USD').split('/')[0].toUpperCase()
    const text = currencyFmt.format(v)
    return code === 'USD' ? text : text.replace('$', `${code} `)
  }
  const fmtPct = (v, digits = 1) => `${v.toFixed(digits)}%`
  const fmtPp = (v) => `${v > 0 ? '+' : ''}${v.toFixed(1)}pp`
  const fmtGrowth = (v) => `${v > 0 ? '+' : ''}${(v * 100).toFixed(1)}%`
  const fmtRatio = (v) => `${v.toFixed(2)}×`
  // Integers in locale form; fractions exactly as stored (the shortest round-trip form), never re-rounded.
  const fmtExact = (v) => (Number.isInteger(v) ? v.toLocaleString('en-US') : String(v))
  const unitLabel = (unit) => (!unit || unit === 'USD' ? '' : unit === 'pure' ? '(ratio)' : unit === '%' || unit === 'percent' ? '%' : unit.endsWith('/shares') ? `${unit.split('/')[0]} per share` : unit)
  function fmtValue(v, series) {
    if (series.percent) return fmtPct(v)
    if (series.unit === 'pure') return fmtRatio(v)
    if (series.unit.endsWith('/shares')) { const code = series.unit.split('/')[0].toUpperCase(); return `${v < 0 ? '-' : ''}${code === 'USD' ? '$' : code + ' '}${Math.abs(v).toFixed(2)}` }
    return fmtMoney(v, series.unit)
  }
  function fmtExactWithUnit(v, series) {
    if (series.percent) return `${fmtExact(v)}%`
    if (series.unit === 'pure') return `${fmtExact(v)} (ratio)`
    if (series.unit.endsWith('/shares')) return `${fmtExact(v)} ${series.unit.split('/')[0]} per share`
    return `${fmtExact(v)} ${series.unit}`
  }
  function fmtDelta(value, percent) {
    if (value == null) return { text: '', dir: 'flat' }
    if (typeof value !== 'number') return { text: 'n/m', dir: 'flat' }
    const dir = value > 0 ? 'up' : value < 0 ? 'down' : 'flat'
    return { text: percent ? fmtPp(value) : fmtGrowth(value), dir }
  }
  const tone = (seriesTone, dir) => (dir === 'flat' ? 'flat' : seriesTone === 'neutral' ? 'flat' : seriesTone === 'inverted' ? (dir === 'up' ? 'down' : 'up') : dir)
  const QKEY = /^(\d{4})(Q[1-4])$/
  const periodLong = (key) => { const m = QKEY.exec(key); return m ? `${m[2]} ${m[1]}` : key }
  const periodShort = (key) => { const m = QKEY.exec(key); return m ? [m[2], `’${m[1].slice(2)}`] : [key, ''] }
  const REASONS = {
    legacy_calculation: 'Saved calculation predates the current source checks; its inputs are not recorded.',
    source_check_needed: 'A source check remains unresolved.',
    unsupported_eps_calculation: 'Quarterly earnings per share cannot be calculated; a reported quarterly figure is needed.',
    source_conflict: 'Available sources disagree on this figure.',
    unit_mismatch: 'The source inputs use different units or currencies.',
    period_mismatch: 'The source inputs cover incompatible reporting periods.',
    incompatible_vintages: 'The inputs come from incompatible versions of the company’s filings.',
    missing_compatible_operand: 'A compatible earlier year-to-date figure is unavailable for this calculation.',
    missing_inputs: 'The source inputs needed for this calculation are unavailable.',
    repair_rolled_back: 'This figure was withdrawn during a data correction.',
    not_in_dataset: 'Not available in this dataset.',
    legacy_unknown: 'Validation details are unavailable for this saved figure. No verification claim is made.',
  }
  const reasonText = (r) => REASONS[r] || 'The source or calculation basis needs review.'
  const FORMULAS = {
    year_over_year_growth: '(current − same quarter last year) ÷ |same quarter last year|',
    quarter_over_quarter_growth: '(current − previous quarter) ÷ |previous quarter|',
    percentage_point_change: 'current − comparison, in percentage points',
    compound_annual_growth: '(last ÷ first) ^ (1 ÷ years) − 1',
  }
  const formulaText = (f) => FORMULAS[f] || (f || '').replace(/_/g, ' ').replace(/abs\(/g, '|').replace(/\)/g, '|')
  const conceptLabel = (c) => ({ revenue: 'Revenue', net_income: 'Net income', operating_income: 'Operating income', operating_cash_flow: 'Operating cash flow', capital_expenditures: 'Capital expenditures', current_assets: 'Current assets', current_liabilities: 'Current liabilities', free_cash_flow: 'Free cash flow', working_capital: 'Working capital', current_ratio: 'Current ratio', net_margin: 'Net margin', operating_margin: 'Operating margin' }[c] || c.replace(/_/g, ' '))

  // ---------- data notes: group every concern by its underlying issue ----------
  const letterFor = (index) => { let out = ''; for (let v = index + 1; v > 0; v = Math.floor((v - 1) / 26)) out = String.fromCharCode(97 + (v - 1) % 26) + out; return out }
  function needsReview(p) { return p && p.provenance ? p.provenance.validation === 'needs_review' : p && p.reconciled === false }
  // A populated figure with no validation record (older snapshots, or a record whose validation is neither
  // passed nor needs_review) gets a note of its own and is never counted as passed.
  function kindOf(p) {
    if (!p || p.value == null) return 'unavailable'
    if (p.provenance) return p.provenance.validation === 'needs_review' ? 'review' : p.provenance.validation === 'passed' ? null : 'unknown'
    return p.reconciled === false ? 'review' : 'unknown'
  }
  function comparisonKindOf(p, basis) {
    if (!p || p[basis] == null) return null
    const prov = p[basis + '_provenance']
    if (prov) return prov.validation === 'needs_review' ? 'review' : prov.validation === 'passed' ? null : 'unknown'
    return p[basis + '_reconciled'] === false ? 'review' : 'unknown'
  }
  // Calculated status survives a missing provenance record: older snapshots carry `derived` instead.
  const isCalculated = (p) => !!p && (p.provenance ? p.provenance.method === 'calculated' : !!p.derived)
  function buildNotes(dataset) {
    const groups = new Map()
    // A note is a distinct SET of reason codes: canonicalise before keying, whatever order the operands supplied.
    const canon = (reasons) => [...new Set(reasons || [])].sort()
    const key = (reasons) => { const r = canon(reasons); return r.length ? r.join('+') : 'source_check_needed' }
    // A populated record whose validation is neither passed nor needs_review keeps the reasons it supplied
    // (lib/dataNotes.ts on main does the same); `legacy_unknown` is the fallback for an empty set only.
    const unknownReasons = (prov) => { const r = canon(prov && prov.reasons); return r.length ? r : ['legacy_unknown'] }
    const unknownKey = (prov) => 'unknown:' + unknownReasons(prov).join('+')
    const get = (k, kind) => { if (!groups.has(k)) groups.set(k, { key: k, kind, reasons: k.replace(/^(unknown|unavailable):/, '').split('+'), values: [], comparisons: [], series: new Map(), comparisonSeries: new Map() }); return groups.get(k) }
    const place = (map, s, p) => { if (!map.has(s.concept)) map.set(s.concept, { label: s.label, periods: [] }); const periods = map.get(s.concept).periods; if (!periods.includes(p.period)) periods.push(p.period) }
    const latest = dataset.periods[dataset.periods.length - 1].key
    for (const s of dataset.series) {
      for (const p of s.points) {
        const kind = p.value != null ? kindOf(p) : null
        if (kind === 'review' || kind === 'unknown') {
          const g = kind === 'review' ? get(key(p.provenance && p.provenance.reasons), 'review') : get(unknownKey(p.provenance), 'unknown')
          g.values.push({ series: s, point: p })
          place(g.series, s, p)
        }
      }
    }
    for (const s of dataset.series) {
      for (const p of s.points) {
        if (p.value != null) continue
        const reasons = (p.provenance && p.provenance.reasons && p.provenance.reasons.length) ? p.provenance.reasons : ['not_in_dataset']
        const g = get('unavailable:' + canon(reasons).join('+'), 'unavailable')
        g.values.push({ series: s, point: p })
        place(g.series, s, p)
      }
    }
    // Comparisons inherit the note of the operand that failed its check.
    for (const s of dataset.series) {
      for (const p of s.points) {
        for (const basis of ['qoq', 'yoy']) {
          const kind = comparisonKindOf(p, basis)
          if (!kind) continue
          const prov = p[basis + '_provenance']
          const g = kind === 'review' ? get(key(prov && prov.reasons), 'review') : get(unknownKey(prov), 'unknown')
          g.comparisons.push({ series: s, point: p, basis })
          // A comparison-only note must still say where it is: record the comparison's metric and period.
          place(g.comparisonSeries, s, p)
        }
      }
    }
    const ORDER = { review: 0, unknown: 1, unavailable: 2 }
    const list = [...groups.values()].sort((a, b) => ORDER[a.kind] - ORDER[b.kind])
    list.forEach((g, i) => { g.letter = letterFor(i) })
    const byKey = Object.fromEntries(list.map((g) => [g.key, g]))
    const noteFor = (p) => { if (!p) return null; if (p.value == null) { const r = (p.provenance && p.provenance.reasons && p.provenance.reasons.length) ? p.provenance.reasons : ['not_in_dataset']; return byKey['unavailable:' + canon(r).join('+')] || null } const k = kindOf(p); return k === 'review' ? byKey[key(p.provenance && p.provenance.reasons)] || null : k === 'unknown' ? byKey[unknownKey(p.provenance)] || null : null }
    const noteForComparison = (p, basis) => { const k = comparisonKindOf(p, basis); if (!k) return null; const prov = p[basis + '_provenance']; return (k === 'unknown' ? byKey[unknownKey(prov)] : byKey[key(prov && prov.reasons)]) || null }
    const reviewValues = list.filter((g) => g.kind === 'review').reduce((n, g) => n + g.values.length, 0)
    const reviewComparisons = list.filter((g) => g.kind === 'review').reduce((n, g) => n + g.comparisons.length, 0)
    const unknownValues = list.filter((g) => g.kind === 'unknown').reduce((n, g) => n + g.values.length, 0)
    const unknownComparisons = list.filter((g) => g.kind === 'unknown').reduce((n, g) => n + g.comparisons.length, 0)
    const unavailable = list.filter((g) => g.kind === 'unavailable').reduce((n, g) => n + g.values.length, 0)
    const total = dataset.series.reduce((n, s) => n + s.points.filter((p) => p.value != null).length, 0)
    const calculated = dataset.series.reduce((n, s) => n + s.points.filter((p) => p.value != null && isCalculated(p)).length, 0)
    const passed = total - reviewValues - unknownValues
    return { list, noteFor, noteForComparison, reviewValues, reviewComparisons, unknownValues, unknownComparisons, unavailable, total, passed, calculated, latest }
  }

  // ---------- state ----------
  const state = { stateName: 'legacy', mode: 'proposed', window: '12', text: 1 }
  function current() { return window.EN_STATES[state.stateName] }

  // Reveal the strip and move focus to the note itself (main's openDataNote): no dead jump, no forced motion.
  function openNote(letter) { const d = $('#data-notes'); if (d) d.open = true; const t = $(`#note-${letter}`); if (!t) return; t.tabIndex = -1; t.focus({ preventScroll: true }); t.scrollIntoView({ block: 'center' }) }
  // ---------- affix: † for calculated, a note letter for a concern ----------
  function affix(point, note, opts) {
    const calc = isCalculated(point)
    const parts = []
    if (calc && !(opts && opts.noDagger)) parts.push(el('span', { class: 'dag', 'aria-hidden': 'true' }, '†'))
    if (note) parts.push(el('sup', { class: 'note' + (note.kind === 'review' ? '' : ' ' + note.kind), 'aria-hidden': 'true' }, note.letter))
    if (!parts.length) return null
    return el('span', { class: 'affix' }, parts)
  }
  function nameFor(series, point, note, cmpNote) {
    const bits = [`${series.label}, ${periodLong(point.period)}: ${point.value == null ? 'unavailable' : fmtValue(point.value, series)}`]
    if (isCalculated(point)) bits.push('calculated')
    if (note) bits.push(`data note ${note.letter}`)
    if (cmpNote) bits.push(`comparison carries data note ${cmpNote.letter}`)
    return bits.join(', ') + '. View source and calculation'
  }

  // ---------- period selector (proposed) ----------
  function renderPicker(root, dataset) {
    const cov = window.EN_COVERAGE
    const quarters = cov.quarterly.map((p) => p.key)
    const first = quarters[0], last = quarters[quarters.length - 1]
    const start = dataset.periods[0].key, end = dataset.periods[dataset.periods.length - 1].key
    const derived = dataset.periods.filter((p) => p.fiscal_period === 'Q4').length
    root.replaceChildren(
      el('div', { class: 'picker' },
        el('div', { class: 'row' },
          el('div', { style: 'display:flex;flex-wrap:wrap;align-items:center;gap:.5rem;font-size:.875rem' }, el('span', { style: 'display:inline-block;width:20px;height:20px;border-radius:50%;background:var(--brand-weak);border:1px solid var(--brand-border)' }), el('b', null, 'Meta Platforms, Inc.'), el('span', { class: 'data', style: 'color:var(--ink-2)' }, 'META')),
        ),
        el('div', { class: 'row' },
          el('div', { class: 'seg adaptive', role: 'group', 'aria-label': 'Analysis mode' }, el('button', { type: 'button', 'aria-pressed': 'false' }, 'Annual'), el('button', { type: 'button', 'aria-pressed': 'true' }, 'Quarterly')),
          el('div', { class: 'presets', role: 'group', 'aria-label': 'Quick ranges' }, ...[4, 8, 12].map((n) => el('button', { type: 'button' }, `Last ${n}`))), // plain actions: no pressed state, no selected tint (§4.9); the summary line states the range
          el('div', { class: 'range' },
            el('label', null, 'From', el('select', { class: 'field' }, ...quarters.map((q) => el('option', { value: q, selected: q === start }, periodLong(q))))),
            el('label', null, 'To', el('select', { class: 'field' }, ...quarters.map((q) => el('option', { value: q, selected: q === end }, periodLong(q))))),
          ),
        ),
        el('p', { class: 'summary', style: 'margin:0' }, el('b', null, `${dataset.periods.length} quarters`), ` · ${periodLong(start)} – ${periodLong(end)} · ${derived} calculated Q4 columns (†) · data available ${periodLong(first)} – ${periodLong(last)} · up to 12 at a time`),
        el('div', null, el('button', { type: 'button', class: 'btn primary' }, 'Run analysis')),
      ),
    )
  }

  // ---------- KPI strip (proposed) ----------
  function latestPoint(series) { for (let i = series.points.length - 1; i >= 0; i -= 1) if (series.points[i].value != null) return series.points[i]; return null }
  function renderKpis(dataset, notes) {
    const by = Object.fromEntries(dataset.series.map((s) => [s.concept, s]))
    const specs = ['revenue', 'net_income', 'free_cash_flow', 'net_margin']
    const strip = el('dl', { class: 'kpi-strip', 'aria-label': 'Headline figures' })
    for (const concept of specs) {
      const s = by[concept]; if (!s) continue
      const p = latestPoint(s); if (!p) continue
      const note = notes.noteFor(p)
      const cmpNote = notes.noteForComparison(p, 'yoy')
      const d = fmtDelta(p.yoy, s.percent)
      const t = tone(s.tone, d.dir)
      const btn = el('button', { type: 'button', 'aria-label': nameFor(s, p, note, cmpNote), onclick: () => openEvidence(s, p, notes, 'yoy') }, fmtValue(p.value, s), affix(p, note))
      strip.append(el('div', { class: 'kpi card', 'data-kpi': concept },
        el('dt', { class: 'label' }, s.label),
        el('dd', { class: 'value' }, btn),
        el('dd', { class: 'sub' },
          el('span', { class: 'period' }, periodLong(p.period), p.period !== notes.latest ? el('span', { class: 'late' }, ' · latest available') : null),
          d.text ? el('span', { class: 'delta ' + t }, el('span', { class: 'sr-only' }, 'year over year '), el('span', { 'aria-hidden': 'true' }, 'YoY '), d.text, cmpNote ? el('sup', { class: 'affix', 'aria-hidden': 'true' }, el('span', { class: 'note' + (cmpNote.kind === 'review' ? '' : ' ' + cmpNote.kind) }, cmpNote.letter)) : null) : el('span', { class: 'delta flat' }, 'YoY —'),
        ),
      ))
    }
    return strip
  }

  // ---------- data notes strip (proposed) ----------
  function describePlaces(map) {
    return [...map.values()].map((s) => `${s.label} (${s.periods.map(periodLong).join(', ')})`).join('; ')
  }
  function renderNotes(dataset, notes) {
    const details = el('details', { class: 'notes', id: 'data-notes' })
    const reviewGroups = notes.list.filter((g) => g.kind === 'review')
    const unknownGroups = notes.list.filter((g) => g.kind === 'unknown')
    const unavailableGroups = notes.list.filter((g) => g.kind === 'unavailable')
    const counts = el('span', { class: 'counts' })
    // Each clause names the letters of the notes it counts, so the resting line stays the key to the marks:
    // a note with values and comparisons appears in both clauses; a comparison-only note (a passed figure
    // whose comparison carries a concern or has no validation record) appears in the comparison clause only.
    const lettersOf = (groups) => groups.map((g) => g.letter).join(', ')
    const withValues = (groups) => groups.filter((g) => g.values.length)
    const withComparisons = (groups) => groups.filter((g) => g.comparisons.length)
    const noteWord = (groups) => (groups.length === 1 ? 'note' : 'notes')
    const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`
    const sep = () => (counts.childNodes.length ? ' · ' : '')
    if (notes.reviewValues) counts.append(el('b', null, plural(notes.reviewValues, 'figure', 'figures')), ` need${notes.reviewValues === 1 ? 's' : ''} review (${lettersOf(withValues(reviewGroups))})`)
    if (notes.reviewComparisons) counts.append(`${sep()}${plural(notes.reviewComparisons, 'comparison carries', 'comparisons carry')} ${noteWord(withComparisons(reviewGroups))} ${lettersOf(withComparisons(reviewGroups))}`)
    if (notes.unknownValues) counts.append(`${sep()}${plural(notes.unknownValues, 'figure has', 'figures have')} no validation record (${lettersOf(withValues(unknownGroups))})`)
    if (notes.unknownComparisons) counts.append(`${sep()}${plural(notes.unknownComparisons, 'comparison has', 'comparisons have')} no validation record (${lettersOf(withComparisons(unknownGroups))})`)
    // Every populated figure passed: say so first, before any comparison-only clause.
    if (!notes.reviewValues && !notes.unknownValues) counts.prepend(el('b', { class: 'ok' }, 'No figures need review'), ` · ${notes.passed} checked${counts.childNodes.length ? ' · ' : ''}`)
    if (notes.unavailable) counts.append(` · ${notes.unavailable} unavailable (${lettersOf(unavailableGroups)})`)
    counts.append(` · ${notes.calculated} calculated †`)
    details.append(el('summary', null, el('span', { class: 'caret', 'aria-hidden': 'true' }), el('span', { class: 'title' }, 'Data notes'), counts))
    const body = el('div', { class: 'body' })
    const ol = el('ol')
    for (const g of [...reviewGroups, ...unknownGroups, ...unavailableGroups]) {
      const li = el('li', { id: `note-${g.letter}` })
      li.append(el('span', { class: 'mark' + (g.kind === 'review' ? '' : ' ' + g.kind) }, g.letter))
      const box = el('div')
      box.append(el('div', { class: 'what' }, g.reasons.map(reasonText).join(' ')))
      if (g.series.size) box.append(el('div', { class: 'where' }, describePlaces(g.series)))
      // The comparisons that carry the note, by metric and period (a comparison-only note has only this line).
      if (g.comparisonSeries.size) box.append(el('div', { class: 'where' }, 'Comparisons: ' + describePlaces(g.comparisonSeries)))
      const c = el('div', { class: 'counts' })
      if (g.kind === 'review') {
        const qoq = g.comparisons.filter((x) => x.basis === 'qoq').length, yoy = g.comparisons.filter((x) => x.basis === 'yoy').length
        const count = (n) => ['none', 'one', 'two', 'three', 'four'][n] || n
        // The table shows the selected window only (§4.5): when it is narrower than the report, the clause says how
        // many of the quarter-over-quarter changes are in the quarters shown; the report-wide count stays.
        const shownKeys = new Set(windowPeriods(dataset).map((p) => p.key))
        const qoqShown = g.comparisons.filter((x) => x.basis === 'qoq' && shownKeys.has(x.point.period)).length
        const windowClause = qoqShown === qoq ? '' : ` (${count(qoqShown)} in the ${shownKeys.size} quarters shown)`
        // YoY changes are displayed on the headline cards (their latest populated point) and, for revenue, on the
        // growth line of the revenue panel (§4.7); the table shows QoQ (or the labelled YoY fallback) and the
        // exports carry every comparison.
        const onCards = g.comparisons.filter((x) => x.basis === 'yoy' && ['revenue', 'net_income', 'free_cash_flow', 'net_margin'].includes(x.series.concept) && latestPoint(x.series) === x.point).length
        // The chart draws a growth marker only for a numeric YoY ("nm" comparisons have no marker or letter).
        const onChart = g.comparisons.filter((x) => x.basis === 'yoy' && x.series.concept === 'revenue' && typeof x.point.yoy === 'number').length
        // The table shows a YoY change only as the labelled fallback of a cell without a QoQ change (§4.5), within the quarters shown.
        const onTable = g.comparisons.filter((x) => x.basis === 'yoy' && x.point.qoq == null && shownKeys.has(x.point.period)).length
        c.append(`${g.values.length} figure${g.values.length === 1 ? '' : 's'}`, g.comparisons.length ? ` · ${g.comparisons.length} comparison${g.comparisons.length === 1 ? '' : 's'} carry this note: ${qoq} quarter-over-quarter change${qoq === 1 ? '' : 's'} in the table${windowClause} and ${yoy} year-over-year change${yoy === 1 ? '' : 's'}, of which the headline cards show ${count(onCards)}${onTable ? `, the table shows ${count(onTable)} as its labelled fallback` : ''}${onChart ? `, the revenue growth chart shows ${count(onChart)}` : ''} and the exports carry all` : '')
        if (g.reasons.includes('legacy_calculation')) c.append(' · figures are shown as stored; their source lineage is not recorded')
        if (g.reasons.includes('source_conflict')) c.append(' · review the original filing before relying on these figures')
      } else if (g.kind === 'unknown') {
        c.append(`${g.values.length} figure${g.values.length === 1 ? '' : 's'} shown as stored`, g.comparisons.length ? ` · ${g.comparisons.length} comparison${g.comparisons.length === 1 ? '' : 's'} carry this note` : '', ' · no verification claim is made')
      } else {
        c.append(`${g.values.length} figure${g.values.length === 1 ? '' : 's'} shown as — · growth is not computed across a gap`)
      }
      box.append(c)
      li.append(box)
      ol.append(li)
    }
    if (!reviewGroups.length && !unknownGroups.length && !unavailableGroups.length) ol.append(el('li', null, el('span', { class: 'mark' }, '—'), el('div', { class: 'what' }, 'No data notes for this report.')))
    body.append(ol)
    body.append(el('div', { class: 'methods' },
      el('p', null, 'Select any figure to inspect its source filing, reporting period and calculation. † marks a figure EarningsNerd calculated from reported inputs; it is not an error. Growth and ratios are calculated from the same inputs. Automated checks confirm that reported figures come from the company’s SEC XBRL data and that calculations combine compatible periods and units; they are not an audit of the company’s accounts.'),
      el('p', null, 'Quarterly cash flows may be calculated by subtracting earlier year-to-date totals; fourth quarters from annual totals less the first nine months. Earnings per share uses a reported quarterly figure only. Free cash flow is operating cash flow minus cash capital expenditures and may differ from the company’s own measure.'),
      el('p', null, `Source data as of ${dataset.data_as_of ? dataset.data_as_of.slice(0, 10) : 'unknown'} · snapshot ${(dataset.snapshot_id || '').slice(0, 12)}.`),
    ))
    details.append(body)
    return details
  }

  // ---------- charts (plain SVG; the app uses recharts with the same marks) ----------
  const SERIES_COLORS = ['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)', 'var(--chart-5)', 'var(--chart-6)']
  function renderPanel(spec, dataset, notes, by) {
    const periods = dataset.periods.map((p) => p.key)
    const n = periods.length
    const entries = spec.lines.filter(([c]) => by[c]).map(([c, label], i) => ({ concept: c, label, color: SERIES_COLORS[i], right: c === spec.rightAxis }))
    const bar = spec.bar && by[spec.bar[0]] ? by[spec.bar[0]] : null
    if (!bar && !entries.length) return null
    const plotted = bar ? [bar] : entries.map((e) => by[e.concept])
    const noteLetters = new Set()
    // Every note the panel's values carry, unavailable ones included (a gap draws no marker, but its note is still this panel's).
    for (const s of plotted) for (const p of s.points) { const nt = notes.noteFor(p); if (nt) noteLetters.add(nt.letter); if (spec.growthLine && typeof p.yoy === 'number') { const cn = notes.noteForComparison(p, 'yoy'); if (cn) noteLetters.add(cn.letter) } }
    const unavailableNotes = plotted.flatMap((s) => { const miss = periods.filter((k) => (s.points.find((p) => p.period === k) || {}).value == null); if (!miss.length) return []; const letters = [...new Set(miss.map((k) => { const nt = notes.noteFor(s.points.find((p) => p.period === k) || {}); return nt && nt.letter }).filter(Boolean))]; return [`${s.label}: unavailable for ${miss.map(periodLong).join(', ')}${letters.length ? ` (note${letters.length > 1 ? 's' : ''} ${letters.join(', ')})` : ''}.`] })

    const W = Math.max(420, n * 28 + 144), H = 224, padL = 56, padR = (bar && spec.growthLine) || spec.rightAxis ? 56 : 16, padT = 14, padB = 46
    const x = (i) => padL + ((i + 0.5) / n) * (W - padL - padR)
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('width', W); svg.setAttribute('role', 'img')
    svg.setAttribute('aria-label', `${spec.title}: ${plotted.map((s) => s.label).join(', ')} by quarter`)
    const S = (tag, attrs, text) => { const e = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const [k, v] of Object.entries(attrs)) if (v != null) e.setAttribute(k, v); if (text != null) e.textContent = text; svg.append(e); return e }
    const scale = (values, zero) => { let lo = Math.min(...values), hi = Math.max(...values); if (zero) { lo = Math.min(0, lo); hi = Math.max(0, hi) } if (hi === lo) hi = lo + 1; const pad = (hi - lo) * 0.08; lo -= lo < 0 ? pad : 0; hi += pad; return (v) => padT + (1 - (v - lo) / (hi - lo)) * (H - padT - padB) }
    const fmtAxis = spec.format
    // gridlines + left axis
    const leftSeries = bar ? [bar] : entries.filter((e) => !e.right).map((e) => by[e.concept])
    const leftVals = leftSeries.flatMap((s) => s.points.map((p) => p.value).filter((v) => v != null))
    const yL = scale(leftVals, true)
    const ticks = 4
    const lo = Math.min(0, ...leftVals), hi = Math.max(0, ...leftVals)
    for (let t = 0; t <= ticks; t += 1) { const v = lo + ((hi - lo) * t) / ticks; const yy = yL(v); S('line', { x1: padL, x2: W - padR, y1: yy, y2: yy, stroke: 'var(--grid)' }); S('text', { x: padL - 6, y: yy + 4, 'text-anchor': 'end', 'font-size': 11, 'font-family': 'Geist Mono, ui-monospace, monospace', fill: 'var(--axis)' }, fmtAxis(v)) }
    // x ticks (two-line like periodAxis.tsx)
    periods.forEach((k, i) => { const [q, y] = periodShort(k); S('text', { x: x(i), y: H - padB + 16, 'text-anchor': 'middle', 'font-size': 11, 'font-family': 'Geist Mono, ui-monospace, monospace', fill: 'var(--axis)' }, q); S('text', { x: x(i), y: H - padB + 28, 'text-anchor': 'middle', 'font-size': 11, 'font-family': 'Geist Mono, ui-monospace, monospace', fill: 'var(--axis)' }, y) })
    S('text', { x: padL + (W - padL - padR) / 2, y: H - 4, 'text-anchor': 'middle', 'font-size': 11, 'font-family': 'Geist Mono, ui-monospace, monospace', fill: 'var(--axis)' }, 'Fiscal Quarter')
    if (bar) {
      const bw = Math.min(44, ((W - padL - padR) / n) * 0.6)
      bar.points.forEach((p, i) => { if (p.value == null) return; const nt = notes.noteFor(p); const y0 = yL(0), y1 = yL(p.value); S('rect', { x: x(i) - bw / 2, y: Math.min(y0, y1), width: bw, height: Math.abs(y0 - y1), rx: 3, fill: SERIES_COLORS[0] }) ; if (nt) S('text', { x: x(i), y: Math.min(y0, y1) - 4, 'text-anchor': 'middle', 'font-size': 11, 'font-family': 'Geist Mono, ui-monospace, monospace', fill: 'var(--ink-2)' }, nt.letter) })
      if (spec.growthLine) {
        const gv = bar.points.map((p) => (typeof p.yoy === 'number' ? p.yoy * 100 : null))
        const yR = scale(gv.filter((v) => v != null), true)
        const glo = Math.min(0, ...gv.filter((v) => v != null)), ghi = Math.max(0, ...gv.filter((v) => v != null))
        for (let t = 0; t <= ticks; t += 1) { const v = glo + ((ghi - glo) * t) / ticks; S('text', { x: W - padR + 6, y: yR(v) + 4, 'font-size': 11, 'font-family': 'Geist Mono, ui-monospace, monospace', fill: 'var(--axis)' }, `${v.toFixed(0)}%`) }
        // One M opens each run of populated points and a gap closes the pen (the line panels' rule);
        // the first four quarters have no YoY comparison, so the path must not start with repeated moves.
        let d = '', pen = false
        gv.forEach((v, i) => { if (v == null) { pen = false; return } d += `${pen ? ' L' : ' M'}${x(i)} ${yR(v)}`; pen = true })
        S('path', { d: d.trim(), fill: 'none', stroke: SERIES_COLORS[1], 'stroke-width': 2, 'stroke-linejoin': 'round' })
        // An affected growth point is a hollow marker with its note letter above it (§4.7), like an affected value point;
        // the letter can fall over a bar, so it carries a panel-colour halo and stays in label ink on either ground.
        bar.points.forEach((p, i) => { if (typeof p.yoy !== 'number') return; const cn = notes.noteForComparison(p, 'yoy'); const cy = yR(p.yoy * 100); S('circle', { cx: x(i), cy, r: cn ? 4.5 : 3, fill: cn ? 'var(--panel)' : SERIES_COLORS[1], stroke: SERIES_COLORS[1], 'stroke-width': 2 }); if (cn) S('text', { x: x(i), y: cy - 8, 'text-anchor': 'middle', 'font-size': 11, 'font-family': 'Geist Mono, ui-monospace, monospace', fill: 'var(--ink-2)', stroke: 'var(--panel)', 'stroke-width': 3, 'stroke-linejoin': 'round', 'paint-order': 'stroke' }, cn.letter) })
      }
    } else {
      const rightEntry = entries.find((e) => e.right)
      const dual = rightEntry && entries.some((e) => !e.right)
      const rightVals = dual ? by[rightEntry.concept].points.map((p) => p.value).filter((v) => v != null) : []
      const yR = dual ? scale(rightVals, true) : null
      if (dual) { const rlo = Math.min(0, ...rightVals), rhi = Math.max(0, ...rightVals); for (let t = 0; t <= ticks; t += 1) { const v = rlo + ((rhi - rlo) * t) / ticks; S('text', { x: W - padR + 6, y: yR(v) + 4, 'font-size': 11, 'font-family': 'Geist Mono, ui-monospace, monospace', fill: 'var(--axis)' }, fmtAxis(v)) } S('line', { x1: W - padR, x2: W - padR, y1: padT, y2: H - padB, stroke: rightEntry.color, 'stroke-width': 2 }); S('text', { x: W - padR, y: padT - 3, 'text-anchor': 'end', 'font-size': 10, 'font-family': 'Geist Mono, ui-monospace, monospace', fill: rightEntry.color }, rightEntry.label) }
      for (const e of entries) {
        const s = by[e.concept]; const yy = dual && e.right ? yR : yL
        let d = '', pen = false
        s.points.forEach((p, i) => { if (p.value == null) { pen = false; return } d += `${pen ? ' L' : ' M'}${x(i)} ${yy(p.value)}`; pen = true })
        S('path', { d: d.trim(), fill: 'none', stroke: e.color, 'stroke-width': 2, 'stroke-linejoin': 'round' })
        s.points.forEach((p, i) => { if (p.value == null) return; const nt = notes.noteFor(p); if (nt) { S('circle', { cx: x(i), cy: yy(p.value), r: 4.5, fill: 'var(--panel)', stroke: e.color, 'stroke-width': 2 }); S('text', { x: x(i), y: yy(p.value) - 8, 'text-anchor': 'middle', 'font-size': 11, 'font-family': 'Geist Mono, ui-monospace, monospace', fill: 'var(--ink-2)' }, nt.letter) } })
      }
    }
    const legendItems = bar ? [{ label: bar.label, color: SERIES_COLORS[0] }, ...(spec.growthLine ? [{ label: 'YoY growth', color: SERIES_COLORS[1] }] : [])] : entries.map((e) => ({ label: entries.some((x) => x.right) && entries.some((x) => !x.right) ? `${e.label} (${e.right ? 'right' : 'left'})` : e.label, color: e.color }))
    const legend = el('div', { class: 'legend' }, ...legendItems.map((it) => el('span', null, el('i', { style: `background:${it.color}` }), it.label)))
    if (noteLetters.size) legend.append(el('button', { type: 'button', class: 'pchip note notes-ref', onclick: () => openNote([...noteLetters][0]) }, `Notes ${[...noteLetters].join(', ')}`))
    const plot = el('div', { class: 'plot', role: 'region', 'aria-label': `${spec.title} chart.` }, svg)
    const panel = el('section', { class: 'card panel', 'aria-labelledby': `panel-${spec.id}` },
      el('div', { class: 'head' }, el('div', { style: 'min-width:0' }, el('h2', { id: `panel-${spec.id}` }, spec.title), legend), el('div', { class: 'controls' }, el('button', { type: 'button', class: 'btn secondary icon', 'aria-label': 'Download chart as PNG', title: 'Download chart as PNG' }, '▣'), el('button', { type: 'button', class: 'btn secondary icon', 'aria-label': 'Expand chart', 'aria-expanded': 'false' }, '⤢'))),
      plot,
      unavailableNotes.length ? el('p', { class: 'foot' }, unavailableNotes.join(' ')) : null,
    )
    // The plot is a named region that is a Tab stop only while it overflows its panel (§4.7, §5), measured
    // like the table's region: after paint and on every resize.
    const tabStop = () => {
      const scrolls = plot.scrollWidth > plot.clientWidth + 1
      if (scrolls) plot.setAttribute('tabindex', '0'); else plot.removeAttribute('tabindex')
      plot.setAttribute('aria-label', scrolls ? `${spec.title} chart. Scroll horizontally to view all quarters.` : `${spec.title} chart.`)
    }
    requestAnimationFrame(tabStop)
    if (window.ResizeObserver) new ResizeObserver(tabStop).observe(plot)
    return panel
  }
  function renderCharts(dataset, notes) {
    const by = Object.fromEntries(dataset.series.map((s) => [s.concept, s]))
    const money = (v) => fmtMoney(v, 'USD').replace('.0', '')
    const panels = [
      { id: 'rev', title: `${by.revenue ? by.revenue.label : 'Top line'} & growth`, lines: [], bar: ['revenue', 'Revenue'], growthLine: true, format: money },
      { id: 'margins', title: 'Margins', lines: [['gross_margin', 'Gross'], ['operating_margin', 'Operating'], ['net_margin', 'Net']], format: (v) => `${v.toFixed(0)}%` },
      { id: 'cash', title: 'Cash generation', lines: [['operating_cash_flow', 'Operating CF'], ['free_cash_flow', 'Free cash flow'], ['net_income', 'Net income']], rightAxis: 'net_income', format: money },
      { id: 'bs', title: 'Balance sheet', lines: [['long_term_debt', 'Long-term debt'], ['shareholders_equity', 'Equity'], ['cash_and_equivalents', 'Cash']], rightAxis: 'shareholders_equity', format: money },
    ]
    const grid = el('div', { class: 'charts' })
    for (const spec of panels) { const p = renderPanel(spec, dataset, notes, by); if (p) grid.append(p) }
    return grid
  }

  // ---------- narrative (proposed): readable amounts, folded operand evidence ----------
  // Relation-safe compaction (§4.8): the money tokens of a line are shortened together, with decimals added
  // until figures that differ stay visibly different, so "$12.8B was below net income of $12.8B" cannot
  // occur; a ratio within rounding of 1.00× keeps the engine's precision, so "1.0033×, above 1.00×" never
  // becomes "1.00×, above 1.00×". Relations themselves are the engine's, computed on raw values.
  function compactify(text, dataset) {
    const compactMoney = (v, d) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', minimumFractionDigits: d, maximumFractionDigits: d }).format(v)
    const distinct = (values, render) => {
      for (let d = 1; d <= 4; d++) { const out = values.map((v) => render(v, d)); if (new Set(out).size === new Set(values).size) return out }
      return values.map((v) => render(v, 4))
    }
    let out = text.replace(/USD (-?\d[\d,]*(?:\.\d+)?) per share/g, (_, n) => { const v = Number(n.replace(/,/g, '')); return `${v < 0 ? '-' : ''}$${Math.abs(v).toFixed(2)}` })
    const moneyRe = /USD (-?\d[\d,]*)/g
    const moneyValues = [...out.matchAll(moneyRe)].map((m) => Number(m[1].replace(/,/g, '')))
    if (moneyValues.length) { const rendered = distinct(moneyValues, compactMoney); let i = 0; out = out.replace(moneyRe, () => rendered[i++]) }
    const ratioRe = /(\d+\.\d{2,})x\b/g
    const ratioValues = [...out.matchAll(ratioRe)].map((m) => Number(m[1]))
    if (ratioValues.length) {
      const rendered = distinct(ratioValues, (v, d) => `${v.toFixed(Math.max(2, d))}×`)
      let i = 0
      out = out.replace(ratioRe, (_, n) => { const r = rendered[i++]; const v = Number(n); return v !== 1 && Math.abs(v - 1) < 0.005 ? `${n}×` : r })
    }
    return out.replace(/\b(\d{4})(Q[1-4])\b/g, '$2 $1')
  }
  function citeChip(n, citations, notes, dataset) {
    const c = citations.find((x) => x.n === n)
    let note = null
    if (c) { const s = dataset.series.find((x) => x.concept === c.concept); const p = s && s.points.find((x) => x.period === c.period); note = p ? notes.noteFor(p) : null }
    const chip = el('button', { type: 'button', class: 'cite' + (note ? ' flag' : ''), 'aria-label': `Citation ${n}${c ? `: ${c.excerpt}` : ''}${note ? `, data note ${note.letter}` : ''}`, onclick: () => { const row = $(`#src-${n}`); if (row) { const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches; row.scrollIntoView({ block: 'center', behavior: still ? 'auto' : 'smooth' }); row.style.transition = still ? 'none' : 'background 200ms'; row.style.background = 'var(--brand-weak)'; setTimeout(() => { row.style.background = '' }, 1800) } } }, `[${n}]`)
    if (note) chip.append(el('span', { class: 'n-note' }, note.letter))
    return chip
  }
  function inlineWithCites(text, citations, notes, dataset) {
    const frag = document.createDocumentFragment()
    const parts = text.split(/(\[\d+\])/g)
    for (const part of parts) {
      const m = /^\[(\d+)\]$/.exec(part)
      if (m) { frag.append(citeChip(Number(m[1]), citations, notes, dataset)); continue }
      // readable figures in the data face
      const sub = part.split(/(\$-?[\d.]+[KMBT]?|[+-]?\d+\.\d%|[+-]?\d+\.\dpp|\d+\.\d\d×)/g)
      sub.forEach((s, i) => { if (i % 2 === 1) frag.append(el('span', { class: 'fig' }, s)); else if (s) frag.append(s) })
    }
    return frag
  }
  function renderNarrative(stateData, notes) {
    const { dataset, completion } = stateData
    const cites = completion.citations
    const body = el('div', { class: 'markdown-body' })
    const lines = completion.narrative.split('\n')
    let section = ''
    for (const raw of lines) {
      if (!raw.trim()) continue
      if (raw.startsWith('## ')) { section = raw.slice(3); body.append(el('h3', null, section)); continue }
      let line = raw
      let operands = null
      const idx = line.indexOf(' Source operands: ')
      if (idx !== -1) { operands = line.slice(idx + ' Source operands: '.length).replace(/\.$/, ''); line = line.slice(0, idx) }
      line = compactify(line, dataset)
      if (state.mode === 'current') { body.append(el('p', null, inlineWithCites(raw, cites, notes, dataset))); continue }
      const p = el('p', null, inlineWithCites(line, cites, notes, dataset))
      body.append(p)
      if (operands) {
        // The tail's [n] markers name the citations; the rows come from those records (concept, period,
        // value), so negative amounts, annual periods or any other operand text never lose their row.
        const items = [...operands.matchAll(/\[(\d+)\]/g)].map((m) => Number(m[1])).map((n) => {
          const c = cites.find((x) => x.n === n)
          const sr = c && dataset.series.find((x) => x.concept === c.concept)
          const pt = sr && sr.points.find((x) => x.period === c.period)
          return c ? { label: sr ? sr.label : conceptLabel(c.concept), period: c.period, value: pt && sr && pt.value != null ? fmtValue(pt.value, sr) : fmtExact(c.value), n, derived: !!(pt && isCalculated(pt)) } : { label: `[${n}]`, n }
        })
        const table = el('table', null, el('thead', null, el('tr', null, el('th', null, 'Quarter'), el('th', null, 'Figure'), el('th', { style: 'text-align:right' }, 'Value'), el('th', null, 'Source'))))
        const tb = el('tbody')
        for (const it of items) tb.append(el('tr', null, el('td', null, it.period ? periodLong(it.period) + (it.derived ? ' †' : '') : ''), el('td', null, it.label), el('td', { class: 'num' }, it.value || ''), el('td', null, it.n ? citeChip(it.n, cites, notes, dataset) : '')))
        table.append(tb)
        const foldLetters = [...new Set(items.map((it) => { const c = cites.find((x) => x.n === it.n); const sr = c && dataset.series.find((x) => x.concept === c.concept); const pt = sr && sr.points.find((x) => x.period === c.period); const nt = pt && notes.noteFor(pt); return nt ? nt.letter : null }).filter(Boolean))]
        if (items.length <= 3) {
          // Short operand lists stay in the reading line, in display form, with their citation chips.
          p.append(' (', ...items.flatMap((it, i) => [i ? '; ' : '', `${it.label} ${it.value}, ${periodLong(it.period || '')} `, citeChip(it.n, cites, notes, dataset)]), ')')
        } else {
          const foldNote = foldLetters.length ? ` · ${foldLetters.length === 1 ? 'figures carry note' : 'figures carry notes'} ${foldLetters.join(', ')}` : ''
          body.append(el('details', { class: 'evidence' }, el('summary', null, `Show the ${items.length} source figures behind this${foldNote}`), el('div', { class: 'scroll' }, table)))
        }
      }
    }
    const letters = new Set(); for (const c of cites) { const s = dataset.series.find((x) => x.concept === c.concept); const p = s && s.points.find((x) => x.period === c.period); const nt = p && notes.noteFor(p); if (nt) letters.add(nt.letter) }
    const head = el('div', { class: 'head' },
      el('div', { class: 'left' }, el('h2', { id: 'narr-h', tabindex: '-1' }, 'AI trend analysis'), el('span', { class: 'chip quiet' }, `${completion.grounded} sources`), letters.size ? el('button', { type: 'button', class: 'pchip note', onclick: () => openNote([...letters][0]) }, `Notes ${[...letters].join(', ')}`) : null, completion.cached ? el('span', { class: 'chip quiet' }, 'Cached') : null),
      el('div', { style: 'display:flex;gap:.5rem;flex-wrap:wrap' }, el('button', { type: 'button', class: 'btn secondary sm' }, '⤓ Export PDF'), el('button', { type: 'button', class: 'btn secondary sm' }, '↻ Refresh analysis')),
    )
    const sources = el('div', { class: 'sources' }, el('div', { class: 'eyebrow' }, 'Sources · SEC XBRL values and computed figures'))
    const ol = el('ol')
    for (const c of cites) {
      const s = dataset.series.find((x) => x.concept === c.concept); const p = s && s.points.find((x) => x.period === c.period); const nt = p && notes.noteFor(p)
      const li = el('li', { id: `src-${c.n}` }, el('span', { class: 'n' }, c.n), el('span', { class: 't' }, `${s ? s.label : c.concept} · ${periodLong(c.period)} · ${s && p ? fmtValue(p.value, s) : ''} (${fmtExact(c.value)}) `, p && isCalculated(p) ? el('span', { class: 'affix', 'aria-hidden': 'true' }, el('span', { class: 'dag' }, '†')) : null, nt ? el('sup', { class: 'affix', 'aria-hidden': 'true' }, el('span', { class: 'note' + (nt.kind === 'review' ? '' : ' ' + nt.kind) }, nt.letter)) : null, p && isCalculated(p) ? el('span', { class: 'sr-only' }, ', calculated') : null, nt ? el('span', { class: 'sr-only' }, `, data note ${nt.letter}`) : null, ' ', c.source_url ? el('a', { href: c.source_url, target: '_blank', rel: 'noopener noreferrer', 'aria-label': `Original filing for source ${c.n}: ${s ? s.label : c.concept}, ${periodLong(c.period)}` }, 'Original filing') : el('span', { class: 'kind' }, 'calculated from filing figures')))
      ol.append(li)
    }
    sources.append(ol)
    return el('section', { class: 'card card-body narrative', 'aria-labelledby': 'narr-h' }, head, body, sources, el('p', { class: 'disclaimer' }, 'AI-generated. Informational only, not investment advice. Source entries identify SEC XBRL values or computed figures. They do not verify every nearby narrative figure or conclusion. The analysis can be incomplete or wrong.'))
  }

  // ---------- metrics table (proposed) ----------
  function windowPeriods(dataset) {
    const all = dataset.periods
    if (state.window === '6n') return all.slice(-6)
    if (state.window === '6e') return all.slice(0, 6)
    return all
  }
  function renderMetrics(dataset, notes) {
    const periods = windowPeriods(dataset)
    const hasDerived = dataset.series.some((s) => s.points.some((p) => isCalculated(p)))
    const table = el('table', { class: 'metrics', style: `width: max(100%, calc(var(--metric-col) + ${periods.length} * var(--period-col)))` })
    table.append(el('caption', { class: 'sr-only' }, `Metrics by period, ${periods.length} of ${dataset.periods.length} quarters: value and quarter-over-quarter change per metric; a change marked YoY compares with the same quarter a year earlier because the prior quarter is unavailable`))
    const cg = el('colgroup', null, el('col', { class: 'metric' }), ...periods.map(() => el('col', { class: 'period' })))
    table.append(cg)
    const thead = el('thead', null, el('tr', null, el('th', { scope: 'col', class: 'sticky' }, 'Metric', el('span', { class: 'basis' }, 'value · Δ vs prior quarter')), ...periods.map((p) => { const [q, y] = periodShort(p.key); return el('th', { scope: 'col' }, q, el('span', { class: 'yr' }, y, p.fiscal_period === 'Q4' ? ' †' : '')) })))
    table.append(thead)
    const tbody = el('tbody')
    const tableLetters = new Set() // every note a rendered cell or change line carries, whatever its kind
    for (const s of dataset.series) {
      const tr = el('tr')
      tr.append(el('th', { scope: 'row', class: 'sticky' }, s.label))
      for (const per of periods) {
        const p = s.points.find((x) => x.period === per.key)
        const td = el('td')
        if (!p) { td.append(el('span', { class: 'empty' }, '—')); tr.append(td); continue }
        const note = notes.noteFor(p)
        if (note) tableLetters.add(note.letter)
        if (p.value == null) {
          td.append(el('div', { class: 'cell' }, el('span', { class: 'v' }, note ? el('button', { type: 'button', class: 'gap', 'aria-label': nameFor(s, p, note), onclick: () => openEvidence(s, p, notes) }, el('span', { class: 'empty' }, '—'), affix(p, note, { noDagger: true })) : el('span', { class: 'empty' }, '—'))))
          tr.append(td); continue
        }
        // QoQ when the prior quarter exists; otherwise today's labelled YoY fallback (§4.5), never an empty line.
        const basis = p.qoq != null ? 'qoq' : p.yoy != null ? 'yoy' : null
        const d = fmtDelta(basis ? p[basis] : null, s.percent)
        const cmpNote = basis ? notes.noteForComparison(p, basis) : null
        if (cmpNote) tableLetters.add(cmpNote.letter)
        const t = tone(s.tone, d.dir)
        const cell = el('div', { class: 'cell' },
          el('span', { class: 'v' }, el('button', { type: 'button', 'aria-label': nameFor(s, p, note, cmpNote), onclick: () => openEvidence(s, p, notes, basis) }, fmtValue(p.value, s), affix(p, note))),
          d.text ? el('span', { class: 'd ' + t, 'data-basis': basis }, el('span', { class: 'sr-only' }, basis === 'yoy' ? 'change vs same quarter last year ' : 'change vs prior quarter '), basis === 'yoy' ? el('span', { 'aria-hidden': 'true' }, 'YoY ') : '', d.text, cmpNote ? el('sup', { class: 'affix', 'aria-hidden': 'true' }, el('span', { class: 'note' + (cmpNote.kind === 'review' ? '' : ' ' + cmpNote.kind) }, cmpNote.letter)) : null) : el('span', { class: 'd empty', 'aria-hidden': 'true' }, '\u00a0'),
        )
        td.append(cell)
        tr.append(td)
      }
      tbody.append(tr)
    }
    table.append(tbody)
    const phone = window.matchMedia('(max-width: 639px)').matches
    const scroll = el('div', { class: 'metrics-scroll', role: 'region', 'aria-label': `Metrics by period, table of ${periods.length} quarters` }, phone ? el('div', { class: 'hint', 'aria-hidden': 'true' }, '← Earlier quarters') : null, table)
    // The hint says what is off-screen, so it shows only while the table is scrolled away from its start (§4.5).
    const atStart = () => scroll.classList.toggle('at-start', scroll.scrollLeft <= 0)
    scroll.addEventListener('scroll', atStart, { passive: true })
    // Focus reveals the focused value's whole column. The browser scrolls a focused element into view and the
    // mandatory snap then settles on whichever stop is nearest, which can leave the value past the edge or under the
    // sticky labels (Tab at 320 px with 200% text showed 11% of one). So focus picks the stop itself, as the app's
    // DataTable does: the column's own stop when it starts left of the labels' edge, else the first stop that shows
    // its far edge. Unstuck, the label column is a stop of its own and nothing overlays the values.
    scroll.addEventListener('focusin', (e) => {
      const cell = e.target !== scroll && e.target.closest('td')
      if (!cell) return
      const unstuck = scroll.classList.contains('unstuck')
      const view = scroll.getBoundingClientRect(), box = cell.getBoundingClientRect()
      const inset = unstuck ? 0 : table.querySelector('thead th').getBoundingClientRect().width
      const range = scroll.scrollWidth - scroll.clientWidth
      const stopOf = (c) => scroll.scrollLeft + c.getBoundingClientRect().left - view.left - inset
      let to = null
      if (box.left < view.left + inset - 0.5) to = stopOf(cell)
      else if (box.right > view.right + 0.5) {
        const need = scroll.scrollLeft + box.right - view.right
        to = Math.min(range, ...[...cell.parentElement.children].filter((c) => c.tagName === 'TD' || unstuck).map(stopOf).filter((s) => s >= need - 0.5))
      }
      if (to != null) scroll.scrollLeft = Math.max(0, Math.min(to, range))
    })
    // Home/End move the table, never the page; arrows step one column through the mandatory snap.
    scroll.addEventListener('keydown', (e) => { if (e.target !== scroll) return; const range = scroll.scrollWidth - scroll.clientWidth; const col = table.querySelector('tbody td'); const step = col ? col.getBoundingClientRect().width : scroll.clientWidth; const to = e.key === 'Home' ? 0 : e.key === 'End' ? range : e.key === 'ArrowRight' ? scroll.scrollLeft + step : e.key === 'ArrowLeft' ? scroll.scrollLeft - step : null; if (to == null) return; e.preventDefault(); scroll.scrollLeft = Math.max(0, Math.min(to, range)) })
    const legend = el('div', { class: 'legend' }, hasDerived ? el('span', null, el('span', { class: 'affix' }, el('span', { class: 'dag' }, '†')), ' calculated') : null, ...(() => { const letters = notes.list.map((g) => g.letter).filter((l) => tableLetters.has(l)); return letters.length ? [el('button', { type: 'button', class: 'pchip note notes-ref', onclick: () => openNote(letters[0]) }, `Notes ${letters.join(', ')}`)] : [] })())
    const windowCtl = el('div', { class: 'window' }, el('span', { role: 'status' }, periods.length === dataset.periods.length ? `All ${dataset.periods.length} quarters` : `Showing ${periods.length} of ${dataset.periods.length} quarters`), el('div', { class: 'seg', role: 'group', 'aria-label': 'Table window' }, ...[['12', 'All 12'], ['6n', 'Newest 6'], ['6e', 'Earliest 6']].map(([v, l]) => el('button', { type: 'button', 'data-window': v, 'aria-pressed': String(state.window === v), onclick: () => { state.window = v; $('#ctl-window').value = v; render(); const again = document.querySelector(`.window button[data-window="${v}"]`); if (again) again.focus() } }, l))))
    const head = el('div', { class: 'head' }, el('div', { class: 'left' }, el('h2', { id: 'metrics-h' }, 'Metrics by period'), legend), el('div', { style: 'display:flex;gap:.75rem;align-items:center;flex-wrap:wrap' }, windowCtl, el('button', { type: 'button', class: 'btn secondary sm' }, '⬇ Export Excel')))
    const section = el('section', { class: 'card card-body metrics', 'aria-labelledby': 'metrics-h' }, head, scroll)
    // The scroll range is kept to a whole number of columns: an inline-end pad makes the far-right
    // rest position start exactly on a column edge, so the sticky metric column never half-hides a
    // value at either end (mandatory snapping alone lets a scroller rest at its range end).
    const alignScrollRange = () => {
      scroll.style.paddingInlineEnd = '0px'
      const col = table.querySelector('tbody td')
      const colWidth = col ? col.getBoundingClientRect().width : 0
      const range = scroll.scrollWidth - scroll.clientWidth
      if (range <= 1 || !colWidth) { scroll.classList.remove('scrolls'); scroll.removeAttribute('tabindex'); return }
      scroll.setAttribute('tabindex', '0')
      // The metric column sticks only while the scroll area leaves room for one whole period column
      // beside it; otherwise (200% text on a phone) the table scrolls as a whole, labels included.
      const sticky = table.querySelector('thead th')
      const unstick = !!sticky && scroll.clientWidth - sticky.getBoundingClientRect().width < colWidth - 1
      table.classList.toggle('unstick', unstick)
      scroll.classList.toggle('unstuck', unstick)
      const pad = state.noPad ? 0 : (colWidth - (range % colWidth)) % colWidth
      scroll.style.paddingInlineEnd = `${Math.round(pad)}px`
      scroll.classList.add('scrolls')
    }
    requestAnimationFrame(() => { alignScrollRange(); if (phone && scroll.classList.contains('scrolls')) scroll.scrollLeft = scroll.scrollWidth; atStart() })
    if (window.ResizeObserver) new ResizeObserver(alignScrollRange).observe(scroll)
    return section
  }

  // ---------- evidence dialog ----------
  let lastOpener = null
  function comparisonBlock(series, point, notes, basis) {
    const prov = point[basis + '_provenance'] || {}
    const cmpNote = notes.noteForComparison(point, basis)
    const kind = comparisonKindOf(point, basis)
    const d = fmtDelta(point[basis], series.percent)
    const block = el('div', { class: 'block' }, el('h3', null, basis === 'yoy' ? 'Change vs same quarter last year' : 'Change vs prior quarter'))
    const mark = cmpNote ? el('span', { class: 'mark' }, ` · Note ${cmpNote.letter}`) : null
    block.append(el('div', { class: 'figure' }, el('span', { class: 'big' }, d.text || '—')))
    if (point[basis] == null) block.append(el('div', { class: 'status' }, 'Unavailable', mark), el('p', { style: 'margin:.25rem 0 0' }, prov.reasons && prov.reasons.length ? prov.reasons.map(reasonText).join(' ') : 'The comparison period is not in this dataset.'))
    else if (kind === 'review') block.append(el('div', { class: 'status review' }, 'Needs review', mark), el('p', { style: 'margin:.25rem 0 0' }, (cmpNote ? cmpNote.reasons : prov.reasons || []).map(reasonText).join(' ')))
    else if (kind === 'unknown') block.append(el('div', { class: 'status' }, 'No validation record', mark), el('p', { class: 'fine', style: 'margin:.25rem 0 0' }, 'No automated check result is recorded for this change. No verification claim is made.'))
    else block.append(el('div', { class: 'status passed' }, el('span', { class: 'mark' }, '✓'), 'Automated checks passed'), el('p', { class: 'fine', style: 'margin:.25rem 0 0' }, 'Calculated from two figures with compatible periods and units. This is not an audit of the company’s accounts.'))
    // "Carries note a: it uses Operating margin, Q2 2025, which needs review" (§4.6), named from the inputs that did not pass.
    const carriers = (prov.inputs || []).filter((i) => i.validation && i.validation !== 'passed')
    if (cmpNote && carriers.length) {
      const where = carriers.map((i) => `${conceptLabel(i.concept)}, ${periodOfInput(i)}`).join(' and ')
      const verb = kind === 'review' ? (carriers.length === 1 ? 'needs review' : 'need review') : (carriers.length === 1 ? 'has no validation record' : 'have no validation record')
      block.append(el('p', { style: 'margin:.25rem 0 0' }, `Carries note ${cmpNote.letter}: it uses ${where}, which ${verb}.`))
    }
    if (prov.formula) block.append(el('div', { class: 'formula' }, formulaText(prov.formula)))
    if (prov.inputs && prov.inputs.length) block.append(operandList(prov.inputs, 0))
    return block
  }
  // An operand names its period by `period_end`; show it as the quarter the report uses when it is one.
  function periodOfInput(input) {
    if (input.period) return periodLong(input.period)
    const match = current().dataset.series.flatMap((s) => s.points).find((p) => p.period_end && p.period_end === input.period_end)
    return match ? periodLong(match.period) : (input.period_end || 'unknown period')
  }
  function operandList(inputs, depth) {
    const ul = el('ul', { class: depth ? '' : 'operands' })
    for (const op of inputs || []) {
      const prov = op.provenance || {}
      const li = el('li')
      li.append(el('span', { class: 'c' }, conceptLabel(op.concept), prov.method === 'calculated' ? ' †' : ''), el('span', { class: 'v' }, op.value == null ? 'Unavailable' : fmtExact(op.value) + (unitLabel(op.unit) ? ' ' + unitLabel(op.unit) : '')))
      const meta = el('span', { class: 'meta' })
      if (op.period_start || op.period_end) meta.append(el('span', { class: 'data' }, [op.period_start, op.period_end].filter(Boolean).join(' → ')))
      if (prov.formula) meta.append(el('span', null, `= ${formulaText(prov.formula)}`))
      const validation = prov.validation || op.validation
      if (validation) meta.append(el('span', null, validation === 'passed' ? 'checks passed' : validation === 'needs_review' ? 'needs review' : validation === 'unavailable' ? 'unavailable' : 'no validation record'))
      if (op.source_url) meta.append(el('a', { href: op.source_url, target: '_blank', rel: 'noopener noreferrer', 'aria-label': `Open filing for ${conceptLabel(op.concept)}, ${periodOfInput(op)}` }, 'Open filing ↗'))
      if (op.accession) meta.append(el('span', { class: 'data' }, op.accession))
      if (op.raw_tag) meta.append(el('span', { class: 'data' }, op.raw_tag))
      li.append(meta)
      if (prov.inputs && prov.inputs.length) li.append(operandList(prov.inputs, depth + 1))
      ul.append(li)
    }
    return ul
  }
  function openEvidence(series, point, notes, basis) {
    lastOpener = document.activeElement
    const note = notes.noteFor(point)
    const prov = point.provenance || {}
    const calc = isCalculated(point)
    $('#evidence-title').textContent = `${series.label} · ${periodLong(point.period)}`
    const body = $('#evidence-body')
    body.replaceChildren()
    body.append(el('div', { class: 'figure' }, el('span', { class: 'big' }, point.value == null ? 'Unavailable' : fmtValue(point.value, series), affix(point, note)), point.value != null ? el('span', { class: 'exact' }, `as stored: ${fmtExactWithUnit(point.value, series)}`) : null))
    const method = el('div', { class: 'block' }, el('h3', null, 'Method'))
    if (calc) {
      method.append(el('p', { style: 'margin:0 0 .25rem' }, 'Calculated by EarningsNerd from reported inputs.'))
      if (prov.formula) {
        method.append(el('div', { class: 'formula' }, formulaText(prov.formula)))
        const ins = prov.inputs || []
        if (ins.length === 2 && point.value != null && ins[0].value != null && ins[1].value != null) {
          // The formula names its operands ("100 * net_income / revenue"); the stored inputs are not in
          // formula order, so match them by concept and fall back to position only for same-concept
          // period arithmetic ("FY - YTD9").
          const tokens = prov.formula.replace(/abs\(/g, '').replace(/\)/g, '').split(/\s*[-\/*+]\s*/).map((t) => t.trim()).filter((t) => t && !/^\d+(\.\d+)?$/.test(t))
          const byConcept = (name) => ins.find((i) => i.concept === name)
          const [a, b] = tokens.length === 2 && byConcept(tokens[0]) && byConcept(tokens[1]) && tokens[0] !== tokens[1] ? [byConcept(tokens[0]), byConcept(tokens[1])] : ins
          const signed = (v) => (v < 0 ? `(${fmtExact(v)})` : fmtExact(v))
          const expr = prov.formula.includes('/') ? `${signed(a.value)} ÷ ${signed(b.value)}${series.percent ? ' × 100' : ''}` : prov.formula.includes('abs(') ? `${signed(a.value)} − |${fmtExact(b.value)}|` : `${signed(a.value)} − ${signed(b.value)}`
          method.append(el('div', { class: 'formula', style: 'color:var(--ink-3)' }, `${expr} = ${fmtExactWithUnit(point.value, series)}`))
        }
      }
    } else if (prov.method === 'reported') method.append(el('p', { style: 'margin:0' }, 'Reported in the source filing.'))
    else method.append(el('p', { style: 'margin:0' }, 'Source method is not recorded for this saved figure.'))
    body.append(method)
    const checks = el('div', { class: 'block' }, el('h3', null, 'Checks'))
    const noteMark = note ? el('span', { class: 'mark' }, ` · Note ${note.letter}`) : null
    if (point.value == null) checks.append(el('div', { class: 'status' }, 'Unavailable', noteMark), el('p', { style: 'margin:.25rem 0 0' }, note ? note.reasons.map(reasonText).join(' ') : reasonText('not_in_dataset'), ' Changes that need this quarter are not shown.'))
    else if (prov.validation === 'passed') checks.append(el('div', { class: 'status passed' }, el('span', { class: 'mark' }, '✓'), 'Automated checks passed'), el('p', { class: 'fine', style: 'margin:.25rem 0 0' }, calc ? 'Calculated from reported figures with compatible periods and units. This is not an audit of the company’s accounts.' : 'Taken from the company’s XBRL data as filed with the SEC. This is not an audit of the company’s accounts.'))
    // The status follows the notes model's own resolution (kindOf): a record without provenance whose
    // reconciled flag is false needs review, as its affix and its note already say.
    else if (prov.validation === 'needs_review' || kindOf(point) === 'review') checks.append(el('div', { class: 'status review' }, 'Needs review', noteMark), el('p', { style: 'margin:.25rem 0 0' }, (prov.reasons && prov.reasons.length ? prov.reasons : note ? note.reasons : ['source_check_needed']).map(reasonText).join(' ')))
    else if (prov.validation === 'unavailable') checks.append(el('div', { class: 'status review' }, 'Unavailable', noteMark), el('p', { style: 'margin:.25rem 0 0' }, (prov.reasons || []).map(reasonText).join(' ')))
    else checks.append(el('div', { class: 'status' }, 'No validation record', noteMark), el('p', { class: 'fine', style: 'margin:.25rem 0 0' }, 'No automated check result is recorded for this figure. No verification claim is made.'))
    body.append(checks)
    const sources = el('div', { class: 'block' }, el('h3', null, calc ? 'Inputs and source filings' : 'Source filing'))
    if (calc) {
      if (prov.inputs && prov.inputs.length) sources.append(operandList(prov.inputs, 0))
      else sources.append(el('div', { class: 'absent' }, 'Source lineage is not recorded for this saved calculation. The figure is shown as stored. Check the original filing before relying on it.'))
    } else {
      const url = point.source_url || prov.source_url
      const meta = el('span', { class: 'meta', style: 'display:flex;flex-wrap:wrap;gap:.25rem .75rem;font-size:.75rem;color:var(--ink-3)' })
      if (point.period_end) meta.append(el('span', { class: 'data' }, `${point.form || ''} · period ended ${point.period_end}`))
      if (point.raw_tag) meta.append(el('span', { class: 'data' }, point.raw_tag))
      if (point.accession) meta.append(el('span', { class: 'data' }, point.accession))
      sources.append(meta)
      if (url) sources.append(el('p', { style: 'margin:.375rem 0 0' }, el('a', { href: url, target: '_blank', rel: 'noopener noreferrer' }, 'Open original SEC filing ↗')))
    }
    body.append(sources)
    // §4.6 item 5: the displayed change is explained in the figure's own dialog, so a passed figure whose
    // change line shows a letter says which operand carries the note.
    if (basis && (point[basis] != null || point[basis + '_provenance'])) body.append(comparisonBlock(series, point, notes, basis))
    if (series.concept === 'free_cash_flow') body.append(el('p', { class: 'fine' }, 'Free cash flow is operating cash flow minus cash capital expenditures. It excludes finance lease principal payments and may differ from the company’s own free cash flow measure.'))
    body.append(el('p', { class: 'fine' }, 'Source links establish where figures came from. Automated checks do not constitute an audit of the company’s accounts.'))
    const scrim = $('#evidence')
    scrim.dataset.open = 'true'
    $('.dialog', scrim).scrollTop = 0
    $('#evidence-close').focus()
  }
  function closeEvidence() { const scrim = $('#evidence'); if (scrim.dataset.open !== 'true') return; scrim.dataset.open = 'false'; if (lastOpener && lastOpener.focus) lastOpener.focus() }
  $('#evidence-close').addEventListener('click', closeEvidence)
  $('#evidence').addEventListener('click', (e) => { if (e.target === $('#evidence')) closeEvidence() })
  window.addEventListener('keydown', (e) => {
    const scrim = $('#evidence'); if (scrim.dataset.open !== 'true') return
    if (e.key === 'Escape') { e.preventDefault(); closeEvidence() }
    if (e.key === 'Tab') { const f = [...scrim.querySelectorAll('button, a[href], [tabindex="0"]')].filter((x) => x.offsetParent !== null); if (!f.length) return; const i = f.indexOf(document.activeElement); if (e.shiftKey && (i <= 0)) { e.preventDefault(); f[f.length - 1].focus() } else if (!e.shiftKey && i === f.length - 1) { e.preventDefault(); f[0].focus() } }
  }, true)

  // ---------- current-production reproduction (what today's markup does) ----------
  function badge(text) { return el('span', { class: 'badge' }, text) }
  function renderCurrent(stateData, notes) {
    const { dataset } = stateData
    const by = Object.fromEntries(dataset.series.map((s) => [s.concept, s]))
    const wrap = el('div', { class: 'cur', style: 'display:flex;flex-direction:column;gap:1rem' })
    const grid = el('div', { class: 'kpi-grid' })
    for (const concept of ['revenue', 'net_income', 'free_cash_flow', 'net_margin']) {
      const s = by[concept]; const p = latestPoint(s)
      const d = fmtDelta(p.yoy, s.percent)
      grid.append(el('div', { class: 'card kpi-card', 'data-kpi': concept }, el('div', { class: 'label' }, `${s.label} (${p.period})`), el('div', { class: 'value' }, fmtValue(p.value, s)), needsReview(p) ? badge('Source check needed') : null, el('div', { class: 'growth ' + tone(s.tone, d.dir) }, `YoY ${d.text}`, ' ', p.yoy_reconciled === false ? badge('Growth source check needed') : null)))
    }
    wrap.append(grid)
    const issues = notes.reviewValues + notes.reviewComparisons
    wrap.append(el('div', { class: 'card card-body' }, el('details', null, el('summary', { style: 'font-size:.875rem;font-weight:500' }, 'Sources & methods ', el('span', { style: 'font-weight:400;color:var(--ink-2)' }, '· SEC filings · includes calculated figures '), issues ? badge(`${issues} source checks needed`) : null))))
    const table = el('table', { class: 'auto' })
    table.append(el('thead', null, el('tr', null, el('th', null, 'Metric'), ...dataset.periods.map((p) => el('th', null, p.key)))))
    const tb = el('tbody')
    for (const s of dataset.series) {
      const tr = el('tr', null, el('th', null, s.label))
      for (const per of dataset.periods) {
        const p = s.points.find((x) => x.period === per.key)
        const td = el('td')
        if (!p || p.value == null) { td.append(p ? el('button', { type: 'button' }, 'Unavailable', p && p.derived ? '†' : '') : '—'); tr.append(td); continue }
        const d = fmtDelta(p.qoq, s.percent)
        const cell = el('div', { class: 'cell' }, el('span', { class: 'v' }, el('button', { type: 'button' }, fmtValue(p.value, s), p.provenance && p.provenance.method === 'calculated' ? el('span', { style: 'margin-left:2px;color:var(--ink-2)' }, '†') : null), needsReview(p) ? badge('Source check needed') : null), d.text ? el('span', { class: tone(s.tone, d.dir), style: 'font-size:.75rem' }, `QoQ ${d.text}`, p.qoq_reconciled === false ? badge('Growth source check needed') : null) : null)
        td.append(cell); tr.append(td)
      }
      tb.append(tr)
    }
    table.append(tb)
    wrap.append(el('section', { class: 'card card-body' }, el('h2', { style: 'font-size:1.25rem;margin-bottom:1rem' }, 'Metrics by period ', el('span', { class: 'chip quiet' }, '† calculated')), el('div', { class: 'scroll' }, table)))
    wrap.append(renderNarrative(stateData, notes))
    return wrap
  }

  // ---------- render ----------
  function render() {
    const data = current()
    const notes = buildNotes(data.dataset)
    renderPicker($('#picker-root'), data.dataset)
    const results = $('#results')
    results.replaceChildren()
    results.style.display = 'flex'; results.style.flexDirection = 'column'; results.style.gap = '1rem'
    if (state.mode === 'current') { results.append(renderCurrent(data, notes)); report(); return }
    results.append(renderKpis(data.dataset, notes), renderNotes(data.dataset, notes), renderCharts(data.dataset, notes), renderNarrative(data, notes), renderMetrics(data.dataset, notes))
    report()
  }
  function report() {
    requestAnimationFrame(() => {
      const doc = document.documentElement
      const over = doc.scrollWidth - window.innerWidth
      let worst = 0
      for (const card of document.querySelectorAll('.kpi, .kpi-card')) { const cr = card.getBoundingClientRect(); for (const c of card.querySelectorAll('*')) { const b = c.getBoundingClientRect(); if (b.width) worst = Math.max(worst, b.right - cr.right, cr.left - b.left) } }
      const t = document.querySelector('table.metrics, table.auto')
      const sc = t && t.parentElement
      $('#readout').innerHTML = `document ${doc.scrollWidth}px wide (layout viewport ${window.innerWidth}) · page overflow <span class="${over > 0 ? 'bad' : ''}">${Math.max(0, Math.round(over))}px</span> · KPI child overflow <span class="${worst > 0.5 ? 'bad' : ''}">${Math.round(worst)}px</span>${t ? ` · table ${Math.round(t.scrollWidth)}px in ${Math.round(sc.clientWidth)}px` : ''}`
    })
  }
  window.EN_PROTO = { render, state, buildNotes, measure: async (configuredWidth) => {
    // Mobile Chromium widens the layout viewport to overflowing content, so innerWidth cannot detect
    // overflow; the harness passes the configured viewport width and overflow is measured against it.
    const viewportWidth = configuredWidth || window.innerWidth
    const settle = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))
    const doc = document.documentElement
    const r = (x) => x.getBoundingClientRect()
    const EPS = 0.5
    // Text-aware containment: element boxes AND the rendered text itself (a nowrap or clipped text
    // keeps its box while the glyphs spill or are cut), excluding screen-reader-only text.
    const textRects = (root) => {
      const out = []
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        if (!node.nodeValue.trim() || node.parentElement.closest('.sr-only')) continue
        const range = document.createRange(); range.selectNodeContents(node)
        for (const b of range.getClientRects()) if (b.width) out.push({ b, text: node.nodeValue.trim().slice(0, 30) })
      }
      return out
    }
    const worstOutside = (root, box) => {
      let worst = 0, text = ''
      for (const c of root.querySelectorAll('*')) { if (c.closest('.sr-only')) continue; const b = r(c); if (!b.width) continue; const o = Math.max(b.right - box.right, box.left - b.left); if (o > worst) { worst = o; text = (c.textContent || '').trim().slice(0, 30) } }
      for (const { b, text: t } of textRects(root)) { const o = Math.max(b.right - box.right, box.left - b.left); if (o > worst) { worst = o; text = t } }
      for (const c of root.querySelectorAll('*')) { if (c.closest('.sr-only')) continue; const cs = getComputedStyle(c); if (cs.overflow !== 'visible' && (c.scrollWidth > c.clientWidth + 1 || c.scrollHeight > c.clientHeight + 1)) { worst = Math.max(worst, c.scrollWidth - c.clientWidth, c.scrollHeight - c.clientHeight); text = (c.textContent || '').trim().slice(0, 30) } }
      return { worst: Math.round(worst * 10) / 10, text }
    }
    const cards = [...document.querySelectorAll('.kpi, .kpi-card')].map((card) => { const cr = r(card); const w = worstOutside(card, cr); const value = card.querySelector('.value'); return { kpi: card.dataset.kpi, width: Math.round(cr.width), height: Math.round(cr.height), valueTop: value ? Math.round(r(value).top - cr.top) : null, worstOverflowPx: w.worst, worstOverflowText: w.text } })
    const t = document.querySelector('table.metrics, table.auto'); const sc = t && t.parentElement
    let table = null
    if (t) {
      const ths = [...t.querySelectorAll('thead th')]
      const cols = ths.map((th) => Math.round(r(th).width))
      const colWidth = ths.length > 1 ? r(ths[1]).width : 0
      // Both-sided cell clipping: the rendered text of every body cell must sit inside the cell's
      // content box (right-aligned overflow goes to the inline start, which scrollWidth never counts).
      const clipped = []
      for (const td of t.querySelectorAll('tbody td, tbody th')) {
        const cs = getComputedStyle(td); const b = r(td)
        const box = { left: b.left + parseFloat(cs.paddingLeft), right: b.right - parseFloat(cs.paddingRight) }
        const w = worstOutside(td, box)
        if (w.worst > EPS) clipped.push({ text: w.text, by: w.worst })
      }
      // Rest positions: the start, every column boundary (the scroll position at which a period header's left edge
      // meets the sticky column's right edge, clamped to the range) and the far-right end; the table snaps, so these
      // are where it rests. A period header that straddles the sticky column's right edge is an occluded column.
      const snap = sc ? getComputedStyle(sc).scrollSnapType : null
      const occluded = []
      const positions = []
      if (sc && ths.length > 1 && t.scrollWidth > sc.clientWidth + 1) {
        const range = sc.scrollWidth - sc.clientWidth
        sc.scrollLeft = 0
        await settle()
        const edge = r(ths[0]).right
        const sorted = [0, ...ths.slice(1).map((th) => r(th).left - edge), range].map((x) => Math.min(Math.max(x, 0), range)).sort((a, b) => a - b)
        const stops = sorted.filter((x, i) => i === 0 || x - sorted[i - 1] > EPS)
        for (const stop of stops) {
          sc.scrollLeft = stop
          await settle()
          const stickyRight = r(ths[0]).right
          const straddling = ths.slice(1).filter((th) => { const hb = r(th); return hb.left < stickyRight - EPS && hb.right > stickyRight + EPS })
          positions.push({ scrollLeft: Math.round(sc.scrollLeft), straddling: straddling.map((th) => th.textContent.replace(/\s+/g, ' ').trim()) })
          if (straddling.length) occluded.push({ scrollLeft: Math.round(sc.scrollLeft), columns: straddling.map((th) => th.textContent.replace(/\s+/g, ' ').trim()) })
        }
        sc.scrollLeft = 0
        await settle()
      }
      const stickyWidth = r(ths[0]).width
      const unstuck = t.classList.contains('unstick')
      table = { rows: t.querySelectorAll('tbody tr').length, tableWidth: Math.round(t.scrollWidth), containerWidth: Math.round(sc.clientWidth), scrolls: t.scrollWidth > sc.clientWidth + 1, columns: cols, minColumn: Math.min(...cols.slice(1)), maxColumn: Math.max(...cols.slice(1)), stickyWidth: Math.round(stickyWidth), stickyColumn: !unstuck, readableColumns: colWidth ? Math.floor((sc.clientWidth - (unstuck ? 0 : stickyWidth)) / colWidth) : null, snap, restPositions: positions.length, occludedPositions: occluded, occludedAtFarRight: occluded.filter((o) => o.scrollLeft >= (sc.scrollWidth - sc.clientWidth) - 1), cellTextClipped: clipped.length > 0, clippedCells: clipped.slice(0, 8), clippedCount: clipped.length }
    }
    const labels = [...document.querySelectorAll('.badge')].filter((b) => /source check/i.test(b.textContent)).length
    const affixes = document.querySelectorAll('.affix .note').length
    const fonts = ['Inter', 'Geist Mono'].map((f) => `${f}:${document.fonts.check(`12px "${f}"`)}`)
    return { viewport: viewportWidth, layoutViewport: window.innerWidth, documentWidth: doc.scrollWidth, pageOverflowPx: doc.scrollWidth - viewportWidth, kpi: cards, table, sourceCheckLabels: labels, noteAffixes: affixes, notes: $('#data-notes') ? $('#data-notes summary').textContent.replace(/\s+/g, ' ').trim() : null, env: { userAgent: navigator.userAgent, fonts } }
  } }

  // controls
  $('#ctl-state').addEventListener('change', (e) => { state.stateName = e.target.value; render() })
  $('#ctl-mode').addEventListener('change', (e) => { state.mode = e.target.value; render() })
  $('#ctl-window').addEventListener('change', (e) => { state.window = e.target.value; render() })
  $('#ctl-theme').addEventListener('click', () => { const dark = document.documentElement.classList.toggle('dark'); $('#ctl-theme').textContent = `Theme: ${dark ? 'dark' : 'light'}`; try { localStorage.setItem('proto-theme', dark ? 'dark' : 'light') } catch (e) {} })
  $('#ctl-text').addEventListener('click', () => { state.text = state.text === 1 ? 2 : 1; document.documentElement.style.fontSize = `${state.text * 100}%`; $('#ctl-text').textContent = `Text: ${state.text * 100}%`; render() })
  if (document.documentElement.classList.contains('dark')) $('#ctl-theme').textContent = 'Theme: dark'
  window.addEventListener('resize', report)
  render()
})()
