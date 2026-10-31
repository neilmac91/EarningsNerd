import path from 'node:path'

/**
 * The modules an icon comes from: `@/lib/icons` (the app's one client boundary for Phosphor, by its alias or a
 * path relative to the importing file) and the Phosphor package at any entry (`@phosphor-icons/react`, its `ssr`
 * and `dist/…` subpaths, a per-icon path). Shared by the gates that read an icon by where it is imported from
 * rather than by its local name: reservedGlyphs.spec.ts (the three reserved glyphs) and brandVoiceRules.spec.ts
 * (no icon inside a heading). An icon re-exported through another app module is outside both gates' reach.
 */
export const PHOSPHOR = '@phosphor-icons/react'

/** Whether an import draws from the icon modules. `fileName` is the importing file, relative to the frontend root. */
export function isIconModule(specifier: string, fileName: string): boolean {
  if (specifier === PHOSPHOR || specifier.startsWith(`${PHOSPHOR}/`)) return true
  const target = specifier.startsWith('@/')
    ? specifier.slice(2)
    : specifier.startsWith('.')
      ? path.posix.normalize(path.posix.join(path.posix.dirname(fileName), specifier))
      : specifier
  return target.replace(/\.tsx?$/, '').replace(/\/index$/, '') === 'lib/icons'
}
