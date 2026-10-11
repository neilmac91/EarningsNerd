// The browser the committed recordings were measured in. A page's layout is its browser's: another Chromium version,
// or the same one on another platform, can shape text and break lines differently, so every width, clipping and
// occlusion result in measurements/ belongs to the browser that measured it, and current.json and prototype.json
// compare like for like only when both come from one. measure-current.mjs and measure-proto.mjs write their recording
// only in this browser, checked right after launch, before anything is measured; a run in any other needs --out naming
// another file. It is Playwright 1.56.1's Chromium, the cloud image's global install (the frontend's own
// @playwright/test is newer and runs a newer Chromium). Retaking the recordings in another browser needs a new pin
// here, both recordings retaken and a README note. The pin is necessary, not sufficient: in this same browser another
// linux x64 machine measured the 97293e7 table at 2,044 px against the recording's 2,076, since text widths also
// follow the machine's font setup, so the recordings are one environment's run and checks elsewhere assert their
// invariants from an --out run.
export const PINNED_BROWSER = { chromium: '141.0.7390.37', platform: 'linux x64' }

// The platform as a recording records it.
export const platform = () => `${process.platform} ${process.arch}`

// Refuses a run that would write `file` in any browser but the pinned one, and closes that browser.
export const requirePinnedBrowser = async (browser, file) => {
  const launched = { chromium: browser.version(), platform: platform() }
  if (launched.chromium === PINNED_BROWSER.chromium && launched.platform === PINNED_BROWSER.platform) return
  await browser.close()
  throw new Error(`${file} is measured only in Chromium ${PINNED_BROWSER.chromium} on ${PINNED_BROWSER.platform} (Playwright 1.56.1's build), the browser both recordings pin; this run launched Chromium ${launched.chromium} on ${launched.platform}, whose layout can differ: run with Playwright 1.56.1 on ${PINNED_BROWSER.platform} (the README's command), or pass --out <another file> for a measurement in this browser`)
}
