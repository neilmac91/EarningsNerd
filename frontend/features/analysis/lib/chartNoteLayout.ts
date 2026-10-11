export interface ChartNoteAnchor {
  key: string
  x: number
  y: number
  letter: string | null
}

export interface ChartNoteBounds { x: number; y: number; width: number; height: number }
export interface ChartNotePosition { x: number; y: number }

// Conservative glyph bounds for the existing 11px data face, including its PNG font fallback.
// Coordinates describe the text baseline. Dot coordinates are never changed by this layout.
const ASCENT = 12
const DESCENT = 4
const DOT_CLEARANCE = 6 // 4px radius + 1px half-stroke + 1px breathing room
const overlaps = (a: ChartNoteBounds, b: ChartNoteBounds) =>
  a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y

/** Place the few chart-series note letters around their true plotted points, within the plot.
 * Pixel positions encode the actual axis scale/order. A stable tie-break and neighbouring
 * periods matter: independently clamping three labels can put them in the same position.
 */
export function layoutChartNotes(anchors: ChartNoteAnchor[], plot: ChartNoteBounds): Map<string, ChartNotePosition> {
  const placements = new Map<string, ChartNotePosition>()
  const placed: ChartNoteBounds[] = []
  const ordered = anchors.map((anchor, index) => ({ ...anchor, index }))
    .filter((anchor) => Number.isFinite(anchor.x) && Number.isFinite(anchor.y))
    .sort((a, b) => a.x - b.x || a.y - b.y || a.index - b.index)
  const dots = ordered.map((anchor) => ({ x: anchor.x - DOT_CLEARANCE, y: anchor.y - DOT_CLEARANCE, width: DOT_CLEARANCE * 2, height: DOT_CLEARANCE * 2 }))

  for (const anchor of ordered) {
    if (!anchor.letter) continue
    const width = Math.max(10, anchor.letter.length * 8 + 2)
    const column = ordered.filter((peer) => Math.abs(peer.x - anchor.x) < 1)
    const rank = column.indexOf(anchor)
    const side = anchor.x > plot.x + plot.width / 2 ? -1 : 1
    const sideX = (direction: number) => anchor.x + direction * (DOT_CLEARANCE + width / 2 + 4)
    const above = { x: anchor.x, y: anchor.y - DOT_CLEARANCE - DESCENT }
    const below = { x: anchor.x, y: anchor.y + DOT_CLEARANCE + ASCENT }
    const beside = { x: sideX(side), y: anchor.y + 4 }
    const preferred = rank === 0 ? above : rank === column.length - 1 ? below : beside
    const candidates = [preferred, above, below, beside, { x: sideX(-side), y: anchor.y + 4 },
      ...[-16, 16, -32, 32, -48, 48].flatMap((dy) => [side, -side].map((direction) => ({ x: sideX(direction), y: anchor.y + 4 + dy }))),
    ].map((position) => ({
      x: Math.max(plot.x + width / 2, Math.min(plot.x + plot.width - width / 2, position.x)),
      y: Math.max(plot.y + ASCENT, Math.min(plot.y + plot.height - DESCENT, position.y)),
    }))
    const box = (position: ChartNotePosition) => ({ x: position.x - width / 2, y: position.y - ASCENT, width, height: ASCENT + DESCENT })
    const clear = candidates.find((candidate) => ![...dots, ...placed].some((obstacle) => overlaps(box(candidate), obstacle)))
    // Even a pathological crowded plot keeps its note; never remove evidence to improve layout.
    const position = clear ?? candidates[0]
    placements.set(anchor.key, position)
    placed.push(box(position))
  }
  return placements
}
