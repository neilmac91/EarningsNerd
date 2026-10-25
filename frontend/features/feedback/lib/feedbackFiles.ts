export const MAX_FEEDBACK_FILES = 3
export const MAX_FEEDBACK_FILE_BYTES = 5 * 1024 * 1024
export const FEEDBACK_FILE_TYPES = ['image/png', 'image/jpeg', 'image/webp'] as const

/** Cheap admission only. The API checks actual image bytes, animation, dimensions and metadata. */
export function feedbackFileError(files: readonly File[], existingCount: number): string | null {
  if (files.length + existingCount > MAX_FEEDBACK_FILES) return 'Add up to 3 screenshots per report.'
  if (files.some((file) => !(FEEDBACK_FILE_TYPES as readonly string[]).includes(file.type))) {
    return 'Choose PNG, JPEG or static WebP screenshots.'
  }
  if (files.some((file) => file.size === 0 || file.size > MAX_FEEDBACK_FILE_BYTES)) {
    return 'Each screenshot must be between 1 byte and 5 MiB. Crop a larger image before adding it.'
  }
  return null
}

const PENDING_KEY = 'en_feedback_pending'
export interface PendingFeedbackMarker { owner: number; key: string }

/** Only opaque receipt identity is persisted; message text, filenames and bytes stay in memory. */
export function readPendingFeedback(owner: number): PendingFeedbackMarker | null {
  try {
    const raw: unknown = JSON.parse(sessionStorage.getItem(PENDING_KEY) ?? 'null')
    if (raw && typeof raw === 'object' && 'owner' in raw && 'key' in raw
      && raw.owner === owner && typeof raw.key === 'string'
      && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(raw.key)) {
      return { owner, key: raw.key }
    }
    sessionStorage.removeItem(PENDING_KEY)
  } catch { /* Browser storage can be disabled; the in-memory draft still works. */ }
  return null
}

export function storePendingFeedback(marker: PendingFeedbackMarker): void {
  try { sessionStorage.setItem(PENDING_KEY, JSON.stringify(marker)) } catch { /* In-memory recovery remains available. */ }
}

export function clearPendingFeedback(owner?: number): void {
  try {
    const marker = JSON.parse(sessionStorage.getItem(PENDING_KEY) ?? 'null') as PendingFeedbackMarker | null
    if (owner === undefined || marker?.owner === owner) sessionStorage.removeItem(PENDING_KEY)
  } catch { /* Nothing sensitive was persisted. */ }
}
