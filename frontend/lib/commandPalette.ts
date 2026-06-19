// Shared contract for opening the global command palette without coupling the
// trigger (e.g. the header button) to the palette component itself.
export const OPEN_COMMAND_PALETTE_EVENT = 'open-command-palette'

export function openCommandPalette() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(OPEN_COMMAND_PALETTE_EVENT))
  }
}
