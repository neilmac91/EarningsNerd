import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Filing } from '@/features/filings/api/filings-api'
import type { FilingContent } from '@/features/filings/api/filing-content-api'

const api = vi.hoisted(() => ({
  filings: [] as number[], contents: [] as [number, boolean | undefined][], downloads: [] as [Blob, string][],
  filing: (_id: number): Promise<Filing> => Promise.reject(new Error('Unexpected filing')),
  content: (_id: number): Promise<FilingContent> => Promise.reject(new Error('Unexpected text')),
}))
vi.mock('@/features/filings/api/filings-api', () => ({ getFiling: (id: number) => { api.filings.push(id); return api.filing(id) } }))
vi.mock('@/features/filings/api/filing-content-api', () => ({ fetchFilingContent: (id: number, strict?: boolean) => { api.contents.push([id, strict]); return api.content(id) } }))
vi.mock('@/lib/downloadBlob', () => ({ downloadBlob: (blob: Blob, name: string) => { api.downloads.push([blob, name]) } }))
import ResearchEvidencePacks from '@/features/research-evidence-packs/components/ResearchEvidencePacks'

function filing(id: number): Filing {
  return { id, filing_type: '10-K', filing_date: `${2024 + id}-02-10T00:00:00+00:00`, report_date: `${2023 + id}-12-31T00:00:00.123456Z`, accession_number: `0000000123-2${4 + id}-000001`, document_url: `https://www.sec.gov/Archives/edgar/data/123/00000001232${4 + id}000001/original.htm`, sec_url: '', company: { id: 123, name: 'Example Industries', ticker: 'TEST' } }
}
const content = (id: number): FilingContent => ({ filingId: id, hasContent: true, markdownContent: `First paragraph ${id}.\n\nSelected paragraph ${id}.` })
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((done) => { resolve = done }); return { promise, resolve } }
function load(id = '1') {
  fireEvent.change(screen.getByLabelText('Filing ID'), { target: { value: id } })
  fireEvent.submit(screen.getByRole('button', { name: 'Load cached filing' }).closest('form')!)
}
beforeEach(() => { api.filings = []; api.contents = []; api.downloads = []; api.filing = async (id) => filing(id); api.content = async (id) => content(id) })
afterEach(cleanup)

describe('research evidence pack workflow', () => {
  it('starts with labelled fiction, performs explicit source revision and reopens edited interpretation', () => {
    render(<ResearchEvidencePacks />)
    expect(screen.getByRole('status')).toHaveTextContent('Invented excerpts')
    expect(api.filings).toEqual([])
    const card = within(screen.getByRole('article', { name: 'Evidence 1' }))
    fireEvent.click(card.getByRole('button', { name: 'Compare selected source' }))
    expect(card.getByText('Review needed')).toBeInTheDocument()
    expect(card.getByRole('heading', { name: 'Current source · revision 1' })).toBeInTheDocument()
    fireEvent.click(card.getByRole('button', { name: 'Accept new revision' }))
    expect(card.getByRole('alert')).toHaveTextContent('Add a review note')
    fireEvent.change(card.getByLabelText('Review note for evidence 1'), { target: { value: 'Reassessed concentration against the later filing.' } })
    const accept = card.getByRole('button', { name: 'Accept new revision' }); accept.focus(); fireEvent.click(accept)
    expect(card.getByRole('heading', { name: 'Evidence 1' })).toHaveFocus()
    expect(card.getByRole('heading', { name: 'Current source · revision 2' })).toBeInTheDocument()
    expect(card.getByText('Preserved source revision 1')).toBeInTheDocument()
    expect(card.getByText('User reviewed')).toBeInTheDocument()
    fireEvent.change(card.getByLabelText('My interpretation for evidence 1'), { target: { value: 'A changed interpretation.' } })
    expect(card.getByText('Unreviewed')).toBeInTheDocument()
    expect(card.getByText(/Interpretation then: Customer concentration/)).toBeInTheDocument()
  })

  it('captures only the selected paragraph with its exact metadata and explicitly keeps historical evidence', async () => {
    render(<ResearchEvidencePacks />)
    fireEvent.click(screen.getByRole('button', { name: 'Cached filings' })); load()
    await screen.findByText('First paragraph 1.')
    expect(api.contents).toEqual([[1, true]])
    fireEvent.change(screen.getByLabelText('Cached paragraph'), { target: { value: '1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save as new evidence' }))
    const card = within(screen.getByRole('article', { name: 'Evidence 1' }))
    expect(card.getByText('Selected paragraph 1.')).toBeInTheDocument()
    expect(card.getByRole('link', { name: 'Open SEC original ↗' })).toHaveAttribute('href', filing(1).document_url)
    expect(card.queryByText('First paragraph 1.')).not.toBeInTheDocument()
    load('2'); await screen.findByText('First paragraph 2.')
    fireEvent.click(card.getByRole('button', { name: 'Compare selected source' }))
    fireEvent.change(card.getByLabelText('Review note for evidence 1'), { target: { value: 'Retain as dated historical context.' } })
    fireEvent.click(card.getByRole('button', { name: 'Keep prior source' }))
    expect(card.getByRole('heading', { name: 'Current source · revision 1' })).toBeInTheDocument()
    expect(card.getByText('Selected paragraph 1.')).toBeInTheDocument()
    expect(card.getByText('Retain as dated historical context.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Export JSON' }))
    expect(api.downloads[0][1]).toBe('research-evidence-pack.json')
    expect(api.downloads[0][0].size).toBeGreaterThan(0)
  })

  it.each(['', '0', '1.5', '2e1'])('rejects invalid ID %j before API use', (value) => {
    render(<ResearchEvidencePacks />); fireEvent.click(screen.getByRole('button', { name: 'Cached filings' })); load(value)
    expect(screen.getByRole('alert')).toHaveTextContent('positive filing ID')
    expect(api.filings).toEqual([])
  })
  it('rejects invalid metadata before loading content', async () => {
    api.filing = async (id) => ({ ...filing(id), document_url: 'https://evil.test/source' })
    render(<ResearchEvidencePacks />); fireEvent.click(screen.getByRole('button', { name: 'Cached filings' })); load()
    expect(await screen.findByRole('alert')).toHaveTextContent('SEC original')
    expect(api.contents).toEqual([])
  })
  it.each([false, true])('abstains from capture on absent cache or mismatched response (missing=%j)', async (missing) => {
    api.content = async (id) => missing ? { filingId: id, hasContent: false, markdownContent: null } : { ...content(id), filingId: 99 }
    render(<ResearchEvidencePacks />); fireEvent.click(screen.getByRole('button', { name: 'Cached filings' })); load()
    await screen.findByRole('alert')
    expect(screen.queryByRole('button', { name: 'Save as new evidence' })).not.toBeInTheDocument()
    expect(screen.getByText(/Your evidence pack is empty/)).toBeInTheDocument()
  })
  it('keeps API and excerpt HTML inert in the UI', async () => {
    const quote = '<script>document.title="changed"</script><img src=x onerror=alert(1)>'
    api.content = async (id) => ({ ...content(id), markdownContent: quote })
    const { container } = render(<ResearchEvidencePacks />); fireEvent.click(screen.getByRole('button', { name: 'Cached filings' })); load()
    expect(await screen.findByText(quote)).toBeInTheDocument()
    expect(container.querySelector('script,img')).toBeNull()
  })
  it('guards duplicate submissions synchronously and ignores a late response after mode change', async () => {
    const pending = deferred<Filing>(); api.filing = () => pending.promise
    render(<ResearchEvidencePacks />); fireEvent.click(screen.getByRole('button', { name: 'Cached filings' }))
    fireEvent.change(screen.getByLabelText('Filing ID'), { target: { value: '1' } })
    const button = screen.getByRole('button', { name: 'Load cached filing' }); button.focus()
    act(() => { fireEvent.submit(button.closest('form')!); fireEvent.submit(button.closest('form')!) })
    expect(api.filings).toEqual([1]); expect(button).toHaveFocus()
    fireEvent.click(screen.getByRole('button', { name: 'Fictional example' }))
    await act(async () => pending.resolve(filing(1)))
    expect(api.contents).toEqual([])
    expect(screen.queryByText('First paragraph 1.')).not.toBeInTheDocument()
  })
  it('invalidates already-loading content on input edit while preserving existing evidence', async () => {
    const pending = deferred<FilingContent>(); api.content = () => pending.promise
    render(<ResearchEvidencePacks />); fireEvent.click(screen.getByRole('button', { name: 'Cached filings' })); load()
    await waitFor(() => expect(api.contents).toEqual([[1, true]]))
    fireEvent.change(screen.getByLabelText('Filing ID'), { target: { value: '2' } })
    await act(async () => pending.resolve(content(1)))
    expect(screen.queryByRole('button', { name: 'Save as new evidence' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Filing ID')).toHaveValue('2')
  })
})
