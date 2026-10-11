import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Filing } from '@/features/filings/api/filings-api'
import type { FilingContent } from '@/features/filings/api/filing-content-api'

// Plain implementations preserve handled rejection behavior under this repository's Vitest.
const api = vi.hoisted(() => ({
  filings: [] as number[],
  contents: [] as number[],
  filing: (_id: number): Promise<Filing> => Promise.reject(new Error('Unexpected filing request')),
  content: (_id: number): Promise<FilingContent> => Promise.reject(new Error('Unexpected content request')),
}))
vi.mock('@/features/filings/api/filings-api', () => ({
  getFiling: (id: number) => { api.filings.push(id); return api.filing(id) },
}))
vi.mock('@/features/filings/api/filing-content-api', () => ({
  fetchFilingContent: (id: number) => { api.contents.push(id); return api.content(id) },
}))

import FilingRedlines from '@/features/filing-redlines/components/FilingRedlines'

function filing(id: number): Filing {
  const earlier = id === 1
  return {
    id, filing_type: '10-K', filing_date: earlier ? '2025-02-10' : '2026-02-10',
    report_date: earlier ? '2024-12-31' : '2025-12-31',
    accession_number: `0000000123-${earlier ? '25' : '26'}-000001`,
    document_url: `https://www.sec.gov/Archives/edgar/data/123/${id}/original.htm`,
    sec_url: `https://www.sec.gov/Archives/edgar/data/123/${id}/`,
    company: { id: 123, ticker: 'TEST', name: 'Test Manufacturer' },
  }
}

function content(id: number, text = id === 1 ? 'Earlier disclosure.' : 'Later disclosure.'): FilingContent {
  return { filingId: id, hasContent: true, markdownContent: text }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

function selectCached() {
  fireEvent.click(screen.getByRole('button', { name: 'Cached filings' }))
  fireEvent.change(screen.getByLabelText('Earlier filing ID'), { target: { value: '1' } })
  fireEvent.change(screen.getByLabelText('Later filing ID'), { target: { value: '2' } })
}

function submit() {
  fireEvent.submit(screen.getByRole('button', { name: 'Compare cached text' }).closest('form')!)
}

beforeEach(() => {
  api.filings = []
  api.contents = []
  api.filing = async (id) => filing(id)
  api.content = async (id) => content(id)
})
afterEach(cleanup)

describe('filing redlines prototype', () => {
  it('starts with a labelled fictional example without reading the API', () => {
    render(<FilingRedlines />)
    expect(screen.getByRole('heading', { name: 'Fictional example comparison' })).toBeInTheDocument()
    expect(screen.getByText(/invented excerpts from a fictional company/)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /original/ })).not.toBeInTheDocument()
    expect(api.filings).toEqual([])
    expect(api.contents).toEqual([])
  })

  it('compares real cached text with metadata and links from the same returned pair', async () => {
    render(<FilingRedlines />)
    selectCached()
    submit()
    expect(await screen.findByText('Later disclosure.')).toBeInTheDocument()
    expect(screen.getByText('Earlier disclosure.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open earlier original ↗' })).toHaveAttribute('href', filing(1).document_url)
    expect(screen.getByRole('link', { name: 'Open later original ↗' })).toHaveAttribute('href', filing(2).document_url)
    expect(screen.getByText(filing(2).accession_number)).toBeInTheDocument()
    expect(screen.getByText(/full-filing coverage has not been verified/)).toBeInTheDocument()
    expect(api.contents).toEqual([1, 2])
  })

  it.each(['', '0', '-1', '1.5', '2e1', '9007199254740992', '2'])('rejects invalid or duplicate earlier ID %j before reading the API', (value) => {
    render(<FilingRedlines />)
    selectCached()
    fireEvent.change(screen.getByLabelText('Earlier filing ID'), { target: { value } })
    submit()
    expect(screen.getByRole('alert')).toHaveTextContent('Enter two distinct positive filing IDs')
    expect(api.filings).toEqual([])
  })

  it.each(['T00:00:00+00:00', 'T00:00:00Z', 'T00:00:00.123456', 'T00:00:00-08:00', 'T00:00:00+09:00'])('accepts API timestamps and retains the stated calendar day (%s)', async (suffix) => {
    api.filing = async (id) => ({ ...filing(id), report_date: filing(id).report_date + suffix, filing_date: filing(id).filing_date + suffix })
    render(<FilingRedlines />)
    selectCached()
    submit()
    await screen.findByText('Later disclosure.')
    expect(screen.getByText(/Period ended 2025-12-31 · Filed 2026-02-10/)).toBeInTheDocument()
  })

  it.each([
    ['another company', { company: { id: 999, name: 'Another company', ticker: 'OTHER' } }],
    ['no company identity', { company: undefined }],
    ['an amendment', { filing_type: '10-K/A' }],
    ['a quarterly report', { filing_type: '10-Q' }],
    ['the wrong ID', { id: 99 }],
    ['a duplicate accession', { accession_number: filing(1).accession_number }],
    ['a missing accession', { accession_number: '' }],
    ['an earlier reporting period', { report_date: '2023-12-31' }],
    ['an equal reporting period', { report_date: '2024-12-31' }],
    ['an impossible date', { report_date: '2025-02-30' }],
    ['an impossible timestamp date', { report_date: '2025-02-30T00:00:00+00:00' }],
    ['a malformed time', { report_date: '2025-12-31T00:99:00Z' }],
    ['a malformed offset', { report_date: '2025-12-31T00:00:00+25:00' }],
    ['a reversed timestamp period', { report_date: '2023-12-31T00:00:00+00:00' }],
    ['an earlier filing date', { filing_date: '2024-02-10' }],
  ] satisfies [string, Partial<Filing>][])('rejects %s before requesting content', async (_description, patch) => {
    api.filing = async (id) => id === 2 ? { ...filing(id), ...patch } : filing(id)
    render(<FilingRedlines />)
    selectCached()
    submit()
    expect(await screen.findByRole('alert')).toHaveTextContent('Comparison unavailable')
    expect(api.contents).toEqual([])
    expect(screen.queryByText('Later disclosure.')).not.toBeInTheDocument()
  })

  it.each([null, '', '  \n  '])('reports missing or empty cached text as unavailable (%j)', async (text) => {
    api.content = async (id) => ({ filingId: id, hasContent: text !== null, markdownContent: text })
    render(<FilingRedlines />)
    selectCached()
    submit()
    expect(await screen.findByRole('alert')).toHaveTextContent('Cached text is unavailable')
    expect(screen.getByRole('link', { name: 'Open later original ↗' })).toBeInTheDocument()
    expect(screen.queryByText(/No paragraph changes/)).not.toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'Added in the later text paragraphs' })).not.toBeInTheDocument()
  })

  it('refuses text returned for a different filing', async () => {
    api.content = async (id) => ({ ...content(id), filingId: 999 })
    render(<FilingRedlines />)
    selectCached()
    submit()
    expect(await screen.findByRole('alert')).toHaveTextContent('returned text does not match')
    expect(screen.queryByText('Later disclosure.')).not.toBeInTheDocument()
  })

  it('abstains when either input exceeds the helper bounds', async () => {
    api.content = async (id) => content(id, id === 2 ? 'x'.repeat(120_001) : 'Earlier text.')
    render(<FilingRedlines />)
    selectCached()
    submit()
    expect(await screen.findByRole('alert')).toHaveTextContent('Comparison unavailable')
    expect(screen.queryByText(/No paragraph changes/)).not.toBeInTheDocument()
  })

  it('handles a failed read without inventing a comparison', async () => {
    api.filing = () => Promise.reject(new Error('Local API unavailable'))
    render(<FilingRedlines />)
    selectCached()
    submit()
    expect(await screen.findByRole('alert')).toHaveTextContent('Local API unavailable')
    expect(api.contents).toEqual([])
  })

  it('renders filing markup as inert exact text', async () => {
    const untrusted = '<img src=x onerror="alert(1)"><script>document.title="changed"</script>'
    api.content = async (id) => content(id, id === 2 ? untrusted : 'Earlier text.')
    const { container } = render(<FilingRedlines />)
    selectCached()
    submit()
    expect(await screen.findByText(untrusted)).toHaveTextContent(untrusted)
    expect(container.querySelector('img,script')).toBeNull()
  })

  it('prevents duplicate form submissions synchronously and keeps the submit mounted', async () => {
    const pending = deferred<Filing>()
    api.filing = (id) => id === 1 ? pending.promise : Promise.resolve(filing(id))
    render(<FilingRedlines />)
    selectCached()
    const button = screen.getByRole('button', { name: 'Compare cached text' })
    const form = button.closest('form')!
    button.focus()
    act(() => { fireEvent.submit(form); fireEvent.submit(form) })
    expect(api.filings).toEqual([1, 2])
    expect(button).toHaveFocus()
    await act(async () => pending.resolve(filing(1)))
    expect(await screen.findByText('Later disclosure.')).toBeInTheDocument()
    expect(button).toHaveFocus()
  })

  it('switching to the fictional example invalidates an in-flight metadata request', async () => {
    const pending = deferred<Filing>()
    api.filing = (id) => id === 1 ? pending.promise : Promise.resolve(filing(id))
    render(<FilingRedlines />)
    selectCached()
    submit()
    fireEvent.click(screen.getByRole('button', { name: 'Fictional example' }))
    await act(async () => pending.resolve(filing(1)))
    expect(screen.getByRole('heading', { name: 'Fictional example comparison' })).toBeInTheDocument()
    expect(api.contents).toEqual([])
    expect(screen.queryByText('Later disclosure.')).not.toBeInTheDocument()
  })

  it('editing the selection invalidates in-flight content and permits a new comparison', async () => {
    const oldContent = deferred<FilingContent>()
    api.content = (id) => id === 2 ? oldContent.promise : Promise.resolve(content(id))
    render(<FilingRedlines />)
    selectCached()
    submit()
    await waitFor(() => expect(api.contents).toEqual([1, 2]))
    fireEvent.change(screen.getByLabelText('Later filing ID'), { target: { value: '3' } })
    api.content = async (id) => content(id, id === 3 ? 'The newly selected filing.' : 'Earlier disclosure.')
    submit()
    expect(await screen.findByText('The newly selected filing.')).toBeInTheDocument()
    await act(async () => oldContent.resolve(content(2, 'Stale content.')))
    const added = screen.getByRole('region', { name: 'Added in the later text' })
    expect(within(added).getByText('The newly selected filing.')).toBeInTheDocument()
    expect(screen.queryByText('Stale content.')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open later original ↗' })).toHaveAttribute('href', filing(3).document_url)
  })

  it('editing either ID clears previously displayed results and source links', async () => {
    render(<FilingRedlines />)
    selectCached()
    submit()
    await screen.findByText('Later disclosure.')
    fireEvent.change(screen.getByLabelText('Earlier filing ID'), { target: { value: '4' } })
    expect(screen.queryByText('Later disclosure.')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /original/ })).not.toBeInTheDocument()
  })
})
