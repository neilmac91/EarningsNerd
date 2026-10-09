import type { Locator } from '@playwright/test'

/**
 * WCAG contrast of an element's text against what is actually painted behind it, from the
 * browser's own resolved colours: the element's ink composited over its effective background, which
 * is every ancestor's background-color composited from the nearest opaque one up to the element
 * itself (the html/body ground when nothing is opaque). Background images and gradients are not
 * read — the surfaces measured with it are flat token fills. A DOM measurement, not a screen-reader
 * or visual test.
 */
export const textContrast = (loc: Locator): Promise<number> =>
  loc.evaluate((el) => {
    type Rgba = { r: number; g: number; b: number; a: number }
    const parse = (c: string): Rgba => {
      const m = c.match(/rgba?\(([^)]+)\)/)
      if (!m) throw new Error(`unparsed colour ${c}`)
      const [r, g, b, a = '1'] = m[1].split(/[\s,/]+/).filter(Boolean)
      return { r: +r, g: +g, b: +b, a: +a }
    }
    const over = (top: Rgba, under: Rgba): Rgba => ({
      r: top.r * top.a + under.r * (1 - top.a),
      g: top.g * top.a + under.g * (1 - top.a),
      b: top.b * top.a + under.b * (1 - top.a),
      a: 1,
    })
    const layers: Rgba[] = []
    for (let node: Element | null = el; node; node = node.parentElement) {
      const bg = parse(getComputedStyle(node).backgroundColor)
      if (bg.a > 0) layers.push(bg)
      if (bg.a === 1) break
    }
    if (!layers.length || layers[layers.length - 1].a !== 1) layers.push({ r: 255, g: 255, b: 255, a: 1 })
    const ground = layers.reduceRight((under, top) => over(top, under))
    const ink = over(parse(getComputedStyle(el).color), ground)
    const lum = ({ r, g, b }: Rgba) => {
      const ch = (v: number) => {
        const s = v / 255
        return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
      }
      return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)
    }
    const [hi, lo] = [lum(ink), lum(ground)].sort((x, y) => y - x)
    return Math.round(((hi + 0.05) / (lo + 0.05)) * 100) / 100
  })

/** Every CSS transition or animation on the element and its subtree has finished. */
export const settled = (loc: Locator): Promise<void> =>
  loc.evaluate(async (el) => {
    await new Promise(requestAnimationFrame)
    await Promise.all(el.getAnimations({ subtree: true }).map((a) => a.finished))
  })
