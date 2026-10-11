/** Read-only comparisons of the Pro offer with what checkout charges: an operator's readback of the
 * serving bindings and Stripe catalog (checkPricingAgreement), or the serving backend's public charge
 * report, GET /api/subscriptions/prices (checkServingCharge), against PRO_PRICING or the offer a live
 * pricing page publishes (livePageOffer). Each reads supplied files only: no credentials, environment
 * reads, network calls, checkout or catalog mutations.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { PRO_PRICING } from '../app/pricing/prices.ts'

const record = (value) => value !== null && typeof value === 'object' && !Array.isArray(value)
const idMatches = (value, prefix) => typeof value === 'string' && new RegExp(`^${prefix}_[a-zA-Z0-9]+$`).test(value)

const expectedCents = () => ({ monthly: Math.round(PRO_PRICING.monthly * 100), yearly: Math.round(PRO_PRICING.yearly * 100) })

export function checkPricingAgreement(snapshot) {
  const errors = []
  const expected = expectedCents()
  const result = () => ({
    ok: errors.length === 0,
    scope: 'Supplied snapshot only; not live checkout verification or activation approval.',
    expected: { currency: 'usd', monthly_cents: expected.monthly, yearly_cents: expected.yearly },
    errors,
  })
  if (!record(snapshot) || !record(snapshot.bindings) || !record(snapshot.prices) || !record(snapshot.product)) {
    errors.push('Supply bindings, prices and product objects from one operator readback.')
    return result()
  }
  const { bindings, prices, product } = snapshot
  const ids = { monthly: bindings.STRIPE_PRICE_MONTHLY_ID, yearly: bindings.STRIPE_PRICE_YEARLY_ID }
  for (const cycle of ['monthly', 'yearly']) {
    if (!idMatches(ids[cycle], 'price')) errors.push(`${cycle}: effective serving price binding is missing or malformed.`)
  }
  if (ids.monthly === ids.yearly) errors.push('Monthly and yearly bindings must select different prices.')
  if (!idMatches(bindings.product_id, 'prod')) errors.push('The intended approved product ID is missing or malformed.')
  if (product.object !== 'product' || product.id !== bindings.product_id || !idMatches(product.id, 'prod')) {
    errors.push('Product readback must match the intended approved product ID.')
  }
  if (product.active !== true || product.livemode !== true || product.deleted === true) {
    errors.push('Product must be active in live mode.')
  }
  for (const cycle of ['monthly', 'yearly']) {
    const price = prices[cycle]
    if (!record(price)) {
      errors.push(`${cycle}: a Stripe Price readback is required.`)
      continue
    }
    if (price.object !== 'price' || price.id !== ids[cycle] || !idMatches(price.id, 'price')) {
      errors.push(`${cycle}: Price readback does not match the effective serving binding.`)
    }
    if (price.product !== bindings.product_id) errors.push(`${cycle}: Price belongs to another product; supply an unexpanded product ID.`)
    if (price.active !== true || price.livemode !== true) errors.push(`${cycle}: Price must be active in live mode.`)
    if (price.currency !== 'usd') errors.push(`${cycle}: Price currency must be USD.`)
    if (price.type !== 'recurring' || !record(price.recurring) || price.recurring.interval !== (cycle === 'monthly' ? 'month' : 'year') || price.recurring.interval_count !== 1 || price.recurring.usage_type !== 'licensed') {
      errors.push(`${cycle}: Price must recur once per ${cycle === 'monthly' ? 'month' : 'year'} with licensed usage.`)
    }
    if (price.billing_scheme !== 'per_unit' || price.custom_unit_amount !== null || price.transform_quantity !== null) {
      errors.push(`${cycle}: Price must use a fixed per-unit amount without quantity transformation.`)
    }
    if (!Number.isSafeInteger(price.unit_amount) || price.unit_amount !== expected[cycle]) {
      errors.push(`${cycle}: Price amount disagrees with PRO_PRICING.`)
    }
    if (price.unit_amount_decimal != null && (typeof price.unit_amount_decimal !== 'string' || !/^\d+(?:\.0{1,12})?$/.test(price.unit_amount_decimal) || Number(price.unit_amount_decimal) !== expected[cycle])) {
      errors.push(`${cycle}: Decimal amount disagrees with the whole-cent offer.`)
    }
  }
  return result()
}

// The offer a live pricing page publishes, in cents: the Product/Offer JSON-LD that
// app/pricing/layout.tsx renders from the deployed PRO_PRICING. Null unless exactly one such product
// carries one USD offer per cycle.
const OFFER_NAMES = { monthly: 'Pro (monthly)', yearly: 'Pro (annual)' }
export function livePageOffer(html) {
  if (typeof html !== 'string') return null
  const products = []
  for (const [, body] of html.matchAll(/<script\b[^>]*\btype="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/g)) {
    let data
    try {
      data = JSON.parse(body)
    } catch {
      continue
    }
    if (record(data) && data['@type'] === 'Product' && typeof data['@id'] === 'string' && data['@id'].endsWith('/pricing#product')) {
      products.push(data)
    }
  }
  if (products.length !== 1 || !Array.isArray(products[0].offers)) return null
  const cents = {}
  for (const [cycle, name] of Object.entries(OFFER_NAMES)) {
    const offers = products[0].offers.filter((offer) => record(offer) && offer.name === name)
    const price = offers.length === 1 && offers[0].priceCurrency === 'USD' ? offers[0].price : undefined
    if (typeof price !== 'number' || !Number.isFinite(price) || price < 0) return null
    cents[cycle] = Math.round(price * 100)
  }
  return cents
}

// The report's problem codes (backend/app/services/billing_serving_prices.py). "unavailable" leaves
// the check without evidence; the others mean checkout has no fixed charge for that cycle.
const PROBLEMS = new Set(['unconfigured', 'unavailable', 'inactive', 'test_mode', 'not_fixed_recurring'])
const INTERVALS = { monthly: 'month', yearly: 'year' }

/** Compare the serving backend's charge report with the page's offer: PRO_PRICING, or `page`, cents
 * read from a live page by livePageOffer. By default they must agree. With `publishing`, the check
 * before a page goes live, it passes while checkout charges no more than the page shows (backend
 * first; docs/PRICING_OFFER.md). `usable` is false when the report is no evidence.
 */
export function checkServingCharge(report, { publishing = false, page = null } = {}) {
  const errors = []
  const notes = []
  let usable = record(report)
  const expected = page ?? expectedCents()
  for (const cycle of ['monthly', 'yearly']) {
    const charge = record(report) ? report[cycle] : undefined
    const interval = INTERVALS[cycle]
    if (!Number.isSafeInteger(expected[cycle]) || expected[cycle] < 0) {
      usable = false
      errors.push(`${cycle}: the offer is not a whole number of cents.`)
    } else if (!record(charge) || (charge.problem !== undefined && !PROBLEMS.has(charge.problem))) {
      usable = false
      errors.push(`${cycle}: the report carries no readable charge.`)
    } else if (charge.problem !== undefined) {
      if (charge.problem === 'unavailable') usable = false
      errors.push(`${cycle}: checkout has no fixed charge (${charge.problem}).`)
    } else if (!Number.isSafeInteger(charge.amount_cents) || charge.amount_cents < 0) {
      usable = false
      errors.push(`${cycle}: the report's amount is not a whole number of cents.`)
    } else if (charge.currency !== 'usd' || charge.interval !== interval || charge.interval_count !== 1) {
      errors.push(`${cycle}: checkout must charge in USD once per ${interval}.`)
    } else if (charge.amount_cents > expected[cycle]) {
      errors.push(`${cycle}: checkout charges ${charge.amount_cents} cents, more than the ${expected[cycle]} the page shows.`)
    } else if (charge.amount_cents < expected[cycle]) {
      const lower = `${cycle}: checkout charges ${charge.amount_cents} cents, less than the ${expected[cycle]} the page shows.`
      if (publishing) notes.push(lower)
      else errors.push(lower)
    }
  }
  return {
    ok: errors.length === 0,
    usable,
    scope: publishing
      ? 'Before publishing: checkout must charge no more than this page shows, so a lower price is bound on the backend first.'
      : 'The serving charge report only; not a catalog readback, live checkout verification or activation approval.',
    expected: { source: page ? 'live page' : 'PRO_PRICING', currency: 'usd', monthly_cents: expected.monthly, yearly_cents: expected.yearly },
    errors,
    notes,
  }
}

const USAGE = [
  'Usage: npm run check:pricing -- /path/to/operator-readback.json',
  '       npm run check:pricing -- --serving [--publishing] [--page /path/to/pricing.html] /path/to/serving-prices.json',
].join('\n')

function parseArgs(args) {
  const file = (arg) => typeof arg === 'string' && arg !== '' && !arg.startsWith('--')
  if (args.length === 1 && file(args[0])) return { file: args[0], serving: false }
  if (args[0] !== '--serving') return null
  let i = 1
  const publishing = args[i] === '--publishing'
  if (publishing) i += 1
  let page = null
  if (args[i] === '--page') {
    if (!file(args[i + 1])) return null
    page = args[i + 1]
    i += 2
  }
  return i === args.length - 1 && file(args[i]) ? { file: args[i], serving: true, publishing, page } : null
}

function main() {
  const args = process.argv.slice(2)
  const call = parseArgs(args)
  if (!call) {
    console.log(USAGE)
    process.exitCode = args.length === 1 && args[0] === '--help' ? 0 : 2
    return
  }
  try {
    const input = JSON.parse(readFileSync(call.file, 'utf8'))
    let page = null
    if (call.page) {
      page = livePageOffer(readFileSync(call.page, 'utf8'))
      if (!page) {
        console.error('The supplied page carries no readable Pro offer. No agreement established.')
        process.exitCode = 2
        return
      }
    }
    const result = call.serving ? checkServingCharge(input, { publishing: call.publishing, page }) : checkPricingAgreement(input)
    console.log(JSON.stringify(result, null, 2))
    process.exitCode = result.usable === false ? 2 : result.ok ? 0 : 1
  } catch {
    console.error('Cannot read or parse the supplied files. No agreement established.')
    process.exitCode = 2
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) main()
