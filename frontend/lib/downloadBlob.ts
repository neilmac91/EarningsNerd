/**
 * Trigger a browser download for an in-memory Blob.
 *
 * Extracted from the filing page's inline export handlers so the DOM plumbing
 * (object URL + synthetic anchor click + cleanup) lives in one place and the
 * feature code only deals with the Blob + filename.
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  // Revoke + remove on a short delay: some browsers (Safari, Firefox) process the download
  // asynchronously, and revoking the object URL synchronously can abort it / yield an empty file.
  setTimeout(() => {
    window.URL.revokeObjectURL(url)
    document.body.removeChild(anchor)
  }, 100)
}
