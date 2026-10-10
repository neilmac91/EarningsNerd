// Shared Playwright/Chromium resolution for the critique scripts.
//   CHROMIUM_PATH set      -> that binary (must exist; an explicit caller value is never overridden)
//   else Playwright's own  -> Playwright's default browser when it is installed
//   else                   -> a Chromium under PLAYWRIGHT_BROWSERS_PATH or /opt/pw-browsers (the cloud image's preinstall)
//   else                   -> a clear error naming both remedies
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

export const HERE = path.dirname(fileURLToPath(import.meta.url))
export const REPO = path.resolve(HERE, '..', '..')

export async function loadPlaywright() {
  const entry = path.join(REPO, 'frontend', 'node_modules', '@playwright', 'test', 'index.mjs')
  if (!fs.existsSync(entry)) throw new Error(`Playwright is not installed: run "npm ci" in ${path.join(REPO, 'frontend')} (looked for ${entry})`)
  return import(pathToFileURL(entry).href)
}

export function resolveExecutablePath(chromium) {
  const explicit = process.env.CHROMIUM_PATH
  if (explicit) {
    if (!fs.existsSync(explicit)) throw new Error(`CHROMIUM_PATH is set to "${explicit}" but no file exists there`)
    return explicit
  }
  let def = null
  try { def = chromium.executablePath() } catch { def = null }
  if (def && fs.existsSync(def)) return undefined // Playwright's own browser: let it choose
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, '/opt/pw-browsers'].filter(Boolean)
  for (const root of roots) {
    const link = path.join(root, 'chromium')
    if (fs.existsSync(link)) return link
    let dirs = []
    try { dirs = fs.readdirSync(root).filter((n) => /^chromium-\d+$/.test(n)).sort().reverse() } catch { dirs = [] }
    for (const d of dirs) for (const rel of ['chrome-linux/chrome', 'chrome-linux64/chrome']) {
      const p = path.join(root, d, rel)
      if (fs.existsSync(p)) return p
    }
  }
  throw new Error(`No Chromium found. Set CHROMIUM_PATH to a Chromium/Chrome binary, or run "npx playwright install chromium" in ${path.join(REPO, 'frontend')} (Playwright looked for ${def || 'its default browser'}).`)
}

export async function launchChromium(options = {}) {
  const pw = await loadPlaywright()
  const executablePath = resolveExecutablePath(pw.chromium)
  const browser = await pw.chromium.launch({ headless: true, ...options, executablePath })
  return { pw, browser, executable: executablePath || 'playwright-default' }
}
