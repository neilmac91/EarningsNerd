/**
 * APCA lightness contrast (Lc), APCA-W3 0.0.98G-4g: apca-w3's `APCAcontrast(sRGBtoY(text), sRGBtoY(ground))`, the
 * measure the trend-chart spec writes its floors in (docs/design/analysis-trend-charts-spec-2026-10.md §3.8). Positive
 * for dark text on a light ground, negative for light text on a dark one; 0 below the low clip. Pure, for the chart
 * gates (tests/unit/chart-apca.spec.ts holds it to apca-w3's own results).
 */

const channels = (hex: string) => {
  const match = /^#([0-9a-f]{6})$/i.exec(hex)
  if (!match) throw new Error(`not a 6-digit hex: ${hex}`)
  return [0, 2, 4].map((at) => parseInt(match[1].slice(at, at + 2), 16))
}

/** Screen luminance: the simple 2.4 curve on each channel, sRGB's coefficients. */
const luminance = (hex: string) => {
  const [r, g, b] = channels(hex).map((value) => (value / 255) ** 2.4)
  return 0.2126729 * r + 0.7151522 * g + 0.072175 * b
}

/** The soft clamp near black. */
const clamp = (y: number) => (y > 0.022 ? y : y + (0.022 - y) ** 1.414)

export function apcaLc(text: string, ground: string): number {
  const yText = clamp(luminance(text))
  const yGround = clamp(luminance(ground))
  if (Math.abs(yGround - yText) < 0.0005) return 0
  if (yGround > yText) {
    const sapc = (yGround ** 0.56 - yText ** 0.57) * 1.14
    return sapc < 0.1 ? 0 : (sapc - 0.027) * 100
  }
  const sapc = (yGround ** 0.65 - yText ** 0.62) * 1.14
  return sapc > -0.1 ? 0 : (sapc + 0.027) * 100
}

/** An `rgba(r,g,b,a)` paint over an opaque ground, as the browser composites it to 8-bit sRGB: a 6-digit hex. */
export function over(paint: string, ground: string): string {
  const match = /^rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)$/.exec(paint.replace(/\s+/g, ''))
  if (!match) throw new Error(`not an rgba() paint: ${paint}`)
  const alpha = Number(match[4])
  const below = channels(ground)
  return `#${[1, 2, 3].map((i) => Math.round(alpha * Number(match[i]) + (1 - alpha) * below[i - 1]).toString(16).padStart(2, '0')).join('').toUpperCase()}`
}
