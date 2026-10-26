'use client'

import { useRef, type RefObject } from 'react'
import { Button } from '@/components/ui'
import { secondaryUnavailableClass } from '@/components/ui/Button'
import type { FeedbackFile } from '../hooks/useFeedbackDraft'

interface Props {
  files: readonly FeedbackFile[]
  locked: boolean
  canAdd: boolean
  onAdd: (files: readonly File[]) => void
  onRemove: (id: string) => void
  messageRef: RefObject<HTMLTextAreaElement | null>
}

export default function FeedbackFilePicker({ files, locked, canAdd, onAdd, onRemove, messageRef }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const addRef = useRef<HTMLButtonElement>(null)
  return (
    <div className="space-y-3">
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        multiple
        tabIndex={-1}
        aria-label="Screenshot files"
        className="hidden"
        onChange={(event) => {
          if (!locked && canAdd) onAdd(Array.from(event.target.files ?? []))
          event.target.value = ''
        }}
      />
      <Button
        ref={addRef}
        type="button"
        variant="secondary"
        wrap
        aria-disabled={locked || !canAdd || files.length >= 3 || undefined}
        aria-describedby="feedback-screenshot-help"
        className={secondaryUnavailableClass}
        onClick={() => { if (!locked && canAdd && files.length < 3) inputRef.current?.click() }}
      >Add screenshots</Button>
      <p id="feedback-screenshot-help" className="text-xs text-text-secondary-light dark:text-text-secondary-dark">
        Select or paste up to 3 PNG, JPEG or static WebP images, 5 MiB each. Crop out personal information you do not want to share.
      </p>
      {files.length > 0 && (
        <ul className="space-y-3" aria-label="Selected screenshots">
          {files.map(({ id, file, preview }, index) => (
            <li key={id} className="min-w-0 space-y-2 rounded-lg border border-border-light p-3 dark:border-white/10">
              {/* These local blobs are never passed to the public Next image optimizer. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={preview} alt={`Selected screenshot ${index + 1}`} className="h-28 w-full rounded object-contain" />
              <p className="break-words text-sm text-text-primary-light [overflow-wrap:anywhere] dark:text-text-primary-dark">{file.name}</p>
              <p className="text-xs text-text-secondary-light dark:text-text-secondary-dark">{(file.size / 1024 / 1024).toFixed(2)} MiB</p>
              <Button type="button" variant="secondary" size="sm" wrap aria-label={`Remove screenshot ${index + 1}`} aria-disabled={locked || undefined} className={secondaryUnavailableClass} onClick={() => {
                if (locked) return
                // Removing this control must hand its keyboard focus to a control that remains.
                ;(addRef.current ?? messageRef.current)?.focus()
                onRemove(id)
              }}>Remove screenshot</Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
